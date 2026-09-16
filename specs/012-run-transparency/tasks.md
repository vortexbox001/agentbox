---

description: "Task list for Run Transparency — Conversation View and Context Snapshot"
---

# Tasks: Run Transparency — Conversation View and Context Snapshot

**Input**: Design documents from `/specs/012-run-transparency/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED — the spec's quickstart names a concrete automated test file per scenario
(`images/tests`, `orchestrator/tests`, `ui/tests`), so test tasks are generated per story.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US5 (maps to the five user stories in spec.md)
- Every task lists an exact file path.

## Path Conventions

Single tree, three service roots: `images/`, `orchestrator/`, `ui/`. Paths are repo-root relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Wiring the viewer and settings need before any capture or read work begins.

- [ ] T001 Add a read-only `$AGENTBOX_DATA` bind mount into the `ui` service in `docker-compose.yml` (the ui service has none today; runs_store reads run directories through it).
- [ ] T002 [P] Add the `retention` placeholder block (`mode: keep_forever`) to `examples/config/settings.yaml` so the shipped example documents the new schema.
- [ ] T003 [P] Add `DATA_ROOT` runs-path and `$AGENTBOX_CONFIG/settings.yaml` accessors to `ui/config.py` (mirrors the existing path helpers; consumed by runs_store and settings_store).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The capture-and-read substrate plus the run-detail page shell. Every user story
renders into this shell and reads from these files, so all of Phase 2 blocks Phase 3+.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

**Capture pipeline**

- [ ] T004 Add run-directory path helpers to `orchestrator/paths.py` — `run_dir(agent, date, run_id)` and the four filenames (`transcript.jsonl`, `events.jsonl`, `context.json`, `report.json`), keeping the legacy flat-file helper for backward compat (contracts/run-directory.md, R1).
- [ ] T005 [P] Extend `orchestrator/tests/test_paths.py` and `orchestrator/tests/test_paths_parity.py` for the new run-directory helpers.
- [ ] T006 Create `images/lib/agent_events.py` — the `NormalizedEvent` dataclass (seven kinds, `ts`/`turn`/`tokens_in`/`tokens_out`/`cost_usd` with null≠0), the JSONL writer, and **generic** instruction-file walk/read primitives, per `contracts/normalized-event.schema.json` (R5). Note: this lib provides only generic file-tree walk/read helpers; per-harness instruction-file *discovery* (CLAUDE.md hierarchy vs AGENTS.md) lives in each wrapper's context fragment (T040–T043).
- [ ] T007 [P] Add `images/tests/test_agent_events.py` — schema round-trip, kind coverage, and the null-vs-0 numeric rule for `agent_events.py`.
- [ ] T008 Create `orchestrator/redact.py` — `redact(text) -> text` over the `ui/secret_scan.py` heuristic, replacing matches with `[REDACTED:<kind>]`, idempotent (contracts/redaction.md, R4).
- [ ] T009 [P] Add `orchestrator/tests/test_redact.py` — per-kind coverage + idempotence; a shared-fixture parity test pinning `redact.py` against `ui/secret_scan.py`; **and** an end-to-end capture test that writes a fixture run directory seeded with a fake secret, `grep -r`'s the whole directory, and asserts no cleartext hit while the value survives only as `[REDACTED:<kind>]` (FR-016 / SC-004).
- [ ] T010 Create `orchestrator/run_capture.py` — run-dir writer (create dir; write `context.json` first for crash-before-first-event; stream+redact transcript lines; redact+move `events.jsonl` from staging; co-locate `report.json`) plus the context-snapshot builder scaffold (contracts/run-directory.md ownership table).
- [ ] T010a Wire the ephemeral **staging mount** the images write `events.jsonl` + the context fragment (`context-harness.json`) to, in `orchestrator/factory.py` (reuse/adjacent to the existing `/pipes` dir). The mount source MUST resolve on the **host** filesystem under `$AGENTBOX_DATA` (never container-private `/tmp` — Docker-outside-of-Docker, see the pipes-dir pitfall), be `--rm`-cleaned per run, and grant no new network or credential reach; it is not `/output` (Constitution I, plan Constitution Check). Add an `orchestrator/tests` assertion pinning the staging path under `$AGENTBOX_DATA` and the `--rm`/no-new-mount invariants.
- [ ] T011 Wire capture into `orchestrator/factory.py` — run-directory assembly at launch, the single redaction pass, image-digest inspect (R10), and the `run_dir` link in `build_metadata`, including the timeout path that authors context+report itself.
- [ ] T012 [P] Extend `orchestrator/tests/test_factory.py` and `orchestrator/tests/test_reports.py` — run-dir assembly, `run_dir` metadata link, and timeout still writing context+report.

**Disk reader**

- [ ] T013 Create `ui/runs_store.py` — `list_runs(agent, status, date_from, date_to)` (report.json+context.json headers only) and `read_run(run_id)` (tolerant four-file load, sets `conversation_available`), per contracts/viewer-routes.md.
- [ ] T014 [P] Add `ui/tests/test_runs_store.py` — list/read against a temp run tree, filter application, and missing-file tolerance (partial write / legacy flat run).

**Design-system shell + detail page container**

- [ ] T015 Finish the `ax-btn--dagster` variant and add the `tab-panel` behaviour + `run_stat_strip` component to the specimen and master CSS in `ui/design-system/templates/run-detail/RunDetail.dc.html` and `ui/design-system/static/app.css` (R9 step 1–2).
- [ ] T016 Sync the `ax-btn--dagster`, `tab-panel`, and `run_stat_strip` CSS byte-for-byte into `ui/static/app.css` (R9 step 3; `test_design_system_sync.py`).
- [ ] T017 Add the `run_stat_strip` macro and the dagster button intent to `ui/templates/components/macros.html`, and add the Runs + Settings nav slots to `ui/templates/base.html` (R9 step 4).
- [ ] T018 Create `ui/static/run-detail.js` with the tab-panel switching skeleton across the four tabs (Conversation / Context / Report / Files).
- [ ] T019 Add the `GET /runs/{run_id}` route to `ui/main.py` and create the shell template `ui/templates/runs/detail.html` (tab container + stat strip via `read_run`, path param through `_unsafe_name()`).

**Checkpoint**: A run writes a full run directory; the detail page opens from disk with empty tabs.

---

## Phase 3: User Story 1 - Read a run's conversation (Priority: P1) 🎯 MVP

**Goal**: Open any run and read a uniform, chat-style history — turns in order, collapsible tool
calls with args + results, file edits as diffs, per-turn tokens/cost, and in-page search.

**Independent Test**: Run one agent on each harness (api/pi, claude-code, codex), open each run's
Conversation tab, and confirm the same threaded shape with tool calls, results, and file-edit
diffs in faithful order.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [ ] T020 [P] [US1] `images/tests/test_claude_events.py` — `to_events()` for the claude-code native stream asserts kinds/order/diff.
- [ ] T021 [P] [US1] `images/tests/test_codex_events.py` — `to_events()` for the codex native stream asserts kinds/order/error/final.
- [ ] T022 [P] [US1] `images/tests/test_pi_events.py` — `to_events()` for the pi native stream (message + agent_end blocks, per-message usage).
- [ ] T023 [P] [US1] `images/tests/test_api_events.py` — synthesised events for the python runner (system + user + assistant + final).
- [ ] T024 [P] [US1] `ui/tests/test_runs.py` — Conversation tab renders the same components for a fixture run of each harness, and marks a missing tool result as missing.

### Implementation for User Story 1

- [ ] T025 [P] [US1] Add `to_events(lines)` to `images/agent-claude/wrapper.py` (system init → system; assistant blocks → assistant/tool_call; user tool_result → tool_result; result → final).
- [ ] T026 [P] [US1] Add `to_events(lines)` to `images/agent-codex/wrapper.py` (turn/item events → assistant/tool_*; error → error; terminal → final).
- [ ] T027 [P] [US1] Add `to_events(lines)` to `images/agent-pi/wrapper.py` (message events + agent_end messages[] → stream; usage per assistant message).
- [ ] T028 [P] [US1] Synthesise events in `images/agent-python/runner.py` (no CLI stream) and write `events.jsonl` to the staging mount.
- [ ] T029 [US1] Extend `run_wrapper` in `images/lib/agent_report.py` so the CLI harnesses call both `parse` and `to_events` on the teed lines and write `events.jsonl` to the staging mount (depends on T025–T027).
- [ ] T030 [US1] Add the `timeline` + `timeline_entry`, `tool_call` (collapsible), and `diff_block` (`ax-diff-add`/`ax-diff-del`) components to the specimen and master CSS in `ui/design-system/templates/run-detail/RunDetail.dc.html` and `ui/design-system/static/app.css`.
- [ ] T031 [US1] Sync the timeline / tool_call / diff CSS byte-for-byte into `ui/static/app.css`.
- [ ] T032 [US1] Add the `timeline`, `timeline_entry`, `tool_call`, and `diff_block` macros to `ui/templates/components/macros.html`.
- [ ] T033 [US1] Add `GET /api/runs/{run_id}/events` to `ui/main.py`, returning normalized events from `runs_store` for the Conversation tab.
- [ ] T034 [US1] Build the Conversation tab in `ui/templates/runs/detail.html` — threaded history via the new macros, per-turn tokens/cost, missing-result markers, and the "conversation only/pruned" fallback when `events.jsonl` is absent.
- [ ] T035 [US1] Add conversation collapse + in-page search to `ui/static/run-detail.js`.

**Checkpoint**: Conversation view renders identically across all four harnesses — MVP is usable.

---

## Phase 4: User Story 2 - Inspect the starting context (Priority: P1)

**Goal**: Open a run's Context tab and see the frozen launch snapshot — prompt, model, tools, MCP
servers + exposed tools, every loaded instruction file (full contents), env var names only,
mounts/network/caps, workspace/output file trees, asset-run details, and a completeness statement.

**Independent Test**: Open a claude-code run's Context tab (tools, MCP, model, full instruction
files, completeness names the vendor base prompt undisclosed); open a pi run (completeness =
complete).

### Tests for User Story 2 ⚠️ (write first, ensure they fail)

- [ ] T036 [P] [US2] `orchestrator/tests/test_run_capture.py` — the context builder produces every FR-009/010/011 field, captures the image digest, and never writes an env value.
- [ ] T037 [P] [US2] `images/tests/test_context_fragment.py` — per-harness fragment (instruction-file contents, MCP exposed tools, completeness) for claude/codex/pi/api.
- [ ] T038 [P] [US2] Extend `ui/tests/test_runs.py` — Context tab renders instruction-file contents, the completeness statement, and env names only.

### Implementation for User Story 2

- [ ] T039 [US2] Implement the full context-snapshot builder in `orchestrator/run_capture.py` — all FR-009 fields, workspace/output file trees (FR-010), and asset-run fields (FR-011), per `contracts/context-snapshot.schema.json`.
- [ ] T040 [P] [US2] Add the context fragment to `images/agent-claude/wrapper.py` (CLAUDE.md hierarchy contents + MCP exposed tools + completeness: vendor base prompt undisclosed).
- [ ] T041 [P] [US2] Add the context fragment to `images/agent-codex/wrapper.py` (AGENTS.md contents + completeness: vendor base prompt undisclosed).
- [ ] T042 [P] [US2] Add the context fragment to `images/agent-pi/wrapper.py` (instruction files + completeness: complete).
- [ ] T043 [P] [US2] Add the context fragment to `images/agent-python/runner.py` (no instruction files + completeness: complete).
- [ ] T044 [US2] Merge the image fragment into `context.json` and run it through redaction in `orchestrator/run_capture.py` (depends on T039–T043).
- [ ] T045 [US2] Add the `context_kv`, `context_section`, and `env_pill` components to the specimen and master CSS in `ui/design-system/templates/run-detail/RunDetail.dc.html` and `ui/design-system/static/app.css`.
- [ ] T046 [US2] Sync the context CSS byte-for-byte into `ui/static/app.css`.
- [ ] T047 [US2] Add the `context_kv`, `context_section`, and `env_pill` macros to `ui/templates/components/macros.html`.
- [ ] T048 [US2] Build the Context tab in `ui/templates/runs/detail.html` — full snapshot, instruction-file contents, completeness statement, asset-run fields, env pills.

**Checkpoint**: Context view renders the full snapshot with correct per-harness completeness.

---

## Phase 5: User Story 3 - Browse and open runs (Priority: P2)

**Goal**: A filterable Runs list (agent, time, status, model, cost, attempts) built from disk that
works with the orchestrator stopped, plus the Report and Files tabs on the detail page.

**Independent Test**: With the orchestrator stopped, open `/runs`, confirm it lists runs from disk,
filters (agent/status/date range) work, and clicking a run opens its detail page with four tabs.

### Tests for User Story 3 ⚠️ (write first, ensure they fail)

- [ ] T049 [P] [US3] Extend `ui/tests/test_runs.py` — `/runs` list renders from disk with no Dagster reachable; filters by agent/status/date range narrow the list.
- [ ] T050 [P] [US3] Add `ui/tests/test_run_files.py` — Files tab lists output artifacts; the file API is path-safe (traversal rejected) and previews/downloads; Report tab renders report.json + notes.
- [ ] T050a [P] [US3] Add `ui/tests/test_viewer_readonly.py` — assert the viewer is read-only (FR-024): every run/viewer route is GET-only, there is no route that mutates run data, and no live-streaming endpoint exists.

### Implementation for User Story 3

- [ ] T051 [US3] Add `read_output_files(run_id)` to `ui/runs_store.py` for the Files tab (lists the run's `/output` artifacts).
- [ ] T052 [US3] Add the runs-list page (reusing the `tabbed-list` pattern) and the `file_row` component to the specimen and master CSS in `ui/design-system/templates/tabbed-list/` and `ui/design-system/static/app.css`.
- [ ] T053 [US3] Sync the list + `file_row` CSS byte-for-byte into `ui/static/app.css`.
- [ ] T054 [US3] Add the `file_row` macro to `ui/templates/components/macros.html`.
- [ ] T055 [US3] Add `GET /runs`, `GET /api/runs`, and `GET /api/runs/{run_id}/files/{path}` (path-safe via `_unsafe_name()`) to `ui/main.py`, with best-effort Dagster status enrichment that never blocks disk reads.
- [ ] T056 [US3] Create `ui/templates/runs/list.html` — filterable list (agent, status, date range) via design-system macros.
- [ ] T057 [US3] Create `ui/static/runs-list.js` — client-side filter/refresh against `/api/runs`.
- [ ] T058 [US3] Add the Report tab (report.json fields + notes markdown) and the Files tab (file_row list, preview/download) to `ui/templates/runs/detail.html`.

**Checkpoint**: Full browse → open flow works from disk with the orchestrator stopped.

---

## Phase 6: User Story 4 - Compare two runs (Priority: P3)

**Goal**: Select any two runs and see a field-by-field diff of their context snapshots; a single
config change surfaces exactly one difference.

**Independent Test**: Rerun an agent changing only its effort, open `/runs/compare?a=&b=`, and
confirm exactly one difference is shown.

### Tests for User Story 4 ⚠️ (write first, ensure they fail)

- [ ] T059 [P] [US4] Add `ui/tests/test_compare.py` — two fixture `context.json` differing by one field yield a single diff row; harness-specific fields present on only one side are shown as present-on-one, not equated.

### Implementation for User Story 4

- [ ] T060 [US4] Add the context field-by-field diff logic (added/removed/changed) to `ui/runs_store.py`.
- [ ] T061 [US4] Add the compare diff-row component to the specimen + master CSS, sync into `ui/static/app.css`, and add its macro to `ui/templates/components/macros.html`.
- [ ] T062 [US4] Add `GET /runs/compare?a=&b=` to `ui/main.py` (any two runs; path params through `_unsafe_name()`).
- [ ] T063 [US4] Create `ui/templates/runs/compare.html` — field-by-field diff render.

**Checkpoint**: Compare surfaces exactly the changed fields between two snapshots.

---

## Phase 7: User Story 5 - Control run retention (Priority: P3)

**Goal**: A Settings page with a Retention section (keep forever / prune after N days) persisted to
`settings.yaml`, a nightly prune job that removes only events+transcript, and pruned-run rendering.

**Independent Test**: Set retention to 1 day, back-date a run dir, run the prune job, confirm
events+transcript are gone while report+context+outputs remain and the run opens with a
"conversation pruned" note.

### Tests for User Story 5 ⚠️ (write first, ensure they fail)

- [ ] T064 [P] [US5] Add `orchestrator/tests/test_prune.py` — a back-dated fixture run: prune removes only `events.jsonl`+`transcript.jsonl`, keeps report/context/outputs; `keep_forever` is a no-op.
- [ ] T065 [P] [US5] Add `ui/tests/test_settings.py` — `settings_store` read/write preserves unknown keys; the Settings page renders; a pruned run renders the "conversation pruned" note.

### Implementation for User Story 5

- [ ] T066 [US5] Create `ui/settings_store.py` — read/write the `retention` block in `settings.yaml`, preserving unknown keys (contracts/settings.md).
- [ ] T067 [US5] Create `orchestrator/prune.py` — for each run dir older than `days`, remove only `events.jsonl` + `transcript.jsonl`; never touch report/context/`/output`; `keep_forever` → no-op.
- [ ] T068 [US5] Register the nightly `sched_prune_runs` Dagster schedule (in `cron_timezone()`) in `orchestrator/factory.py` and expose it via `orchestrator/definitions.py`.
- [ ] T069 [US5] Add the Settings retention-section components to the specimen + master CSS, sync into `ui/static/app.css`, and add any new macros to `ui/templates/components/macros.html`.
- [ ] T070 [US5] Add `GET /settings` and `POST /api/settings/retention` (validate + persist) to `ui/main.py`, keeping the existing theme picker.
- [ ] T071 [US5] Create `ui/templates/settings/page.html` — Retention section (keep forever / prune after N days).
- [ ] T072 [US5] Add the retention form handling to `ui/static/settings.js`.
- [ ] T073 [US5] Render the "conversation pruned" note in `ui/templates/runs/detail.html` when `conversation_available` is false (distinct from a live run), driven by `runs_store`.

**Checkpoint**: Retention persists, the nightly job prunes correctly, pruned runs still open.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T074 [P] Add the Retention section and update the Layout run-directory description in `README.md` (FR-029), including the debugging examples (README ~L93, L493-499) whose transcript path changes from flat `runs/<agent>/<date>/<run-id>.jsonl` to `runs/<agent>/<date>/<run-id>/transcript.jsonl`. The `agent-logs -> runs` compat symlink is unaffected (it points at the `runs/` root) — no bootstrap change needed.
- [ ] T075 [P] Update the debugging runbook in `CLAUDE.local.md` for the new run-directory layout (transcript/events/context/report).
- [ ] T076 Run the design-system hygiene gates (`ui/tests/test_conformance.py`, `test_ui_consistency.py`, `test_design_system_sync.py`) and fix any literal-color/inline-style/CSS-sync violations across the new templates.
- [ ] T077 Execute the `quickstart.md` scenarios end-to-end (all five stories + the redaction guarantee) and confirm SC-001..SC-008.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–7)**: all depend on Foundational.
  - US1 (P1) and US2 (P1) are the MVP core and can proceed in parallel after Phase 2.
  - US3 (P2) depends only on Phase 2 (it adds the list + Report/Files tabs); best after US1/US2 so the detail tabs are populated. **Note (by design)**: the four-tab detail *shell* is built in Foundational (T018-T019) because both P1 stories render into it, so US3's acceptance scenario 4 ("page presents four distinct tabs") is partly satisfied before US3 — a deliberate trade of strict per-story independence for a single shared shell.
  - US4 (P3) depends on US2's `context.json` builder (it diffs snapshots).
  - US5 (P3) depends only on Phase 2 (run dirs + runs_store).
- **Polish (Phase 8)**: after the desired stories are complete.

### Within Each User Story

- Tests are written first and must fail before implementation.
- Design-system promotion is ordered: specimen/master CSS → byte-equal sync → macros → templates.
- Per-harness `to_events`/fragments (T025–T028, T040–T043) precede the shared `run_wrapper`/merge wiring (T029, T044).

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T005, T007, T009, T012, T014 (tests) in parallel; T006/T008 (distinct libs) in parallel with T004. T010a follows T010 (both touch `factory.py`/capture wiring — not parallel with T011).
- US1: all four harness event tests (T020–T023) and the four `to_events` implementations (T025–T028) run in parallel.
- US2: all four context-fragment implementations (T040–T043) run in parallel; the three test tasks (T036–T038) run in parallel.
- Across teams: US1, US2, and US5 can be built concurrently once Phase 2 lands.

---

## Parallel Example: User Story 1

```bash
# Tests first, in parallel (distinct files):
Task: "images/tests/test_claude_events.py"
Task: "images/tests/test_codex_events.py"
Task: "images/tests/test_pi_events.py"
Task: "images/tests/test_api_events.py"

# Then the four harness translators, in parallel (distinct files):
Task: "to_events() in images/agent-claude/wrapper.py"
Task: "to_events() in images/agent-codex/wrapper.py"
Task: "to_events() in images/agent-pi/wrapper.py"
Task: "synthesised events in images/agent-python/runner.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup.
2. Phase 2: Foundational (capture pipeline + disk reader + detail shell).
3. Phase 3: User Story 1 (Conversation view).
4. **STOP and VALIDATE**: run one agent per harness, confirm the identical threaded shape.

### Incremental Delivery

1. Setup + Foundational → run directories captured, detail page opens from disk.
2. US1 → uniform Conversation view (MVP).
3. US2 → Context snapshot view (transparency complete for a single run).
4. US3 → browsable/filterable Runs list, Report + Files tabs.
5. US4 → Compare.
6. US5 → Retention + Settings.

---

## Notes

- [P] = different files, no dependency on incomplete tasks.
- Redaction is a single orchestrator-owned pass (Phase 2); no harness image redacts.
- The viewer is strictly read-only and disk-only; Dagster enrichment is best-effort, never a precondition.
- Env variable values are never captured to disk anywhere (FR-015) — by construction, not by redaction.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
</content>
</invoke>
