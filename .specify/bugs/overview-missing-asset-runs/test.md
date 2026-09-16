# Bug Verification: Agents overview shows no latest run / history for asset agents

- **Slug**: overview-missing-asset-runs
- **Tested**: 2026-09-16
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom no longer reproduces: on the deployed UI, `GET /api/agents/activity` now
returns populated `latest_run` and `history` for the asset agents `notes` and `speckit-implement`
(previously empty). Plain job agents are unaffected, and the full UI suite passes with no
regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `curl http://localhost:8080/api/agents/activity` against the restarted UI container | pass | `notes` → latest SUCCESS, history len 10; `speckit-implement` → latest SUCCESS, history len 1. Both were empty before. `reachable: true`, all 38 agents keyed. |
| No regression on job agents | same endpoint, inspect a plain job agent | pass | `hello-cc-opus` → latest SUCCESS, history len 2 (job pipeline path unchanged). |
| New / updated tests | `cd ui && ../.venv/bin/python -m pytest tests/test_dagster.py -q` | pass | 8 passed — query builder, failure-inclusion, both-kind merge, stubbed end-to-end. |
| Regression suite | `cd ui && ../.venv/bin/python -m pytest -q` | pass | 464 passed. |
| Lint / type-check | — | not-run | No lint/type-check configured for `ui/`. |

## Output Excerpts

```
tests/test_dagster.py ........                                           [100%]
8 passed in 0.13s

464 passed in 4.83s

# live deployed endpoint
reachable: True | agents keyed: 38
notes => latest: SUCCESS run_id: 3725d07f-... | history len: 10
speckit-implement => latest: SUCCESS run_id: a948c046-... | history len: 1
hello-cc-opus (job) => latest: SUCCESS | history len: 2
REPRO_RESOLVED: True
```

## Residual Risks

- `_ASSET_RUNS_LIMIT = 250` is shared across all asset agents; a single very busy asset could still
  crowd another asset's last-10 within that shared window (noted as a follow-up in fix.md).
- The deployed-container fix required `docker compose restart ui` (app code is served from the
  read-only repo mount and imported once at uvicorn start). Future `ui/` code edits need the same
  restart to take effect — a deploy-process note, not a code defect.

## Recommendation

Close the bug — verified end-to-end. The reproduction from the assessment was exercised against the
live, deployed UI endpoint (not tests alone): asset agents `notes` and `speckit-implement` now show
their latest run and history, and plain job agents are unchanged. New tests lock the behavior in and
the full suite is green.
