# Contract: Orchestrator model — deps, composed conditions, handoff, chain depth, governors

How the orchestrator turns `depends_on` + the two triggers into Dagster definitions, builds the
read-only handoff, derives `chain_depth`, and enforces the governors. Authority:
`orchestrator/factory.py`, `orchestrator/definitions.py`, new `orchestrator/governors.py`.

## §1 `depends_on` → asset deps (FR-001/FR-007)

`build_asset(cfg, file, cron, depends_on)` and `_build_checked_asset(...)` attach one Dagster dep
per `depends_on` entry:

- **Checkless path** (`AssetsDefinition.from_op`): pass `deps=[AssetKey(k.split("/")) for k in
  depends_on]`.
- **Check-bearing path** (`dagster_internal_init` + `AssetSpec`): the `AssetSpec` gains
  `deps=[AssetDep(AssetKey(k.split("/")), partition_mapping=mapping) for k in depends_on]`.
- **Partition mapping**: identity `TimeWindowPartitionMapping()` when both assets are `daily`
  (daily→daily, FR-007). For an unpartitioned pair, no mapping. Applied only when
  `partition_upstream_supported()` (R2); otherwise a daily asset's upstream condition is dropped and
  a load-warning is logged (see §6).

Deps are **non-arg** — the op signature is unchanged; the data handoff is the file (§2), not
Dagster IO.

## §2 Composed automation condition + one sensor (FR-004/FR-005/FR-008/FR-010)

New `compose_automation_condition(cfg, *, cron, on_upstream, on_missing, partitioned)` returns a
single `AutomationCondition` or `None`:

```python
parts = []
if cron:
    parts.append(AutomationCondition.on_cron(cron, cron_timezone=cron_timezone()))
if on_upstream and (not partitioned or partition_upstream_supported()):
    parts.append(AutomationCondition.any_deps_updated())
if on_missing:
    parts.append(AutomationCondition.missing() & AutomationCondition.in_latest_time_window())
if not parts:
    return None
cond = parts[0]
for p in parts[1:]:
    cond = cond | p
return cond & ~AutomationCondition.in_progress()
```

- The condition is attached where `on_cron` is today (`automation_conditions_by_output_name` on the
  checkless path; `AssetSpec(automation_condition=…)` on the checked path).
- `build_asset_automation_sensor(cfg, asset_def)` (unchanged: `autocond_<name>`, `STOPPED`) is
  created whenever **any** of `{asset_schedule, on_upstream, on_missing}` is set — not only
  `asset_schedule`. The unchanged name preserves the operator's existing toggle.
- **Blocking-check gating** (FR-006): no extra code — `any_deps_updated()` reacts to
  materializations, and a failed blocking check yields an `AssetObservation` not a materialization
  (existing `_build_checked_asset` behavior), so the downstream does not fire until the upstream
  materializes with blocking checks passing.

## §3 Upstream handoff (FR-011/FR-012/FR-012a/FR-013)

New `build_upstream_handoff(cfg, context, handoff_dir) -> dict[str, str]` (env-var name → in-
container path), called in the op before `_build_agent_cmd`:

1. For each `k` in `produces.depends_on`:
   - Resolve the matching partition: `context.partition_key` if the downstream is partitioned, else
     `None` (daily→daily identity, R2).
   - Query the latest matching materialization:
     - partitioned: `context.instance.get_event_records(EventRecordsFilter(
       DagsterEventType.ASSET_MATERIALIZATION, asset_key=AssetKey(k.split("/")),
       asset_partitions=[partition]), limit=1, ascending=False)`.
     - unpartitioned: `context.instance.get_latest_materialization_event(AssetKey(k.split("/")))`.
   - Read `output_files`, the spec-007 `report` fields, `materialized_at`, `chain_depth`,
     `automated` off the materialization metadata (via `build_metadata`'s recorded keys).
   - Write `<handoff_dir>/<key-slug>.json` per
     [upstream-handoff.schema.json](upstream-handoff.schema.json). When there is no matching
     materialization, write the file with `materialized: false` and null/empty fields (FR-012a).
     `chmod 0644` so the non-root container reads it.
2. Return `{f"AGENTBOX_UPSTREAM_{upper_snake(k)}": f"/upstreams/{key-slug}.json"}` for every `k`.

Wiring:
- `handoff_dir = tempfile.mkdtemp(prefix=..., dir=STAGING_ROOT-like host==container root)`,
  `chmod 0777`; `--rm`-cleaned in the op's `finally` (like pipes/staging).
- `_build_agent_cmd` gains `-v <handoff_dir>:/upstreams:ro` (read-only, FR-013) and the returned
  env vars (merged into the launch like `runtime_env`).
- `_launch_env_names` adds the `AGENTBOX_UPSTREAM_*` names; `_launch_mounts` adds
  `{source: handoff_dir, target: "/upstreams", mode: "ro"}`.

**Key transform** `upper_snake("notes/daily") == "NOTES_DAILY"`; `-` and `/` → `_`, uppercased.
`key-slug` (filename) is the lowercased key with `/` → `_` (e.g. `notes_daily.json`).

## §4 Cycle & dangling-reference rejection at load (FR-002/FR-003)

In `definitions.discover()`, after `pending_assets` is collected (asset key ⇒ file is known):

1. Build `graph = {asset_key: [depends_on keys]}` for every pending asset; `produced = set(asset
   keys)`.
2. **Dangling**: for each asset, any `depends_on` key not in `produced` ⇒ reject that asset,
   `log.warning("%s: depends_on names unknown asset key %r", file, key)` (FR-002 / US4 #3).
3. **Cycle**: DFS over `graph`; for every asset on a cycle, reject it,
   `log.warning('dependency cycle: %s', " -> ".join(cycle_keys))` naming the assets (FR-003 / US4 #1).
4. **Cascade**: iterate to a fixpoint — an asset whose upstream was rejected now dangles ⇒ reject
   too. Every unrelated asset still loads.
5. Rejected assets are added to `rejected_files` (existing mechanism) so their asset def, sensor,
   and materializing job are all skipped — no automation runs against a bad graph (US4 "before any
   automation runs").

An acyclic graph with all keys present loads unchanged (US4 #2).

## §5 chain_depth derivation + recording (FR-015)

In the op, after building the handoff (§3), reuse the read materializations:

```python
depths = [m["chain_depth"] for m in upstream_matches if m.get("automated")]
chain_depth = (max(depths) + 1) if depths else 1
```

- Recorded in the run: `context.instance.add_run_tags(context.dagster_run,
  {"agentbox/chain_depth": str(chain_depth), "agentbox/automated": "1" if automated else "0"})`,
  and added to `build_metadata` (`chain_depth`, `automated`) so downstreams read it via §3.
- A manual upstream is excluded from `depths` (its `automated` is false) ⇒ its downstream is a root
  (depth 1), matching FR-015.

## §6 Governors (FR-014/FR-016/FR-017/FR-018)

**Reader** — new `orchestrator/governors.py`:

```python
DEFAULT_GOVERNORS = {"max_runs_per_hour": 12, "max_chain_depth": 5}

def load_governors() -> dict:
    """Read the governors block from paths.SETTINGS_FILE, falling back to DEFAULT_GOVERNORS
    per-key when the file/block/key is absent or invalid. Twin of ui/settings_store defaults."""
```

**Enforcement** — a helper `governor_gate(context, cfg, chain_depth, automated) -> None` called at
op start (both op bodies), after §5:

1. `add_run_tags` (§5).
2. If not `automated` → return (manual bypass, FR-017).
3. `gov = load_governors()`.
4. If `chain_depth > gov["max_chain_depth"]` → `refuse(context, cfg, f"chain_depth {chain_depth} >
   max_chain_depth {gov['max_chain_depth']}")` (FR-016).
5. Count launched automated runs in the trailing 60 minutes:
   `context.instance.get_run_records(RunsFilter(created_after=now-60m,
   tags={"agentbox/automated": "1", "agentbox/launched": "1"}))`; if `count >=
   gov["max_runs_per_hour"]` → `refuse(context, cfg, f"max_runs_per_hour {…} reached in the last
   60m")` (FR-014, rolling window).
6. Otherwise `add_run_tags(..., {"agentbox/launched": "1"})` **before** launch, so it counts toward
   the window; then launch.

`refuse(context, cfg, reason)`:
- `context.log.warning(f"{cfg['name']}: automated run refused — {reason} (manual runs bypass)")`
  (visible in the daemon log, FR-014/FR-016/US5 #1/#2).
- Emit `AssetObservation(asset_key, partition, metadata={"refused": reason, ...})` (asset) or
  `context.add_output_metadata({"refused": reason})` (job) — the partition is **not** greened.
- `raise GovernorRefusal(reason)` to end the run. The run is **not** tagged `agentbox/launched`, so
  it never consumes a per-hour slot (spec clarification).

Manual re-trigger of the same agent skips step 2 onward and launches (US5 #3).

**Race note**: the count-then-launch window admits at most one extra run under simultaneous ticks;
acceptable on the single-host Pi and documented (R8).

## §7 What is unchanged

`make_run_op` / `_run_producer` container launch, Pipes transport, redaction, run-directory
capture, checks execution, and the asset/job/both routing (spec 006) are untouched apart from: the
added `deps`, the composed condition, the `:ro /upstreams` mount + `AGENTBOX_UPSTREAM_*` env vars,
the `add_run_tags` calls, and the governor gate. No per-harness code path is added.
