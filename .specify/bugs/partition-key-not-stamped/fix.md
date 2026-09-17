# Bug Fix: Refuse partitionless materialization of a daily asset

- **Slug**: partition-key-not-stamped
- **Fixed**: 2026-09-17
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added an op-level guard that refuses an asset-materializing run of a `partition: daily` asset
when the run carries no partition key, before any launch work. This makes `partition=None` on a
daily asset impossible at the source and removes the downstream cascade (an upstream that can
never be unpartitioned can never fire an unpartitioned downstream). Chosen behavior: **refuse**
(loud), per the user's decision on the assessment's open question.

## Root cause (confirmed, see assessment History)

The emission path stamps the partition correctly when the run is partitioned (proven by repro).
`partition=None` daily materializations came from runs with **no partition key** — chiefly
manual/job launches of a partitioned asset with no partition selected — which then cascaded to
unpartitioned downstream runs via `on_upstream`'s `any_deps_updated()`. The system permitted a
partitioned asset to be materialized with no partition; the guard closes that.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `orchestrator/factory.py` | added `PartitionRequired` exception | raised when a daily asset run has no partition key |
| `orchestrator/factory.py` | added `require_partition(cfg, context, is_asset)` | no-op for plain jobs and unpartitioned assets; raises otherwise |
| `orchestrator/factory.py` | call in checkless `from_op` op (`run_agent`) | after `is_asset`, before governor/launch |
| `orchestrator/factory.py` | call in checked `@multi_asset` op (`run_agent_checked`) | before governor/launch (always an asset) |
| `orchestrator/tests/test_factory.py` | added 5 tests | guard behavior + partitioned-success regression |

## Diff Highlights

```python
class PartitionRequired(Exception):
    """A daily asset was materialized with no partition key (bug partition-key-not-stamped)."""

def require_partition(cfg, context, is_asset):
    produces = cfg.get("produces") or {}
    if not is_asset or produces.get("partition") != "daily":
        return
    if getattr(context, "has_partition_key", False):
        return
    raise PartitionRequired(
        f"{cfg['name']}: daily asset '{produces.get('asset')}' was materialized without a "
        "partition. Daily assets must target a concrete partition key — select a partition.")
```

Called before launch work in both op paths:
```python
is_asset = bool((cfg.get("produces") or {}).get("asset"))
require_partition(cfg, context, is_asset)     # from_op path
...
require_partition(cfg, context, True)         # @multi_asset path
```

## Tests Added or Updated

- `test_require_partition_refuses_daily_without_partition` — daily asset + no partition ⇒ `PartitionRequired`.
- `test_require_partition_allows_daily_with_partition` — daily asset + partition key ⇒ no raise.
- `test_require_partition_noop_for_unpartitioned_asset` — no `partition: daily` ⇒ no raise.
- `test_require_partition_noop_for_plain_job` — `is_asset=False` (plain job) ⇒ no raise.
- `test_daily_success_materialization_records_partition` — partitioned run still succeeds and the
  recorded `AssetMaterialization.partition == "2026-09-09"` (guard doesn't break the happy path).

## Local Verification

- `pytest orchestrator/tests/test_factory.py -q` → **50 passed** (5 new).
- `pytest orchestrator/tests/ -q` → **206 passed** (was 201; +5), no regressions.

## Deviations from Assessment

None from the **revised** assessment — the fix implements its preferred remediation (op-level
refuse guard). Note the original (2026-09-16) assessment proposed an emission-side fix that was
disproven; the assessment was rewritten on 2026-09-17 before this fix (see its History section).

## Follow-ups

- **Data hygiene**: pre-existing `partition=None` events remain in the event log for
  `notes/daily` and `refined/daily`; consider wiping them so the assets show a clean partitioned
  history now that new ones can't be created.
- **`on_upstream` chattiness** (secondary, not addressed): a daily upstream materialized
  repeatedly still re-fires the downstream once per event. Out of scope for this bug; open a
  separate item if the noise matters.
- **Operator note**: any launcher/script that fired a partitioned asset without a partition will
  now fail loudly with `PartitionRequired` — that is intended. Mention in the changelog.
