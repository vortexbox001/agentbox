---

description: "Task list for feature: Automation Config"
---

# Tasks: Automation Config

**Input**: Design documents from `/specs/005-automation-config/`

**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The plan's Testing section and quickstart's "Automated tests" make `pytest` coverage part of this feature's deliverable (schema/emitter/API + the new `automation_store` in `ui/tests/`; `factory`/`definitions` unit tests with a stubbed launch in `orchestrator/tests/`; a dedicated `scripts/migrate-schedules.py` test). Live schedule/condition firing and reload parity are verified manually via quickstart.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Include exact file paths in descriptions

## Path Conventions

Two packages, each owning its half (plan.md Structure Decision), plus a repo-root script and data dir:
- `orchestrator/` — Dagster code location (`factory.py`, `definitions.py`) + `orchestrator/tests/` (exists from feature 004; `dagster==1.13.21` is installed in `.venv`)
- `ui/` — management UI (`schema.py`, `agents_store.py`, `main.py`, `dagster.py`, new `automation_store.py`, templates, static) + existing `ui/tests/`
- `automation/` — NEW trigger data dir; `scripts/migrate-schedules.py` — NEW one-off; `agents/`, `docker-compose.yml`, `README.md` at repo root
- UI tests run via the project venv: `cd ui && ../.venv/bin/python -m pytest -q`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish a green baseline before the schema and orchestrator changes land.

- [X] T001 Verify the UI test harness runs green before changes: `cd ui && ../.venv/bin/python -m pytest -q` (baseline for the schema/emitter/API tests Phases 2–8 extend)
- [X] T002 Verify the orchestrator test harness runs green: `cd orchestrator && ../.venv/bin/python -m pytest -q` (confirms the `orchestrator/tests/` stubbed-launch fixture from feature 004 is usable for the schedule/sensor tests below)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Remove `schedule` from the agent schema and stand up the shared mount and cron rule. Every user story assumes these. Complete before Phases 3–8.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [X] T003 [P] In `docker-compose.yml`, mount the new `automation/` dir: add `- ./automation:/opt/agentbox/automation:ro` to BOTH `dagster-webserver` and `dagster-daemon`, add `- ./automation:/opt/agentbox/automation` (writable) to the `ui` service, and add `AUTOMATION_DIR: /opt/agentbox/automation` to the `ui` service env (research R1 / contracts automation-format §1)
- [X] T004 [P] Create the `automation/` directory with a committed placeholder (e.g. `automation/.gitkeep`) so the mount target exists before the migration writes `migrated.yaml`
- [X] T005 [P] In `orchestrator/factory.py`, add `is_valid_cron(s) -> bool` (exactly five whitespace-separated fields; reject `@`-macros) — the shared cron rule reused by `build_schedule`/`definitions` (contracts orchestrator-triggers §2; the twin copy lives in the UI, T016)
- [X] T006 In `ui/schema.py`: delete the `SchemaField("schedule", …)` field; rename the `{"id": "schedule", "label": "Schedule", …}` SECTION to `{"id": "status", "label": "Enabled", "group": "runs"}` holding only the `enabled` field; remove `"schedule"` from `ALWAYS_WRITTEN`; simplify the `_is_unset` empty-string branch from `return f.id != "schedule"` to `return True` (with `schedule` gone, an empty string is unset for EVERY field — do NOT write `return False`, which would treat empty strings as real values) and delete the `if "schedule" in agent: _validate_schedule(...)` call; KEEP the five-field cron logic as a reusable helper; set `SCHEMA_VERSION = 3` and append `(3, migrate_2_to_3)` to `MIGRATIONS` where `migrate_2_to_3(data)` pops `schedule` (contracts ui-automation §1–§2 / research R6)
- [X] T007 In `ui/agents_store.py`, at the read/migration site (around the `apply_migrations` call where the file path is known), log a warning naming the file when the parsed file carried a `schedule` key before migration (FR-002); confirm the emitter writes no `schedule` now that the field is gone
- [X] T008 Regenerate `ui/tests/golden/*.yaml` so each carries a `# agentbox-schema: 3` header and no `schedule:` line (the schema change invalidates them; downstream UI tests depend on green goldens)

**Checkpoint**: `schedule` is gone from the schema/emitter/goldens; the `automation/` mount and the shared cron rule exist. User stories can begin.

---

## Phase 3: User Story 1 - Triggering lives in `automation/`, not the agent file (Priority: P1) 🎯 MVP

**Goal**: A job-mode agent with a `cron` entry in `automation/` gets a schedule on that cron; an `on_demand`/absent entry gets none; the agent's own YAML carries no triggering key.

**Independent Test**: Put a `cron` entry for a job-mode agent in `automation/`, reload, confirm `sched_<name>` exists on that cron (paused); switch it to `on_demand: true`, reload, confirm the schedule is gone and the agent still runs by hand; confirm the agent YAML has no triggering key.

### Implementation for User Story 1

- [X] T009 [US1] In `orchestrator/definitions.py`, add `load_automation(glob="/opt/agentbox/automation/*.yaml")` that reads every file (each a `{name → trigger}` map), merges them into one dict, and applies SYNTACTIC validation: duplicate agent key across files → raise naming the agent + files (FR-011); entry with both `cron` and `on_demand` → raise (FR-005); invalid `cron` via `is_valid_cron` → raise naming the entry (FR-009); entry with neither key → treat as `on_demand` (contracts automation-format §2–§3 / research R2). Returns `{name → {"cron": str} | {"on_demand": True}}`
- [X] T010 [US1] In `orchestrator/factory.py`, split `build_job_and_schedule` into `build_job(cfg)` (the existing `@job` named `agent_<name>`, no schedule) and `build_schedule(job, cron)` → `ScheduleDefinition(job=job, cron_schedule=cron, name=f"sched_{cfg['name'].replace('-','_')}")` with NO `default_status` (Dagster default STOPPED = paused; stable name preserves prior on/off — FR-014/FR-021 / contracts orchestrator-triggers §2–§3). `build_schedule` takes the ALREADY-BUILT job object so exactly one `agent_<name>` job exists per agent, shared by the `jobs` list and its schedule (building a second job with the same name would make Dagster reject the `Definitions`). Update the two existing callers of `build_job_and_schedule` in `orchestrator/tests/test_definitions.py` (around lines 91 and 113) to the new `build_job`/`build_schedule` split so `orchestrator` pytest stays green (the T002 baseline)
- [X] T011 [US1] In `orchestrator/definitions.py`, after discovering agents, call `load_automation()`; for each ENABLED job-mode agent (no `produces`) build its job once via `build_job(cfg)`, append it to `jobs`, and — when its name has a `cron` trigger — append `build_schedule(job, cron)` (passing that same job object) to `schedules`; agents with `on_demand`/no entry get no schedule; log a warning naming any agent file that still carries a `schedule` key (do NOT act on it — research R7). Assemble `Definitions(jobs=jobs, schedules=schedules, assets=assets, sensors=sensors)` (sensors list may be empty until US4)
- [X] T012 [P] [US1] In `orchestrator/tests/test_definitions.py`, unit-test (stubbed launch): a job-mode agent with a `cron` entry yields a `ScheduleDefinition` named `sched_<name>` on that cron with paused default status; an `on_demand`/absent entry yields no schedule; two automation files merge into one map; an agent file carrying a stray `schedule` key produces a warning and NO schedule (research R7)
- [X] T013 [P] [US1] In `orchestrator/tests/test_factory.py`, unit-test `build_schedule` names the schedule `sched_<name>`, uses the given cron, and sets no explicit running status; `is_valid_cron` accepts a five-field expression and rejects `@daily` and wrong-arity strings
- [X] T014 [P] [US1] In `ui/tests/test_schema.py`, assert `/api/schema` (and `to_public`) contain NO `schedule` field and NO `schedule` section; `enabled` is present under a Runs-group section and `timeout_seconds`/`max_turns` remain; `apply_migrations({"schedule": "0 7 * * *"}, 2)` drops `schedule`; `SCHEMA_VERSION == 3`
- [X] T015 [P] [US1] In `ui/tests/test_agents_store.py`, assert the emitter writes no `schedule` line, and reading a file that still contains `schedule:` logs a warning naming the file and yields a dict without `schedule` (FR-002)

**Checkpoint**: Triggers are read from `automation/` and job-mode cron → paused schedule; the agent schema/emitter carry no triggering key. MVP deliverable.

---

## Phase 4: User Story 2 - Existing schedules migrate with full parity (Priority: P1)

**Goal**: One idempotent script moves every agent's existing schedule into `automation/migrated.yaml` and strips the key from every agent file; after reload the same schedules exist on the same crons with prior on/off preserved.

**Independent Test**: Run the script on the repo — confirm each non-template agent's cron lands in `migrated.yaml`, no agent YAML (templates included) keeps `schedule`, no template contributes an entry; run again → zero changes; reload → same schedules, same crons, same on/off.

### Implementation for User Story 2

- [X] T016 [US2] Create `scripts/migrate-schedules.py`: for every `agents/*.yaml`, textually remove the `schedule:` line and bump the `# agentbox-schema:` stamp to `3` (preserving all other comments/formatting); for every NON-template file (basename not starting with `_`) whose removed schedule was non-empty, add `‹name›:\n  cron: "‹value›"` to `automation/migrated.yaml`; manual-only (`schedule: ""`) and templates contribute NO entry; make a second run a no-op (contracts automation-format §4 / research R9)
- [X] T017 [P] [US2] Create `ui/tests/test_migrate_schedules.py` (or `scripts/tests/`) driving the script over a fixture agents dir: asserts the `schedule:` line is stripped and the stamp bumped in every file; a non-template agent's cron is written to `migrated.yaml`; a template with a schedule and a manual-only agent produce NO entry; a second invocation changes nothing (SC-002)
- [X] T018 [US2] Run the migration on the real repo: `python3 scripts/migrate-schedules.py`. Verify `automation/migrated.yaml` contains only `repo-librarian-agentbox:\n  cron: "30 2 * * *"`, no `agents/*.yaml` retains `schedule`, and `git status` after a second run is clean (SC-001/SC-002)
- [ ] T019 [US2] Manually verify reload parity per quickstart Scenario 2: after migration, reload the orchestrator and confirm `sched_repo_librarian_agentbox` exists on `30 2 * * *` with its prior on/off state preserved (FR-014/SC-003); record the result in the quickstart run notes

**Checkpoint**: Schedules are migrated losslessly and idempotently; reload parity confirmed.

---

## Phase 5: User Story 3 - Manage triggers from the Automation view (Priority: P2)

**Goal**: A new Automation view lists every non-template agent with its trigger and lets an operator edit it; saving writes `automation/` and reloads Dagster. The agent form's Schedule card is gone; Runs keeps Enabled + Limits (+ Produces).

**Independent Test**: Open `/automation`, see agents with their triggers, change one to a cron and save → the entry is written and the orchestrator reloads with a paused schedule; open the agent form → no Schedule card, Runs shows Enabled/Limits/Produces.

### Implementation for User Story 3

- [X] T020 [US3] Create `ui/automation_store.py`: read/merge `automation/*.yaml`; `per_agent_view()` returns one row per **non-template** agent — INCLUDING disabled ones (a disabled agent is listed so its trigger can be pre-set; it simply won't fire until enabled) — as `{name, harness, mode: "asset" if produces else "job", trigger}`, defaulting missing agents to `{on_demand: True}`; `validate(entries, known_agent_names)` (agent must exist, exactly one trigger, cron via a local `is_valid_cron` twin); `write(entries)` rewrites the canonical `automation/migrated.yaml` (on-demand agents omitted) (contracts ui-automation §3 / research R8)
- [X] T021 [US3] In `ui/main.py`, add `GET /automation` rendering `templates/automation/list.html` via `_shell_context`, `GET /api/automation` returning `automation_store.per_agent_view()`, and `PUT /api/automation` whose body is the FULL desired trigger set — `{"triggers": {"<name>": {"cron": "…"} | {"on_demand": true}, …}}` (whole-file replace, matching how `write` rewrites the canonical file) — that validates, calls `automation_store.write(...)`, then `await dagster.reload()` and returns `{ok, message, reload}` (reuse the existing StorageError/validation-error handlers) (contracts ui-automation §3–§4)
- [X] T022 [P] [US3] Add `ui/templates/automation/list.html` (the agent→trigger table with an inline per-row editor) and an "Automation" nav link in `ui/templates/base.html`
- [X] T023 [P] [US3] Add `ui/static/automation.js`: fetch `GET /api/automation`, render the table, edit a row's trigger (on-demand ↔ cron), and on save `PUT /api/automation`, surfacing the reload outcome with the same banner pattern the agent form uses
- [X] T024 [P] [US3] In `ui/tests/test_automation_store.py`, unit-test merge across files, `per_agent_view` defaulting to on-demand and setting `mode` from `produces`, `validate` accept/reject, and `write` round-trip (write → re-read yields the same triggers)
- [X] T025 [P] [US3] In `ui/tests/test_api.py`, test `GET /api/automation` shape, `PUT /api/automation` writes `migrated.yaml` and triggers a reload (mock `dagster.reload`), `/automation` renders, and the agent form (`/agents/{name}` markup or `/api/schema`) has NO Schedule card while Enabled + Limits remain under Runs (FR-017)

**Checkpoint**: Triggers are editable from the UI with an automatic reload; the agent form is Schedule-free.

---

## Phase 6: User Story 4 - Asset-producing agents are triggered by a cron automation condition (Priority: P2)

**Goal**: An asset-mode agent (declares `produces`) with a `cron` entry gets an `AutomationCondition.on_cron` on its asset plus a paused per-asset sensor — not a `ScheduleDefinition` — and materializes the right partition at the cron time.

**Independent Test**: Add `produces` + a `cron` entry to an agent, reload, confirm an asset with an automation condition (not a schedule) and a paused `autocond_<name>` sensor appear; turn the sensor on and confirm the current-day partition materializes at the tick.

### Implementation for User Story 4

- [X] T026 [US4] In `orchestrator/factory.py`, extend `build_asset(cfg, file, automation_condition=None)` to pass `automation_condition` through to the asset (via `AssetsDefinition.from_op(..., automation_condition=…)`, or the asset-spec API if `from_op` does not accept it on `dagster==1.13.21`), and add `build_asset_automation_sensor(cfg)` → `AutomationConditionSensorDefinition(name=f"autocond_{name}", target=AssetSelection.assets(key), default_status=DefaultSensorStatus.STOPPED)` (contracts orchestrator-triggers §2)
- [X] T027 [US4] In `orchestrator/definitions.py`, for each ENABLED asset-mode agent whose name has a `cron` trigger, build the asset with `AutomationCondition.on_cron(cron)` and append `build_asset_automation_sensor(cfg)` to `sensors`; asset-mode agents with `on_demand`/no entry get a plain asset and no sensor; include `sensors` in `Definitions(...)` (contracts orchestrator-triggers §1)
- [X] T028 [P] [US4] In `orchestrator/tests/test_definitions.py`, unit-test: an asset-mode agent with a `cron` entry produces an asset carrying an automation condition and a `Definitions.sensors` entry `autocond_<name>` with STOPPED default, and NO `ScheduleDefinition` for it; an asset-mode agent with `on_demand`/no entry produces neither (research R4)
- [X] T029 [US4] Null-Action verification (build-time, quickstart §7): confirm `AutomationCondition.on_cron` on a `DailyPartitionsDefinition` root asset materializes the CURRENT day's partition on `dagster==1.13.21`. If it does not, switch that asset's trigger to the documented fallback — `build_schedule_from_partitioned_job(define_asset_job("materialize_<name>", AssetSelection.assets(key), partitions_def=daily))` named `sched_<name>`, STOPPED — and record the switch here and in the plan's Null-Action note (research R5 / contracts orchestrator-triggers §4)

**Checkpoint**: Asset-mode cron becomes an operator-toggleable, paused automation condition targeting the correct partition (or the recorded fallback).

---

## Phase 7: User Story 5 - Deleting an entry leaves the agent runnable, just not triggered (Priority: P2)

**Goal**: Removing an agent's automation entry (or setting it on-demand) removes only its schedule/sensor; the agent stays listed and hand-runnable.

**Independent Test**: Delete an agent's entry, reload, confirm the agent is still present (job or asset), has no schedule/condition, and launches by hand; the Automation view shows it "on demand".

### Implementation for User Story 5

- [X] T030 [P] [US5] In `orchestrator/tests/test_definitions.py`, unit-test that an agent absent from the automation map still appears as its job (`agent_<name>`) or asset with NO schedule and NO automation sensor, and that flipping an entry from `cron` to `on_demand` removes the schedule/sensor while the job/asset remains (FR-020 / Story 5)
- [X] T031 [P] [US5] In `ui/tests/test_automation_store.py`, assert that writing on-demand for an agent removes its `cron` entry from `migrated.yaml` (the agent is simply absent) and never edits any `agents/*.yaml`, and that `per_agent_view` reports it as `{on_demand: True}`

**Checkpoint**: Trigger removal is reversible and never touches the agent definition.

---

## Phase 8: User Story 6 - A bad automation entry is rejected by name (Priority: P3)

**Goal**: An entry naming a non-existent agent fails the reload with a naming message, and the UI refuses to save it; invalid crons are refused at both entry points.

**Independent Test**: Hand-write an entry naming a non-existent agent → reload fails naming the entry+file; try to save the same in the Automation view → refused with a naming message; invalid cron refused at both.

### Implementation for User Story 6

- [X] T032 [US6] In `orchestrator/definitions.py`, add the SEMANTIC unknown-agent check to the load path: build the known-agent-name set from EVERY `agents/*.yaml` `name` (templates and disabled agents included — the file exists, so it is not "unknown"; a disabled agent's entry simply attaches to nothing, per the spec edge case); an automation key not in that set → raise an error naming the entry and its file, FAILING the reload (FR-010 — deliberately stronger than 004's skip-one-file). Do NOT re-implement the dup-key/invalid-cron raises from T009; add a test (T034) asserting they name their offenders (contracts automation-format §3)
- [X] T033 [US6] In `ui/automation_store.py` + `ui/main.py`, make `PUT /api/automation` refuse (HTTP 422, message naming the offender) an entry that names a non-existent agent or carries an invalid cron, before any file is written (FR-009/FR-010 / contracts ui-automation §3)
- [X] T034 [P] [US6] In `orchestrator/tests/test_definitions.py`, unit-test that a dangling entry (unknown agent) raises with a message naming the entry and file, and a duplicate agent key across two files raises naming the agent and both files
- [X] T035 [P] [US6] In `ui/tests/test_api.py`, test `PUT /api/automation` returns 422 naming the offender for an unknown-agent entry and for an invalid cron, and writes nothing in either case

**Checkpoint**: Bad entries are caught by name at both the reload and the UI.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Docs and template hygiene so file format, code, and docs agree (Constitution VI).

- [X] T036 [P] In `README.md`, remove the `schedule` row from the agent key table and add an "Automation" section documenting `automation/` (the name-keyed map, `cron` vs `on_demand`, default-on-demand, one entry per agent) and the fact that new triggers start paused (FR-019)
- [X] T037 [P] Confirm every `agents/_template-*.yaml` carries no `schedule:` line after the migration (T018 strips them); update any lingering schedule-related comment in the templates so their guidance points at `automation/` instead (FR-018)
- [X] T038 [P] Update the module docstrings in `orchestrator/definitions.py` and `orchestrator/factory.py` that describe schedules to reflect that cron comes from `automation/` (Docs Track Reality)
- [ ] T039 Run the full quickstart (`specs/005-automation-config/quickstart.md`) Scenarios 1–7 on the Pi host and the automated suites (`cd ui && ../.venv/bin/python -m pytest -q`; `cd orchestrator && ../.venv/bin/python -m pytest -q`); record pass/fail and the Null-Action outcome (T029)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (removes `schedule` from the schema, adds the mount and cron rule).
- **User Stories (Phases 3–8)**: All depend on Foundational.
  - US1 (P1) is the MVP and should go first — it establishes `load_automation` and `build_schedule` that US4/US5/US6 extend.
  - US2 (P1) depends only on Foundational (the schema-3 stamp) — can run alongside US1.
  - US3 (P2) depends on Foundational; its `per_agent_view` reads the same files US1 writes but the UI half is independent.
  - US4 (P2) extends US1's loader/definitions (asset branch) — start after US1's T009/T011.
  - US5 (P2) is verification over US1/US4 behavior — after those land.
  - US6 (P3) finalizes the rejection paths seeded in US1's loader and US3's API.
- **Polish (Phase 9)**: After the desired stories are complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only. Independently testable.
- **US2 (P1)**: Foundational only. Independently testable (script + repo run).
- **US3 (P2)**: Foundational only for the UI; independently testable via the API/tests.
- **US4 (P2)**: Builds on US1's `load_automation`/`definitions` (asset branch) + feature 004's `build_asset`.
- **US5 (P2)**: Behavioral verification over US1 + US4.
- **US6 (P3)**: Completes the naming-rejection behavior across US1's loader and US3's API.

### Within Each User Story

- Tests marked [P] can run in parallel (distinct files).
- Orchestrator loader/factory before definitions wiring; store before endpoints before UI markup.
- Story complete and its checkpoint green before moving to the next priority.

### Parallel Opportunities

- Foundational: T003, T004, T005 are [P] (compose, dir, factory helper); T006→T007→T008 are sequential in `ui/schema.py`/`agents_store.py`/goldens.
- US1 tests T012–T015 are [P] across `orchestrator/tests` and `ui/tests`.
- US3 UI pieces T022 (template) and T023 (JS) are [P]; T024/T025 tests are [P].
- Polish T036/T037/T038 are [P] (different files).
- With capacity, US2 and US3 can proceed in parallel with US1 once Foundational is done.

---

## Parallel Example: User Story 1

```bash
# After T009–T011 land, run US1's tests together:
Task: "test_definitions.py — job cron→sched_<name> paused; on_demand→none; merge; stray-schedule warning"
Task: "test_factory.py — build_schedule naming + is_valid_cron accept/reject"
Task: "test_schema.py — no schedule field/section; enabled under Runs; migrate 2→3 drops schedule"
Task: "test_agents_store.py — emitter writes no schedule; stray-schedule read warns naming the file"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Phase 1: Setup (green baseline).
2. Phase 2: Foundational (schema loses `schedule`; mount + cron rule) — CRITICAL, blocks everything.
3. Phase 3: US1 — triggers read from `automation/`, job-mode cron → paused schedule.
4. Phase 4: US2 — migrate the real repo losslessly and confirm reload parity.
5. **STOP and VALIDATE**: quickstart Scenarios 1–3 pass; the one existing schedule survives.

### Incremental Delivery

1. Foundational → US1 → US2 = the core move is live and lossless (MVP).
2. Add US3 → triggers editable from the UI with auto-reload.
3. Add US4 → asset-mode cron via automation condition (+ Null-Action check).
4. Add US5 → confirm reversibility; Add US6 → rejection-by-name guardrails.
5. Polish → README/templates/docstrings/quickstart run.

---

## Notes

- [P] = different files, no dependencies.
- The cron rule is intentionally duplicated (orchestrator `is_valid_cron` + UI twin) across the container boundary; T005/T020 must keep them in lockstep and a test pins both (plan Complexity Tracking).
- FR-010 makes an unknown-agent entry FAIL the reload (stronger than 004's skip) — do not soften it to a skip.
- New triggers start paused (FR-021); migrated ones keep prior on/off via stable `sched_<name>` names — never force `default_status=RUNNING`.
- The Null-Action fallback (T029) is expected NOT to fire on `dagster==1.13.21`, but verify against the live UI before closing US4.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
