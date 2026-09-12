# Bug Fix: Failed asset run renders its partition green/"materialized"

- **Slug**: failed-asset-shows-materialized
- **Fixed**: 2026-09-12
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

On the asset failure path, `make_run_op` now emits an `AssetObservation` (carrying the full report
metadata) instead of an `AssetMaterialization` before raising. A materialization event is Dagster's
positive signal that greens a partition, so emitting one on failure made a failed partition render
MATERIALIZED; an observation attaches the same report without materializing, so the failed run
leaves the partition red — the SC-003 intent.

## Pre-fix verification (Dagster 1.13.21)

Before changing code, I reproduced the mechanism in-process against the pinned Dagster, resolving
the assessment's open question. A daily-partitioned asset that fails after emitting each event kind:

| Failure emits | `get_and_update_asset_status_cache_value` result |
|---|---|
| `AssetMaterialization` (old code) | **materialized** = {partition}, failed = {} → green |
| `AssetObservation` (fix) | materialized = {}, **failed** = {partition} → red |
| nothing | materialized = {}, failed = {partition} → red |

So the observation is strictly better than emitting nothing: red partition **with** the report
attached. Read-back confirmed the observation is durably recorded and its metadata (`status`,
`error`, `transcript`, …) is reachable from the instance event log.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `orchestrator/factory.py` | modified | Import `AssetObservation`; failure path emits `AssetObservation` (was `AssetMaterialization`); comment rewritten to explain why. |
| `orchestrator/tests/test_reports.py` | modified | `_materialize_expecting_failure` now reads back observations and returns the instance; new `_partition_status` helper; failure/missing-report/timeout tests updated; added partition-status regression assertion. |
| `specs/007-run-reports-via-pipes/contracts/pipes-transport.md` | modified | §3 asset-failure rule now specifies `AssetObservation`, with the rationale. |
| `specs/007-run-reports-via-pipes/contracts/metadata.md` | modified | "Same on success and failure" note now references the observation event. |

## Diff Highlights

`orchestrator/factory.py` (asset failure branch):

```python
if is_asset:
    # ... a materialization event greens a partition, so emitting one here made a failed
    # partition render MATERIALIZED. An AssetObservation attaches the report WITHOUT
    # marking it materialized, so the failed run leaves the partition red WITH the report.
    context.log_event(
        AssetObservation(
            asset_key=AssetKey(cfg["produces"]["asset"].split("/")),
            partition=context.partition_key if context.has_partition_key else None,
            metadata=metadata,
        )
    )
```

## Tests Added or Updated

- `test_reports.py::test_failed_asset_records_observation_and_partition_shows_red` — replaces the
  old `..._records_materialization_and_raises`. Asserts: run fails; exactly one observation carrying
  `status: failed` + `error` + transcript; **no `ASSET_MATERIALIZATION` event**; and the derived
  partition status is **failed and not materialized** (the assertion the previous test lacked, which
  is why the bug slipped through). This last assertion is the regression guard — it fails if the
  failure path ever re-greens the partition.
- `test_reports.py::test_missing_report_authors_failed` — updated to read the observation.
- `test_reports.py::test_timeout_authors_timeout_with_null_numerics_and_kills` — updated to read the
  observation; docstring corrected.
- `test_reports.py::test_job_only_failure_raises_without_materialization` — unchanged (job-only path
  was never materializing; still correct).

## Local Verification

- `cd orchestrator && ../.venv/bin/python -m pytest -q` → **50 passed** (was 50 before; the renamed
  failure test replaces the old one 1:1).
- Pre-fix mechanism check (scratch script, Dagster 1.13.21) → confirmed materialization greens /
  observation reds the partition, as tabulated above.

## Deviations from Assessment

None. The assessment's preferred remediation (`AssetObservation` instead of `AssetMaterialization`)
was applied. Its open question — whether, on 1.13.21, a failed run + observation renders the
partition red — was resolved empirically before coding (see the table above), so the asset-check
alternative was not needed.

## Follow-ups

- **UI metadata visibility**: the partition status is now correct (red). Whether the Dagster
  partitions *detail panel* surfaces observation metadata as prominently as materialization metadata
  is a UI nuance; the report is also in the run log (`result:` summary) and the transcript, and the
  observation is queryable in the asset's event history. Worth an eyeball on the live UI at
  `assets/verify/fail?view=partitions` after the next failed run.
- **Historical false-greens**: partitions already recorded green by the old code (e.g. `verify/fail`
  `2026-09-11`) stay green until re-materialized; this fix is forward-looking.
- **Docs**: `spec.md` / `research.md` still describe the failure event as a "materialization" in
  places; left as historical design records (the living *contracts* were corrected). Update if the
  spec is revised.
- Suggested next: `/speckit-bug-test slug=failed-asset-shows-materialized` — ideally including a live
  run of `verify/fail` on the host to confirm the partition shows red in the actual UI.
