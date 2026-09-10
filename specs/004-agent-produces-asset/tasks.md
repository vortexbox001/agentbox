---

description: "Task list for feature: Agent Produces Asset"
---

# Tasks: Agent Produces Asset

**Input**: Design documents from `/specs/004-agent-produces-asset/`

**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The plan's Testing section and quickstart's "Automated checks" make `pytest` coverage part of this feature's deliverable (schema/emitter/API in `ui/tests/`; factory/definitions unit tests with a stubbed launch). Live materialization is verified manually via quickstart.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Two packages, each owning its half (plan.md Structure Decision):
- `orchestrator/` — Dagster code location (`factory.py`, `definitions.py`) + new `orchestrator/tests/`
- `ui/` — management UI (`schema.py`, `agents_store.py`) + existing `ui/tests/`
- `agents/` — YAML definitions and templates; `docker-compose.yml`, `README.md` at repo root
- UI tests run via the project venv: `cd ui && ../.venv/bin/python -m pytest -q`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding for the orchestrator half (the UI half already has `ui/tests/`).

- [X] T001 Verify the UI test harness runs green before changes: `cd ui && ../.venv/bin/python -m pytest -q` (establishes the schema/emitter baseline that Phases 4–6 will extend)
- [X] T002 Create `orchestrator/tests/` with `__init__.py` and `conftest.py` providing a stubbed-launch fixture (monkeypatches the container-launch call in `orchestrator/factory.py` so `make_run_op`/`build_asset`/`definitions` can be unit-tested without `docker run`). NOTE: `dagster` is already installed in `.venv` (1.13.21, verified importable) — the test-interpreter blocker is resolved; do not re-install. `AssetsDefinition.from_op(op, keys_by_output_name={"result": key}, partitions_def=...)` was smoke-tested and preserves the op's `run_<name>` step name, so the T008 Null Action guard is not expected to fire.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting scaffolding that multiple user stories build on. Complete before Phases 3–6.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [X] T003 [P] Add the read-only outputs mount `- /data/outputs:/data/outputs:ro` to BOTH the `dagster-webserver` and `dagster-daemon` services in `docker-compose.yml` (contract §8 / research R7 — required for the op's before/after snapshot to read `output_dir`)
- [X] T004 [P] In `orchestrator/factory.py` add the shared asset-key regex constant `ASSET_KEY_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"`, a `validate_asset_key(cfg, path)` helper, and a `RejectAgent(Exception)` type that carries the offending file name (used by US1 `build_asset` and US4 load-time rejection — research R6)
- [X] T005 In `ui/schema.py` bump `SCHEMA_VERSION` from 1 to 2 and add `(2, migrate_1_to_2)` to `MIGRATIONS`, where `migrate_1_to_2` is the identity function (schema-1 files have no `produces`; nothing to transform — contract schema-and-yaml §1, underpins US2 SC-005 and US3)

**Checkpoint**: Outputs mount, shared asset-key validation primitives, and the schema-2 migration all in place.

---

## Phase 3: User Story 1 - Declare an agent's output as a tracked asset (Priority: P1) 🎯 MVP

**Goal**: An agent with a `produces` block appears in the orchestrator as a Dagster asset (daily-partitioned when declared) that materializes via the SAME container launch and records per-run metadata pointing at existing output files.

**Independent Test**: Add `produces: {asset: repo-review/agentbox, partition: daily}` to an agent, reload, confirm an asset with a daily partition (and no bare job) appears; materialize and confirm the same `run_<name>` step launches, the output stays in place with no copy, and metadata carries `output_files`, `transcript`, `run_stamp`, `session_id`, `harness`, `model`, `partition`.

### Implementation for User Story 1

- [X] T006 [US1] In `orchestrator/factory.py`, extend `make_run_op(cfg)` (keeping its `run_{name}` name, FR-010): snapshot `cfg["output_dir"]` as `{path: (mtime, size)}` before launch (empty dict if the dir is absent), snapshot again after the container exits and the transcript is written, and compute `output_files` = new-or-mtime-changed paths within the run window (contract §2 / research R4)
- [X] T007 [US1] In `orchestrator/factory.py`, give `make_run_op` one nominal output (value `None`) and, just before returning, attach `context.add_output_metadata({...})` with `output_files`, `transcript`, `run_stamp` (`AGENTBOX_RUN_STAMP`), `session_id` (`AGENTBOX_SESSION_ID`), `harness` (`cfg.harness`), `model` (`cfg.model`), and `partition` only when `context.has_partition_key` — leaving the dict open-ended for later token/cost fields (data-model Materialization record; FR-008/FR-008a/FR-008b/FR-009)
- [X] T008 [US1] In `orchestrator/factory.py`, add `build_asset(cfg)` that calls `validate_asset_key`, builds `key = AssetKey(cfg["produces"]["asset"].split("/"))`, sets `partitions_def = DailyPartitionsDefinition(start_date="2026-09-09")` when `partition == "daily"` else `None`, and wraps the SAME op object via `AssetsDefinition.from_op(make_run_op(cfg), keys_by_output_name={"result": key}, partitions_def=partitions_def)` — the op is NOT re-implemented and `docker run` is not duplicated (Null Action / contract §3 / research R1–R2). If `from_op` cannot wrap the op without changing the launch, STOP and report per the Null Action.
- [X] T009 [US1] In `orchestrator/definitions.py`, route each enabled agent: `"produces" in cfg` → `build_asset(cfg)` appended to `assets`, else `build_job_and_schedule(cfg)` as today; assemble `Definitions(jobs=jobs, schedules=schedules, assets=assets)` (contract §6)
- [X] T010 [P] [US1] In `orchestrator/tests/test_factory.py`, unit-test (stubbed launch): `build_asset` yields an `AssetsDefinition` whose key equals the split asset path and whose compute step is named `run_<name>` (FR-010); `partition: daily` attaches a `DailyPartitionsDefinition(start_date="2026-09-09")` and `none`/omitted attaches none; the partition key is NEVER injected into the launch command/mounts/`output_dir` (FR-008b); the before/after snapshot yields the correct `output_files` (new file, mtime-changed file, and empty-when-nothing-written cases)
- [X] T011 [P] [US1] In `orchestrator/tests/test_definitions.py`, unit-test that an agent with `produces` becomes an asset (present in `Definitions.assets`, no bare job) and one without stays a job named `agent_<name>` (contract §1/§6)

**Checkpoint**: Asset-mode representation, shared launch, and metadata are functional and unit-tested. MVP deliverable.

---

## Phase 4: User Story 2 - Reverting to job-mode leaves nothing else changed (Priority: P1)

**Goal**: Removing `produces` returns the agent to a job named `agent_<name>` with identical behavior; agent files that never had `produces` load with zero warnings and zero migration noise.

**Independent Test**: Take an asset-mode agent, remove `produces`, reload → it is `agent_<name>` again with identical launch/output/schedule; load the full current agent set (none declaring `produces`) → zero warnings, zero migration-noise.

### Implementation for User Story 2

- [X] T012 [US2] In `orchestrator/factory.py`, confirm the job-mode path is untouched by US1: the op's new nominal output and `add_output_metadata` are harmless when the op runs inside the existing `@job` wrapper (nothing consumes the output) — job-mode launch, output location, and schedule are byte-for-byte as before (research R3/R8; FR-004/FR-018)
- [X] T013 [P] [US2] In `orchestrator/tests/test_definitions.py`, unit-test reversibility (SC-004): the SAME cfg with `produces` present → asset; with `produces` removed → job `agent_<name>` and no asset, with no other observable difference in the built job (op name/launch args unchanged)
- [X] T014 [P] [US2] In `ui/tests/test_schema.py`, test the schema-2 migration is identity (SC-005): a schema-1 agent dict (no `produces`) passes through `MIGRATIONS` unchanged and loads with no warnings/migration messages; `SCHEMA_VERSION == 2`

**Checkpoint**: Job↔asset is proven reversible and backward-compatible; existing files load noise-free.

---

## Phase 5: User Story 3 - Create an asset-producing agent from the management UI (Priority: P2)

**Goal**: The agent form gains a "Produces" card under Runs; saving writes a nested `produces:` block (one comment per field) into the Runs section; reopening shows the same values; leaving it empty writes no block.

**Independent Test**: Create an agent in the UI with the Produces fields filled → the YAML has a commented `produces:` block in the Runs section; reopen → values round-trip; leave empty → no `produces` block, stays a job.

### Implementation for User Story 3

- [X] T015 [US3] In `ui/schema.py`, add the section `{"id": "produces", "label": "Produces", "group": "runs"}` and the two `SchemaField`s `asset` (string, `pattern=ASSET_KEY_RE`, help text verbatim) and `partition` (enum, `choices=["none","daily"]`, `default="none"`, help text verbatim), both applying to all harnesses (`_ALL`) and marked as belonging to the `produces` block; keep `produces` OUT of `ALWAYS_WRITTEN` so an empty asset emits a commented block (contract schema-and-yaml §2)
- [X] T016 [US3] In `ui/schema.py`, ensure `to_public()`/`applicable_fields` expose the `produces` section, both fields (with `pattern`/`choices`/`help`), `schema_version: 2`, and include `asset`/`partition` in every harness's field list (contract schema-and-yaml §5)
- [X] T017 [US3] In `ui/agents_store.py`, make `read_agent` lift a `produces:` mapping from the file into the flat `asset`/`partition` fields so the form shows them and they count as *managed* (never routed to "Unmanaged") — contract schema-and-yaml §3 (read)
- [X] T018 [US3] In `ui/agents_store.py`, make `emit_yaml` write the two flat fields back as a nested `produces:` block in the Runs section with one help-text comment per field; when `asset` is unset emit the whole block commented-out (opt-in, matching templates); guarantee byte-stable round-trip emit→load→read→emit (contract schema-and-yaml §3 write / FR-017 / SC-007)
- [X] T019 [P] [US3] Regenerate the four golden files `ui/tests/golden/{api,claude-code,codex,pi}.yaml`: header becomes `# agentbox-schema: 2` and a commented `produces` block appears in the Runs section (values of existing fields unchanged) — contract schema-and-yaml §7
- [X] T020 [P] [US3] Add a commented-out `produces` block to the Runs section of each template: `agents/_template-claude-code.yaml`, `agents/_template-pi.yaml`, `agents/_template-codex.yaml`, `agents/_template-api.yaml`, `agents/_template-repo-librarian.yaml` (FR-016)
- [X] T021 [P] [US3] Add `produces.asset` and `produces.partition` rows to the key table in `README.md`, derived verbatim from the schema help text (schema stays authoritative — FR-015 / Constitution VI)
- [X] T022 [P] [US3] In `ui/tests/test_schema.py`, test the `produces` section and both fields are present with correct `pattern`/`choices`/`help`/`default` and public shape (contract schema-and-yaml §2/§5)
- [X] T023 [P] [US3] In `ui/tests/test_agents_store.py`, test the nested block round-trips (emit→load→emit byte-stable), is placed in the Runs section, carries one comment per field, and is emitted commented-out when `asset` is empty (FR-017/SC-007)
- [X] T024 [P] [US3] In `ui/tests/test_api.py`, test `/api/schema` carries the `produces` section/fields with `schema_version: 2`, and the rendered agent form shows a "Produces" card under the Runs column (FR-013)

**Checkpoint**: Operators can author, save, and round-trip an asset declaration entirely from the UI.

---

## Phase 6: User Story 4 - Invalid asset keys are rejected with a helpful message (Priority: P2)

**Goal**: Both the UI (before save) and the orchestrator (at load) reject invalid asset keys; the orchestrator's message names the offending file; two enabled agents sharing an asset key have their conflicting files rejected by name while all others load.

**Independent Test**: Enter `Bad Key` in the UI → rejected before save with a reason on the asset field; hand-write `produces: {asset: "Bad Key"}` into a file and reload → that file rejected with a message naming it, others still load; give two enabled agents the same key → both rejected by name, others load.

### Implementation for User Story 4

- [X] T025 [US4] In `orchestrator/definitions.py`, wrap per-file building in a try/except that catches `RejectAgent` (invalid asset key, empty `produces`, bad `partition`) and logs a message NAMING the offending file, then skips only that file — all others still load (contract §4 / FR-012); message form e.g. `agents/foo.yaml: invalid produces.asset "Bad Key" — must match <regex>`
- [X] T026 [US4] In `orchestrator/definitions.py`, after per-file validation, collect asset keys across enabled/valid asset agents and reject ALL files sharing a key with a message naming them, loading everything else (contract §5 / FR-019); message form e.g. `asset key "repo-review/agentbox" declared by agents/a.yaml, agents/b.yaml — all rejected`
- [X] T027 [US4] In `ui/schema.py` `validate`, enforce per-field: if `asset` is set it must match `ASSET_KEY_RE` (else field error on `asset`); `partition` must be `none`/`daily`; a `produces` present in the source with no `asset` is an empty declaration → error on `asset` ("an asset declaration must name an asset") — contract schema-and-yaml §4 / FR-011
- [X] T028 [P] [US4] In `orchestrator/tests/test_definitions.py`, test that an invalid `produces.asset` rejects only that file with a message naming it (others load), and that two enabled agents with the same asset key are both rejected by name while others load (FR-012/FR-019/SC-006)
- [X] T029 [P] [US4] In `ui/tests/test_schema.py`, test `validate` rejects a bad asset key (field error on `asset`), rejects an empty `produces` declaration, and accepts a valid key/partition (FR-011)
- [X] T030 [P] [US4] Add a shared accept/reject fixture list and a test (in `ui/tests/test_schema.py` and mirrored in `orchestrator/tests/test_factory.py`) asserting the UI's `ASSET_KEY_RE` and the orchestrator's `ASSET_KEY_RE` accept/reject the SAME fixtures, so the two deliberately-duplicated regexes cannot drift (research R6 / Constitution VI)

**Checkpoint**: Bad and conflicting declarations are caught at both entry points; the two regex copies are pinned in agreement.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across both packages.

- [X] T031 Run the full UI suite `cd ui && ../.venv/bin/python -m pytest -q` and the orchestrator suite (`../.venv/bin/python -m pytest orchestrator/tests -q` or equivalent) — all green
- [ ] T032 Execute `specs/004-agent-produces-asset/quickstart.md` Scenarios 1–4 against the live Dagster UI (`docker compose build && docker compose up -d`), confirming SC-001..SC-007 (asset appears with partition, metadata complete, no duplicate output, reversibility, zero migration noise, invalid-key naming, UI round-trip)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (outputs mount, shared asset-key primitives, schema-2 migration).
- **User Stories (Phase 3–6)**: All depend on Foundational.
  - US1 (P1) is the MVP and is the natural first story (orchestrator asset representation).
  - US2 (P1) builds directly on US1's factory/definitions changes (reversibility of the same routing).
  - US3 (P2) is UI-side; depends on the schema-2 migration (T005) and the shared regex (T004) but is otherwise independent of US1/US2 and can proceed in parallel with them once Foundational is done.
  - US4 (P2) depends on `build_asset`/routing (US1) for the orchestrator half and the `produces` fields (US3, T015) for the UI-validate half.
- **Polish (Phase 7)**: Depends on all targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependency on other stories.
- **US2 (P1)**: After US1 (verifies/uses US1's factory + definitions routing).
- **US3 (P2)**: After Foundational (T004, T005). Independent of US1/US2 — the UI half.
- **US4 (P2)**: After US1 (orchestrator rejection needs `build_asset`/routing) and after US3 T015 (UI validate needs the `asset` field). Its two halves (T025/T026 orchestrator, T027 UI) are otherwise independent.

### Within Each User Story

- `orchestrator/factory.py` edits (T006→T007→T008) are sequential (same file, building on each other); `definitions.py` (T009) follows the factory.
- Tests marked [P] touch distinct test files and can run in parallel once their production code exists.
- `ui/schema.py` edits (T015, T016) precede the store edits (T017, T018) which precede golden regeneration (T019).

### Parallel Opportunities

- Foundational T003 (compose) and T004 (factory regex) are [P] (different files); T005 (schema) is also independent but is the same-file base for US3.
- US1 tests T010/T011 are [P] (different test files) after the code lands.
- US3 T019/T020/T021 (golden, templates, README) are [P]; test tasks T022/T023/T024 are [P] across different test files.
- US4 tests T028/T029/T030 are [P].
- Once Foundational is done, the UI story (US3) and the orchestrator stories (US1→US2) can be developed by different people in parallel.

---

## Parallel Example: User Story 1

```bash
# After T006–T009 land, run the two US1 test files in parallel:
Task: "Unit-test build_asset key/partition/naming/snapshot in orchestrator/tests/test_factory.py"
Task: "Unit-test asset-vs-job routing in orchestrator/tests/test_definitions.py"
```

## Parallel Example: User Story 3

```bash
# After the schema + store edits (T015–T018), these are independent:
Task: "Regenerate ui/tests/golden/{api,claude-code,codex,pi}.yaml to schema 2 + commented produces"
Task: "Add commented produces block to all agents/_template-*.yaml"
Task: "Add produces.asset / produces.partition rows to README.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1: orchestrator asset representation + shared launch + metadata.
3. **STOP and VALIDATE**: run US1 unit tests; manually materialize per quickstart Scenario 1.
4. This alone delivers the core value: an agent's output as a first-class, historied asset.

### Incremental Delivery

1. Foundational → US1 (asset representation, MVP) → validate.
2. US2 (reversibility + backward compat) → validate the job↔asset door swings both ways.
3. US3 (UI authoring) → operators can declare assets without hand-editing YAML.
4. US4 (validation at both entry points) → bad/conflicting declarations caught safely.
5. Polish → full suites + live quickstart.

### Parallel Team Strategy

After Foundational: one developer takes the orchestrator track (US1 → US2 → US4 orchestrator half), another takes the UI track (US3 → US4 UI half). They meet at Phase 7.

---

## Notes

- **Null Action guard (T008)**: if `AssetsDefinition.from_op` cannot wrap the existing op without changing the container launch, STOP and report — do not fork `docker run` into two paths.
- **Partition is a label only (T007/T010)**: never inject the partition key into the container, `output_dir`, or file names.
- **No copies (T006)**: the asset points at existing output files; the run must not duplicate them.
- **Deliberate duplication (T004/T030)**: the asset-key regex is stated once per package (separate containers, no shared import) and pinned in agreement by a shared-fixture test.
- Commit after each task or logical group; each user story is an independently testable increment.
