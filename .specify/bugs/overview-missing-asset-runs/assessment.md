# Bug Assessment: Agents overview shows no latest run / history for asset agents

- **Slug**: overview-missing-asset-runs
- **Created**: 2026-09-16
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> latest run and run history aren't appearing on the agents overview page for a number of
> agents that have been run, e.g. `notes` or `speckit-implement`

## Symptom

On the `/agents` overview page, the "latest run" and run-history columns are empty (em-dashes)
for agents that have demonstrably been run. Expected: those columns reflect the agent's most
recent run and its recent status history. The affected agents are all **asset-declaring** agents
(`notes` is asset-only; `speckit-implement` is both-kind). Plain job agents are unaffected. The
Runs list page (which reads run directories from disk) *does* show these runs, so the runs clearly
exist — only the overview's live activity read misses them.

## Reproduction

1. Have an asset agent (e.g. `notes`, asset `notes/daily`) materialize via its automation
   condition / `autocond_<name>` sensor at least once.
2. Open `http://10.0.0.100:3000/agents` (the overview list). Wait for `GET /api/agents/activity`.
3. Observe the `notes` and `speckit-implement` rows: latest-run and history columns are empty,
   even though `/data/agentbox/runs/notes/...` and `.../speckit-implement/...` contain runs and
   the Runs list page shows them.

Verified against the live box:
- Disk runs exist: `notes` run `88c7ba46-…` and `speckit-implement` run `a948c046-…`.
- Dagster reports both with `pipelineName: "__ASSET_JOB"` (not `agent_notes` /
  `agent_speckit_implement`), each carrying `assetSelection.path` = `["notes","daily"]` /
  `["speckit","implement"]`.

## Suspected Code Paths

- `ui/dagster.py:160-164` — `_build_query` filters each agent's runs with
  `pipelineRunsOrError(filter: {pipelineName: <job>})`, where `job = "agent_" + name` (hyphens →
  underscores). This is the bug: asset materializations triggered by the automation condition run
  under Dagster's implicit `__ASSET_JOB`, **not** under `agent_<name>`. Asset-only agents have no
  `agent_<name>` job at all; both-kind agents have one, but automation-triggered materializations
  still land on `__ASSET_JOB` (only an explicit job launch uses `agent_<name>`). So the filter
  matches zero runs for asset agents.
- `ui/dagster.py:193-208` — `_parse_runs` shapes `latest_run` + `history` from that (empty) alias
  result; nothing downstream is wrong, it is simply fed no rows.
- `ui/dagster.py:142-148` — `_asset_key_path(row)` already extracts the asset key segments from a
  row's `/assets/<key>` `dagster_path`; the fix can reuse it to identify asset rows and match runs.
- `ui/dagster.py:255-289` — `activity()` assembles the per-agent payload; unaffected in logic but
  the place the new asset-run data must flow through.
- `ui/agents_store.py:364-380` / `read_agent` — sets `dagster_job = agent_<stem>` and
  `dagster_path = /assets/<key>` for asset rows; the row already carries `is_asset` and the asset
  path, so no new data is needed from the store.

## Root Cause Hypothesis

The overview's activity read keys every agent's run history off the named job pipeline
`agent_<name>`. Runs that materialize an asset via the automation condition are launched by
Dagster on the implicit `__ASSET_JOB` pipeline and identify their target only via
`assetSelection`. The `pipelineName: agent_<name>` filter therefore returns nothing for asset
agents, so latest-run and history render empty even though the runs exist and are visible on the
disk-backed Runs page. Confidence: **high** (reproduced live: the two named runs both report
`pipelineName: __ASSET_JOB` with the matching `assetSelection`).

## Proposed Remediation

**Preferred**: In `ui/dagster.py`, fetch runs for **asset** rows by asset key instead of by the
`agent_<name>` job name. Because this Dagster's `RunsFilter` has **no** asset-key field (confirmed
via introspection — only `runIds/pipelineName/tags/statuses/snapshotId/updated*/created*/mode`),
the workable path within the single aliased read is:

- For an asset row (`row["is_asset"]` with an asset key from `_asset_key_path`), alias a
  `pipelineRunsOrError(filter: {pipelineName: "__ASSET_JOB"}, limit: N)` sub-read that also selects
  `assetSelection { path }` on each result, then in `_parse_runs` (or a variant) keep only results
  whose `assetSelection` contains the row's asset key path, take the first 10, and derive
  `latest_run` + `history` from those. Use a generous `limit` (e.g. 50) since `__ASSET_JOB` is
  shared across all asset agents and a small limit could starve one agent's history.
- For a both-kind agent, optionally **union** the `__ASSET_JOB`-filtered results with the existing
  `agent_<name>` job results (job-launched runs use the named pipeline) and sort by `startTime`
  desc so an explicit job launch and an automation materialization both show.
- Keep plain job agents on the existing `pipelineName: agent_<name>` path unchanged.

Do **not** use `assetOrError.assetMaterializations` as the sole source: it only lists **successful**
materializations (verified — the failed `notes` run `88c7ba46-…` does not appear there), so it
cannot reproduce a failure-inclusive latest-run/history. `assetSelection` filtering keeps failures.

**Alternatives**:
- One `__ASSET_JOB` read shared across all asset rows (dedupe the alias), bucketed client-side by
  asset key. Fewer/smaller GraphQL aliases and avoids N overlapping large reads, at the cost of a
  bigger single `limit`; a good optimization once the correctness fix lands.
- Tag-based filtering was considered and rejected: the sampled runs carry no per-asset-key tag
  (only `dagster/code_location`, `dagster/from_ui`), so there is nothing reliable to filter on.

**Files likely to change**:
- `ui/dagster.py` (`_build_query`, `_parse_runs`, possibly `activity`)
- `ui/tests/test_dagster.py` (or wherever activity/query tests live)

**Tests to add or update**:
- `_build_query` emits an asset-key/`__ASSET_JOB` runs sub-read for an asset row and the plain
  `agent_<name>` filter for a job-only row.
- `activity()` (with a mocked GraphQL payload) returns a non-null `latest_run` + populated
  `history` for an asset agent whose `__ASSET_JOB` results include that asset key, and correctly
  ignores `__ASSET_JOB` results belonging to a *different* asset key.
- A both-kind agent surfaces both a job-launched run and an automation materialization, newest
  first.
- Regression: a run with a **failed** status still appears in history/latest for an asset agent
  (guards against an `assetMaterializations`-only implementation).

## Risks & Considerations

- **Query cost / limit tuning**: `__ASSET_JOB` is shared, so a per-agent `limit` that is too small
  can miss an agent's runs when other assets are noisy. The shared-read alternative mitigates this.
- **GraphQL shape drift**: adds `assetSelection { path }` to the runs selection; keep the
  degrade-to-`reachable:false` behavior on any parse error (contract dagster-activity §B) intact.
- **Schedules/checks columns**: unaffected — this only touches the runs sub-read; keep the
  instigation and asset-check aliases as-is.
- **Both-kind ordering**: unioning two sources requires a stable sort by `startTime` (nulls last)
  so latest-run is deterministic.
- No migration, no API breakage for existing job agents.

## Open Questions

- [NEEDS CLARIFICATION: preferred `limit` for the shared `__ASSET_JOB` read given expected asset
  count on this box — 50 is a starting guess.]
- [NEEDS CLARIFICATION: should a both-kind agent's history merge job-launched + automation runs, or
  is showing only the asset-materialization history acceptable for the overview?]
