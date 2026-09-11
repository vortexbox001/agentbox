---

description: "Task list for Explicit Asset/Job Model & Automation Shell Cleanup"
---

# Tasks: Explicit Asset/Job Model & Automation Shell Cleanup

**Input**: Design documents from `/specs/006-explicit-asset-job/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (agent-model.md, orchestrator-model.md, ui-automation-and-shell.md), quickstart.md

**Tests**: Included — the plan's Testing section and all three contracts define an explicit pytest surface (schema, stores, orchestrator routing, migration, UI, consistency greps). Test tasks are therefore first-class here.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. US1 and US2 are both P1 and ship together (the model plus its lossless trigger carry-over); US3 and US4 are P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are included in every task

## Path Conventions

Two packages plus a repo-root one-off: `orchestrator/`, `ui/` (with `ui/tests/`), and `scripts/`.
Agent config lives in `agents/`. Paths below are repo-root-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working environment; no scaffolding is needed (existing project).

- [X] T001 Confirm branch `006-explicit-asset-job` is checked out and the UI venv is present: `cd ui && ../.venv/bin/python -m pytest -q` runs (baseline green on schema 3) before changes, and the orchestrator suite also baselines green (`cd orchestrator && ../.venv/bin/python -m pytest -q` — `dagster 1.13.21` is in the same `.venv`); if `.venv/` is missing, rebuild per `CLAUDE.local.md` (`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r ui/requirements.txt`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The data model both P1 stories build on — the `job` flag, the `triggers` block, schema v4 migration, validation, and the reader/emitter machinery. Every user story reads and writes this format.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 In `ui/schema.py`, add the `job` boolean SchemaField (Job group, `type=bool`, applies to all harnesses; NOT in `ALWAYS_WRITTEN`) and two cron SchemaFields `asset_schedule` and `job_schedule` with `block="triggers"` (mirroring how `asset`/`partition` use `block="produces"`), per contracts/agent-model.md §1–§2.
- [X] T003 In `ui/schema.py`, bump `SCHEMA_VERSION = 4`, add `migrate_3_to_4(data)` (no `produces` ⇒ set `data["job"]=True`; has `produces` ⇒ leave `job` unset; never fabricate `triggers`), and append `(4, migrate_3_to_4)` to `MIGRATIONS`, per contracts/agent-model.md §4.
- [X] T004 In `ui/schema.py` `validate(...)`, add the four rules from contracts/agent-model.md §3: (1) nature invariant — neither asset flag nor `job: true` ⇒ error keyed to `job` "the agent must be an asset, a job, or both."; (2) produces-required-when-asset (existing empty-`asset` check fires when asset flag on); (3) cron shape on `asset_schedule`/`job_schedule` (five-field, no `@`-macros, reuse existing cron validator / `croniter.is_valid`); (4) kind/schedule agreement — schedule set for a kind that is off names the offending field.
- [X] T005 In `ui/agents_store.py`, extend the **reader** (`read_agent`) to lift the `triggers` block into flat managed `asset_schedule`/`job_schedule` fields (never routed to "Unmanaged"; absent/non-mapping block ⇒ both unset), exactly as `produces` is lifted, per contracts/agent-model.md §2/§6.
- [X] T006 In `ui/agents_store.py`, extend the **emitter** (`emit_yaml`): add `_triggers_block_lines` that re-nests the two flat fields into a `# --- Triggers ---` block (real block when ≥1 schedule set, fully commented-out opt-in block when both unset, a schedule whose kind is off omitted), and emit the `job:` line as a real line when the agent has a job / commented placeholder otherwise, in the section order given in contracts/agent-model.md §5 (Produces → Triggers → Job group).
- [X] T007 [P] In `ui/tests/test_schema.py`, add tests for the new `job` field and `triggers` cron fields in `/api/schema`-shaped output, `migrate_3_to_4` (both branches, no `triggers` fabricated), and the four `validate` rules (nature invariant, produces-required, cron shape, kind/schedule agreement).
- [X] T008 [P] In `ui/tests/test_agents_store.py`, add round-trip tests: emitter writes `job:` and the `# --- Triggers ---` block (real, commented, and kind-omitted variants); reader lifts `triggers` back to flat fields; byte-determinism preserved.
- [X] T009 Regenerate the golden files in `ui/tests/golden/` (`api.yaml`, `claude-code.yaml`, `codex.yaml`, `pi.yaml`) for schema 4 — new header stamp `# agentbox-schema: 4`, the `job:` line, and the `# --- Triggers ---` block — and confirm the golden test asserts byte-equality (depends on T006).

**Checkpoint**: Schema v4 + store round-trip green. User story implementation can now begin.

---

## Phase 3: User Story 1 - Declare an agent as an asset, a job, or both (Priority: P1) 🎯 MVP

**Goal**: An agent's nature (asset / job / both) is an explicit, operator-chosen property; the orchestrator builds the right Dagster definitions for each kind, and the form presents independent Asset and Job cards with the at-least-one rule.

**Independent Test**: Tick only the Asset card → orchestrator shows a materializable asset and no `agent_<name>` job. Tick only the Job card → a launchable `agent_<name>` plain op job and no asset. Tick both → the asset has a materializing job `agent_<name>` whose run records a materialization. Untick both → save rejected with the nature message.

### Implementation for User Story 1

- [X] T010 [US1] In `orchestrator/factory.py`, add `build_materializing_job(cfg, asset_def)` → `dagster.define_asset_job(name="agent_<name>", selection=AssetSelection.assets(asset_def))`, reusing the asset that already wraps `make_run_op(cfg)` (no re-implemented launch op); keep `build_asset` and `build_job` unchanged, per contracts/orchestrator-model.md §2.
- [X] T011 [US1] In `orchestrator/definitions.py` `discover`, replace produces-presence inference with two explicit flags — `is_asset` (valid `produces` block) and `is_job` (`cfg.get("job") is True`) — and route the three kinds: asset-only ⇒ `build_asset` only (no job); job-only ⇒ `build_job`; both ⇒ `build_asset` + `build_materializing_job`; an enabled agent with neither flag is rejected by name and skipped (a `RejectAgent`), per contracts/orchestrator-model.md §1–§2.
- [X] T012 [P] [US1] In `ui/static/agent-form.js`, render the **Asset card** (checkbox "make agent an asset" gating the Produces fields + the `asset_schedule` cron field) and the **Job card** (checkbox "create agent job" gating `job: true` + the `job_schedule` cron field), independent, with a client-side hint when neither is ticked (server remains authority), per contracts/ui-automation-and-shell.md §1.
- [X] T013 [P] [US1] In `ui/templates/agents/form.html`, ensure the mounts the two cards render into exist (asset/job card containers + the two schedule fields); no new server-rendered fields required beyond mounts (contracts/ui-automation-and-shell.md §1).
- [X] T014 [P] [US1] In `orchestrator/tests/test_definitions.py` (and `orchestrator/tests/test_factory.py` for `build_materializing_job`), using the existing `stub_launch` fixture in `orchestrator/tests/conftest.py`, assert kind routing: asset-only → asset present + no `agent_<name>` job (except the FR-015 fallback case — see T018); job-only → plain job + no asset; both → asset + `agent_<name>` materializing job whose selection is the asset; neither-flag agent rejected by name while other agents still load (contracts/orchestrator-model.md §8).
- [X] T015 [P] [US1] In `ui/tests/test_api.py`, assert `/api/schema` includes the `job` field and the `triggers` block fields, and that the agent form renders the Asset card + Job card mounts.

**Checkpoint**: All three kinds build correctly and the form authors them; US1 is independently testable.

---

## Phase 4: User Story 2 - Each agent carries its own trigger(s) (Priority: P1)

**Goal**: Triggering lives on the agent's `triggers:` block; the orchestrator reads triggers only from there (asset_schedule → on_cron + sensor, job_schedule → schedule); the legacy `automation/` store, `on_demand`, and the 005 migration script are retired; existing 005 crons carry over losslessly with on/off state preserved.

**Independent Test**: On a repo carrying 005 `automation/migrated.yaml`, run the carry-over; confirm `categorize-commits` expresses `job_schedule: "30 2 * * *"` (+ `job: true`) and `list-commits-pi-kimi` expresses `asset_schedule: "20 17 * * *"`, the `automation/` dir and `on_demand` are gone, and the orchestrator reloads with the identical set of live triggers (same names, crons, and paused/running state).

### Implementation for User Story 2

- [X] T016 [US2] In `orchestrator/definitions.py`, read triggering only from `cfg["triggers"]`: `asset_schedule` (asset kind) → attach `AutomationCondition.on_cron` via `build_asset`'s `cron` arg + register paused per-asset sensor `autocond_<name>` (`DefaultSensorStatus.STOPPED`); `job_schedule` (job kind) → register `build_schedule(job_def, cron)` named `sched_<name>` on the agent's job object; absent/blank ⇒ no trigger, per contracts/orchestrator-model.md §3/§6.
- [X] T017 [US2] In `orchestrator/definitions.py`, remove the entire legacy automation path — `load_automation`, `_normalize_trigger`, `AUTOMATION_GLOB`, `RejectAutomation`, the unknown-agent/dup-key automation checks, and every `on_demand` reference — and rewrite the module header to describe the per-agent `triggers:` model; keep the `RejectAgent` skip-one-file behavior (contracts/orchestrator-model.md §5, FR-010/SC-008).
- [X] T018 [US2] In `orchestrator/factory.py`, implement the partition Null-Action fallback (FR-015): primary `on_cron` on `DailyPartitionsDefinition`; when a build-time check shows it cannot target the correct partition, fall back to a partition-filling `ScheduleDefinition` named `sched_<name>` on the asset's materializing job (defining that job for an asset-only agent if needed), emit a load-time warning log naming agent+asset, and set a `fallback` marker surfaced via the automation API; ensure `build_schedule` works against either job object (contracts/orchestrator-model.md §4).
- [X] T019 [P] [US2] Create `scripts/migrate-automation-to-triggers.py`: read `automation/migrated.yaml`; for each `name: {cron}` open `agents/<name>.yaml`, decide kind by `produces` presence, write the cron onto `triggers.asset_schedule` (asset) or `triggers.job_schedule` (job, also set `job: true`), bump the file's `# agentbox-schema:` stamp to 4, then remove the `automation/` directory; idempotent (re-run "nothing to do"); missing named agents printed and skipped (contracts/orchestrator-model.md §7).
- [X] T020 [P] [US2] In `docker-compose.yml`, remove the three `./automation` mounts (webserver, daemon, ui) and the `AUTOMATION_DIR` env (contracts/orchestrator-model.md §5).
- [X] T021 [P] [US2] Update the agent templates `agents/_template-claude-code.yaml`, `agents/_template-pi.yaml`, `agents/_template-codex.yaml`, `agents/_template-api.yaml`, `agents/_template-repo-librarian.yaml`: add the `# --- Triggers ---` block and the `job:` flag, drop any `automation` note, stamp schema 4 (data-model.md §Triggers block).
- [X] T022 [US2] Run `python3 scripts/migrate-automation-to-triggers.py` to carry over the two live crons: `agents/categorize-commits.yaml` gains `triggers: { job_schedule: "30 2 * * *" }` + `job: true`; `agents/list-commits-pi-kimi.yaml` gains `triggers: { asset_schedule: "20 17 * * *" }`; both stamped schema 4; `automation/` removed (depends on T019; quickstart §2).
- [X] T023 [P] [US2] Create `ui/tests/test_migrate_automation.py` (over a fixture repo): asserts per-kind write (asset-mode cron → asset_schedule, job-mode cron → job_schedule + `job: true`), schema stamp bump, `automation/` removal, and idempotency; delete the retired `ui/tests/test_migrate_schedules.py` and `scripts/migrate-schedules.py` (contracts/orchestrator-model.md §7).
- [X] T024 [P] [US2] In `orchestrator/tests/test_definitions.py`, add trigger-routing tests (stubbed launch): `asset_schedule` → `on_cron` on the asset + a paused `autocond_<name>` sensor; `job_schedule` → a paused `sched_<name>` schedule on the agent's job; `sched_<name>`/`autocond_<name>` names unchanged (state-preservation guard); a timezone assertion that `cron_timezone()` is applied to both `ScheduleDefinition.execution_timezone` and `AutomationCondition.on_cron` (FR-016); an import/grep-level assertion that no `automation/` reader and no `on_demand` remain (contracts/orchestrator-model.md §8).
- [X] T024b [P] [US2] Retire/rewrite `orchestrator/tests/test_automation.py`, which drives the legacy `definitions.discover(agents_glob, automation_glob)` + `automation/` store removed in T017. Either delete it (moving its still-valid naming/rejection assertions into `test_definitions.py`) or rewrite it to the per-agent `triggers:` model; after this task no orchestrator test references `automation_glob`, `load_automation`, or `on_demand` (FR-010/SC-008).

**Checkpoint**: Triggers load from the agent files, the legacy path is gone, and the carry-over is lossless — US1 + US2 (the P1 MVP) are complete.

---

## Phase 5: User Story 3 - Manage triggers on the reworked Automation page (Priority: P2)

**Goal**: The Automation page shows per agent exactly the schedule rows its kind entitles it to (asset, job, or both grouped as one unit), each editable on-demand ↔ cron independently; saving writes onto the agent definition and reloads Dagster.

**Independent Test**: Open `/automation`; an asset-only agent shows only an asset row, a job-only agent only a job row, a both-kind agent shows both grouped. Toggle one row on-demand → cron and save; the change is written to that agent's `triggers:` block, Dagster reloads, the trigger is live, and the other row (for a both-kind agent) is unchanged.

### Implementation for User Story 3

- [X] T025 [US3] In `ui/automation_store.py`, rework `per_agent_view` to read `triggers` off each agent file and emit per-kind rows (`kinds` = `["asset"]` / `["job"]` / `["asset","job"]`; a `schedules` entry per applicable kind with `cron` null when on-demand and a `fallback` marker on the asset row); repoint `write` to edit `agents/*.yaml` via `agents_store` (the `triggers` block) and drop the `migrated.yaml` writer; keep the five-field cron rule (contracts/ui-automation-and-shell.md §2, data-model.md §Automation page row).
- [X] T026 [US3] In `ui/main.py`, update `GET /api/automation` to return `{"agents":[{name,harness,enabled,kinds,schedules:[{kind,cron,fallback}]}]}` (templates `_`-prefixed excluded) and `PUT /api/automation` to accept `{"triggers":{"<name>":{"asset_schedule"?,"job_schedule"?}}}`, validate cron shape + kind agreement (400 `{"error":"validation","fields":{…}}` naming agent+field), write via `agents_store`, reload Dagster, and return the shared `{ok,message,reload}` shape (contracts/ui-automation-and-shell.md §2).
- [X] T027 [US3] In `ui/static/automation.js`, render one visual group per agent with its asset/job rows grouped (both-kind as one unit); each row = a trigger `<select class="ax-select">` (on-demand / cron) + cron input + reserved warning slot; enhance every row `<select>` via `dropdown.enhanceSelects` (incl. dynamically added rows); use `shell.showStatus` for save/reload/error notices; render the partition-`fallback` marker with tooltip on the asset row (contracts/ui-automation-and-shell.md §2).
- [X] T028 [P] [US3] In `ui/templates/automation/list.html`, remove the bespoke `#ax-automation-banner`/`.ax-banner` save notice and provide the container for the grouped rows (contracts/ui-automation-and-shell.md §5).
- [X] T029 [P] [US3] In `ui/tests/test_automation_store.py`, assert `per_agent_view` yields per-kind rows off `triggers` (asset-only/job-only/both) and that `write` edits `agents/*.yaml` (not `automation/`), leaving the untouched schedule unchanged.
- [X] T030 [P] [US3] In `ui/tests/test_api.py`, assert the Automation page renders grouped rows per kind and that `GET/PUT /api/automation` round-trips including per-kind validation and writing back to `agents/*.yaml`.

**Checkpoint**: Operators can view and edit per-agent triggers through the UI; US3 is independently testable.

---

## Phase 6: User Story 4 - Consistent, reusable UI shell and components (Priority: P2)

**Goal**: One fixed shell (fixed sidebar + pinned top bar, responsive to phone width), one shared dropdown component everywhere, one shared notice pattern everywhere, and reserved cron-warning space so it never shifts the layout.

**Independent Test**: Scroll a long page — sidebar and top bar stay pinned; shrink to ~400px — nothing overlaps or hides content. `grep -rn "<select" ui/templates ui/static` shows only the shared-component path. The Automation save notice and the agent-save notice are visually identical. Typing a cron value that toggles the shape warning does not shift the row.

### Implementation for User Story 4

- [X] T031 [US4] In `ui/static/app.css`, implement the fixed shell: `.ax-app` `height:100dvh`; `.ax-sidebar` own scroll (`overflow-y:auto`) fixed by the grid column; `.ax-topbar` `position:sticky; top:0`; `.ax-content` the sole scroller (`overflow-y:auto; flex:1`); one `@media (max-width:640px)` collapsing to a single column with a non-overlapping sidebar strip and sticky top bar; plus reserved `.ax-field-error` one-line `min-height` and the asset/job card + grouped-row styles (contracts/ui-automation-and-shell.md §3/§5).
- [X] T032 [US4] In `ui/templates/base.html`, apply the shell markup tweaks for the fixed layout (`.ax-app` grid, `.ax-sidebar`, sticky `.ax-topbar`, scrolling `.ax-content`) with no structural nav change (contracts/ui-automation-and-shell.md §3).
- [X] T033 [P] [US4] Add the consistency grep test (`ui/tests/test_ui_consistency.py`, or fold into `ui/tests/test_api.py`): assert no raw `<select>` remains outside the shared `dropdown.js`/`ax-select` path and no `.ax-banner` is used as a save notice, across `ui/templates` and `ui/static` (SC-004/SC-005, contracts/ui-automation-and-shell.md §4/§6).

**Checkpoint**: Shell, dropdown, and notice are shared and consistent app-wide; the warning space is reserved.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs-track-reality and end-to-end validation across all stories.

- [X] T034 [P] Update `README.md`: replace the Automation/`automation/` section with the per-agent triggers model (asset/job/both + `triggers:` block); refresh the key-table rows to include `job` and `triggers` (quickstart §9, Constitution VI).
- [X] T035 [P] Update `CLAUDE.local.md`: correct the debugging notes that reference `automation/` to the per-agent `triggers:` model.
- [X] T036 Run **both** suites green from the shared `.venv` (carries `dagster 1.13.21`): the UI suite (`cd ui && ../.venv/bin/python -m pytest -q`) and the orchestrator suite (`cd orchestrator && ../.venv/bin/python -m pytest -q`) — covering schema, stores, api, migration, the consistency grep, and kind/trigger routing — and confirm `grep -rn "on_demand\|automation/" agents/ orchestrator/ ui/ scripts/ docker-compose.yml` returns no matches (SC-008; quickstart §1–§2).
- [X] T037 Execute quickstart validation against live Dagster (`docker compose up -d`): three-kind creation (§3), per-agent trigger load (§4), carry-over parity + on/off preservation (§5), Automation rows/grouping/independence (§6), shared shell/dropdown/notice + no-layout-shift (§7), and the partition Null-Action targeting check (§8) that gates which FR-015 path ships.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (schema + store are the shared data model).
- **User Stories (Phase 3–6)**: All depend on Foundational.
  - US1 (P1) and US2 (P1) are the MVP and are tightly related (US2's trigger routing sits in the same `definitions.py`/`factory.py` that US1 touches) — sequence US1 → US2 to avoid same-file churn.
  - US3 (P2) depends on US1 + US2 (reads the model and the `triggers` block).
  - US4 (P2) is largely independent CSS/shell + a grep test; its consistency test (T033) is strongest after US3's `automation.js` rework lands.
- **Polish (Phase 7)**: Depends on all desired stories.

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependency on other stories.
- **US2 (P1)**: After Foundational. Shares `definitions.py`/`factory.py` with US1 — do US1 first.
- **US3 (P2)**: After US1 + US2 (needs the model + `triggers` block + automation API rework).
- **US4 (P2)**: After Foundational; grep test best after US3.

### Within Each User Story

- Orchestrator kind routing (US1) before trigger routing (US2) — same files.
- `automation_store` (US3 T025) before `main.py` API (T026) before `automation.js` (T027).
- Tests marked [P] for a story run alongside that story's implementation once their target files exist.

### Parallel Opportunities

- Foundational: T007 and T008 (different test files) run in parallel after their targets (T002–T006) land; T009 golden regen after T006.
- US1: T012 (agent-form.js) and T013 (form.html) and the test tasks T014/T015 are all different files — parallelizable once T010/T011 exist.
- US2: T019 (migration script), T020 (docker-compose), T021 (templates), T023/T024 (tests) touch distinct files — parallelizable; T022 (run migration) depends on T019.
- Polish: T034 and T035 are different files — parallel.

---

## Parallel Example: User Story 2

```bash
# Distinct files — can proceed together once definitions.py/factory.py routing exists:
Task: "Create scripts/migrate-automation-to-triggers.py"                 # T019
Task: "Remove ./automation mounts + AUTOMATION_DIR from docker-compose.yml"  # T020
Task: "Add # --- Triggers --- + job: to the five agent templates"        # T021
Task: "Create ui/tests/test_migrate_automation.py; delete test_migrate_schedules.py" # T023
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1: Setup.
2. Phase 2: Foundational (schema v4 + store round-trip) — CRITICAL.
3. Phase 3: US1 — the explicit asset/job/both model + form cards.
4. Phase 4: US2 — per-agent triggers, legacy removal, lossless carry-over.
5. **STOP and VALIDATE**: quickstart §2–§5 and §8; this is the safe-to-adopt MVP.

### Incremental Delivery

1. Foundational → schema/store ready.
2. + US1 → three kinds build and author (demo).
3. + US2 → triggers on the agent, carry-over lossless (MVP demo).
4. + US3 → manage triggers in the Automation UI.
5. + US4 → consistent shell/dropdown/notice.

---

## Notes

- [P] = different files, no dependencies. Same-file tasks (all of `definitions.py`/`factory.py` across US1/US2) are intentionally sequential.
- [Story] labels trace each task to its user story.
- Verify tests fail (or the golden diff is expected) before implementing where practical; commit after each task or logical group.
- The two cross-boundary duplications (asset-key regex; five-field cron rule) stay stated once per package and pinned by shared-fixture tests (plan Complexity Tracking) — do not introduce a shared import.
