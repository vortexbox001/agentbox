# Bug Verification: Refuse partitionless materialization of a daily asset

- **Slug**: partition-key-not-stamped
- **Tested**: 2026-09-17
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom no longer reproduces: launching the materializing asset job for a daily
asset **without a partition** — the exact production path that produced `partition=None` events —
is now refused with `PartitionRequired` and records **zero** materializations. All guard tests
and the full orchestrator regression suite pass. Verified in-process; the live deployed
orchestrator still needs an image rebuild to carry the fix (see Residual Risks).

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | in-process `get_job_def("agent_…").execute_in_process()` on a daily asset with **no** partition | pass | run refused (`PartitionRequired` at factory.py:553); `ASSET_MATERIALIZATION` events = 0 |
| New / updated tests | `pytest -k "require_partition or daily_success_materialization"` | pass | 5 passed |
| Regression suite | `pytest orchestrator/tests/ -q` | pass | 206 passed (was 201; +5 from the fix) |
| Live end-to-end (deployed daemon + sensor cascade) | rebuild image, un-pause `autocond_*`, observe | skipped | requires `docker compose build`; not run to avoid repopulating the just-wiped history |
| Lint / type-check | — | not-run | project has no configured lint/type gate for orchestrator |

## Output Excerpts

Reproduction (partitionless daily job):
```
File ".../orchestrator/factory.py", line 553, in require_partition
    raise PartitionRequired(
REPRO: partitionless daily job refused; materializations recorded = 0
1 passed
```

Guard + regression:
```
5 passed, 45 deselected      # require_partition / daily_success_materialization
206 passed, 30 warnings      # full orchestrator suite
```

## Deployment Confirmation (2026-09-17, post-rebuild)

- Orchestrator image rebuilt and restarted. `class PartitionRequired` + `def require_partition`
  are present in the running `dagster-daemon` and `dagster-webserver` containers
  (`grep` inside the container → 2 matches).
- `notes/daily` and `refined/daily` still show 0 materializations — the wipe held and no new
  `partition=None` events appeared after the rebuild.
- A live end-to-end launch was NOT performed: `notes`/`refined` are now `enabled: false`
  (deliberately disabled to stop the loop), so they are unregistered and there is no partitioned
  asset to fire a live partitionless run against. Functional behavior remains proven by the
  in-process reproduction above.

## Residual Risks

- **Live end-to-end not exercised.** The guard is confirmed deployed and proven in-process, but a
  partitionless launch against the *running* daemon was not run (the target assets are disabled).
  If `notes`/`refined` are re-enabled, confirm they accrue only partitioned materializations.
- **Cascade not exercised live.** The downstream loop (`refined` firing off unpartitioned `notes`
  events) was not reproduced against the live daemon; it is prevented by construction (the source
  `None` event can no longer be created), but that inference was not observed end-to-end.
- **`on_upstream` chattiness unchanged** (by design): a daily upstream materialized repeatedly
  still re-fires the downstream once per event. Out of scope for this bug.

## Recommendation

Close the bug — verified at the code level against the actual production path (partitionless
materializing job → refused, no `partition=None` recorded), with the full regression suite green.
Before relying on it in production, rebuild the orchestrator image so the guard is live, then
re-enable the `notes`/`refined` automation and confirm the assets accrue only partitioned
materializations.
