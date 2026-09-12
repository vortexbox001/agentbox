# Bug Assessment: spec-007 run reports never arrive (Pipes dir in container-private /tmp)

- **Slug**: pipes-dir-tmp-mismatch
- **Created**: 2026-09-12
- **Source**: pasted text (troubleshooting session; failing runs `6daddbe9-dfc6-4c88-acc7-3bfd93b5656d` and `e984a27c-2417-4c67-bb98-f4e2a70d3c5e`)
- **Verdict**: valid
- **Severity**: critical

## Report (verbatim or summarized)

Every spec-007 agent run records `status=failed` with error "run report was missing or
malformed", even when the agent runs successfully and writes its output file
(`files_written=1`). The Dagster run log shows `[pipes] did not receive any messages from
external process`. The structured run report never reaches the orchestrator.

Reported as affecting `orchestrator/factory.py` (the Dagster Pipes round-trip) and, because
the transport is shared, all four harnesses (api/claude-code/codex/pi). Reproduced with
`agent_verify_api`. The reporter's root-cause hypothesis: agent containers are launched
Docker-outside-of-Docker, so the `-v {pipes_dir}:/pipes` bind mount is resolved by the host
daemon against the host filesystem, but `pipes_dir` is created with a bare
`tempfile.mkdtemp()` that lands in the dagster container's private `/tmp` — a path the host
does not share — so the agent and the orchestrator end up watching two different files.

## Symptom

- **Observed**: a run whose agent succeeds (output `.md` written, container exits 0) is
  marked FAILED; run/materialization metadata shows `status=failed`, all numerics null,
  `files_written=1`; run log warns `[pipes] did not receive any messages from external process`.
- **Expected**: the orchestrator recovers the report the agent emitted over Pipes —
  `status=ok` with real tokens/cost/turns/notes — and attaches it as metadata (materialization
  metadata for asset agents, run/output metadata for job-only agents).

## Reproduction

1. On the Pi (arm64) with the `docker compose` stack up (dagster-webserver + daemon launch
   agent containers via the mounted host docker socket — Docker-outside-of-Docker).
2. Launch job `agent_verify_api` (or materialize any spec-007 agent).
3. Run finishes in ~2s (no OOM / no load needed to trigger it).

Result: run FAILS. The output `.md` is written under `/data/outputs/...`, but the run report
is absent and the run is marked failed. Confirmed reproducible independent of host load — the
earlier OOM-affected run failed identically for the same reason.

## Suspected Code Paths

- `orchestrator/factory.py:407` — `pipes_dir = tempfile.mkdtemp(prefix=f"agentbox-pipes-{context.run_id[:8]}-")`.
  Creates the Pipes messages dir under the default temp root (`/tmp`), which is **inside** the
  dagster container and not bind-mounted to the host. This is the defect.
- `orchestrator/factory.py:409-412` — `open_pipes_session(..., message_reader=PipesFileMessageReader(path=os.path.join(pipes_dir, "messages")))`.
  The orchestrator watches `pipes_dir/messages` on the **dagster container** filesystem.
- `orchestrator/factory.py:418-426` — builds `-v {pipes_dir}:/pipes` and injects it into the
  `docker run` argv. Because the launch goes through the host docker daemon, the host resolves
  `pipes_dir` against the **host** filesystem (a nonexistent path → Docker creates an empty
  host dir and mounts that).
- `orchestrator/factory.py:489-494` — `_extract_report()` returns `None` (no messages), so the
  orchestrator authors `_authored_report("failed", "run report was missing or malformed", ...)`.
- `orchestrator/factory.py:539` — `shutil.rmtree(pipes_dir, ignore_errors=True)` cleanup;
  unaffected by the fix (still removes whatever dir `pipes_dir` names).

Comparison anchors (why only the report is lost, not the output): the output dir is
`/data/outputs/...` and `/data/{dagster,outputs,workspaces}` are bind-mounted **identically**
(host path == container path) into dagster-webserver, so those paths line up across the DooD
boundary; `/tmp` is the one path that does not.

## Root Cause Hypothesis

**High confidence.** Docker-outside-of-Docker bind-mount path mismatch. `tempfile.mkdtemp()`
defaults to `/tmp`, which is private to the dagster container. The agent container, launched by
the host daemon, mounts a *different* (host-side, empty) `/tmp/agentbox-pipes-...` at `/pipes`.
The agent writes `/pipes/messages` into the host copy; the orchestrator's
`PipesFileMessageReader` tails the container copy. The files never coincide, so zero messages
are read and the orchestrator authors a "failed" report. Verified this session: (a) the
dagster-webserver mounts only `/data/*` identically plus the docker socket — `/tmp` is not
shared; (b) a directory created in the container's `/tmp` does not appear on the host's `/tmp`;
(c) the agent image has `dagster-pipes==1.13.21`, matching the orchestrator's Dagster 1.13.21,
and `emit()` reaches `open_dagster_pipes()` cleanly (no wire-format mismatch); (d) the run exits
0, so `emit()` does not raise — the report is simply written to the wrong filesystem.

## Proposed Remediation

**Preferred**: create `pipes_dir` under a path that is bind-mounted **identically** on both the
host and the dagster container — i.e. under `/data/dagster` (the same root `AGENT_LOG_ROOT =
/data/dagster/agent-logs` already relies on). Define a `PIPES_ROOT = "/data/dagster/pipes"`
constant near the other module constants (`AGENT_LOG_ROOT`, factory.py:80), ensure it exists,
and pass it as `dir=` to `mkdtemp`:

```python
PIPES_ROOT = "/data/dagster/pipes"  # bind-mounted identically host<->container (DooD);
                                    # /tmp is container-private and does not cross the boundary
...
os.makedirs(PIPES_ROOT, exist_ok=True)
pipes_dir = tempfile.mkdtemp(prefix=f"agentbox-pipes-{context.run_id[:8]}-", dir=PIPES_ROOT)
```

The existing `finally: shutil.rmtree(pipes_dir, ignore_errors=True)` (factory.py:539) removes
the per-run dir unchanged, so nothing accumulates under `/data/dagster/pipes`. This is an
orchestrator-only change — **no agent image rebuild required**. Because runs execute in a fresh
subprocess that re-imports the code, the next launch picks it up; reload the Dagster code
location to be certain.

**Alternatives**:
- Bind-mount the host `/tmp` (or a dedicated host tmp dir) into the dagster containers at the
  same path in `docker-compose.yml`, leaving `tempfile.mkdtemp()` untouched. Trade-off: adds a
  compose mount and keeps ephemeral run state in `/tmp` rather than the already-managed `/data`
  root; less self-contained than putting it under `/data/dagster`.
- Use a Pipes message transport that does not depend on a shared filesystem (e.g. a
  socket/stdout-based reader). Larger change; not warranted when a shared-path dir fixes it.

**Files likely to change**:
- `orchestrator/factory.py` (constant + the `mkdtemp` call; optionally the missing-report guard below)
- `orchestrator/tests/test_reports.py` and/or `orchestrator/tests/conftest.py` (regression coverage)

**Tests to add or update**:
- A unit test asserting `pipes_dir` is created under `/data/` (a shared root), not the default
  temp root — i.e. `mkdtemp` is called with an explicit `dir=` under `/data`. This is the
  cheapest test that would have caught the bug (the DooD mount boundary can't be exercised in a
  plain unit test).
- If a regression guard is added (below), a test that a run whose container writes **no** Pipes
  message surfaces a distinct "transport/report-missing" signal rather than an ordinary agent
  `status=failed`.

## Risks & Considerations

- **Low blast radius**: single call site plus a constant; cleanup path unchanged.
- **Directory creation**: `/data/dagster` is already writable by the orchestrator (it writes
  `agent-logs/` there), so `os.makedirs(PIPES_ROOT)` should succeed; confirm permissions on the
  Pi.
- **Deploy note**: orchestrator-only; no image rebuild. Reload the Dagster code location (or
  restart the webserver/daemon) so the running code server picks up the edit — the
  webserver/daemon are long-lived.
- **Silent-failure class**: this bug masqueraded as an agent failure. Worth a follow-up guard
  (see Open Questions) so a broken transport is never again indistinguishable from a real
  `status=failed`.
- **No security/migration/API-compat impact.**

## Open Questions

- [NEEDS CLARIFICATION: should the fix also add a regression guard that distinguishes "container
  emitted no report at all" (transport broken) from "agent reported status=failed" (genuine
  failure)? The reporter flagged this as optional; decide whether it lands in this bug-fix or a
  separate change.]
- [NEEDS CLARIFICATION: confirm the orchestrator process user can create/write `/data/dagster/pipes`
  on the Pi host (it already writes `/data/dagster/agent-logs`, so expected to be fine).]

---

## Addendum (2026-09-12): follow-on defect found during verification

Applying the preferred remediation (dir under `/data/dagster/pipes`) fixed the **api** harness
but exposed a second defect on the non-root harnesses. `tempfile.mkdtemp` creates the per-run
dir **0700, owned by root** (the orchestrator's uid). Agent containers pass **no `--user`**, so
they run as their image's `USER`: `agent-python` (api) is **root**, but `agent-claude`,
`agent-codex`, and `agent-pi` all declare `USER node` (**uid 1000**). A uid-1000 container
cannot create `/pipes/messages` in a root-owned 0700 dir → `emit()` raises
`PermissionError: [Errno 13] Permission denied: '/pipes/messages'`, the wrapper exits 1, the
orchestrator reads no message and authors a `failed` report (run
`e003f919-c24f-4f37-8b21-af9832e5a5fa`, `agent_repo_librarian_agentbox`). The agent's actual work
had completed (`files_written=3`; asset materialized) — only the report emit failed.

**Severity**: high — silently breaks 3 of 4 harnesses' reports (all but api).

**Remediation (folded into the same fix)**: `os.chmod(pipes_dir, 0o777)` immediately after
`mkdtemp`. The dir is ephemeral, per-run, under `/data`, and `rmtree`'d in the `finally`, so a
world-writable mode is acceptable on this single-tenant host. Verified via a cross-UID write
proof against the real `agentbox/agent-claude` image. See fix.md and test.md.

### Addendum 2 (2026-09-12): the permission defect had two layers

The `chmod 0777` on the dir (Addendum 1) fixed traversal but a follow-up claude-code run
(`fd1596d6` / `0fb5b966`, `agent_hello_cc_sonnet`) still hit `PermissionError: '/pipes/messages'`
— with the dir confirmed `mode=777` at runtime. Cause: Dagster's `PipesFileMessageReader.read_messages()`
does `open(path, "w").close()` when the session opens, creating `messages` **root-owned 0644**
*before* the container launches. A non-root (uid 1000) container cannot append to a root-owned
file regardless of the dir mode. Second fix: `os.chmod(msg_path, 0o666)` immediately after
`open_pipes_session(...)` enters (the reader has created the file by then). Both layers are
needed — dir `o+x` to reach the file, file `o+w` to append. Verified live end-to-end
(`agent_hello_cc_sonnet` run `99250a5b`, `status=ok`).
