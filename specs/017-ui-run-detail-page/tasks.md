---

description: "Task list for feature 017 — Run Detail Page"
---

# Tasks: Run Detail Page

**Input**: Design documents from `/specs/017-ui-run-detail-page/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md,
contracts/ (run-detail.md, design-system.md), quickstart.md

**Feature branch**: `207-ui-run-detail-page` (the `specs/017-…` directory and the `207-…` branch name
both refer to this one feature — plan.md "Directory/branch note").

**Tests**: INCLUDED. The spec makes the UI suite the acceptance gate (SC-010) and quickstart.md names
the exact test surfaces, so test tasks are first-class here (not optional).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1–US7); Setup/Foundational/Polish carry no label
- Every task names an exact product-tree file path

## Path Conventions

Single-package UI feature (plan.md "Structure Decision"): all product code under `ui/` plus the design
system it owns (`ui/design-system/`). Tests sit in `ui/tests/`. No orchestrator, image, litellm, or
scripts change. Never write tasks against `config/` or `/data/…` (instance config/state).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Working dev environment and a known-green baseline before any change.

- [ ] T001 Set up the repo-root venv and install UI deps per AGENTS.md → Dev environment:
  `python3.12 -m venv .venv && .venv/bin/pip install -r ui/requirements.txt dagster==1.13.21 dagster-pipes==1.13.21`.
- [ ] T002 Record the green baseline: run `.venv/bin/python -m pytest -q ui/tests` and confirm it passes
  before any change (so regressions are attributable).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared building blocks every section depends on — the design-system **Disclosure**
component + macro (used by all five sections, FR-037 design-system-first) and the golden run fixture
every story test reads.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Add a shared golden run fixture that exercises **every** section, under `ui/tests/` (extend
  `ui/tests/conftest.py` and/or a `ui/tests/fixtures/` run tree): a `report.json` with a markdown
  `notes` final message (heading, bold, code span, bullet list, URL); an `events.jsonl` with tool calls
  whose IN/OUT exceed 3 lines, a diff result, a `missing`/refused result, a GitHub `pull/N` `html_url`
  result, a git commit result with a short SHA, and a workspace write; a `context.json` with prompt +
  appended system prompt + ≥1 instruction file; plus a legacy run variant with neither report notes nor
  a final event (SC-010, quickstart "Automated validation"). Blocks all story tests.
- [ ] T004 [P] Add the **Disclosure / section-card** design-system component:
  `ui/design-system/components/layout/Disclosure.jsx` (+ `Disclosure.d.ts`, `Disclosure.prompt.md`) — a
  bordered card with a full-width, keyboard-operable disclosure header (chevron reflecting state, title,
  right-aligned muted closed-state note, `aria-expanded`, Enter/Space) — and a specimen in the layout
  category `*.card.html` (FR-003, contract design-system.md §1).
- [ ] T005 Register Disclosure in `ui/design-system/_ds_manifest.json` (name + sourcePath + a
  `startingPoints` specimen), rebuild `ui/design-system/_ds_bundle.js`, and document it in
  `ui/design-system/readme.md` (FR-037, SC-010). (Depends on T004.)
- [ ] T006 Add the shared `disclosure` / `section_card` macro in
  `ui/templates/components/macros.html` mirroring the Disclosure component (bordered card, disclosure
  header with chevron, title, right-aligned muted `note`, body slot, stable `id`/`aria-controls`)
  (FR-003). (Depends on T005.)
- [ ] T007 [P] Add tokens-only styling for the section card / header / chevron / note in
  `ui/static/app.css` — colours, spacing, type, radius, border all via `var(--…)` tokens, no literals,
  no inline styles (FR-036, SC-009).

**Checkpoint**: The Disclosure macro renders a bordered, keyboard-operable collapsible card and the
golden fixture exists — user stories can now build their sections on top.

---

## Phase 3: User Story 1 — Sectioned layout, defaults, and per-browser persistence (Priority: P1) 🎯 MVP

**Goal**: Replace the two-view main column with five collapsible sections (Summary, Output, Checks,
Context, Transcript) in fixed order, with the FR-002 open/closed defaults, per-browser persistence
shared across all `/runs/{id}` pages, closed-state notes, and the header/rail preserved (except the two
moves handled in US3/US4). Each section wraps today's content as a minimal body; later stories enrich
each body.

**Independent Test**: Open a completed run — the main column is exactly five sections in order;
Summary/Output/Checks/Transcript open and Context collapsed on first load; each closed section shows a
chevron, title, and right-aligned note; collapse a section, reload → state remembered; open a different
run → same choice applies (shared per browser); fresh profile / disabled localStorage → defaults, no
error; header + six-stat strip unchanged.

- [ ] T008 [P] [US1] Add the section-note builder helpers in `ui/runs_store.py` (or a small
  `_section_notes` block) for the plumbing US1 owns — Context note "prompt · appended · N instruction
  file(s)" and Transcript note "N turns · M tool calls" — plus signatures for the Summary/Output/Checks
  notes that US3/US4/US5 fill in (FR-020/FR-034/FR-009/FR-014/FR-018).
- [ ] T009 [US1] Rework `_run_detail_page` in `ui/main.py` to build an ordered list of five Section
  view models (`id`, `title`, `default_open`, `note`, `body`) — Summary/Output/Checks/Transcript
  `default_open=True`, Context `default_open=False` — each body wrapping today's content as a starting
  point, and pass the list to the template. No route-signature change; still disk-first via
  `runs_store.read_run` (FR-001/FR-002, contract run-detail.md §A). (Depends on T003.)
- [ ] T010 [US1] Replace the two-view main column in `ui/templates/runs/detail.html` with the five
  section cards rendered from the `disclosure` macro over the section list, preserving the page header,
  crumb, status tag, agent/date chips, "View in Dagster" link and the six-stat strip unchanged
  (FR-001/FR-005). (Depends on T006, T009.)
- [ ] T011 [US1] Implement section disclosure toggle + persistence in `ui/static/run-detail.js`: a
  single shared `localStorage` key `agentbox.runDetail.sections` mapping section id → open (NOT keyed
  per run id), applying saved state over server defaults on load, keyboard (Enter/Space) toggle with
  `aria-expanded` updates, and a safe fallback to the FR-002 defaults when localStorage is unavailable
  (no error) (FR-003/FR-004). (Depends on T010.)
- [ ] T012 [US1] Tests in `ui/tests/test_runs.py`: exactly five sections in the fixed order; the FR-002
  open/closed defaults present in the rendered markup; each closed section renders a chevron + title +
  right-aligned note; the header and six-stat strip are unchanged (FR-001/FR-002/FR-003/FR-005,
  SC-001). (Depends on T009, T010.)

**Checkpoint**: The five-section shell is live, persists per browser, and is independently testable.

---

## Phase 4: User Story 2 — IN/OUT tool cards (Priority: P1)

**Goal**: Render every transcript tool invocation as a compact IN/OUT card — head line (name,
description, right-aligned `exit N`/`failed`), IN and OUT rows clamped to 3 lines with a fade + "Show
all N lines" link when overflowing, click/keyboard expand-collapse, diff colouring preserved, and a
transcript-toolbar Expand-all/Collapse-all (view-only, non-persistent).

**Independent Test**: A tool call with many OUT lines shows 3 lines + fade + "Show all N lines"; click
expands and shows "Show less"; a ≤3-line call shows no fade/link; Expand-all expands every card and
becomes Collapse-all, an individual card still collapses while "all" is on; a refused write shows
`failed` and its OUT reads in the failed colour; a diff preserves its colouring; reload → cards clamped.

- [ ] T013 [P] [US2] Add the **IN/OUT tool card** design-system component
  `ui/design-system/components/data/ToolCard.jsx` (+ `ToolCard.d.ts`, `ToolCard.prompt.md`) and a
  specimen in the data category `*.card.html`: head line (name, ellipsised description, right-aligned
  mono marker), IN/OUT rows clamped to 3 lines with a token-**background** fade only when overflowing,
  diff OUT expanded by default, missing/failed OUT intents (FR-021–FR-027, contract design-system.md
  §2). (Depends on T004 pattern; independent file.)
- [ ] T014 [US2] Register ToolCard in `ui/design-system/_ds_manifest.json`, rebuild
  `ui/design-system/_ds_bundle.js`, document it in `ui/design-system/readme.md` (FR-037). (Depends on
  T013.)
- [ ] T015 [US2] Add the `tool_card` macro in `ui/templates/components/macros.html` (props: `name`,
  `description`, `marker`, `in_text`/`out_text`, `in_overflow`/`out_overflow`, `in_lines`/`out_lines`,
  `is_diff`, `out_intent`) — leaving the existing `tool_call`/`timeline`/`diff_block`/`tool_out` macros
  untouched for the compare page (FR-037). (Depends on T014.)
- [ ] T016 [US2] Add tool-card enrichment in `ui/runs_store.py` over each tool from
  `conversation_entries(events)`: `description` (call description → file path for read/write/edit → arg
  summary), `marker` (`failed` when `missing` or a permission-refusal marker; `exit N` only when the
  result text carries a recognizable exit code; else none), `in_text`/`out_text`,
  `in_overflow`/`out_overflow` (`line_count > 3`), `in_lines`/`out_lines`, `is_diff` (expanded by
  default), `out_intent` (failed/warning colour). Pure, read-path only (FR-021–FR-027, R6/R7, contract
  run-detail.md §C).
- [ ] T017 [US2] Render the Transcript section's tool invocations with the `tool_card` macro in
  `ui/templates/runs/detail.html` (replacing US1's minimal transcript body for tool entries) and add a
  transcript toolbar with the outlined ghost **Expand all / Collapse all output** control (FR-028).
  (Depends on T015, T016, T010.)
- [ ] T018 [US2] Add clamp/expand behaviour in `ui/static/run-detail.js`: per-card `is-expanded` toggle
  on row/link click and via keyboard (Enter/Space, `aria-expanded`), flip "Show all N lines" ↔ "Show
  less", and the Expand-all/Collapse-all toolbar toggle that is **view-only and does not persist**
  (resets to clamped on reload) while still allowing single-card collapse (FR-025/FR-028). (Depends on
  T017.)
- [ ] T019 [P] [US2] Add tokens-only styling for the tool card (head, IN/OUT box ground, 3-line clamp,
  fade following the **background** token, marker mono, failed/warning OUT intents) in
  `ui/static/app.css` (FR-024/FR-026/FR-027/FR-036, SC-009).
- [ ] T020 [US2] Tests in `ui/tests/test_runs_store.py` (clamp overflow > 3 lines; `exit`/`failed`
  derivation; description fallback order) and `ui/tests/test_runs.py` (a card renders with `exit N`/
  `failed`, an overflowing OUT shows the "Show all N lines" affordance, a ≤3-line row shows none, a diff
  OUT is expanded) (SC-005/SC-006, FR-022/FR-024). (Depends on T016, T017.)

**Checkpoint**: Long transcripts are scannable; tool cards clamp/expand independently of the other
sections.

---

## Phase 5: User Story 3 — Summary as formatted text (Priority: P1)

**Goal**: The Summary section renders the agent's final message as a safe markdown subset with the
`report.notes` → final-event → foot-line fallback ladder, and the final-message notes leave the rail.

**Independent Test**: A run whose report notes carry heading/bold/code/bullets renders each as
formatted text with no raw markup; a run with no notes but a final event shows the event text; a legacy
run with neither shows the foot line + "No final message was captured."; the rail's Usage block no
longer shows the notes.

- [ ] T021 [P] [US3] Add **`ui/markdown.py`** — a dependency-free `render_summary(text) -> Markup` that
  escapes all input first, then emits only the FR-007 subset (paragraphs, `##`/`###` → small uppercase
  labels, `**bold**`, `` `inline code` ``, `-`/`*` bullet lists, bare/`[label](url)` URLs → links) and
  renders everything else as escaped plain text — **no raw HTML pass-through** (FR-007, R2, contract
  run-detail.md §D).
- [ ] T022 [P] [US3] Add the **Summary** design-system component
  `ui/design-system/components/data/Summary.jsx` (+ `.d.ts`, `.prompt.md`) and a data-category specimen:
  headings as small uppercase labels, bold, inline-code chips, bullet lists, links, plus a `fallback`
  slot — tokens only (FR-007, contract design-system.md §5). (Depends on T004 pattern; independent
  file.)
- [ ] T023 [US3] Register Summary in `ui/design-system/_ds_manifest.json`, rebuild
  `ui/design-system/_ds_bundle.js`, document it in `ui/design-system/readme.md` (FR-037). (Depends on
  T022.)
- [ ] T024 [US3] Add the `summary` macro in `ui/templates/components/macros.html` (props: `html`,
  optional `fallback`) (FR-007). (Depends on T023.)
- [ ] T025 [US3] Build the Summary view model in `ui/main.py`: source precedence `report.notes` →
  final event text → none; when none, the run **foot line** (status · turns · files written) + note
  "No final message was captured."; otherwise render via `render_summary` and set the note "final
  message from the agent" (FR-008/FR-009, R3). (Depends on T021, T009.)
- [ ] T026 [US3] Render the Summary section body with the `summary` macro in
  `ui/templates/runs/detail.html`, and **remove the `report.notes` line** from the rail's Usage block in
  `ui/templates/runs/_rail.html` (it now lives only in the Summary) (FR-006/US3-AC4). (Depends on T024,
  T025.)
- [ ] T027 [P] [US3] Add tokens-only styling for the rendered summary (heading label, code chip, list,
  link) in `ui/static/app.css` (FR-036, SC-009).
- [ ] T028 [US3] Tests: `ui/tests/test_runs.py` — the three fallback cases render correctly and the
  rail no longer carries the notes; add a golden/byte assertion for the reference-message rendering (no
  raw markup, `<script>`/tables not passed through) covering `ui/markdown.py` (SC-003/SC-008, FR-007).
  (Depends on T025, T026.)

**Checkpoint**: The operator's first question ("did it work") is answered by a readable Summary at the
top.

---

## Phase 6: User Story 4 — Output, including produced elsewhere (Priority: P2)

**Goal**: The Output section lists `/output` artifacts as file rows, and when there are none shows "No
output artifacts" plus a best-effort Produced-elsewhere list (PRs → commits → files) mined from the
event stream; the output artifacts leave the rail; the note counts what was produced.

**Independent Test**: A run with files shows file rows; a run with no files that opened a PR and pushed
a commit shows "No output artifacts" then a Produced-elsewhere list (Pull request row + Commit short
SHA) each with an Open action and the note "0 files · 1 pull request"; a run with no minable evidence
shows the file list / "No output artifacts" alone.

- [ ] T029 [US4] Add `produced_elsewhere(events) -> list[dict]` to `ui/runs_store.py` — a pure,
  best-effort miner returning `{kind, identifier, action}` grouped **pull_request → commit → file**,
  event order within each kind: PR = a `tool_result` whose `result` contains a `https://github.com/…/
  pull/N` URL; commit = a git result with a 7–40 hex short SHA after a commit/push marker; file = a
  Write/Edit/MultiEdit/NotebookEdit `tool_call` with a `file_path`/`path` arg. Returns `[]` when nothing
  matches; never raises (FR-011/FR-012/FR-013, R4, contract run-detail.md §B).
- [ ] T030 [US4] Add the Output note builder in `ui/runs_store.py`: "N files · M pull request(s)", each
  part only when non-zero, "0 files" alone when nothing produced (FR-014).
- [ ] T031 [P] [US4] Add the **Produced-elsewhere row** design-system component
  `ui/design-system/components/data/ProducedRow.jsx` (+ `.d.ts`, `.prompt.md`) and a data-category
  specimen: kind label (Pull request / Commit / File), identifier in mono, Open/Preview action
  (FR-012, contract design-system.md §4). (Independent file.)
- [ ] T032 [US4] Register ProducedRow in `ui/design-system/_ds_manifest.json`, rebuild
  `ui/design-system/_ds_bundle.js`, document it in `ui/design-system/readme.md` (FR-037). (Depends on
  T031.)
- [ ] T033 [US4] Add the `produced_row` macro in `ui/templates/components/macros.html` (props: `kind`,
  `identifier`, `action`) (FR-012). (Depends on T032.)
- [ ] T034 [US4] Build the Output view model in `ui/main.py` (files via `read_output_files`; `produced`
  via `produced_elsewhere` shown when files empty and evidence exists; the Output note) (FR-010–FR-014).
  (Depends on T029, T030, T009.)
- [ ] T035 [US4] Render the Output section in `ui/templates/runs/detail.html` — the existing `file_row`
  macro for artifacts, then "No output artifacts" + the `produced_row` list when applicable — and
  **remove the Output-artifacts block** from `ui/templates/runs/_rail.html` (FR-006/FR-010/FR-011).
  (Depends on T033, T034.)
- [ ] T036 [P] [US4] Add tokens-only styling for the produced-elsewhere row (kind label, mono
  identifier, action) in `ui/static/app.css` (FR-036, SC-009).
- [ ] T037 [US4] Tests: `ui/tests/test_runs_store.py` (`produced_elsewhere` PR/commit/file detection,
  grouping order, `[]` on no evidence, no raise on garbage; the Output note builder) and
  `ui/tests/test_runs.py` (the Output section renders file rows / the produced list / "No output
  artifacts" alone; the note reads "0 files · 1 pull request"; the rail no longer carries artifacts)
  (SC-004, FR-011–FR-014). (Depends on T029, T030, T034, T035.)

**Checkpoint**: The operator's second question ("what did it produce") is answered, including PRs/
commits made outside `/output`.

---

## Phase 7: User Story 5 — Checks (Priority: P2)

**Goal**: The Checks section surfaces the run's recorded checks in the Agents-overview mark language
(mark + icon, name, one-line detail, right-aligned recorded time), read best-effort from
`dagster.run_status([run_id])`, degrading to the empty state + "—" note when Dagster is unreachable.

**Independent Test**: A run with checks shows each with a pass/warn/fail mark + icon, name, detail and
recorded time, and the note counts outcomes (e.g. "4 passed · 1 warning"); a run with no checks (or
Dagster stopped) shows "No checks were configured for this agent." and the note reads "—".

- [ ] T038 [US5] Extend the check sub-selection in `ui/dagster.py` (`_ASSET_CHECKS_SUBQUERY` and its
  parse in `_run_checks_by_id`) to **additively** select each execution's **timestamp** and a one-line
  **detail** (evaluation description → severity), so each check becomes `{name, status, detail,
  recorded}`; absent fields degrade to `—`; every existing failure arm still collapses to plain data so
  the section degrades to empty when Dagster is unreachable (FR-015/FR-016, R5, contract run-detail.md
  §E). No new query, no new check types, read-only.
- [ ] T039 [US5] Add the Checks note builder in `ui/runs_store.py` (or the notes block): "K passed · L
  warning(s)" / "P failed" counting outcomes; "—" when empty (FR-017/FR-018).
- [ ] T040 [P] [US5] Add the **Check row** design-system component
  `ui/design-system/components/data/CheckRow.jsx` (+ `.d.ts`, `.prompt.md`) and a data-category
  specimen, reusing the existing `ax-result` mark + `CHECK_META` vocabulary (pass/warn/fail-blocking/
  not-run) so the mark matches the Agents overview; props `status`, `name`, `detail`, `recorded`
  (FR-015/FR-016, contract design-system.md §3). (Independent file.)
- [ ] T041 [US5] Register CheckRow in `ui/design-system/_ds_manifest.json`, rebuild
  `ui/design-system/_ds_bundle.js`, document it in `ui/design-system/readme.md` (FR-037). (Depends on
  T040.)
- [ ] T042 [US5] Add the `check_row` macro in `ui/templates/components/macros.html` (a row around the
  existing `ax-result` mark; props `status`, `name`, `detail`, `recorded`) (FR-015). (Depends on T041.)
- [ ] T043 [US5] Build the Checks view model in `ui/main.py`: fetch checks best-effort via
  `dagster.run_status([run_id])`, map to `{status, name, detail, recorded}`, compute the note, and set
  the empty text "No checks were configured for this agent." when empty; the page still renders with
  Dagster stopped (FR-015/FR-017/FR-018, R5). (Depends on T038, T039, T009.)
- [ ] T044 [US5] Render the Checks section in `ui/templates/runs/detail.html` with the `check_row` macro
  (or the empty-state line) (FR-015/FR-017). (Depends on T042, T043.)
- [ ] T045 [P] [US5] Add tokens-only styling for the check row (mark, name, one-line detail,
  right-aligned recorded time) in `ui/static/app.css` (FR-036, SC-009).
- [ ] T046 [US5] Tests: `ui/tests/test_dagster.py` (the additive time + detail fields parse; the Checks
  read still degrades to `{}`/"—" when Dagster is unreachable) and `ui/tests/test_runs.py` (checks
  render with mark/name/detail/time and the outcome-count note; the empty state + "—" note when there
  are none) (SC-008, FR-015–FR-018). (Depends on T038, T043, T044.)

**Checkpoint**: The operator's third question ("did the checks pass") is answered, matching the overview
language.

---

## Phase 8: User Story 6 — Context (Priority: P2)

**Goal**: The Context section wraps the existing "Context given to the agent" card verbatim (prompt,
appended system prompt, instruction files with click-to-expand), collapsed by default, with a note
counting instruction files; harness/container/inputs/completeness stay in the rail.

**Independent Test**: Expand Context — the prompt, appended system prompt and each instruction file show
with click-to-expand rows exactly as today; the note counts instruction files; harness/container/
inputs/completeness remain in the rail in order.

- [ ] T047 [US6] Nest the existing `ui/templates/runs/_context_card.html` verbatim inside the Context
  section body in `ui/templates/runs/detail.html`, keeping its interaction unchanged, and confirm the
  Context section is collapsed by default (FR-002/FR-019). (Depends on T010.)
- [ ] T048 [US6] Wire the Context note "prompt · appended · N instruction file(s)" (counting
  `context.instruction_files`) into the Context Section view model in `ui/main.py` using the US1 note
  helper (FR-020). (Depends on T008, T009.)
- [ ] T049 [US6] Tests in `ui/tests/test_runs.py`: the Context section contains the context card content
  and is collapsed by default; the note counts instruction files; the rail still contains
  Configuration/Container/Inputs/Completeness/Asset run/Issue/Usage in order (FR-019/FR-020/US6-AC3).
  (Depends on T047, T048.)

**Checkpoint**: The operator's fourth question ("what was it given") is answered without disturbing the
rail.

---

## Phase 9: User Story 7 — Search and skim the transcript (Priority: P2)

**Goal**: The Transcript section carries search (now matching tool IN/OUT content, with auto-expand on
clamped-only matches) + match count, the relocated Readable/Raw-log control, unchanged turn entries, a
single deduped Result, and the run foot line at the bottom.

**Independent Test**: Search a term that appears only inside a tool card's IN/OUT — matching entries
stay, the rest hide, the count reports, the matching card auto-expands; clearing restores every entry
and the card's clamped state; the Readable/Raw-log toggle switches to the unchanged `transcript.jsonl`
view and back; the last assistant message + final event render once as a Result; the foot line sits at
the bottom.

- [ ] T050 [US7] Move the **Readable / Raw-log** control and the **search box + match count** into the
  Transcript section header in `ui/templates/runs/detail.html` (no longer page-level chrome); keep the
  raw `transcript.jsonl` view unchanged; ensure the last assistant message + final event dedupe to a
  single **Result** entry and the run **foot line** (status · turns · files written · tool calls)
  renders at the bottom of the section (FR-030/FR-031/FR-032/FR-033). (Depends on T017.)
- [ ] T051 [US7] Extend the transcript search in `ui/static/run-detail.js` to match message text **and**
  tool IN/OUT content, hide non-matching entries, report the match count, **auto-expand** a card that
  matches only on clamped IN/OUT while the search is active and restore its prior clamped state when the
  search is cleared; wire the relocated Readable/Raw-log toggle (FR-029/FR-030). (Depends on T050,
  T018.)
- [ ] T052 [US7] Ensure `_run_detail_page`/`runs_store` expose the Result-dedup flag and the transcript
  foot line (status · turns · files written · tool calls) to the template in `ui/main.py`
  (FR-032/FR-033). (Depends on T009.)
- [ ] T053 [US7] Tests in `ui/tests/test_runs.py`: search over IN/OUT content keeps matching entries and
  reports the count; the raw-log toggle is inside the Transcript header; the duplicate final message is
  a single Result; the foot line sits at the bottom (SC-007, FR-029–FR-033). (Depends on T050, T052.)

**Checkpoint**: The operator's fifth question ("what exactly happened") is answered with a searchable,
skimmable transcript.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Conformance, docs, and the full-suite gate across all sections.

- [ ] T054 [P] Refresh the run-detail description in `README.md` (five sections, the IN/OUT card,
  produced-elsewhere) so docs track reality (Principle VI, FR — plan.md).
- [ ] T055 Extend `ui/tests/test_design_system_sync.py` to assert manifest ↔ macro ↔ bundle parity for
  all five new components (Disclosure, ToolCard, CheckRow, ProducedRow, Summary) and
  `ui/tests/test_design_system_docs.py` to assert the readme documents each (SC-010, FR-037). (Depends
  on T005, T014, T023, T032, T041.)
- [ ] T056 Extend `ui/tests/test_conformance.py` so the new markup stays tokens-only, macro-composed,
  with no inline styles and no literal colours/pixels — including that the clamp fade colour follows the
  **background** token (FR-036, SC-009, SC-010).
- [ ] T057 Run the full gate `.venv/bin/python -m pytest -q ui/tests` and confirm every suite passes
  (runs, runs_store, dagster, conformance, ds-sync, ds-docs), including the golden fixture rendering
  every section (SC-010, quickstart "Automated validation").
- [ ] T058 Walk quickstart.md US1–US7 + the theme check against the reference run (`speckit-open-pr`,
  2026-09-18) in light/dark/Indigo, confirming the section borders, IN/OUT box ground + fade, muted OUT
  text and check marks all read correctly (SC-009).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories** (the Disclosure macro and
  the golden fixture are shared by every section).
- **User Stories (Phases 3–9)**: all depend on Foundational.
  - **US1 (P1)** is the shell every other section renders into: US2–US7 render their bodies inside the
    sections US1 creates, so in practice **US1 lands first**, then US2/US3 (P1), then US4/US5/US6/US7
    (P2). Each story remains independently testable once US1's shell exists.
- **Polish (Phase 10)**: depends on all desired stories being complete.

### Cross-story coupling (kept explicit)

- The **rail removals** are owned by the sections that absorb them: US3 removes the `report.notes` line
  from `_rail.html` (T026); US4 removes the Output-artifacts block from `_rail.html` (T035). US1's
  "header/rail unchanged" test (T012) asserts the *untouched* parts; US6's rail test (T049) asserts the
  final surviving order (Configuration/Container/Inputs/Completeness/Asset run/Issue/Usage).
- The Transcript **tool cards** (US2, T017) are a prerequisite for the Transcript **search/raw-log**
  relocation (US7, T050/T051).

### Within a story

- Design-system component (source + specimen) → manifest/bundle/readme registration → shared macro →
  view model / template render → JS behaviour → styling → tests.

### Parallel Opportunities

- Setup T001 → T002 are sequential; Foundational T004 and T007 are `[P]` (different files).
- Across stories, the **design-system component sources** are independent files and can be built in
  parallel once Foundational is done: T013 (ToolCard), T022 (Summary), T031 (ProducedRow), T040
  (CheckRow) — all `[P]`.
- The **`app.css` styling** tasks (T007, T019, T027, T036, T045) all touch the same file, so they are
  **not** mutually `[P]`; sequence them (each is `[P]` only relative to non-CSS work in its story).
- `ui/markdown.py` (T021) is a standalone new file, `[P]` with any other story's component work.

---

## Parallel Example: design-system component sources (after Foundational)

```bash
# These are independent .jsx files — build them together:
Task: "T013 Add ToolCard.jsx (+ specimen) in ui/design-system/components/data/"
Task: "T022 Add Summary.jsx (+ specimen) in ui/design-system/components/data/"
Task: "T031 Add ProducedRow.jsx (+ specimen) in ui/design-system/components/data/"
Task: "T040 Add CheckRow.jsx (+ specimen) in ui/design-system/components/data/"
```

Each component's manifest/bundle/readme registration (T014/T023/T032/T041) and its macro
(T015/T024/T033/T042) then follow per story.

---

## Implementation Strategy

### MVP First (the three P1 stories)

1. Phase 1 Setup → Phase 2 Foundational (Disclosure macro + fixture).
2. **US1** — the five-section shell with defaults + persistence. **STOP and VALIDATE** (SC-001/SC-002).
3. **US2** — IN/OUT tool cards (SC-005/SC-006).
4. **US3** — Summary as formatted text (SC-003/SC-008).
5. The page now answers "did it work / what exactly happened (scannably) / did it work in prose" — a
   shippable MVP.

### Incremental Delivery (P2)

6. **US4** Output + produced-elsewhere (SC-004) → **US5** Checks (SC-008) → **US6** Context → **US7**
   search + raw-log relocation (SC-007). Each is an independent increment behind the same shell.
7. Phase 10 Polish: README + conformance/sync/docs tests + the full-suite gate (SC-009/SC-010).

---

## Notes

- `[P]` = different files, no dependency on incomplete tasks. Same-file tasks (notably `ui/main.py`,
  `ui/templates/runs/detail.html`, `ui/static/run-detail.js`, `ui/static/app.css`,
  `ui/templates/components/macros.html`, the three `ui/design-system/_ds_*`) are **not** `[P]` with each
  other and must be sequenced.
- Presentation and read-path only: no task writes the run record, bumps `SCHEMA_VERSION`, adds a
  dependency, adds a check type, or touches the compare page / its `tool_call`/`timeline` macros
  (FR-035/FR-037).
- Run `.venv/bin/python -m pytest -q ui/tests` after each story to keep the suite green.
