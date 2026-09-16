# Phase 0 Research: Event-Driven Triggers — Asset Dependency Graph

Decisions resolving the Technical Context unknowns. The feature extends existing surfaces (spec
004 `produces`, spec 006 `triggers` + `autocond_<name>` sensor, spec 008 checks, spec 012
`settings.yaml`), so most groundwork is carried forward; the new decisions concern how Dagster
1.13.21 expresses upstream/missing triggers, the read-only handoff, `chain_depth`, and the
governors.

**Unattended note**: `/speckit-plan` ran with no human to answer questions. Every choice below
that a clarifying question would have raised was decided here against the spec + repo and is
called out as **Decision (unattended)**; the spec's own Clarifications (2026-09-16) resolved the
five product-level questions already.

---

## R1 — Wiring `on_upstream` (FR-004/FR-006)

**Decision (unattended)**: Give the downstream asset real Dagster **deps** on each declared
upstream asset key, and drive `on_upstream` with `AutomationCondition.any_deps_updated()`.

- `depends_on: [notes/daily]` ⇒ the downstream `AssetsDefinition` declares
  `deps=[AssetKey(["notes", "daily"])]`. On the checkless path this passes through
  `AssetsDefinition.from_op(the_op, keys_by_output_name=…, deps=[…])`; on the check-bearing path
  the `AssetSpec` already built in `_build_checked_asset` gains `deps=[…]`. These are
  **non-arg** deps — the op takes no upstream value as a function argument; the actual data
  handoff is the `AGENTBOX_UPSTREAM_<KEY>` file (R6), not Dagster IO.
- The automation condition contribution for `on_upstream` is `AutomationCondition.any_deps_updated()`
  — it becomes true for a downstream partition when one of its dep partitions newly materializes.

**Blocking-check gating (FR-006)** falls out of the existing orchestrator behavior: a failed
**blocking** check fails the upstream step, so the upstream does **not** emit a successful
materialization (the orchestrator records an `AssetObservation`, not a `MaterializeResult` — see
`_build_checked_asset`, bug `failed-asset-shows-materialized`). `any_deps_updated()` keys off
materializations, so a blocking-failed upstream never marks the dep "updated" and the downstream
does not fire; once the check passes and the upstream materializes, it does (Acceptance US1 #2/#3).
If a future Dagster made `any_deps_updated()` fire on a materialization co-emitted with a failed
blocking check, AND `AutomationCondition.all_deps_blocking_checks_passed()` into the condition —
noted as the hardening lever; not needed on 1.13.21 given the observation-not-materialization
behavior.

**Rationale**: `any_deps_updated()` is the canonical "fire when a parent updates" primitive and
composes with the existing `on_cron` and the paused sensor. Declaring real deps also makes the
graph visible in the Dagster asset lineage, not just in YAML.

**Alternatives considered**: *A custom sensor that polls materialization events* — rejected: it
would re-implement what `any_deps_updated()` already does and would not share the
`autocond_<name>` toggle. *`AutomationCondition.eager()`* — rejected as the whole condition: eager
bundles missing-handling and scope rules we want to control per-flag; we compose the primitives
ourselves so `on_upstream` and `on_missing` are independent (FR-010).

## R2 — Partitioned `on_upstream` mapping + fallback (FR-007)

**Decision (unattended)**: Map partitioned upstream→downstream one-to-one with Dagster's identity
`TimeWindowPartitionMapping()` (the default for two `DailyPartitionsDefinition`s sharing a start
date), so a today upstream partition drives the today downstream partition. Gate shipping this
behind a build-time check, exactly like the existing `partition_on_cron_supported()` lever: add
`partition_upstream_supported()` returning True on 1.13.21, overridable by
`AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY=1`. When unsupported, **restrict `on_upstream` to
unpartitioned assets**: a daily asset with `on_upstream` is loaded without the upstream condition,
a load-warning names the asset, and the README states the restriction (spec Assumptions "Null
action").

**Rationale**: The spec's assumption pre-authorizes this exact fallback and demands it be stated.
Reusing the established build-time-check + load-warning pattern (R5 of 006) keeps one mechanism for
"a partition path that may not hold on every Dagster."

**Alternatives considered**: *Always restrict to unpartitioned* — rejected: the spec's primary
path is daily→daily and 1.13.21 supports identity mapping. *A non-identity mapping (daily→weekly)*
— explicitly out of scope.

## R3 — Wiring `on_missing` (FR-008/FR-009)

**Decision (unattended)**: `on_missing` contributes
`AutomationCondition.missing() & AutomationCondition.in_latest_time_window()` to the asset's
condition.

- `missing()` is true for a partition that has never materialized; `in_latest_time_window()`
  restricts evaluation to the current partition (today for daily). For an unpartitioned asset
  `in_latest_time_window()` is trivially the single partition, so `missing()` alone governs.
- It never backfills history (older partitions are outside the latest window, FR-008) and never
  re-fires once the partition exists (`missing()` turns false, FR-009 / Acceptance US3 #2).

**Rationale**: These are the exact primitives for "materialize the current partition if it has
never been produced." Composed with `|` alongside `on_upstream`/`on_cron` behind the one sensor,
US3 #3 (both conditions, either fires) is true by construction.

**Alternatives considered**: *`AutomationCondition.eager()`* — rejected (see R1). *Backfilling all
missing partitions* — rejected by the spec clarification (latest only).

## R4 — One composed condition behind one sensor (FR-005/FR-010)

**Decision (unattended)**: Build the asset's automation condition by OR-composing only the
enabled contributions, then AND-ing `~AutomationCondition.in_progress()` so a run in flight is not
re-triggered:

```
parts = []
if asset_schedule: parts.append(on_cron(cron, tz))
if on_upstream and (unpartitioned or partition_upstream_supported()): parts.append(any_deps_updated())
if on_missing: parts.append(missing() & in_latest_time_window())
cond = reduce(|, parts) & ~in_progress()   # None when parts is empty
```

The single per-asset `autocond_<name>` sensor (built by `build_asset_automation_sensor`, STOPPED
by default) is created whenever **any** asset-kind trigger is set — not just `asset_schedule`.
The unchanged sensor name means an asset that already had `asset_schedule` keeps its operator
toggle when `on_upstream`/`on_missing` are added (spec 006 R6 state-preservation).

**Rationale**: One condition + one sensor is the minimal, spec-mandated model ("both conditions
living behind the one `autocond_<name>` sensor"). Composition with `|`/`&`/`~` is first-class in
Dagster's `AutomationCondition`.

**Alternatives considered**: *A separate sensor per trigger kind* — rejected by FR-010 (one
sensor). *A global automation sensor* — rejected: the per-asset STOPPED sensor is what makes new
triggers paused-by-default (spec 006 R4).

## R5 — Cycle & dangling-reference rejection at load (FR-002/FR-003)

**Decision (unattended)**: In `definitions.discover()`, after the `pending_assets` list is built
(asset key → file is already known there), construct the directed graph
`asset_key → [upstream asset keys]` from each agent's `produces.depends_on`. Then:

1. **Dangling ref**: any `depends_on` entry naming a key not produced by any loaded asset ⇒ reject
   that agent, logging a message that names the missing key (FR-002 / Acceptance US4 #3).
2. **Cycle**: run a DFS; every asset on a cycle (direct or transitive) ⇒ reject, logging a message
   that names the assets in the cycle (FR-003 / Acceptance US4 #1).
3. **Cascade**: an asset whose (valid) upstream was itself rejected now has a dangling dep ⇒ also
   rejected, transitively, so no half-wired edge survives.

Rejection = the established **skip-and-log** path (spec 006 FR-010, `RejectAgent`): the offending
assets are skipped and every unrelated agent still loads; rejected assets get **no sensor**, so no
automation runs against a bad graph ("before any automation runs", US4). The UI's `validate`
additionally blocks saving a cycle or dangling ref from the form, so the operator is told
immediately at author time.

**Reconciling with US4 "reloading fails"**: hard-aborting the whole `Definitions` load would take
down every unrelated agent on one bad edge — violating Agent Isolation and the one-bad-file-costs-
only-itself invariant the loader is built on. Skipping the offending assets with a named error
satisfies the observable intent (the mistake is named; no automation runs on it) while preserving
resilience. This deviation from a literal reading of US4 is deliberate and recorded here.

**Rationale**: Matches the existing loader, the constitution, and the acyclic-graph requirement.
Building the graph from `pending_assets` reuses data already collected.

**Alternatives considered**: *Raise from `discover()` on any cycle* — rejected (kills unrelated
agents). *Only validate in the UI* — rejected: FR-002/FR-003 require load-time rejection for
hand-edited files.

## R6 — Upstream handoff env var + read-only file (FR-011/FR-012/FR-012a/FR-013)

**Decision (unattended)**: At op start, before building the launch argv, for **each** key in
`produces.depends_on` the orchestrator:

1. **Resolves the matching partition**: the downstream's `context.partition_key` (daily→daily
   identity, R2); `None` for an unpartitioned downstream.
2. **Queries the upstream's latest materialization** for that partition off the Dagster instance —
   `context.instance.get_latest_materialization_event(AssetKey)` for unpartitioned, or
   `get_event_records(EventRecordsFilter(ASSET_MATERIALIZATION, asset_key, asset_partitions=[p]))`
   taking the newest (FR: "latest" of multiple, edge case). From the materialization metadata it
   reads `output_files`, the spec-007 report fields (status/tokens/cost/turns/files_written/…),
   the materialization timestamp, and the recorded `chain_depth` + `automated` flag (for R7).
3. **Writes one JSON file per upstream** to a per-run handoff dir (`tempfile.mkdtemp` under
   `$AGENTBOX_DATA`, host==container, `--rm`-cleaned like pipes/staging), shape in
   [contracts/upstream-handoff.schema.json](contracts/upstream-handoff.schema.json). When there is
   **no** matching-partition materialization, the file is still written with `materialized: false`
   and null/empty fields (FR-012a).
4. **Mounts the handoff dir read-only** at `/upstreams` (`-v <dir>:/upstreams:ro`, FR-013) and sets
   `AGENTBOX_UPSTREAM_<KEY>=/upstreams/<key>.json` per upstream.

**Env-var key transform**: the asset key is upper-snaked — `/` and `-` → `_`, letters uppercased:
`notes/daily` → `AGENTBOX_UPSTREAM_NOTES_DAILY`, `repo-review/list-commits` →
`AGENTBOX_UPSTREAM_REPO_REVIEW_LIST_COMMITS`. Stated verbatim in the README and pinned by a test.
These names are added to `_launch_env_names` (snapshot) and the mount to `_launch_mounts`.

**Rationale**: Reading the latest materialization event off the instance is the source of truth for
"what the upstream produced" and already carries the spec-007 report metadata and output paths
(built by `build_metadata`). A read-only mount enforces Constitution V/FR-013 at the Docker layer,
not by convention. Reusing the host==container ephemeral-dir pattern avoids any new mount or the
`/tmp`-doesn't-cross-DooD pitfall documented for pipes/staging.

**Alternatives considered**: *Pass the handoff inline via op-config `inputs`* (the existing
`asset.upstream_inputs` scaffold) — rejected as the transport: the container needs a **file** it
can read (FR-012) and the op-config path cannot be populated for Dagster-managed automation runs.
The `inputs` field stays as the captured provenance in the context snapshot; the file is the
launch-time handoff. *One combined JSON for all upstreams* — rejected: FR-011 requires one var
**per** declared upstream.

## R7 — `chain_depth` derivation without tag injection (FR-015)

**Decision (unattended)**: Automation-condition runs are launched by Dagster's daemon; the
orchestrator cannot inject a custom launch tag into them ahead of time. So compute `chain_depth`
**at op start** from the upstream materializations the handoff query (R6) already reads:

```
depths = [m.chain_depth for m in upstream_matches if m.automated]   # manual upstream ⇒ excluded
chain_depth = (max(depths) + 1) if depths else 1
```

- A **root** automated run — schedule- or `on_missing`-initiated, or fired by a **manual** upstream
  — has no automated upstream contributing, so `chain_depth = 1` (FR-015 exactly).
- A downstream fired by an automated upstream carries that upstream's depth + 1 (max across
  upstreams for fan-in safety).
- Each run **records** its own `chain_depth` and an `automated` boolean in `build_metadata`, so its
  own downstreams can read them on their next handoff query. This closes the loop with no tag
  injection.

**Rationale**: The handoff query is already happening; deriving depth from it is free and correct.
Recording depth in the materialization metadata makes it durable and inspectable in Dagster.

**Alternatives considered**: *Inject a `chain_depth` run tag from the launching run* — rejected:
not possible for Dagster-managed automation runs. *Walk the run-launch causation graph via the
instance* — rejected: heavier and less direct than reading the metadata we already write.

## R8 — Governors: settings surface + enforcement (FR-014/FR-016/FR-017/FR-018)

**Decision (unattended)**:

**Settings surface.** Add a `governors:` block to `config/settings.yaml`
(`max_runs_per_hour`, `max_chain_depth`), written by the UI (`settings_store`) and read by the
orchestrator (new `orchestrator/governors.py:load_governors()`). Both sides default to
`max_runs_per_hour=12`, `max_chain_depth=5` when the block/key is absent (the twin defaults, pinned
by a parity test). The Settings page gains a governors card beside Retention;
`POST /api/settings/governors` validates (both positive ints; sane upper bounds) and persists,
preserving other keys — exactly the `write_retention` pattern. This is the same file the prune
job's `retention` block already lives in (no new file, no new mount).

**Enforcement (at op start, both op bodies).**
1. Classify the run: **automated** iff `context.run.tags` carry a Dagster automation/sensor/
   schedule tag (`dagster/auto_materialize`, `.../sensor_name`, `.../schedule_name`); else
   **manual** (launchpad / GraphQL materialize).
2. Compute `chain_depth` (R7). Tag the run with `agentbox/chain_depth` and `agentbox/automated`
   via `context.instance.add_run_tags` for inspection.
3. If **manual** → skip the governors entirely (FR-017) and launch.
4. If **automated**:
   - **Depth**: if `chain_depth > max_chain_depth` → **refuse** (FR-016).
   - **Rate**: count automated runs that **actually launched** in the trailing 60 minutes —
     `get_run_records` filtered to runs created in `[now-60m, now]` carrying both
     `agentbox/automated=1` and `agentbox/launched=1`; if `count >= max_runs_per_hour` → **refuse**
     (FR-014, rolling window).
   - Otherwise tag `agentbox/launched=1` **before** launching (so it counts toward the window) and
     launch.

**Refusal** = log a clear message to the daemon log (`context.log.warning`, naming the agent,
the limit, and the value), emit an `AssetObservation` (asset) / `add_output_metadata` (job) marking
`refused` so the partition is **not** greened, and raise `GovernorRefusal` to end the run. A
refused run is **not** tagged `agentbox/launched`, so it never consumes a per-hour slot (spec
clarification / FR-014). Manual re-triggering of the same agent bypasses the governors and proceeds
(Acceptance US5 #3).

**Rationale**: Enforcing inside the op is the only place with a live Dagster context that runs for
both manual and automated launches and can both read the instance (for the rolling count) and
decline to launch the container. Counting only `launched`-tagged automated runs makes "refused runs
don't consume a slot" true by construction. Reading the *file* (`settings.yaml`) for the live value
keeps the config the single source of truth; only the fallback defaults are duplicated.

**Alternatives considered**: *Enforce in the sensor* — rejected: the automation-condition sensor is
Dagster-managed and not a place to run custom gating. *A separate ledger file for the rolling
window* — rejected: Dagster's run storage already records every run with timestamps and tags; a
second ledger would drift. *Refuse by succeeding-but-not-launching (green partition)* — rejected:
it would falsely mark the partition materialized; an observation + raise leaves it red-with-reason,
which is visible and honest.

**Race note**: the count-then-launch check can, under two near-simultaneous sensor ticks, admit one
extra run past the cap. On a single-host Pi with a daily/upstream cadence this is acceptable and is
documented; a strict lock is out of scope.

## R9 — Schema + form + settings UI (FR-001/FR-018/FR-019/FR-020)

**Decision (unattended)**:
- **Schema** (`ui/schema.py`): add `depends_on` (new `list` field, `block="produces"`, each entry
  validated against `ASSET_KEY_RE`) and `on_upstream` / `on_missing` (bool, `block="triggers"`,
  default false). `validate`: `depends_on` entries must match the asset-key regex; the two trigger
  flags apply **only** when the agent is an asset (mirror of the `asset_schedule` kind rule).
  `SCHEMA_VERSION` 6→7 with `migrate_6_to_7` = identity (additive fields), same posture as
  `migrate_4_to_5`/`5_to_6`. Golden files regenerated with the schema-7 header + commented fields.
- **Form** (`agent-form.js` + `form.html`): FR-019's "Depends-on" card is rendered inside the
  asset card region — a list control for `depends_on` — and the two triggers become toggles in the
  asset card's grid (they are asset-kind, so they belong with the asset). `collect()` omits
  `depends_on`/`on_upstream`/`on_missing` when the asset card is off, mirroring the existing
  asset-card gating. All controls use the shared macros/tokens (Constitution VII).
- **Automation surface** (FR-020): the agents-list schedules/sensors column shows pills for
  `on_upstream`/`on_missing` alongside `asset_schedule`, driven by the lifted flags.
- **Settings** (`settings.js` + `page.html`): a governors card with two number inputs saving via
  `POST /api/settings/governors`, using the shared notice/status pattern.

**Rationale**: This is the minimal extension of the existing schema-driven form and settings page;
no new field type is needed beyond reusing the `list` type for `depends_on`.

**Alternatives considered**: *A standalone Depends-on card outside the asset card* — the spec says
"a Depends-on card"; rendering it within the asset region keeps dependency + asset identity
together and lets the same on/off gating drop all asset-only keys at once. Either placement
satisfies FR-019; the in-asset-card placement is chosen for cohesion.

## R10 — Cross-container duplication discipline (Constitution)

**Decision**: Continue 004–012's discipline. New twins this feature introduces: the governor
defaults (12/5) in `orchestrator/governors.py` and `ui/settings_store.py`, and the
`AGENTBOX_UPSTREAM_<KEY>` transform (orchestrator writer + README/docs). Each is stated once per
package and pinned by a shared-fixture parity test (`test_paths_parity.py` extended). The live
governor **value** is the single `settings.yaml`; only the fallback default is duplicated.

**Rationale**: The two packages ship as separate images with no shared import; a tiny constant +
a pinning test is cheaper and clearer than a shared dependency (established rationale).

---

## Decisions summary

| Question | Decision |
|----------|----------|
| How does `on_upstream` fire? | Asset `deps` + `AutomationCondition.any_deps_updated()`; blocking-check gating via observation-not-materialization (R1) |
| Partitioned upstream mapping? | daily→daily identity `TimeWindowPartitionMapping`; build-time-checked fallback to unpartitioned-only + README (R2) |
| How does `on_missing` fire? | `missing() & in_latest_time_window()` (R3) |
| One sensor for all triggers? | OR-composed condition + one paused `autocond_<name>` sensor, created for any asset-kind trigger (R4) |
| Cycle / dangling handling? | Graph built in `discover()`; skip-and-log the offending assets (cascade), others load; UI blocks author-time (R5) |
| Handoff transport? | One `:ro` JSON file per upstream under `$AGENTBOX_DATA`, `AGENTBOX_UPSTREAM_<KEY>` env var; null/empty file when no materialization (R6) |
| chain_depth propagation? | Derived at op start from upstream materialization metadata (automated depth + 1; else 1); recorded in own metadata (R7) |
| Governor storage + enforcement? | `governors:` block in `settings.yaml`; enforced at op start; refused = log + observation + raise, not `launched`-tagged; manual bypass (R8) |
| Schema / form / settings UI? | `depends_on` list + two trigger bools; schema 6→7; Depends-on card + toggles; Settings governors card (R9) |
| Cross-container twins? | Governor defaults + handoff transform, pinned by parity tests; value lives in `settings.yaml` (R10) |
