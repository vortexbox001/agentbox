# Bug Assessment: Daily assets can be materialized with no partition (partition=None), which cascades downstream

- **Slug**: partition-key-not-stamped
- **Created**: 2026-09-16
- **Revised**: 2026-09-17 (root cause corrected after reproduction — see History)
- **Source**: pasted text + live forensics on the `refined`/`notes` daily agents
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> Fix the partition propagation — the automated materialize path should stamp the run's
> partition key on the emitted materialization. That's the real bug; partition=None on a
> daily asset should never happen. Worth filing against 013.

The intent ("partition=None on a daily asset should never happen") is correct; the mechanism
("the automated path fails to stamp the partition") is **not** — see History / Root Cause.

## Symptom

Daily-partitioned assets (`notes/daily`, `refined/daily`) accumulate materializations with
`partition=None`. Because an unpartitioned materialization does not satisfy any partition-scoped
automation condition (`missing()`, per-partition `any_deps_updated()`), and because an
unpartitioned upstream event propagates to unpartitioned downstream runs, the assets never
present a clean partitioned history and downstream agents fire repeatedly. Expected: a
daily-partitioned asset is only ever materialized against a concrete partition key.

## Reproduction

1. Define daily asset `notes/daily` (`produces.partition: daily`, `triggers.on_missing: true`)
   and `refined/daily` (`depends_on: [notes/daily]`, `triggers.on_upstream: true`).
2. Materialize `notes` **without selecting a partition** — e.g. launch the plain
   `agent_notes` / `__ASSET_JOB` with no `dagster/partition` tag. Observe the recorded
   `AssetMaterialization.partition` is `None`.
3. Observe `refined` fire via `on_upstream` and itself record a `partition=None` materialization
   (the unpartitioned upstream event maps to an unpartitioned downstream run).
4. Repeat manual materializations; each one re-fires `refined`.

Confirmed on the live instance via run tags (`agentbox/automated`, `dagster/partition`,
`dagster/sensor_name`):

- `notes/daily` (19 mats): 10 were **manual, partition=None**; 7 manual `2026-09-15`; only 2
  were automation-driven (`autocond_notes`) and **both correctly partitioned** (2026-09-15,
  2026-09-16).
- `refined/daily` (15 mats): fired ~1:1 per `notes` materialization via `autocond_refined`; its
  `partition=None` runs are the downstream image of `notes`' partitionless events.

## Suspected Code Paths

- `orchestrator/factory.py` — the run op (`make_run_op` / `run_agent`, ~lines 1194-1290 checkless
  `from_op`, and ~lines 1417-1490 checked `@multi_asset`): neither path refuses to run when the
  asset is partitioned but `context.has_partition_key` is False; it proceeds and records an
  unpartitioned materialization/observation. This is where a guard belongs.
- `orchestrator/factory.py:386-387` — partition metadata is only added `if has_partition_key`;
  consistent with an unpartitioned run producing a partitionless event.
- `orchestrator/factory.py:1256-1261` — checkless success `Output(value=None)`. **Verified NOT
  the bug**: a reproduction test showed it records `partition='2026-09-09'` correctly when the
  run is partitioned.
- `orchestrator/factory.py:build_materializing_job` (~1554-1562) — `define_asset_job` over the
  asset yields a job (`agent_<name>`) that can be launched with no partition, one route by which
  a partitionless daily materialization is created.
- `orchestrator/factory.py:1592-1624` (`compose_automation_condition`) — `on_upstream` →
  `any_deps_updated()` re-fires the downstream on every upstream materialization, so a chatty or
  unpartitioned upstream produces many (and unpartitioned) downstream runs. Secondary factor.

## Root Cause Hypothesis

Confidence: **high**. The emitted materialization is stamped correctly **when the run carries a
partition key** (proven by reproduction). `partition=None` daily events come from **runs that
have no partition key at all** — principally manual/job launches of a partitioned asset with no
partition selected — and that unpartitioned state then **cascades downstream** through
`on_upstream` (`any_deps_updated()`), which faithfully maps an unpartitioned upstream event to an
unpartitioned downstream run. Nothing drops a partition key that was present; the system simply
**permits a partitioned asset to be materialized with no partition**, and propagates it.

## Proposed Remediation

**Preferred**: Guard at the run op. At the start of `run_agent` (before launching the container
or recording any materialization/observation), if the agent declares a partition
(`cfg["produces"].get("partition") == "daily"`) but `context.has_partition_key` is False, refuse
the run with a clear error (e.g. `RejectRun`/`Failure`: "daily asset <key> materialized without a
partition"). This makes `partition=None` on a daily asset impossible at the source, which also
removes the downstream cascade (an upstream that can never be unpartitioned can never fire an
unpartitioned downstream). Legitimate paths are unaffected: the Dagster UI forces partition
selection for partitioned assets, and automation targets the latest partition. Apply the guard on
both the checkless `from_op` path and the checked `@multi_asset` path.

**Alternatives**:
- **Route instead of refuse**: coerce a partitionless daily materialization to the latest
  partition rather than failing. More forgiving, but silently rewriting the target is surprising
  and can mask a real misconfiguration; prefer explicit refusal.
- **Restrict at the job layer**: prevent `agent_<name>` (materializing job) from launching a
  partitioned asset without a partition. Narrower, but does not cover every route that can
  produce an unpartitioned run.
- **013 null action**: set `notes`/`refined` to `partition: none`. Config-only mitigation that
  sidesteps the whole class, at the cost of losing daily partitioning.

**Files likely to change**:
- `orchestrator/factory.py`
- `orchestrator/tests/test_factory.py`

**Tests to add or update**:
- Materializing a daily asset **without** a partition key is refused (both `from_op` and
  `@multi_asset` paths); no `partition=None` materialization/observation is recorded.
- Materializing a daily asset **with** a partition key still succeeds and records that partition
  (regression lock for the verified-correct emission path).
- A daily `on_upstream` downstream, when its upstream is materialized against a partition, fires
  for the matching partition (not `None`).

## Risks & Considerations

- **FR-008b tension**: "the partition is a label; materializing any partition launches the same
  container." The guard must distinguish *no partition* (refuse) from *any specific partition*
  (allow) — it targets only the `has_partition_key is False` case.
- **Existing automation**: launchers/scripts that currently fire a partitioned asset without a
  partition will start failing loudly. That is the intended correction, but call it out in the
  changelog.
- **Data hygiene**: pre-existing `partition=None` events remain in the log; consider wiping them
  so the assets show a clean partitioned history after the guard lands.
- **`on_upstream` chattiness** (secondary): even with the guard, a daily upstream materialized
  repeatedly (manually) will still re-fire the downstream once per event. If that is undesirable,
  handle separately; it is not required to stop the `partition=None` bug.

## Open Questions

- [NEEDS CLARIFICATION: refuse vs. route-to-latest for a partitionless daily materialization —
  the preferred fix refuses; confirm that is the desired operator experience.]

## History

- **2026-09-16 (original)**: hypothesized the automated success path failed to stamp the
  partition on the emitted materialization (emission-side fix at factory.py:1256-1261).
- **2026-09-17 (this revision)**: a reproduction test recorded the partition correctly on that
  path, and run-tag forensics showed the `partition=None` events originate from **partitionless
  runs** (mostly manual launches) that cascade downstream via `on_upstream`. Root cause and
  remediation rewritten accordingly. See `fix.md` (status: not-applied) for the disproof detail.
