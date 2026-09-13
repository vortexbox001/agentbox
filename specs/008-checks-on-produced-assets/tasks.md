---

description: "Task list for feature: Checks on Produced Assets"
---

# Tasks: Checks on Produced Assets

**Input**: Design documents from `/specs/008-checks-on-produced-assets/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/check-model.md](./contracts/check-model.md), [contracts/check-execution.md](./contracts/check-execution.md), [quickstart.md](./quickstart.md)

**Tests**: INCLUDED — the plan's Testing section and quickstart §0 explicitly require orchestrator (`orchestrator/tests/`) and UI (`ui/tests/`) coverage for this feature.

**Organization**: Tasks are grouped by user story (US1–US5) so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1–US5)
- Exact file paths are included in each description

## Path Conventions

Single project. Orchestrator code location at `orchestrator/`, agent container images at `images/`, declarative agent YAML at `agents/`, FastAPI editor at `ui/`. Paths below are repo-root-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing test environments run before changing anything (baseline).

- [X] T001 Confirm baseline test suites are green before changes: run `cd orchestrator && ../.venv/bin/python -m pytest -q` and `cd ui && ../.venv/bin/python -m pytest -q` (both suites share the Python 3.12 `.venv/` that carries Dagster 1.13.21 — the PEP 668 host's system `python` has no Dagster; recreate `.venv/` per `CLAUDE.local.md` only if missing)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema evolution and the shared launch+report core that ALL user stories build on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Bump `SCHEMA_VERSION` 4 → 5 and add identity `migrate_4_to_5` in [ui/schema.py](../../ui/schema.py) (per data-model.md "Schema evolution")
- [X] T003 Add the `produces.checks` list-of-objects field and per-item validation in [ui/schema.py](../../ui/schema.py): `name` (required, `^[a-z0-9]+(-[a-z0-9]+)*$`, unique within agent), `command` (required, non-empty), optional `image`, `blocking` (bool, default `true`), `timeout_seconds` (`1..86400`, default `300` when omitted), `network` (enum `agentnet-isolated|agentnet|bridge`); reject `checks` present without a valid `produces.asset` and duplicate check names (contracts/check-model.md §2–§3)
- [X] T004 [P] Add the checks help/comment text constant beside `PRODUCES_BLOCK_HELP` in [ui/schema.py](../../ui/schema.py) (authoritative wording for FR-012; emitted verbatim by the YAML writer)
- [X] T005 [P] Extract the shared launch+report core (Popen / live stdout stream / stderr drain / agent `timeout_seconds` / spec-007 report extraction / fallback report / `build_metadata`) out of `make_run_op` into a reusable helper in [orchestrator/factory.py](../../orchestrator/factory.py); the unchanged checkless `AssetsDefinition.from_op` path calls it and behaves byte-for-byte as before (FR-013, contracts/check-execution.md §1–§2)
- [X] T006 Add the `HARNESS_IMAGE` harness→default-check-image map in [orchestrator/factory.py](../../orchestrator/factory.py) (used to resolve a check's default image, R6)

**Checkpoint**: Schema v5 accepts/validates `checks`; the producer launch core is reusable by both asset paths.

---

## Phase 3: User Story 1 - Declare a check that gates an asset (Priority: P1) 🎯 MVP

**Goal**: An asset agent's `produces.checks` run after the producer in fresh containers and each surfaces as a green/red Dagster asset check on the produced asset, with the last 4 KB of output attached.

**Independent Test**: Add one check `name: has-output`, `command: test -n "$(ls /output)"` to an asset agent, materialize it, and confirm the asset shows a single asset check `has-output` — green when the run wrote a file, red when `/output` is empty — with captured output attached.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T007 [P] [US1] Add a check-container docker-run stub (alongside the existing agent-launch stub) in [orchestrator/tests/conftest.py](../../orchestrator/tests/conftest.py)
- [X] T008 [US1] Create [orchestrator/tests/test_checks.py](../../orchestrator/tests/test_checks.py) with US1 tests: check argv (`-v <out>:/output:ro`, `[-v <ws>:/workspace:ro]`, `-v …/report.json:/report.json:ro`, `--network none`, `--entrypoint sh <image> -c "<command>"`); exit 0 ⇒ `passed=True`, non-zero ⇒ `passed=False`; `metadata.output` = last 4 KB tail; `metadata.exit_code` recorded (contracts/check-execution.md §3, quickstart §0)

### Implementation for User Story 1

- [X] T009 [US1] Implement `run_checks(...)` in [orchestrator/factory.py](../../orchestrator/factory.py): resolve image (`check.image` or `HARNESS_IMAGE[harness]`), build the check argv, launch one `--rm` container per check in declared order, capture combined stdout/stderr, and return one `AssetCheckResult(check_name, passed=(exit==0), metadata={output: last-4KB tail, exit_code, blocking, image})` per check (contracts/check-execution.md §3)
- [X] T010 [US1] Add the `@multi_asset(specs=[AssetSpec…], check_specs=[AssetCheckSpec…])` construction path for check-bearing asset agents in `build_asset` in [orchestrator/factory.py](../../orchestrator/factory.py); generator-op body launches the producer via the shared core (T005), writes the report dict to `<pipes_dir>/report.json`, calls `run_checks`, and `finally` `rmtree`s the per-run pipes dir after checks run (R1/R2, contracts/check-execution.md §1–§2)
- [X] T011 [US1] On producer OK, `yield MaterializeResult(asset_key, metadata=<spec-007 metadata union>, check_results=<all results>)` in [orchestrator/factory.py](../../orchestrator/factory.py) (R3, contracts/check-execution.md §4)
- [X] T012 [P] [US1] Add the repeatable-object-rows **Checks card** control inside `buildAssetCard()` (each row: `name`, `command`, `image`, `blocking`, `timeout_seconds`, `network`) plus its collect logic in [ui/static/agent-form.js](../../ui/static/agent-form.js) (contracts/check-model.md §4)
- [X] T013 [P] [US1] Lift `produces.checks` in `read_agent` and add the `_produces_block_lines` branch that emits a nested `checks:` sequence-of-mappings (with header comment, only set fields) in [ui/agents_store.py](../../ui/agents_store.py) (contracts/check-model.md §5)
- [X] T014 [P] [US1] Add a UI round-trip test in [ui/tests/](../../ui/tests/) — `produces.checks` validates, emits, and reads back unchanged
- [X] T015 [P] [US1] Create the verification fixture [agents/verify-checks.yaml](../../agents/verify-checks.yaml) with the four checks from quickstart §1 (`has-output`, `advisory-fail`, `readonly-guard`, `slow`) — exercises US1–US4 for manual quickstart validation

**Checkpoint**: A single check materializes green/red on its asset with output attached — MVP delivered.

---

## Phase 4: User Story 2 - Blocking vs. non-blocking checks (Priority: P1)

**Goal**: A failed blocking check gates downstream automation (run marked failed, materialization still recorded); a failed non-blocking check is advisory (red, but asset still materialized and nothing blocked). Absent `blocking` ⇒ blocking.

**Independent Test**: Add two checks — `command: false` with `blocking: false`, and one that passes. Materialize and confirm the asset still counts as materialized, both checks appear, the non-blocking one is red, and nothing downstream is blocked.

### Tests for User Story 2 ⚠️

- [X] T016 [US2] Add blocking/severity tests to [orchestrator/tests/test_checks.py](../../orchestrator/tests/test_checks.py): `blocking: true` ⇒ `AssetCheckSeverity.ERROR` + `AssetCheckSpec(blocking=True)`; `blocking: false` ⇒ `WARN` + `blocking=False`; absent ⇒ blocking (default true); a failing non-blocking check leaves the run successful and the asset materialized; a failing blocking check records the materialization while failing the run (contracts/check-execution.md §4, quickstart §3)

### Implementation for User Story 2

- [X] T017 [US2] Map `blocking` → `AssetCheckSpec(name, asset, blocking=…)` in the `check_specs` list and → `severity=AssetCheckSeverity.ERROR if blocking else WARN` in the `AssetCheckResult` in [orchestrator/factory.py](../../orchestrator/factory.py) (FR-006, R3)

**Checkpoint**: Blocking gates automation; non-blocking is advisory-only — both visible on the asset.

---

## Phase 5: User Story 3 - A check sees the output but cannot change it (Priority: P2)

**Goal**: Every check container mounts `/output` and `/workspace` read-only and `/report.json`, receives no env/creds, and cannot add/remove/modify a produced file.

**Independent Test**: Add a check `command: touch /output/x`, materialize, and confirm the check fails with a read-only/permission error in its captured output and `/output` is unchanged.

### Tests for User Story 3 ⚠️

- [X] T018 [US3] Add read-only isolation tests to [orchestrator/tests/test_checks.py](../../orchestrator/tests/test_checks.py): assert the argv mounts `/output` and `/workspace` with `:ro`, mounts `/report.json`, passes no `env`/`env_file`/credential mounts, and defaults to `--network none` (a workspaceless agent omits the `/workspace` mount) (contracts/check-execution.md §5, quickstart §4)

### Implementation for User Story 3

- [X] T019 [US3] Ensure `run_checks` in [orchestrator/factory.py](../../orchestrator/factory.py) mounts `-v <output_dir>:/output:ro`, `-v <workspace>:/workspace:ro` (only when the agent has a workspace), and `-v <pipes_dir>/report.json:/report.json:ro`, and passes no env/creds — no isolation flag on the producer launch changes (FR-003/FR-009, Constitution I & V)

**Checkpoint**: Checks are read-only observers; a produced file is never modified by its own checks.

---

## Phase 6: User Story 4 - A check that runs too long is failed with a timeout (Priority: P2)

**Goal**: A check exceeding its `timeout_seconds` is killed and reported failed with `timed_out` in metadata; no check container from that run survives.

**Independent Test**: Add `command: sleep 60`, `timeout_seconds: 2`, materialize, and confirm the check is failed with `timed_out` in metadata and no `check-verify-checks-…` container remains.

### Tests for User Story 4 ⚠️

- [ ] T020 [US4] Add timeout tests to [orchestrator/tests/test_checks.py](../../orchestrator/tests/test_checks.py): a command exceeding its `timeout_seconds` ⇒ `passed=False` with `metadata.timed_out == True`, and the kill-by-name path is invoked (no surviving container) (FR-008/SC-004, quickstart §5)

### Implementation for User Story 4

- [ ] T021 [US4] Enforce each check's independent `timeout_seconds` (defaulting to 300 s when the check omits it — never unbounded) in `run_checks` in [orchestrator/factory.py](../../orchestrator/factory.py): on expiry `docker kill check-<agent>-<check>-<runid[:8]>`, mark the result failed with `metadata.timed_out=True`; every declared check still runs in order (FR-017 — no short-circuit)

**Checkpoint**: A hung check never stalls the asset; every declared check still reports.

---

## Phase 7: User Story 5 - Checks require an asset (Priority: P2)

**Goal**: The UI hides the Checks card for a job-only agent, and the orchestrator rejects an agent file declaring `checks` without a `produces.asset` (or with duplicate check names) at load — naming the file — while other agents load.

**Independent Test**: Open a job-only agent in the UI and confirm no Checks card; hand the orchestrator a file with `checks` but no `produces.asset` and confirm that file is rejected by name while every valid agent still loads.

### Tests for User Story 5 ⚠️

- [ ] T022 [P] [US5] Add load-rejection tests in [orchestrator/tests/test_definitions.py](../../orchestrator/tests/test_definitions.py): `checks` without `produces.asset` ⇒ `RejectAgent` naming the file; duplicate check names ⇒ rejected; a check missing `name`/`command` ⇒ rejected; other agents still load (FR-010, contracts/check-execution.md §6)
- [ ] T023 [P] [US5] Add UI tests in [ui/tests/](../../ui/tests/): a job-only agent renders no Checks card; when the asset gate is off, checks are dropped on collect; `checks` without an asset (and missing `name`/`command`) fails `schema.validate` (FR-011, contracts/check-model.md §3–§4)

### Implementation for User Story 5

- [ ] T024 [US5] Implement `validate_checks(cfg, file)` in [orchestrator/factory.py](../../orchestrator/factory.py): raise `RejectAgent(file, msg)` when `checks` present without a valid `produces.asset`, when a check lacks `name`/`command`, or when two checks share a `name` (contracts/check-execution.md §6)
- [ ] T025 [US5] Call `validate_checks` in the per-file try/except of `discover` (beside `validate_asset_key`) in [orchestrator/definitions.py](../../orchestrator/definitions.py) so one bad file is logged by name and skipped, all others load (FR-010)

**Checkpoint**: Checks-without-asset is impossible to author (UI) and rejected at load (orchestrator) without taking down other agents.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: The failed-producer path, partition metadata, image-resolution failure, and the FR-012 documentation.

- [ ] T026 [US1] Add the failed/timeout producer emission path in [orchestrator/factory.py](../../orchestrator/factory.py): `yield` each `AssetCheckResult`, `context.log_event(AssetObservation(asset_key, partition, metadata))` (red, no materialization — spec 007), log `stderr[-4000:]`, then `raise` — checks run even when the producer is non-`ok` (contracts/check-execution.md §4, edge case)
- [ ] T027 [US1] Add a failed-producer test in [orchestrator/tests/test_checks.py](../../orchestrator/tests/test_checks.py) asserting against `instance.event_log_storage.get_logs_for_run(run_id)`: **no** `ASSET_MATERIALIZATION`, exactly one `ASSET_OBSERVATION`, and one `ASSET_CHECK_EVALUATION` per check (quickstart §0 test lens)
- [ ] T028 [US1] Handle unresolvable check `image` in `run_checks` in [orchestrator/factory.py](../../orchestrator/factory.py): report that check failed with the resolution error in `metadata`, and continue to the next check (never abort the materialization) (FR-015, edge case)
- [ ] T029 [US1] Record the partition key in each check's `metadata.partition` when the producing run is partitioned in [orchestrator/factory.py](../../orchestrator/factory.py) (FR-014, R10); cover it with a partitioned-materialize assertion in [orchestrator/tests/test_checks.py](../../orchestrator/tests/test_checks.py)
- [ ] T030 [P] Document `produces.checks` and every check field in the `schema.py` help strings in [ui/schema.py](../../ui/schema.py) (authoritative wording — FR-012)
- [ ] T031 [P] Update the README agent-YAML reference rows and the `produces:` narrative to document the `checks:` list in [README.md](../../README.md) (FR-012)
- [ ] T032 [P] Add the optional `checks:` list to the `produces` block comments of the agent templates in [agents/_template-claude-code.yaml](../../agents/_template-claude-code.yaml), [agents/_template-api.yaml](../../agents/_template-api.yaml), [agents/_template-codex.yaml](../../agents/_template-codex.yaml), [agents/_template-pi.yaml](../../agents/_template-pi.yaml), and [agents/_template-repo-librarian.yaml](../../agents/_template-repo-librarian.yaml) (FR-012)
- [ ] T033 Run the full quickstart validation (`specs/008-checks-on-produced-assets/quickstart.md`) — both test suites plus the manual US1–US5 checks against `agents/verify-checks.yaml`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories** (schema v5 + shared launch core).
- **User Stories (Phase 3–7)**: All depend on Foundational.
  - US1 (Phase 3) establishes `run_checks` + the `@multi_asset` path that US2/US3/US4 refine, so US2–US4 depend on US1.
  - US5 (Phase 7) is independent of US1–US4 (validation/gating only) and can proceed right after Foundational.
- **Polish (Phase 8)**: Depends on US1 (extends the emission path, `run_checks`, and docs).

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependency on other stories (the MVP).
- **US2 (P1)**: Builds on US1's emission (`check_results`) — severity/blocking mapping.
- **US3 (P2)**: Builds on US1's `run_checks` argv — read-only mounts.
- **US4 (P2)**: Builds on US1's `run_checks` — per-check timeout/kill.
- **US5 (P2)**: Independent — validation + UI gating; parallelizable with US1–US4.

### Parallel Opportunities

- Foundational: [ui/schema.py](../../ui/schema.py) work (T002→T003, T004) runs in parallel with [orchestrator/factory.py](../../orchestrator/factory.py) work (T005 [P], T006).
- US1: T012 (agent-form.js), T013 (agents_store.py), T014 (ui/tests), T015 (verify-checks.yaml) are all different files — run in parallel; T007 (conftest) is parallel with them.
- US5: T022 (orchestrator tests) and T023 (ui tests) are different files — parallel.
- Polish: T030 (schema.py), T031 (README.md), T032 (templates) are different files — parallel.
- **Whole stories in parallel**: once Foundational lands, US5 can be built by one developer while US1→US2→US3→US4 proceed on another track.

---

## Parallel Example: User Story 1

```bash
# After T008–T011 land the orchestrator core, the UI + fixture tasks are independent files:
Task: "T012 Checks card control in ui/static/agent-form.js"
Task: "T013 produces.checks read/emit in ui/agents_store.py"
Task: "T014 UI round-trip test in ui/tests/"
Task: "T015 verification fixture agents/verify-checks.yaml"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (schema v5 + shared launch core).
2. Phase 3 US1 → a single check surfaces green/red on its asset with output attached.
3. **STOP and VALIDATE**: materialize `agents/verify-checks.yaml`'s `has-output` check.

### Incremental Delivery

1. Foundational → US1 (MVP) → validate → demo.
2. US2 (blocking/advisory) → US3 (read-only) → US4 (timeout) — each independently testable on the same fixture.
3. US5 (guardrails) in parallel at any point after Foundational.
4. Polish: failed-producer path, partition metadata, image-resolution failure, docs (FR-012), full quickstart.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- Same-file test additions (T008/T016/T018/T020/T027/T029 all touch `test_checks.py`) are sequenced, not parallel.
- Verify each new test fails before implementing its story.
- `.specify/bugs` aside: commit `agents/verify-checks.yaml`, `tasks.md`, and code together per your usual staging.
- Constitution invariants: no per-check-type logic in the orchestrator; checks judged by exit code only.
