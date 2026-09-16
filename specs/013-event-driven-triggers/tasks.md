---

description: "Task list for Event-Driven Triggers — Asset Dependency Graph"
---

# Tasks: Event-Driven Triggers — Asset Dependency Graph

**Input**: Design documents from `/specs/013-event-driven-triggers/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED — the plan's Testing section, the quickstart, and every contract name concrete
automated test files per package (`orchestrator/tests`, `ui/tests`), so test tasks are generated
per story. Live-Dagster end-to-end behavior is validated by the quickstart (Phase 8), matching the
006/008/012 posture.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
independently. US1 + US2 (both P1) are the MVP; US3/US4 (P2) and US5 (P3) are increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: US1–US5 (maps to the five user stories in spec.md).
- Every task lists an exact file path.

## Path Conventions

Single tree, two service roots: `orchestrator/` and `ui/`, plus `examples/` and `README.md`. Paths
are repo-root relative. No compose change — the per-run handoff dir reuses the existing
`$AGENTBOX_DATA` host==container mount.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Version bump and shipped-example documentation the schema, form, and settings work
build on.

- [ ] T001 Bump `SCHEMA_VERSION` 6 → 7 and add `migrate_6_to_7(data)` (identity — the three new fields are additive) plus its `(7, migrate_6_to_7)` entry to `MIGRATIONS` in `ui/schema.py` (contracts/agent-model.md §6; same posture as `migrate_5_to_6`).
- [ ] T002 [P] Add commented `depends_on:` under `produces:` and `on_upstream:` / `on_missing:` under `triggers:` (with the field help text) and re-stamp the `# agentbox-schema:` header to 7 in `examples/config/agents/_template-api.yaml`, `_template-claude-code.yaml`, `_template-codex.yaml`, `_template-pi.yaml`, `_template-repo-librarian.yaml` (contracts/agent-model.md §7).
- [ ] T003 [P] Add a commented `governors:` block (`max_runs_per_hour: 12`, `max_chain_depth: 5`) documenting the two limits + defaults to `examples/config/settings.yaml`, beside the existing `retention:` block (data-model.md "Instance settings document").

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema/store substrate that lets `depends_on` + the two triggers be authored,
validated, emitted, and loaded. Every user story that touches agent config (US1/US3 triggers,
US4 `depends_on`) depends on this phase.

**⚠️ CRITICAL**: No user-story config work can begin until this phase is complete. (US5's governors
are settings-only and do not depend on Phase 2, but ship last by priority.)

- [ ] T004 Add the three `SchemaField` defs to `FIELDS` in `ui/schema.py` — `depends_on` (`section`/`block`="produces", `type`="list", harnesses `_ALL`) and `on_upstream` / `on_missing` (`section`/`block`="triggers", `type`="bool", default `False`, choices `[True, False]`, harnesses `_ALL`), with the help text verbatim from contracts/agent-model.md §2. `to_public()` picks them up via `FIELDS`; `ALWAYS_WRITTEN` unchanged.
- [ ] T005 Add validation to `ui/schema.py:validate` — `depends_on` must be a list of strings each matching `ASSET_KEY_RE` (else name the offending entry) and requires an asset; `on_upstream`/`on_missing` must be bools and apply only when `is_asset` (mirror of the `asset_schedule` kind rule), per contracts/agent-model.md §3.
- [ ] T006 [P] Extend `ui/tests/test_schema.py` — the three fields present in `FIELDS`/`to_public`; `migrate_6_to_7` is identity and a schema-6 file loads with no noise + re-stamps to 7 on save; validation cases (asset-key entries, depends_on-needs-asset, trigger-applies-only-to-asset).
- [ ] T007 Lift/emit `produces.depends_on` (as a YAML sequence, beside `asset`/`partition`/`checks`) and `triggers.on_upstream` / `on_missing` (as booleans, beside `asset_schedule`/`job_schedule`) — each with its help comment — in `ui/agents_store.py`; unknown keys preserved (contracts/agent-model.md §4).
- [ ] T008 [P] Extend `ui/tests/test_agents_store.py` — emit/lift the three fields, read→write round-trip is stable, unknown keys preserved.
- [ ] T009 Add a load-time `depends_on` shape backstop to `orchestrator/factory.py` (list of asset-key strings; `RejectAgent` naming the file on a malformed entry — the structural twin of the UI guard, no `croniter`-style extras), and extend `orchestrator/tests/test_factory.py` to cover it (contracts/agent-model.md §5).

**Checkpoint**: The three fields author, validate, emit, round-trip, and pass the orchestrator shape
backstop — config plumbing ready for the triggers and the graph.

---

## Phase 3: User Story 1 - Fire a downstream asset when its upstream materializes (Priority: P1) 🎯 MVP

**Goal**: A downstream asset with `depends_on: [notes/daily]` + `on_upstream: true` materializes on
its own when its upstream materializes and passes its blocking checks — an explicit declared graph
edge, no folder-watching, no manual action, new triggers paused by default.

**Independent Test**: Configure A → B with B's `on_upstream: true`, turn on B's `autocond_<name>`
sensor, materialize A's today partition; confirm B materializes for the matching partition with no
manual action against B, and does not fire while the sensor is off or while A's blocking check fails.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [ ] T010 [P] [US1] Extend `orchestrator/tests/test_factory.py` — `depends_on` → asset `deps` (checkless `from_op` deps + checked `AssetSpec` deps with identity daily→daily `TimeWindowPartitionMapping`); `compose_automation_condition` yields `on_cron | any_deps_updated() & ~in_progress()` for an `on_upstream` asset; `build_asset_automation_sensor` is created (STOPPED, unchanged name) for an `on_upstream`-only asset; the `partition_upstream_supported()==False` fallback drops a daily asset's upstream condition and logs a warning naming the asset — all against `DagsterInstance.ephemeral()`.
- [ ] T011 [P] [US1] Extend `ui/tests/test_api.py` — `/api/schema` includes `depends_on` + `on_upstream`; the agent form renders the Depends-on card and the `on_upstream` toggle inside the asset card.

### Implementation for User Story 1

- [ ] T012 [US1] Add `partition_upstream_supported()` to `orchestrator/factory.py` (returns `True` on Dagster 1.13.21, overridable via `AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY=1`), mirroring the existing `partition_on_cron_supported()` build-time-check lever (research R2).
- [ ] T013 [US1] Thread a `depends_on` param through `build_asset(cfg, file, cron, depends_on)` and `_build_checked_asset(...)` in `orchestrator/factory.py` and attach one Dagster dep per entry — checkless path `AssetsDefinition.from_op(..., deps=[AssetKey(k.split('/'))])`; checked path `AssetSpec(deps=[AssetDep(AssetKey(k.split('/')), partition_mapping=TimeWindowPartitionMapping())])` — identity daily→daily mapping applied only when `partition_upstream_supported()`; deps are non-arg (op signature unchanged) (contracts/orchestrator-model.md §1).
- [ ] T014 [US1] Add `compose_automation_condition(cfg, *, cron, on_upstream, on_missing, partitioned)` to `orchestrator/factory.py` OR-composing the enabled contributions — `on_cron(cron, tz)` and (when `on_upstream and (not partitioned or partition_upstream_supported())`) `any_deps_updated()` — then AND `~in_progress()`; return `None` when empty. Attach it where `on_cron` is today (`automation_conditions_by_output_name` on the checkless path, `AssetSpec(automation_condition=…)` on the checked path). (The `on_missing` branch is added in US3/T022.) (contracts/orchestrator-model.md §2, research R1/R4.)
- [ ] T015 [US1] Make `build_asset_automation_sensor` (`autocond_<name>`, STOPPED, unchanged name) be created whenever ANY asset-kind trigger (`asset_schedule` | `on_upstream` | `on_missing`) is set — update the sensor-creation gate in `orchestrator/factory.py` and its call site so the operator's existing toggle is preserved (research R4).
- [ ] T016 [US1] In `orchestrator/definitions.py:discover()`, read `produces.depends_on` and `triggers.on_upstream`/`on_missing`, thread them through the `pending_assets` tuple, pass `depends_on` into `build_asset`, and build the sensor for any asset with any asset-kind trigger (contracts/orchestrator-model.md §2).
- [ ] T017 [US1] Add the "Depends-on" list control + the `on_upstream` toggle into the asset-card region in `ui/static/agent-form.js` + `ui/templates/agents/form.html`; add all three new keys to `CARD_SECTIONS` / the asset-card grid and to the removal-on-toggle-off list so `collect()` omits them when the agent is not an asset (contracts/ui-settings-and-form.md §1).
- [ ] T018 [US1] Show an `on_upstream` pill in the schedules/sensors column and recognize it in the "scheduled" tab narrowing — `ui/templates/agents/list.html` + `ui/static/agents-list.js` (FR-020, contracts/ui-settings-and-form.md §2).

**Checkpoint**: A declared `depends_on` + `on_upstream` fires the downstream on the upstream's
materialization (blocking-check-gated, paused-by-default) — the MVP graph edge works.

---

## Phase 4: User Story 2 - Hand upstream outputs to the downstream container (Priority: P1)

**Goal**: When a downstream fires, its container receives one `AGENTBOX_UPSTREAM_<KEY>` env var per
declared upstream, each pointing at a read-only JSON handoff file listing that upstream's latest
matching-partition output paths, report metadata, and materialization time — or a null/empty "no
materialization" file when there is none.

**Independent Test**: With A → B fired by A's materialization, inspect B's container env and confirm
`AGENTBOX_UPSTREAM_NOTES_DAILY` is a readable, read-only JSON file listing A's outputs/report/time
for the matching partition; a second declared upstream with no materialization yields a present var
pointing at a `materialized: false` file.

### Tests for User Story 2 ⚠️ (write first, ensure they fail)

- [ ] T019 [P] [US2] Extend `orchestrator/tests/test_factory.py` — the handoff builder's env-var naming (`upper_snake`: `notes/daily → AGENTBOX_UPSTREAM_NOTES_DAILY`), matching-partition selection, latest-of-many, and the `materialized: false` null/empty "no materialization" file (FR-012a); the launch snapshot carries the `:ro /upstreams` mount and the `AGENTBOX_UPSTREAM_*` env names — against `DagsterInstance.ephemeral()`, validated against `contracts/upstream-handoff.schema.json`.
- [ ] T020 [P] [US2] Extend `orchestrator/tests/test_run_capture.py` — `asset.upstream_inputs` in the context snapshot is populated from the handoff data (no longer hardcoded `None`), per R6.

### Implementation for User Story 2

- [ ] T021 [US2] Add `build_upstream_handoff(cfg, context, handoff_dir) -> dict[str, str]` to `orchestrator/factory.py`: for each `produces.depends_on` key, resolve the matching partition (`context.partition_key` when partitioned, else `None`), query the latest matching materialization (partitioned: `get_event_records(EventRecordsFilter(ASSET_MATERIALIZATION, asset_key, asset_partitions=[p]), limit=1, ascending=False)`; unpartitioned: `get_latest_materialization_event(AssetKey)`), read `output_files`/`report`/`materialized_at`/`chain_depth`/`automated` off the materialization metadata, write one `<key-slug>.json` per upstream (`materialized: false` + null/empty when none, FR-012a) `chmod 0644`, and return `{f"AGENTBOX_UPSTREAM_{upper_snake(k)}": f"/upstreams/{key-slug}.json"}` (contracts/orchestrator-model.md §3, upstream-handoff.schema.json).
- [ ] T022 [US2] Wire the handoff into both op bodies in `orchestrator/factory.py` — create `handoff_dir = tempfile.mkdtemp(...)` under the host==container staging root, `chmod 0777`, `--rm`-clean in the op's `finally` (like pipes/staging); add `-v <handoff_dir>:/upstreams:ro` in `_build_agent_cmd` and merge the returned env vars into the launch; add the `AGENTBOX_UPSTREAM_*` names to `_launch_env_names` and the `{source, target:/upstreams, mode:ro}` mount to `_launch_mounts` (contracts/orchestrator-model.md §3, FR-013).
- [ ] T023 [US2] Populate `asset.upstream_inputs` in the context snapshot from the handoff data in `orchestrator/factory.py` / `orchestrator/run_capture.py` (the provenance scaffold; the file remains the launch-time transport) (research R6).

**Checkpoint**: A downstream run sees a read-only handoff file per declared upstream and can read
exactly what each upstream produced — the graph is useful, not merely a firing mechanism.

---

## Phase 5: User Story 3 - Materialize a partition that has never been produced (Priority: P2)

**Goal**: An asset with `on_missing: true` materializes its current/latest expected partition
(today for daily; the single partition when unpartitioned) when it has never been produced — no
history backfill, no re-fire once it exists — behind the same paused `autocond_<name>` sensor,
composing with `on_upstream`.

**Independent Test**: Give an asset `on_missing: true`, turn on its sensor for a never-produced
partition, confirm it materializes that partition on its own and does not re-fire once it exists;
with both triggers on, either condition materializes it behind the one sensor.

### Tests for User Story 3 ⚠️ (write first, ensure they fail)

- [ ] T024 [P] [US3] Extend `orchestrator/tests/test_factory.py` — `compose_automation_condition` for an `on_missing`-only asset yields `missing() & in_latest_time_window() & ~in_progress()`; an asset with both `on_upstream` and `on_missing` OR-composes both behind one `autocond_<name>` sensor (US3 #3) — against `DagsterInstance.ephemeral()`.
- [ ] T025 [P] [US3] Extend `ui/tests/test_api.py` / `ui/tests/test_schema.py` — `on_missing` in `/api/schema`, the toggle renders in the asset card, validation applies-only-to-asset.

### Implementation for User Story 3

- [ ] T026 [US3] Add the `on_missing` branch — `AutomationCondition.missing() & AutomationCondition.in_latest_time_window()` — to `compose_automation_condition` in `orchestrator/factory.py`, OR-composed alongside `on_cron`/`any_deps_updated` behind the one sensor (research R3; never backfills history, never re-fires once the partition exists).
- [ ] T027 [US3] Add the `on_missing` toggle to the asset-card grid (and the removal-on-toggle-off list) in `ui/static/agent-form.js` + `ui/templates/agents/form.html`, and an `on_missing` pill in `ui/templates/agents/list.html` + `ui/static/agents-list.js` (FR-020, contracts/ui-settings-and-form.md §1/§2).

**Checkpoint**: `on_missing` fills a never-produced latest partition on its own and composes with
`on_upstream` behind the single sensor.

---

## Phase 6: User Story 4 - Reject dependency cycles at load (Priority: P2)

**Goal**: A `depends_on` graph with a cycle (direct or transitive) or a reference to a non-existent
asset is rejected at load, naming the offending assets/keys, before any automation runs — while
every unrelated agent still loads (skip-and-log, per the resilient loader).

**Independent Test**: Wire B → C → B, reload, and confirm both assets are rejected with a daemon-log
message naming them; a dangling `depends_on` key rejects that agent naming the key; an acyclic graph
loads cleanly and unrelated agents are unaffected.

### Tests for User Story 4 ⚠️ (write first, ensure they fail)

- [ ] T028 [P] [US4] Extend `orchestrator/tests/test_definitions.py` — a B↔C cycle rejects both, naming them; a `depends_on` naming a non-existent key rejects that agent, naming the key; the cascade rejects dependents of a rejected asset; unrelated agents still load; an acyclic all-keys-present graph loads unchanged (SC-004 / US4 #1–#3).
- [ ] T029 [P] [US4] Extend `ui/tests/test_schema.py` — the best-effort author-time guard blocks saving a `depends_on` that names an unknown asset key or forms a cycle against the known agent set.

### Implementation for User Story 4

- [ ] T030 [US4] In `orchestrator/definitions.py:discover()`, after `pending_assets` is collected, build `graph = {asset_key: [depends_on keys]}` and `produced = set(asset keys)`; reject any asset with a dangling `depends_on` key (`log.warning` naming the missing key), reject every asset on a cycle (DFS, `log.warning` naming the assets joined by `" -> "`), and cascade to a fixpoint (an asset whose upstream was rejected now dangles ⇒ reject too); add all rejected assets to `rejected_files` so their asset def, sensor, and job are skipped — no automation runs against a bad graph (contracts/orchestrator-model.md §4, research R5).
- [ ] T031 [US4] Add the best-effort author-time cross-check to `ui/schema.py:validate` (or the form save path) — using the known set of agents, block saving a `depends_on` that names a non-existent asset key or forms a cycle, with a clear message (the load-time check remains the authority) (contracts/agent-model.md §3).

**Checkpoint**: Cycles and dangling refs are caught at load with the offending assets/keys named,
before any automation runs, and the operator is warned at author time.

---

## Phase 7: User Story 5 - Cap automated run rate and chain depth (Priority: P3)

**Goal**: `config/settings.yaml` governors `max_runs_per_hour` (default 12, rolling 60-min window)
and `max_chain_depth` (default 5) bound automated chaining; every automated run carries a
`chain_depth`; a run that would breach either limit is refused, logged, and skipped without
consuming a per-hour slot; manual runs bypass both; both are editable on the Settings page.

**Independent Test**: With `max_runs_per_hour: 2`, the third automated run in a rolling 60-min window
is refused and logged (no slot consumed); with `max_chain_depth: 5`, the sixth link in an automated
chain is refused; a manual run of the same agent proceeds; Settings edits persist to `settings.yaml`.

### Tests for User Story 5 ⚠️ (write first, ensure they fail)

- [ ] T032 [P] [US5] Add `orchestrator/tests/test_governors.py` — `load_governors()` returns the `settings.yaml` values, falling back per-key to `DEFAULT_GOVERNORS` when the file/block/key is absent or invalid.
- [ ] T033 [P] [US5] Extend `orchestrator/tests/test_factory.py` — depth refusal (`chain_depth > max_chain_depth`), rolling-window refusal (`count >= max_runs_per_hour`), a refused run leaves its partition unmaterialized and is NOT tagged `agentbox/launched` (no slot consumed), manual runs bypass both, and `chain_depth` derivation (root=1, automated-upstream depth+1, manual-upstream ⇒ 1) — against `DagsterInstance.ephemeral()`.
- [ ] T034 [P] [US5] Extend `ui/tests/test_settings.py` — `read_governors` default when absent; `validate_governors` rejects non-int/non-positive/over-cap; `write_governors` preserves the `retention` block + unknown keys; `POST /api/settings/governors` round-trips + 400s on bad input; the Settings page renders the governors card.

### Implementation for User Story 5

- [ ] T035 [US5] Create `orchestrator/governors.py` — `DEFAULT_GOVERNORS = {"max_runs_per_hour": 12, "max_chain_depth": 5}` and `load_governors()` reading the `governors` block from `paths.SETTINGS_FILE` with per-key fallback to the defaults when absent/invalid (contracts/orchestrator-model.md §6, the twin of `ui/settings_store`).
- [ ] T036 [US5] Add `chain_depth` derivation + recording to both op bodies in `orchestrator/factory.py` — classify the run as automated iff its Dagster run tags carry an automation/sensor/schedule tag; `depths = [m.chain_depth for m in upstream_matches if m.automated]; chain_depth = max(depths)+1 if depths else 1` (reusing the handoff query from T021); `add_run_tags({"agentbox/chain_depth": str(chain_depth), "agentbox/automated": "1"/"0"})` and record `chain_depth`/`automated` in `build_metadata` so downstreams read them via the handoff query (contracts/orchestrator-model.md §5, research R7).
- [ ] T037 [US5] Add `governor_gate(context, cfg, chain_depth, automated)` + `refuse(context, cfg, reason)` + a `GovernorRefusal` exception to `orchestrator/factory.py`, called at op start (both bodies) after T036: manual → return (bypass, FR-017); if `chain_depth > max_chain_depth` → refuse; else count launched automated runs in the trailing 60 min (`get_run_records(RunsFilter(created_after=now-60m, tags={"agentbox/automated":"1","agentbox/launched":"1"}))`) and if `>= max_runs_per_hour` → refuse; otherwise `add_run_tags({"agentbox/launched":"1"})` before launch. `refuse` = `log.warning` naming agent/limit/value + `AssetObservation`/`add_output_metadata({"refused": reason})` (partition not greened) + `raise GovernorRefusal` (no `launched` tag ⇒ no slot consumed) (contracts/orchestrator-model.md §6, research R8).
- [ ] T038 [US5] Add `DEFAULT_GOVERNORS = {"max_runs_per_hour": 12, "max_chain_depth": 5}`, `class GovernorError(ValueError)`, and `read_governors()` / `validate_governors(...)` (each int ≥ 1 and ≤ a sane cap) / `write_governors(...)` (preserve every other key, like `write_retention`) to `ui/settings_store.py` (contracts/ui-settings-and-form.md §5).
- [ ] T039 [US5] Add `GET` page context (`governors = settings_store.read_governors()`) and `POST /api/settings/governors` (validate → persist → 200 `{"governors": {...}}` / 400 `{"error":"validation", ...}`; log `event=governors_updated`; no Dagster reload) to `ui/main.py` (contracts/ui-settings-and-form.md §4).
- [ ] T040 [US5] Add the governors card (id `#ax-governors-card`) beside the retention card in `ui/templates/settings/page.html` from the shared `card` + `text_input` (type number, min 1) + `button` macros, and add `initGovernors()` (mirrors `initRetention`) to `ui/static/settings.js` — read current values from page context, save via `POST /api/settings/governors`, reflect the response via the shared status/notice (contracts/ui-settings-and-form.md §3).

**Checkpoint**: The governors bound the rate and depth of automated chains (refuse-log-skip, no slot
for refusals), manual runs bypass, and both persist from the Settings page.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T041 [P] Extend `orchestrator/tests/test_paths_parity.py` — pin `orchestrator/governors.DEFAULT_GOVERNORS == ui/settings_store.DEFAULT_GOVERNORS == {"max_runs_per_hour": 12, "max_chain_depth": 5}` and the `AGENTBOX_UPSTREAM_<KEY>` upper-snake transform to its documented form (research R10).
- [ ] T042 [P] Document in `README.md`: `produces.depends_on`; `triggers.on_upstream` / `on_missing`; the `AGENTBOX_UPSTREAM_<KEY>` env var + read-only handoff file (with the key transform stated verbatim); the two governors and their defaults; and the partitioned-`on_upstream` unpartitioned-only fallback (FR-021, quickstart §7).
- [ ] T043 [P] Regenerate `ui/tests/golden/*.yaml` with the `# agentbox-schema: 7` header + the new commented fields, and extend `ui/tests/test_conformance.py` for the new-field golden coverage.
- [ ] T044 Run the design-system + docs hygiene gates (`ui/tests/test_conformance.py`, `test_ui_consistency.py`, `test_design_system_sync.py`, `test_docs_layout.py`) and fix any literal-color / inline-style / raw-`<select>` / CSS-sync / docs-layout violations across the new form (Depends-on card + toggles) and Settings (governors card) templates.
- [ ] T045 Execute the `quickstart.md` §1–§7 scenarios end-to-end against live Dagster and confirm SC-001..SC-006 (firing, handoff read-back, blocking-check gating, `on_missing`, cycle/dangling rejection, governors, and the partitioned-`on_upstream` build-time check + fallback).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup (schema-version bump) — BLOCKS the config-authoring
  stories (US1/US3/US4).
- **User Stories (Phase 3–7)**:
  - **US1 (P1)** and **US2 (P1)** are the MVP core; US2's handoff builder reads the same upstream
    materializations US1's deps create, and both wire into the op body, so US2 lands right after US1.
  - **US3 (P2)** extends US1's `compose_automation_condition` (adds the `on_missing` branch) and the
    US1 form card — best after US1.
  - **US4 (P2)** builds on Phase 2's `depends_on` parsing; independent of US1's condition/handoff.
  - **US5 (P3)** is largely independent (settings + governor gate); its `chain_depth` derivation
    (T036) reuses US2's handoff query (T021), so it follows US2.
- **Polish (Phase 8)**: after the desired stories are complete (T041 parity needs US5's governors;
  T043 golden regen needs Phase 2's fields; T045 quickstart needs all five stories).

### Within Each User Story

- Tests are written first and must fail before implementation.
- `partition_upstream_supported()` (T012) precedes the deps + condition wiring (T013–T014).
- `compose_automation_condition` (T014, US1) is extended by the `on_missing` branch (T026, US3) —
  same function, sequential, not `[P]`.
- The handoff builder (T021) precedes both its op-body wiring (T022) and US5's `chain_depth`
  derivation (T036), which reuses its upstream-materialization read.
- Design-system controls use only shared macros/tokens (Constitution VII).

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T006, T008 (tests, distinct files) in parallel; T004→T005 sequential (same file).
- US1: the two test tasks T010/T011 in parallel; orchestrator (T012–T016) and UI (T017–T018) tracks
  proceed largely in parallel once tests exist.
- US2: T019/T020 (tests) in parallel; T021 before T022/T023.
- US5: T032/T033/T034 (tests) in parallel; T035 (governors reader) and T038 (settings_store) in
  parallel; T036→T037 sequential (same op bodies).
- Across teams: US4 (load-time graph) can be built concurrently with US1/US2/US3; US5 (governors)
  can be built concurrently with everything once Phase 2 lands.

---

## Parallel Example: User Story 5

```bash
# Tests first, in parallel (distinct files):
Task: "orchestrator/tests/test_governors.py — load + per-key defaults"
Task: "orchestrator/tests/test_factory.py — depth/rate refusal, no-slot, manual bypass, chain_depth"
Task: "ui/tests/test_settings.py — read/validate/write governors + POST round-trip + 400s"

# Then the two readers/stores, in parallel (distinct files):
Task: "orchestrator/governors.py — DEFAULT_GOVERNORS + load_governors()"
Task: "ui/settings_store.py — read/validate/write_governors + DEFAULT_GOVERNORS"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Phase 1: Setup (schema bump + example docs).
2. Phase 2: Foundational (schema fields + validation + emitter + shape backstop).
3. Phase 3: US1 (deps + `on_upstream` condition + sensor-for-any-trigger + form card).
4. Phase 4: US2 (read-only handoff files + env vars + `:ro` mount).
5. **STOP and VALIDATE**: wire A → B, confirm B fires on A's materialization and reads the handoff.

### Incremental Delivery

1. Setup + Foundational → the three fields author/validate/emit/load.
2. US1 → declared upstream fires the downstream (MVP graph edge).
3. US2 → the downstream reads what each upstream produced (handoff).
4. US3 → `on_missing` fills never-produced latest partitions.
5. US4 → cycles / dangling refs rejected at load, named.
6. US5 → governors bound automated rate + chain depth; Settings edits persist.

---

## Notes

- [P] = different files, no dependency on incomplete tasks.
- The dependency graph is an **explicit declared edge** (`produces.depends_on`) — there is no
  change-watching path anywhere (FR-001).
- All asset-kind triggers (`asset_schedule`, `on_upstream`, `on_missing`) OR-compose into ONE
  `AutomationCondition` behind the ONE paused `autocond_<name>` sensor; new triggers start paused.
- Blocking-check gating is by construction — a failed blocking check records an `AssetObservation`,
  not a materialization, so `any_deps_updated()` never fires the downstream (no extra code, FR-006).
- The handoff is mounted **read-only** (`:ro`) — one `AGENTBOX_UPSTREAM_<KEY>` file per declared
  upstream, always present (null/empty when no materialization, FR-012a).
- Governors bound automated runs only; refused runs are logged + skipped and never consume a
  per-hour slot; manual runs bypass both (FR-014/FR-016/FR-017).
- Cycle/dangling rejection follows the resilient **skip-and-log** loader: the offending assets (and
  their dependents) are skipped and named; every unrelated agent still loads (research R5).
- Cross-container twins (governor defaults 12/5, the `AGENTBOX_UPSTREAM_<KEY>` transform) are each
  stated once per package and pinned by a parity test; the live governor value is `settings.yaml`.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
