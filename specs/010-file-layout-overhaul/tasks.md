---

description: "Task list for File Layout Overhaul — Three Roots"
---

# Tasks: File Layout Overhaul — Three Roots

**Input**: Design documents from `/specs/010-file-layout-overhaul/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The spec, plan, quickstart, and every contract's §4 call for unit tests
(path resolution, migration planner, LiteLLM generator, path validation, parity). Box-level
stories (US1/US2/US3) are validated by the quickstart on a box copy, not CI.

**Organization**: Tasks are grouped by user story. Foundational phase carries the one shared
architectural addition — the single-resolution-point pattern (FR-002/SC-009) — plus the shared
compose/bootstrap rewiring both P1 stories build on. Every story derives paths from Foundational.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- All paths are repo-relative from `/home/vortex/GitHub/agentbox/`

## Path Conventions

- Orchestrator process: `orchestrator/` (runs in the orchestrator/daemon container)
- UI process: `ui/` (separate container, no shared import with the orchestrator)
- The two processes resolve roots independently — mirrored, pinned by a parity test (research R2)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Product-repo scaffolding that later phases land files into.

- [ ] T001 Add `/config/` to `.gitignore` at repo root so a config repo can be checked out at the config path without polluting the product repo (FR-006); include a comment noting the generated `litellm.rendered.yaml` lives inside that ignored tree (R-LL-4).
- [ ] T002 [P] Create the `examples/config/` directory skeleton with `agents/`, `prompts/`, `projects/`, and `external-assets/` subdirectories (empty, `.gitkeep` where needed) so US2/US6 content has a home and every config subpath FR-005 lists is defined; `projects/` and `external-assets/` remain reserved for their owning briefs (data-model §Instance-configuration tree).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The three-root resolution contract, its consumption by the orchestrator, and the
shared compose/bootstrap rewiring. Every user story derives its paths and its stack wiring from
here.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Create `orchestrator/paths.py` as the orchestrator's single resolution point: read `AGENTBOX_CONFIG`, `AGENTBOX_DATA`, `DAGSTER_HOME` once at import (defaults per contracts/path-resolution.md §1) and expose `CONFIG_ROOT`, `DATA_ROOT`, `DAGSTER_ROOT`, `AGENTS_GLOB`, `PROMPTS_DIR`, `RUNS_ROOT`, `OUTPUTS_ROOT`, `WORKSPACES_ROOT`, `CREDENTIALS_ROOT`, `KEYS_ROOT`, `PIPES_ROOT` (= `DAGSTER_ROOT/pipes`), helpers `default_output_dir(name)`/`default_workspace(name)`, and the host-path forms for `docker run -v` (FR-001/FR-002, contract §2).
- [ ] T004 Extend `ui/config.py` (the UI's single resolution point) to derive from the same three vars: repoint `AGENTS_DIR`/`PROMPTS_DIR` under `CONFIG_ROOT`, add `EXAMPLES_DIR`/`TEMPLATES_DIR` and an explicit `PRODUCT_ROOT` (product tree, read-only — the anchor the FR-025 "under the product tree" check needs), `LITELLM_RENDERED` under `CONFIG_ROOT`, `DATA_ROOT`, and expose the roots needed for schema path validation; replace the `/opt/agentbox/...` literals (FR-002, contract §2).
- [ ] T005 [P] Add `orchestrator/tests/test_paths.py`: monkeypatch each var → assert derived constants; unset → defaults (R-PR-1); non-default roots → no default-path leakage (R-PR-2); `PIPES_ROOT` under `DAGSTER_ROOT`, `RUNS_ROOT` under `DATA_ROOT` (R-PR-3) — contract §4.
- [ ] T006 [P] Add UI path-resolution tests in `ui/tests/test_config_paths.py`: same monkeypatch/default/leakage assertions for `ui/config.py`, including `PRODUCT_ROOT` (R-PR-1/2/3) — contract §4.
- [ ] T007 Add a shared-fixture parity test (mirror the existing `ASSET_KEY_RE`/`is_valid_cron` twin-parity idiom) asserting any constant duplicated between `orchestrator/paths.py` and `ui/config.py` (root names, default subpaths) agrees across both — contract §4.
- [ ] T008 Rewire `orchestrator/factory.py` to derive every path from `orchestrator/paths.py`: replace `AGENT_LOG_ROOT = "/data/dagster/agent-logs"` with `RUNS_ROOT` (transcripts now under `$AGENTBOX_DATA/runs`, FR-010/R3), `PIPES_ROOT`, the `/data/workspaces/<name>` and `/data/credentials/...` literals, `output_dir` defaults, and the `HOST_REPO`/host-path builders — leaving the agent-container internal mount points (`/workspace`, `/output`, `/config/prompt.md`) unchanged (FR-024, R-PR-4).
- [ ] T009 Update `orchestrator/definitions.py` so the agent-YAML discovery glob derives from `paths.AGENTS_GLOB` (config root) instead of the product `agents/` dir (FR-002).
- [ ] T010 Update `orchestrator/dagster.yaml` and `orchestrator/workspace.yaml` so Dagster's storage/history/compute-logs paths derive from `$DAGSTER_HOME` and nothing agentbox-owned resolves under it (FR-012).
- [ ] T011 Rewrite `scripts/bootstrap.sh` to create the `$AGENTBOX_DATA` subtree (`runs outputs workspaces repo-mirrors provenance credentials keys`) owned by `AGENTBOX_UID:AGENTBOX_GID` (default 1000), with `credentials/` and `keys/` `chmod 700`, plus `$DAGSTER_HOME` and the `config/` dir; leave `/data/logs` untouched (FR-011/FR-022, R9, Clarification C).
- [ ] T012 Rewrite `docker-compose.yml` mounts to exactly: product tree read-only, config root (writable for UI), state root, Dagster home (orchestrator+daemon only), the Docker socket, and — for LiteLLM — only `config/litellm.rendered.yaml`; pass the three root env vars through; no mount outside the three roots + product + socket (FR-013/FR-023/FR-024, R9).

**Checkpoint**: Both processes resolve all paths from the three roots; the orchestrator writes run records under `$AGENTBOX_DATA/runs`; the stack (compose + bootstrap) is wired to the three roots. All user stories — including the US1 restart-validation step — can now proceed.

---

## Phase 3: User Story 1 - Migrate the existing box without losing anything (Priority: P1) 🎯 MVP

**Goal**: A dry-run-by-default tool relocates the live box's config and state into the new roots — moves, in-YAML path rewrites, and a compatibility symlink — losing nothing.

**Independent Test**: On a box copy, `migrate-layout.py` dry-run prints a plan and changes nothing; `--apply` performs the moves; after restart (Foundational compose/bootstrap) every agent/prompt/schedule/past-run/output is present and `git status` shows only the `agents/`+`prompts/` deletions and the new gitignore entry (quickstart US1, SC-001/SC-002).

- [ ] T013 [P] [US1] Add `scripts/tests/test_migrate_layout.py` (planner): synthesize an old-layout fixture tree in tmp; assert the computed plan lists exactly the expected moves/rewrites/symlink/left-untouched entries (R-MIG-1/3/4/6); clobber case: pre-populate one destination → assert refusal names it and nothing changes (R-MIG-2) — contract migration-cli §4.
- [ ] T014 [US1] Create `scripts/migrate-layout.py` planner core (Python 3.12, stdlib + pyyaml): read the three roots from env (path-resolution §1), compute the ordered plan of moves — `agents/`→`$CONFIG/agents/`, `prompts/`→`$CONFIG/prompts/`, `orchestrator/settings.yaml`→`$CONFIG/settings.yaml` (only if present, R5), each recognized `/data/<x>`→`$DATA/<x>`, `/data/dagster/agent-logs`→`$DATA/runs` — and print the full plan on dry-run, changing nothing (R-MIG-1, contract §2).
- [ ] T015 [US1] Implement `--apply` in `scripts/migrate-layout.py`: perform the moves and create the `/data/dagster/agent-logs -> $AGENTBOX_DATA/runs` compatibility symlink for migrated history (recorded in the plan), leaving the PIPES dir and Dagster storage/DB untouched (FR-018/FR-021, R-MIG-4).
- [ ] T016 [US1] Add in-YAML path rewriting to `scripts/migrate-layout.py`: rewrite `output_dir`/`workspace`/`env_file` values that **begin with an old root** to the corresponding new root, leaving already-migrated/unrelated values as-is (FR-019, R-MIG-3).
- [ ] T017 [US1] Add product-repo cleanup + left-untouched recording to `scripts/migrate-layout.py`: remove the moved `agents/`/`prompts/` from the checkout and add `/config/` to `.gitignore` if absent (surfaced as the SC-002 git delta), and record every unrecognized old-root dir (e.g. `/data/logs`), the PIPES dir, and Dagster storage as "left untouched" in the printed plan (FR-018, R-MIG-6).
- [ ] T018 [US1] Add the clobber-refusal guard to `scripts/migrate-layout.py`: if **any** destination already has content, refuse to run (with or without `--apply`), name the blocking destination, and make no changes (FR-020, R-MIG-2).

**Checkpoint**: Migration tool complete and unit-tested; box-copy validation runs via quickstart US1 (Foundational already supplies the compose/bootstrap the restart step needs).

---

## Phase 4: User Story 2 - Fresh install from examples (Priority: P1)

**Goal**: A new box stands up by copying `examples/config/` to `config/`, pointing the roots at empty dirs, running bootstrap, and `docker compose up` — every write landing under the two instance roots.

**Independent Test**: In a clean clone, copy examples→config, set roots to empty dirs, bootstrap, up. The UI lists the example agents; one materializes; its run dir appears under `$AGENTBOX_DATA/runs/`; a filesystem watch records zero writes outside the two roots and no agentbox run dirs under `$DAGSTER_HOME` (quickstart US2, SC-003/SC-004).

- [ ] T019 [P] [US2] Move `agents/_template-*.yaml` (api, claude-code, codex, pi, repo-librarian) into `examples/config/agents/` so templates leave the instance agents dir (FR-008/FR-015, R7).
- [ ] T020 [P] [US2] Author the rest of `examples/config/`: a sample prompt in `prompts/`, a sample project in `projects/`, a minimal `settings.yaml` (reserved/mostly-empty per R5), sufficient to seed a working box by copying (FR-015). *(LiteLLM overlay example is authored in US6/T034.)*
- [ ] T021 [US2] Repoint the UI template picker to the examples tree: `ui/main.py` create form (`?from=<template>`) and the template-listing in `ui/agents_store.py`/`ui/automation_store.py` source templates from `EXAMPLES_DIR`, not the instance agents dir; the `_`-prefix `is_template` convention no longer matches instance agents (FR-008, R7).
- [ ] T022 [P] [US2] Add a UI test in `ui/tests/test_agents_store.py` (or `test_api.py`) asserting the template picker lists templates from the examples tree and that instance agents (no `_` prefix) are not treated as templates (FR-008, R7).

**Checkpoint**: A clean clone stands up from examples with all writes under the two roots.

---

## Phase 5: User Story 3 - Relocate the roots to any disk (Priority: P2)

**Goal**: With both instance roots set to non-default paths, every service follows them and nothing is written back to the defaults.

**Independent Test**: Set both roots to non-default empty dirs, run an agent, confirm all reads/writes hit the configured paths and the default locations receive zero writes (quickstart US3, SC-005).

- [ ] T023 [US3] Audit both resolution modules and `orchestrator/factory.py` for any residual default-location leakage (e.g. a helper that rebuilds a `/data/...` path instead of deriving from `DATA_ROOT`); route every remaining derived path through `paths.py`/`ui/config.py` (FR-004, R-PR-2).
- [ ] T024 [P] [US3] Add non-default-root leakage tests to `orchestrator/tests/test_paths.py` and `ui/tests/test_config_paths.py`: with roots set to `/mnt/...` paths, assert every derived path is under the configured root and none resolve to `/data/agentbox` or `<repo>/config` (SC-005, R-PR-2).

**Checkpoint**: Roots are genuinely relocatable end to end with no default fallback.

---

## Phase 6: User Story 4 - Configuration edits stay out of the product repo (Priority: P2)

**Goal**: UI edits to agents and prompts land in the config root and never touch the product tree.

**Independent Test**: Check out a separate git repo at the config path, edit an agent + a prompt through the UI, confirm the edits appear in `config/` and the product repo's `git status` is clean (quickstart US4, SC-007).

- [ ] T025 [US4] Verify/adjust `ui/agents_store.py` and `ui/prompts_store.py` so all reads and writes resolve through `config.AGENTS_DIR`/`config.PROMPTS_DIR` (now under `CONFIG_ROOT`) and no write path can reach the product tree (FR-007).
- [ ] T026 [P] [US4] Add tests in `ui/tests/test_agents_store.py`/`ui/tests/test_prompts_store.py` (monkeypatching `CONFIG_ROOT` to a tmp dir) asserting a create/edit writes under the config root and touches nothing in the product tree (SC-007).

**Checkpoint**: UI configuration edits are confined to the config root.

---

## Phase 7: User Story 5 - Config paths are validated against the roots (Priority: P2)

**Goal**: Agent definitions whose `output_dir`/`workspace`/`env_file` point into the product tree or outside the data root are rejected with a field-named message; the schema bumps to version 6.

**Independent Test**: Submit an agent whose `output_dir` is under the product tree → rejected naming the field and stating the data-root rule; submit one under the data root / omitted / documented default → accepted (quickstart US5, SC-006).

- [ ] T027 [P] [US5] Add tests to `ui/tests/test_schema.py`: `validate` with `output_dir` under the product tree → error dict names `output_dir` and states the data-root rule (R-PV-1); {omitted, documented default, under data root} for each of `output_dir`/`workspace`/`env_file` → no path error (R-PV-2) — contract path-validation §4.
- [ ] T028 [US5] Add the path-validation rule to `ui/schema.py:validate` (reading `PRODUCT_ROOT`/`DATA_ROOT` from `ui/config.py`, matching the existing `prompt_exists` injection style): reject values under `PRODUCT_ROOT` or outside `DATA_ROOT` unless equal to a documented default; the message names the field and states the rule (FR-025, contract §1).
- [ ] T029 [US5] In `ui/schema.py`, make `output_dir` optional with the documented default `$AGENTBOX_DATA/outputs/<name>` (was `required=True`, schema.py:257), bump `SCHEMA_VERSION` 5→6, add `migrate_5_to_6` (identity) to the migrations list, and record the root change in the migration docstring (FR-026, contract §2).
- [ ] T030 [P] [US5] Add a migration round-trip test to `ui/tests/test_schema.py`: a schema-5 fixture reads as version 6 in memory with unchanged fields and re-stamps to 6 only on save (R-PV-3).

**Checkpoint**: Config paths cannot point state at the product tree or outside the data root; schema is at version 6.

---

## Phase 8: User Story 6 - LiteLLM config is generated from template plus overlay (Priority: P2)

**Goal**: The product ships an alias-tier template; the instance supplies providers/keys/bindings in an overlay; a generator merges them into the loaded config and fails at render time on a missing key.

**Independent Test**: Run the generator against the template + overlay → rendered config binds the alias tiers to the overlay's providers and preserves `os.environ/<KEY>` refs; unset a referenced key → non-zero exit naming the key and no file written (quickstart US6, SC-008).

- [ ] T031 [P] [US6] Add `litellm/tests/test_generate.py` (or under an existing suite): template+overlay fixtures → assert rendered `model_list` binds each tier to the overlay provider/model and preserves `os.environ/` refs (R-LL-1); overlay referencing an absent `MISSING_KEY` → non-zero exit, the name in the message, no output file (R-LL-2); `api_key` value never appears expanded (Constitution III) — contract litellm-generator §4.
- [ ] T032 [US6] Rename `litellm/config.yaml` → `litellm/config.template.yaml` and reduce it to the product-owned alias tiers features depend on (`cheap`, `smart`, `opus`, `kimi`, `kimi-k3`), expressing each tier's concrete `model`/`api_base`/pricing as overlay-fillable (FR-014, R6).
- [ ] T033 [US6] Repoint every existing consumer of the renamed `litellm/config.yaml` (broken by T032): in `ui/schema.py:415-421` read model-alias completion from the **rendered** config (`config.LITELLM_RENDERED`) instead of `config.LITELLM_CONFIG`; update `ui/tests/conftest.py:44-46` to build a rendered-config fixture and `ui/tests/test_schema.py:395` accordingly; move the custom-endpoint pricing regression guard `ui/tests/test_litellm_pricing.py:16` to read the overlay/rendered config, since per-model pricing becomes instance overlay data (R6). Remove the now-dead `LITELLM_CONFIG` var if nothing references it (FR-014).
- [ ] T034 [US6] Author `examples/config/litellm.overlay.yaml` (the instance overlay sample): providers, `api_key` env-var **names**, `api_base`, alias→model bindings, and any pricing (incl. the Kimi/custom-endpoint pricing the T033 guard now checks) (FR-015, R6).
- [ ] T035 [US6] Create `litellm/generate.py`: deep-merge overlay over `config.template.yaml` (overlay wins), write `$AGENTBOX_CONFIG/litellm.rendered.yaml` keeping `os.environ/<NAME>` refs unexpanded; before writing, assert every referenced `<NAME>` is present in the env, else exit non-zero naming the missing key(s) and write nothing (FR-016/FR-017, R-LL-2/R-LL-3).
- [ ] T036 [US6] Wire `litellm/generate.py` to run at stack start (a compose init step / entrypoint that runs before the LiteLLM container loads its config) so a fresh `docker compose up` regenerates the rendered config; the Foundational compose (T012) already mounts `config/litellm.rendered.yaml` (FR-016, contract §1).

**Checkpoint**: LiteLLM config is generated from template+overlay; a missing key fails at render, not first request; no existing consumer of the old config path is left broken.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (Constitution VI / FR-027–029) and end-to-end validation.

- [ ] T037 [P] Add a "Layout" section to `README.md` describing the three-kinds model and both instance trees, and rewrite the repo's file-tree listing to match the real subpaths (FR-027).
- [ ] T038 [P] Update `AGENTS.md` with contributor guidance stating where each kind of file goes: product code in the product, instance config under the config root, state under the data root, samples under `examples/` (FR-028).
- [ ] T039 [P] Add `.env.example` documenting `AGENTBOX_CONFIG`, `AGENTBOX_DATA`, `DAGSTER_HOME` (with defaults) plus `AGENTBOX_UID`/`AGENTBOX_GID` (FR-029).
- [ ] T040 Add a docs test (extend `ui/tests/test_design_system_docs.py` pattern or a new `test_docs_layout.py`) asserting all three root vars are documented and the README layout tree lists the real subpaths (Constitution VI preferred automated verification).
- [ ] T041 Run the full suites (`orchestrator`, `ui`, `images/tests`, and the new `litellm`/`scripts` tests) and execute the quickstart US1/US2 validation on a box copy; confirm SC-001…SC-009 hold.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories. Delivers FR-002/SC-009 (the single-resolution-point spine) **and** the shared compose/bootstrap wiring (T011/T012) both P1 stories build on.
- **User Stories (Phases 3–8)**: All depend on Foundational.
- **Polish (Phase 9)**: Depends on all targeted stories.

### Cross-story notes

- With compose/bootstrap now in Foundational, **US1's restart-validation step no longer depends on US2** — both P1 stories stand on the Foundational stack wiring independently.
- **US1's gitignore delta (SC-002)** relies on the `/config/` entry (T001/T017).
- **US6/T033** repairs the existing consumers of `litellm/config.yaml` that T032's rename breaks — do T033 in the same change as T032 to keep the UI suite green.
- **US6/T036** completes the fresh-install path: `docker compose up` regenerates the rendered LiteLLM config that the Foundational compose (T012) mounts.
- **US3** is largely hardening + tests over the Foundational rewire; its only exclusive code is T023.

### User Story Dependencies

- US1 (P1), US2 (P1): independent of each other once Foundational is done.
- US3, US4, US5, US6 (P2): each independent once Foundational is done; can proceed in parallel.

### Within Each User Story

- Tests (marked [P], written first where practical) → implementation.
- Migration: planner (T014) before apply (T015) before rewrite/cleanup/guard (T016–T018).
- Schema: rule (T028) and version bump (T029) before the round-trip test passes.
- LiteLLM: rename (T032) and consumer repair (T033) land together before the generator (T035).

### Parallel Opportunities

- Setup: T002 ∥ T001.
- Foundational: T003 ∥ T004 (different processes); T005 ∥ T006 after them.
- Once Foundational is done, the six user stories can be staffed in parallel.
- Within stories, all [P]-marked tests and independent-file tasks run together.

---

## Parallel Example: Foundational + kickoff

```bash
# The two resolution modules are in different processes — build in parallel:
Task T003: "Create orchestrator/paths.py"
Task T004: "Extend ui/config.py to three roots (+ PRODUCT_ROOT)"

# Then their tests in parallel:
Task T005: "orchestrator/tests/test_paths.py"
Task T006: "ui/tests/test_config_paths.py"
```

```bash
# After Foundational, launch the P2 stories' test-first tasks together:
Task T027: "Path-validation tests in ui/tests/test_schema.py"
Task T031: "LiteLLM generator tests in litellm/tests/test_generate.py"
```

---

## Implementation Strategy

### MVP First (the two P1 stories)

1. Phase 1: Setup → Phase 2: Foundational (CRITICAL spine + compose/bootstrap).
2. Phase 3: US1 migration (T013–T018) and Phase 4: US2 fresh-install (T019–T022) — both now build directly on Foundational.
3. **STOP and VALIDATE**: run quickstart US1 + US2 on a box copy (SC-001…SC-004).
4. This is the shippable MVP: existing box migrates, fresh box installs.

### Incremental Delivery

1. Foundational + US1 + US2 → migrate/fresh-install works (MVP).
2. Add US3 → confirm relocation with no default leakage.
3. Add US5 → path validation guards authoring.
4. Add US6 → LiteLLM template/overlay generation (repairing config consumers in the same step).
5. Add US4 → config-repo cleanliness.
6. Polish → docs + doc test + full-suite/quickstart pass.

---

## Notes

- [P] = different files, no dependencies.
- The orchestrator and UI have **no shared import** (separate containers); the two resolution
  modules are deliberately mirrored and pinned by the parity test (T007) — do not try to unify them.
- PIPES stays under `$DAGSTER_HOME`; only `agent-logs`→`runs` moves out (FR-010, R3/R4).
- Never `pip install` outside `.venv` (PEP 668 host); run suites with `../.venv/bin/python -m pytest -q`.
- Commit the `specs/010-file-layout-overhaul/` artifacts with the work.
- Commit after each task or logical group; stop at any checkpoint to validate a story.
