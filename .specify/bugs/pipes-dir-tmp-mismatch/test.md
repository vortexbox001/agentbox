# Bug Verification: spec-007 Pipes messages dir moved off container-private /tmp

- **Slug**: pipes-dir-tmp-mismatch
- **Tested**: 2026-09-12 (amended same day after the follow-on permission fix)
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces. **api** (root) is verified end-to-end: a live `agent_verify_api`
run succeeded with a real structured report (`status=ok`, real tokens/cost) and the log shows
the Pipes channel opening instead of `did not receive any messages`.

Non-root agent containers (node, uid 1000) then surfaced a two-layer permission defect: (1) the
0700 dir blocked traversal (run `e003f919`), and (2) after chmod-ing the dir, `PipesFileMessageReader`
pre-creates `messages` root-owned 0644, which the container still can't append to (runs
`fd1596d6`/`0fb5b966`). Both are fixed (`chmod 0777` dir + `chmod 0666` file) and **verified live
end-to-end**: `agent_hello_cc_sonnet` (claude-code) run `99250a5b-f817-4450-8980-569f33bc1091`
completed `status=ok` with `[pipes] external process successfully opened dagster pipes`. The unit
suite (50 tests, incl. the pipes-dir regression tests) passes.

codex and pi were not launched but share the identical transport + non-root (uid 1000) path, so
the same fix covers them.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Regression suite | `../.venv/bin/python -m pytest -q` (orchestrator) | pass | 50 passed (incl. 3 pipes-dir regression tests) |
| Code-location reload | GraphQL `reloadRepositoryLocation("definitions.py")` (×2) | pass | `LOADED`, no `PythonError` — live orchestrator runs the fixed code (reloaded again after the chmod amendment) |
| Reproduction — api (root) | Launched `agent_verify_api` (run `846128f3-…`) | pass | `SUCCESS`; `status=ok turns=1 tokens_in/out=42/10 cost_usd=9.2e-05 files_written=1`; log shows `[pipes] external process successfully opened dagster pipes` |
| Reproduction — non-root perms (dir) | uid-1000 `agent-claude` writing into a real pipes dir, 0700 vs 0777 | pass | 0700 → `Permission denied`; 0777 → `WROTE ok` |
| Reproduction — non-root perms (file) | uid-1000 `agent-claude` appending to `messages`, root:0644 vs 0666 | pass | 0644 → `Permission denied` (reproduces `fd1596d6`); 0666 → `APPEND_OK` |
| Reproduction — claude-code end-to-end (post-fix) | Launched `agent_hello_cc_sonnet` (run `99250a5b-…`) | pass | `SUCCESS`; `status=ok turns=1 tokens_in/out=2571/19 cost_usd=None`; `[pipes] external process successfully opened dagster pipes` |
| Shared-mount sanity | `ls /data/dagster/pipes/` | pass | Dir created by the fix; per-run subdirs cleaned up by the `finally` rmtree |

## Output Excerpts

Pre-fix (run `6daddbe9-…`, from the assessment):
```
result: status=failed turns=None tokens_in/out=None/None cost_usd=None files_written=1
[pipes] did not receive any messages from external process.
```

Post-fix, api (run `846128f3-0641-4983-876b-9c63236e961b`):
```
[pipes] external process successfully opened dagster pipes.
result: status=ok turns=1 tokens_in/out=42/10 cost_usd=9.2e-05 files_written=1
```

Non-root failure (run `fd1596d6`/`0fb5b966`) and the two-layer syscall proof + live fix:
```
# in-run failure (dir already 0777; file was root:0644):
PermissionError: [Errno 13] Permission denied: '/pipes/messages'   (container /app/lib/agent_report.py open("a"))

# syscall proof (real agent-claude image, real /data/dagster/pipes):
--- messages root:0644 → append: Permission denied
--- messages 0666      → append: APPEND_OK

# post-fix live claude-code run 99250a5b:
[pipes] external process successfully opened dagster pipes.
result: status=ok turns=1 tokens_in/out=2571/19 cost_usd=None files_written=0
```

## Residual Risks

- **codex and pi** (also uid 1000) were not launched; they share the identical transport +
  non-root permission path as claude-code (now verified live), so the same fix covers them.
- The **daemon** was not separately restarted/reloaded (only the webserver's gRPC code server via
  the reload mutation). Matters for schedule/sensor-launched runs; reload/restart the daemon if
  a scheduled run misbehaves.
- The optional regression guard ("no report emitted" vs genuine `status=failed`) remains
  unimplemented. This bug took two iterations precisely because a transport/permission failure
  keeps surfacing as an ordinary `status=failed` — a strong argument for the guard as a follow-up.

## Recommendation

Close the bug. All defects are fixed and live: **api** (root) and **claude-code** (non-root)
are both verified end-to-end with real reports, and the two-layer permission fix is proven at the
syscall level against the real image. Regression tests lock in the shared-mount path plus the
dir-0777 / file-0666 permissions. Follow-ups: consider the transport-error guard, and note the
daemon-reload caveat for scheduled runs.
