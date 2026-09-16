# Bug Fix: Agents overview shows no latest run / history for asset agents

- **Slug**: overview-missing-asset-runs
- **Fixed**: 2026-09-16
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The agents-list activity read now sources an **asset** agent's run history from Dagster's implicit
asset job (`__ASSET_JOB`) filtered by asset key, instead of the `agent_<name>` pipeline that
automation-triggered materializations never use. Plain job agents are unchanged; both-kind agents
merge their job-launched runs with their asset materializations, newest first.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `ui/dagster.py` | modified | `_build_query` skips the `agent_<name>` runs read for asset-only agents, emits one shared `__ASSET_JOB` runs read (with `assetSelection`) when any asset agent is present, and reuses the computed asset key for the checks alias. |
| `ui/dagster.py` | added | Helpers `_results_of`, `_run_row`, `_selection_has_key`, and `_agent_runs` (merge job + asset-materialization runs, sort newest-first); `activity()` calls `_agent_runs`. Constants `_ASSET_JOB_PIPELINE`, `_ASSET_RUNS_LIMIT = 250`. |
| `ui/tests/test_dagster.py` | added | New unit + stubbed-transport tests for the query builder and run shaping. |

## Diff Highlights

Query builder — asset agents get no job read but share one asset-job read:

```python
has_job = bool(row.get("is_job")) or asset_key is None
if has_job:
    meta["runs"] = f"a{i}_runs"
    ... pipelineRunsOrError(filter: {pipelineName: "agent_<name>"}) ...
if asset_key is not None:
    any_asset = True
...
if any_asset:
    fields.append('asset_runs: pipelineRunsOrError('
        'filter: {pipelineName: "__ASSET_JOB"}, limit: 250) '
        '{ ... results { runId status startTime endTime assetSelection { path } } } }')
```

Run shaping — merge the two sources and keep newest first (failures included):

```python
def _agent_runs(data, meta, asset_runs):
    key = meta.get("asset_key")
    if key is None:
        return _parse_runs(data.get(meta["runs"]))      # plain job agent, Dagster order
    results = [r for r in asset_runs if _selection_has_key(r, key)]
    if meta["runs"] is not None:                         # both-kind: add job-launched runs
        results = results + _results_of(data.get(meta["runs"]))
    if not results:
        return None, None
    results.sort(key=lambda r: r.get("startTime") or 0, reverse=True)
    return _run_row(results[0]), [r.get("status") for r in results][:10]
```

## Tests Added or Updated

- `ui/tests/test_dagster.py::test_build_query_job_agent_filters_its_own_pipeline` — job agents keep the `agent_<name>` filter and add no asset read.
- `...::test_build_query_asset_only_agent_has_no_job_read_and_shares_asset_read` — asset-only agent has `meta["runs"] is None` and the query emits the `__ASSET_JOB` read with `assetSelection`.
- `...::test_build_query_both_kind_agent_reads_job_and_asset` — both pipelines read.
- `...::test_agent_runs_job_only_preserves_dagster_order` — no behavior change for job agents.
- `...::test_agent_runs_asset_only_from_shared_read_includes_failures` — a **failed** materialization still appears (guards against an `assetMaterializations`-only implementation).
- `...::test_agent_runs_asset_only_no_matching_runs_is_null` — other assets' runs are ignored.
- `...::test_agent_runs_both_kind_merges_job_and_asset_newest_first` — union sorted by start time.
- `...::test_activity_populates_asset_agent_from_shared_asset_runs` — end-to-end via a stubbed transport.

## Local Verification

- `cd ui && ../.venv/bin/python -m pytest tests/test_dagster.py -q` → **8 passed**.
- `cd ui && ../.venv/bin/python -m pytest -q` → **464 passed** (no regressions).
- Live Dagster (host `localhost:3000`), the exact shared read the fix emits, bucketed by key:
  - `notes/daily` → matched **12** runs, history `[SUCCESS×6, FAILURE×4, …]` (previously empty).
  - `speckit/implement` → matched **1** run, latest `SUCCESS` (previously empty).

## Deviations from Assessment

- Chose the assessment's **alternative** (one shared `__ASSET_JOB` read bucketed client-side by
  asset key) over the *preferred* per-agent alias. It is both more correct (no per-agent limit
  starvation) and cheaper (a single alias regardless of asset-agent count) — the assessment already
  flagged it as the right optimization once correctness landed. Open question on `limit` resolved
  to a shared `250`.
- Both-kind ordering open question resolved to **merge** job-launched runs with asset
  materializations (newest first), so an explicit job launch and an automation run both show.

## Follow-ups

- If the box grows to many noisy asset agents, revisit `_ASSET_RUNS_LIMIT` (250) — a single very
  busy asset could still crowd another's last-10 within the shared window.
- `.specify/bugs/overview-missing-asset-runs/` artifacts are tracked; stage them with the fix commit.
