# Bug Verification: Failed asset run renders its partition green/"materialized"

- **Slug**: failed-asset-shows-materialized
- **Tested**: 2026-09-12
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug is gone, confirmed end-to-end: a failed asset run now records an `AssetObservation` (not a
materialization), and the partition renders **failed (red)**, not **materialized (green)**. The full
orchestrator suite passes with no regressions, the regression guard is in place, and — the step that
upgrades this from partial to **verified** — the operator ran the live reproduction on the host
(10.0.0.100) and confirmed a failed `verify/fail` partition now shows red in the Dagster UI.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction — live host UI | Materialize `verify/fail` on 10.0.0.100, view partition color | pass | Operator ran it live; the failed partition renders red (confirmed 2026-09-12). |
| Reproduction — automated equivalent | `pytest ...::test_failed_asset_records_observation_and_partition_shows_red` | pass | Materializes the real `factory.build_asset` asset to failure; asserts partition is in Dagster's **failed** subset and **not** in the **materialized** subset via `get_and_update_asset_status_cache_value` (the same API the partitions view uses). |
| New / updated tests | `../.venv/bin/python -m pytest tests/test_reports.py -q` | pass | Failure/missing-report/timeout tests updated to read the observation. |
| Regression suite | `cd orchestrator && ../.venv/bin/python -m pytest -q` | pass | **50 passed**. |
| Pre-fix mechanism proof | scratch script on Dagster 1.13.21 (during fix) | pass | `AssetMaterialization` → materialized subset (green); `AssetObservation` → failed subset (red). Confirms the guard would fail under the old code. |
| Lint / type-check | — | not-run | Project has no configured lint/type-check gate for the orchestrator. |
| `images/` tests | not run | skipped | Out of scope — the fix touches only `orchestrator/factory.py` + its tests + spec contract docs; no image/harness code changed. |

## Output Excerpts

Full suite:

```
50 passed, 15 warnings in 4.19s
```

Regression test (automated reproduction):

```
tests/test_reports.py::test_failed_asset_records_observation_and_partition_shows_red PASSED
1 passed, 1 warning in 1.65s
```

Pre-fix mechanism table (Dagster 1.13.21), reproduced during the fix:

| Failure emits | materialized subset | failed subset |
|---|---|---|
| `AssetMaterialization` (old) | {partition} (green) | {} |
| `AssetObservation` (fix) | {} | {partition} (red) |

## Residual Risks

- **UI metadata visibility.** The partition now renders red; whether the partitions *detail panel*
  surfaces the observation's `error`/`transcript`/counts as prominently as it did materialization
  metadata is a UI nuance not covered by these checks (the data is also in the run log and
  transcript). Worth an eyeball on the live UI.
- **Historical false-greens** (e.g. `verify/fail` `2026-09-11`) remain green until re-materialized;
  the fix is forward-looking, as expected.

## Recommendation

Close the bug — verified end-to-end. The fix holds at the code and partition-status-API level, the
full suite passes with a regression guard in place, and the operator confirmed the live host UI now
renders a failed `verify/fail` partition red. The one already-recorded false-green partition
(`2026-09-11`) will clear on its next materialization; the fix is forward-looking as expected.
