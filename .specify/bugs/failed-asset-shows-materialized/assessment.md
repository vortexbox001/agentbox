# Bug Assessment: Failed asset run renders its partition green/"materialized"

- **Slug**: failed-asset-shows-materialized
- **Created**: 2026-09-12
- **Source**: pasted text + URL `http://10.0.0.100:3000/assets/verify/fail?view=partitions&partition=2026-09-11`
- **Verdict**: valid
- **Severity**: medium

## URL handling

- **URL supplied**: `http://10.0.0.100:3000/assets/verify/fail?view=partitions&partition=2026-09-11`
- **Host parsed**: `10.0.0.100`
- **Policy branch**: `auto-refused: RFC1918 private space (10.0.0.0/8)` — not fetched. This is
  the operator's own Dagster UI (the agentbox host); its contents are not needed to assess the
  bug, which is grounded in the code. No preflight request was issued.

## Report (summarized)

The `verify-fail` agent — an asset agent (`produces.asset: verify/fail`, `partition: daily`)
whose prompt deliberately fails — ran and produced a report with `status: failed`. In the
Dagster asset partitions view, the `2026-09-11` partition nonetheless shows **green /
"materialized"**, rather than red/failed as spec 007 (SC-003) promised for a failed asset run.

## Symptom

A non-`ok` asset run marks the Dagster **run** as failed, but the corresponding **asset
partition** displays as materialized (green). Expected (spec 007 SC-003 / spec.md:66,130-131):
the partition shows **red** *with* a report attached (`status: failed`, `error`, transcript
path), not green.

## Reproduction

1. Ensure `agents/verify-fail.yaml` is enabled (it is) — asset `verify/fail`, `partition: daily`.
2. In Dagster, materialize a partition of `verify/fail` (e.g. `2026-09-11`). The agent is built to
   fail, so the container hands back a report with `status: failed`.
3. Observe: the run appears **failed** in the Runs list, but the partition in
   `assets/verify/fail?view=partitions` shows **green / "materialized"**.

Expected: the partition shows **red / failed**, carrying the `status: failed` report metadata.

## Suspected Code Paths

- `orchestrator/factory.py:534-544` — the asset failure branch of `make_run_op`'s op. On a
  non-`ok`/non-zero/timeout run it calls
  `context.log_event(AssetMaterialization(asset_key=..., partition=..., metadata=metadata))`
  **then** `raise`. Emitting an `AssetMaterialization` is exactly the event Dagster uses to mark a
  partition **materialized (green)**. The subsequent `raise` fails the *run* but does not un-record
  the materialization, so the *partition* stays green. **This is the defect.**
- `orchestrator/factory.py:524-529` — the success branch returns `Output(...)`; for contrast, this
  is the only place a materialization *should* be recorded.
- `specs/007-run-reports-via-pipes/research.md:101-116` — the design decision that assumed
  `log_event(AssetMaterialization(...)) + raise` yields "red with the report attached." That
  assumption about Dagster's partition-status semantics is incorrect: a materialization event is a
  *success* signal for the partition; it cannot coexist with a red/failed partition.
- `orchestrator/tests/test_reports.py:182-199`
  (`test_failed_asset_records_materialization_and_raises`) — asserts a materialization is recorded
  and the run fails, but **never asserts the partition status is failed/red**, so it passed while
  the user-visible behavior is wrong. The test encodes the flawed intent.

## Root Cause Hypothesis

**Confidence: high.** Dagster derives an asset partition's status from its event log: a partition
with an `AssetMaterialization` event is shown MATERIALIZED (green); a partition is shown FAILED
(red) when a run that targeted it failed **without** producing a materialization. The failure path
in `make_run_op` emits a genuine `AssetMaterialization` for the partition and then raises. The
raise marks the *run* failed, but the materialization event is already durably recorded (indeed the
US2 tests read it back from the instance event log on purpose), so the *partition* renders green.
Spec 007's goal of "red **with** a materialization" is not achievable through an
`AssetMaterialization` event, because that event is precisely the thing that makes a partition
green. The report metadata must be attached to the asset by a non-materializing event instead.

## Proposed Remediation

**Preferred**: On the asset failure path, replace the `AssetMaterialization` event with an
`AssetObservation` carrying the same metadata union, then `raise`. An `AssetObservation` records
metadata against the asset/partition **without** marking it materialized, so the failed run (which
now produces no materialization for that partition) leaves the partition in the FAILED (red) state,
while the observation preserves the report (`status`, `error`, `transcript`, counts) for
auditability. Concretely, in `make_run_op`'s `is_asset` failure branch, swap
`context.log_event(AssetMaterialization(asset_key=k, partition=p, metadata=metadata))` for
`context.log_event(AssetObservation(asset_key=k, partition=p, metadata=metadata))`. The success
path is unchanged. Verify on the pinned Dagster (1.13.21) that (a) a failed asset run's partition
renders red, and (b) the observation's metadata is reachable from the partition/asset view; if the
partitions detail panel does not surface observation metadata as desired, fall back to the
alternative below.

**Alternatives**:
- **Asset check failure**: attach an `AssetCheckResult(passed=False, metadata=...)` (or a failed
  asset check) to carry the failure signal and metadata. Trade-off: requires defining an asset
  check per asset and changes the asset's shape more invasively than an observation; heavier than
  the problem warrants.
- **Accept green + rely on the Runs list / run metadata for failures** (i.e. drop SC-003's "red"
  goal and document it): least code, but abandons the spec's central promise that a failed
  partition is visibly distinguishable from a healthy one — not recommended.

**Files likely to change**:
- `orchestrator/factory.py` (the `is_asset` failure branch in `make_run_op`; import
  `AssetObservation`)
- `orchestrator/tests/test_reports.py` (update the failure-path tests)
- `specs/007-run-reports-via-pipes/research.md`, `contracts/pipes-transport.md`,
  `contracts/metadata.md`, `quickstart.md`, `spec.md` (correct the "red with a materialization"
  language to "red with an observation"; docs-only, do at fix time)

**Tests to add or update**:
- Update `test_failed_asset_records_materialization_and_raises` (and the timeout / missing-report
  variants) to assert that after a failed run **no materialization event exists** for the
  partition, an **observation** carrying `status: failed` (or `timeout`) does, and — the assertion
  the current test is missing — that the partition's derived status is **failed/not-materialized**
  (e.g. via `DagsterInstance`/`AssetRecord` partition-status APIs, so a regression that re-greens
  the partition is caught).
- Keep `test_success_records_exactly_one_materialization` green (success path unchanged).

## Risks & Considerations

- **Dagster version semantics**: the exact partition-status rendering (does a failed run with an
  observation reliably show red? does the partitions detail panel show observation metadata?) is
  version-dependent — validate against the pinned 1.13.21 before/while fixing. This is the main
  reason the "verify" step matters here.
- **Observability regression the other way**: ensure the observation still surfaces `error`,
  `transcript`, and counts where an operator looks; if only materializations appear in the
  partition detail panel, prefer the asset-check alternative or also log the report to the run log
  (the one-line `result:` summary already does this in `factory.py:516-522`).
- **Job-only path unaffected**: job-only agents already attach report metadata via
  `add_output_metadata` + `raise` (no asset key, no materialization) — do not change that branch.
- **No data/API/migration risk**: change is confined to which Dagster event the failure path emits;
  the report shape, Pipes transport, and launch isolation are untouched.
- **Historical partitions**: already-recorded false-green materializations (like `2026-09-11`) will
  remain green until re-materialized; the fix is forward-looking only.

## Open Questions

- [NEEDS CLARIFICATION: On the pinned Dagster 1.13.21, does a failed run that emits an
  `AssetObservation` (and no materialization) render the partition red in
  `?view=partitions`, and is the observation's metadata visible from that view? The remediation is
  correct in principle; this determines whether the observation form is sufficient or the
  asset-check alternative is needed.]
