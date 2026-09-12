# Bug Fix: spec-007 Pipes messages dir moved off container-private /tmp

- **Slug**: pipes-dir-tmp-mismatch
- **Fixed**: 2026-09-12 (amended same day — see "Follow-on fix" below)
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The per-run Dagster Pipes messages dir was created with a bare `tempfile.mkdtemp()`, landing
in the orchestrator container's private `/tmp` — a path the host daemon does not share, so the
`-v <pipes_dir>:/pipes` bind mount (resolved host-side under Docker-outside-of-Docker) pointed
at a different filesystem than the one the orchestrator watched, and every run's report was
lost. The fix creates the dir under a new `PIPES_ROOT = /data/dagster/pipes` constant — a path
bind-mounted identically on host and container (like `AGENT_LOG_ROOT`).

**Follow-on fix (amended):** moving the dir onto the shared mount exposed a **non-root permission**
defect with two layers. Every harness except **api** runs its container as **node (uid 1000)**
while the orchestrator runs as root, so both the per-run dir and its `messages` file must be
reachable/writable by uid 1000:
1. `mkdtemp` creates the dir 0700 → the container can't traverse into it. Fixed by
   `os.chmod(pipes_dir, 0o777)` (run `e003f919`, `agent_repo_librarian_agentbox`).
2. `PipesFileMessageReader.read_messages()` pre-creates `messages` **root-owned 0644** when the
   session opens → the container can't append to it even inside a 0777 dir, so `emit()` still
   died with `PermissionError` (run `fd1596d6`/`0fb5b966`, `agent_hello_cc_sonnet`). Fixed by
   `os.chmod(msg_path, 0o666)` right after the session opens.

api passed throughout only because `agent-python` runs as root.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `orchestrator/factory.py` | modified | Added `PIPES_ROOT = "/data/dagster/pipes"` constant (next to `AGENT_LOG_ROOT`); `mkdtemp(dir=PIPES_ROOT)`; **`os.chmod(pipes_dir, 0o777)`** (dir traversal) and **`os.chmod(msg_path, 0o666)`** after the session opens (messages-file append) so non-root agent containers can write `/pipes/messages`. |
| `orchestrator/tests/conftest.py` | modified | `stub_launch` now also redirects `factory.PIPES_ROOT` into the test temp dir (mirrors the existing `AGENT_LOG_ROOT` redirect) so ops materialize without writing to `/data`. |
| `orchestrator/tests/test_reports.py` | added tests | Three regression tests (see below). |

## Diff Highlights

```python
# factory.py — new constant
PIPES_ROOT = "/data/dagster/pipes"   # host==container shared mount; /tmp is container-private

# factory.py — pipes_dir creation
os.makedirs(PIPES_ROOT, exist_ok=True)
pipes_dir = tempfile.mkdtemp(prefix=f"agentbox-pipes-{context.run_id[:8]}-", dir=PIPES_ROOT)
msg_path = os.path.join(pipes_dir, "messages")
os.chmod(pipes_dir, 0o777)   # dir traversal for non-root agent containers (node, uid 1000)
with open_pipes_session(..., message_reader=PipesFileMessageReader(path=msg_path)) as session:
    os.chmod(msg_path, 0o666)   # reader pre-creates it root:0644; widen so the container can append
```

The existing `finally: shutil.rmtree(pipes_dir, ignore_errors=True)` is unchanged, so per-run
dirs under `/data/dagster/pipes` are still cleaned up.

## Tests Added or Updated

- `orchestrator/tests/test_reports.py::test_pipes_root_is_under_shared_data_mount` — asserts the
  production `factory.PIPES_ROOT` starts with `/data/` (not `/tmp`). This is the cheapest check
  that would have caught the bug; the DooD mount boundary itself can't be exercised in-process.
  Deliberately does **not** use `stub_launch`, so it reads the unpatched module value.
- `orchestrator/tests/test_reports.py::test_pipes_dir_created_under_pipes_root` — materializes an
  api asset and asserts the launched `:/pipes` mount source lives under `factory.PIPES_ROOT`,
  proving `mkdtemp` is called with `dir=PIPES_ROOT` rather than defaulting to `/tmp`.
- `orchestrator/tests/test_reports.py::test_pipes_dir_world_writable_for_nonroot_agents` —
  spies on `os.chmod` and asserts **both** the per-run dir is chmod'd `0o777` and the `messages`
  file is chmod'd `0o666`; regression for the two-layer non-root PermissionError.

## Local Verification

- `cd orchestrator && ../.venv/bin/python -m pytest -q` → **50 passed** (no collateral breakage).
- Syscall-level proof against the real `agentbox/agent-claude` image / real `/data/dagster/pipes`:
  a uid-1000 container appending to `messages` gets `Permission denied` when the file is root:0644
  and `APPEND_OK` after `chmod 0666` (and the same for dir 0700 → 0777 traversal).
- End-to-end: **api** (`agent_verify_api`, run `846128f3`) and **claude-code**
  (`agent_hello_cc_sonnet`, run `99250a5b`) both `status=ok` with the Pipes channel opening
  cleanly. See test.md.

## Deviations from Assessment

The assessment's preferred remediation (move the dir onto a shared mount) was applied as
specified but was **incomplete**: it did not anticipate that agent containers run as non-root
(node, uid 1000) while the orchestrator runs as root. Closing that took two iterations, both
folded into this fix as strict extensions of the same root-cause area (the Pipes files):
`os.chmod(pipes_dir, 0o777)` for dir traversal, then `os.chmod(msg_path, 0o666)` for the
reader-created messages file. Without both, the fix only worked for the api harness (root).

The assessment's **optional** regression guard (distinguish "container emitted no report at all"
from a genuine agent `status=failed`) is still **not** implemented — left as an open question,
and this incident is a good argument for it (a broken transport again surfaced as `status=failed`).
Recorded as a follow-up.

## Follow-ups

- **Deploy**: orchestrator-only change, no agent image rebuild. Reload the Dagster code location
  (or restart the webserver/daemon — they've been long-lived) so the running code server picks
  up the edit before re-testing.
- **Optional regression guard** (open question from the assessment): make a missing Pipes report
  surface as a distinct transport error rather than an ordinary `status=failed`, so a broken
  transport can never again masquerade as an agent failure. Decide whether to do this here or as
  a separate change.
- Confirm the orchestrator process can create/write `/data/dagster/pipes` on the Pi (it already
  writes `/data/dagster/agent-logs`, so expected to be fine).
