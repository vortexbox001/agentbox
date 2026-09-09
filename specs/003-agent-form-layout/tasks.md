---

description: "Task list for Agent Form Layout"
---

# Tasks: Agent Form Layout

**Input**: Design documents from `/specs/003-agent-form-layout/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/schema-and-yaml.md, contracts/layout.md, quickstart.md

**Tests**: Included, scoped as in plan.md. `pytest` covers what is statically checkable: schema group/section integrity, emitter order via golden files, page markup, the layout CSS being present, and the design guide matching the stylesheet. Column behaviour at 1800/1440/900 px is verified in a browser per quickstart.md; the repo has no browser-automation harness.

**Organization**: Tasks are grouped by user story. The schema reshuffle is foundational because every story reads grouping from it and the emitter output changes the moment it lands.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1–US5 from spec.md
- Every task names the exact file(s) it touches

## Path Conventions

Single `ui/` package: schema and emitter in `ui/`, browser code in `ui/static/`, pages in `ui/templates/agents/`, design reference in `ui/design-system/`, tests in `ui/tests/`. Run tests from `ui/` with the repo venv: `cd ui && ../.venv/bin/python -m pytest -q`. Superseded contract text lives in `specs/001-agent-management-ui/`.

## Shared-file coordination (read before parallelizing)

These files are touched by more than one phase, so tasks on the same file are **sequential**, never `[P]` with each other:

- `ui/static/app.css` — US1 (groups, lead strip, base grid), US2 (three-column query), US3 (two-column query), US4 (narrow-width fixes)
- `ui/static/agent-form.js` — US1 only, but T009 and T010 are ordered
- `ui/tests/test_api.py` — US1, US2, US3, US4 markup and CSS checks
- `ui/schema.py` — Foundational (T004) and Polish (T027 comment cleanup)

US5 (contract documents) and the Polish design-guide tasks touch only markdown and their own test file, so they can run alongside any story.

---

## Phase 1: Setup

**Purpose**: A known-good baseline before changing the schema.

- [X] T001 Ensure a repo venv exists at `.venv/` (create with `python3 -m venv .venv` and `.venv/bin/pip install -r ui/requirements.txt` if absent), then run `cd ui && ../.venv/bin/python -m pytest -q` and record the passing count (206 at plan time) so regressions are obvious later

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Move the grouping into the schema. Every story and the emitter read from it, and the golden files must move with it in the same step or the suite goes red.

**⚠️ CRITICAL**: T004 and T005 must land together; the golden test fails between them.

- [X] T002 [P] Add schema integrity tests to `ui/tests/test_schema.py`: `GROUPS` is `[runs, job, box]` in order; every `SECTIONS` entry has `group` in `GROUPS` ids or `None`; exactly one section (`identity`) has `None`; every `FIELDS[].section` names a `SECTIONS` id; `FIELDS` is contiguous by section in `SECTIONS` order; `public_schema()` returns `groups` and `sections` each carrying `group`; every field's `section` in the data-model.md re-homing table matches (data-model.md "Field re-homing"). Confirm these fail before T004
- [X] T003 [P] Add an emitter order test to `ui/tests/test_agents_store.py`: for each `GOLDEN` definition, the `# --- … ---` headers in `emit_yaml()` output appear in `schema.SECTIONS` label order and `name:` is the first key line. Confirm it fails before T004 (headers are still the old labels)
- [X] T004 Rework `ui/schema.py` per contracts/schema-and-yaml.md §1: add `GROUPS: list[dict]` (`runs`/Runs, `job`/Job, `box`/Box); replace `SECTIONS` with the nine entries from data-model.md each carrying `"group"` (`identity` → `None`); change every `SchemaField.section` to its new id per the re-homing table; reorder `FIELDS` so fields are contiguous by section in `SECTIONS` order (`name`; `enabled`, `schedule`; `timeout_seconds`, `max_turns`; `prompt_file`, `append_system_prompt`; `workspace`, `wipe_workspace`, `output_dir`; `env_file`, `env`; `permission_mode`, `allowed_tools`, `disallowed_tools`, `mcp_config`; `harness`, `model`, `effort`, `fallback_model`, `max_tokens`; `network`, `memory`, `cpus`); expose `"groups": [dict(g) for g in GROUPS]` in `public_schema()` next to `sections`. Do not touch types, defaults, help, validation, or `harnesses`
- [X] T005 Regenerate `ui/tests/golden/{claude-code,pi,api,codex}.yaml` with the quickstart §2 one-liner, then review `git diff ui/tests/golden/` and confirm every hunk is a moved block or a renamed `# --- … ---` header with no value line changed
- [X] T006 Run `cd ui && ../.venv/bin/python -m pytest -q` and confirm green, including T002/T003 and `test_repo_agents_round_trip` (every real `agents/*.yaml` still round-trips)

**Checkpoint**: `/api/schema` serves groups and the new sections; files emit in the new order; the form still renders (eight or nine cards in one column, old renderer) because it only reads `sections` and `fields`.

---

## Phase 3: User Story 1 — Fields regrouped into Runs, Job, and Box (Priority: P1) 🎯 MVP

**Goal**: The form renders the three labelled groups with their cards, the name in a lead strip, the template picker beside it on the create screen, and the reload toggle first under Save. Single column at this point; the arrangements come in US2–US4.

**Independent Test**: Open the edit screen of a claude-code agent and the create screen, and check every card and field placement against data-model.md and quickstart §3, including harness switching.

### Tests for User Story 1

- [X] T007 [US1] Add page markup checks to `ui/tests/test_api.py`: `GET /agents/new` and `GET /agents/<existing>` contain `id="ax-form-lead"` with class `ax-form-lead`, `id="ax-form-lead-fields"`, and `id="ax-form-sections"` carrying class `ax-grid-agent`; the `ax-form-actionbar` appears before `ax-form-lead`, which appears before `ax-form-sections` in the HTML; on the create page `id="ax-template-select"` sits inside the lead strip and the lead strip has no `ax-card` class. Confirm they fail before T008

### Implementation for User Story 1

- [X] T008 [US1] Restructure `ui/templates/agents/form.html` per contracts/layout.md §1: keep `.ax-form-actionbar` as the form's first child; replace the create-mode `div.ax-card.ax-form-lead` with `div#ax-form-lead.ax-form-lead.ax-grid-form` that holds the existing template-picker `label.ax-field` (create mode only) followed by an always-present `div#ax-form-lead-fields`; add class `ax-grid-agent` to `div#ax-form-sections[data-sections]`, leaving the `#ax-form-loading` placeholder inside it
- [X] T009 [US1] Rework `renderForm` in `ui/static/agent-form.js` per research R4/R5: clear `#ax-form-lead-fields` and the sections mount; build one `section.ax-form-group[data-group=<id>]` per `SCHEMA.groups` with an `h2.ax-form-section-heading` showing the group label; for each `SCHEMA.sections` entry, compute its applicable fields and either append them straight into the lead mount (when `group` is `null`, no card) or build the existing `section.ax-card.ax-form-section` (h2 + `.ax-grid-form`) and append it to its group container; append the three group containers to the sections mount; call `enhanceSelects` on the form rather than only the sections mount
- [X] T010 [US1] Scope field lookups in `ui/static/agent-form.js` to the whole form so the lead-strip name field is found: `lockName` (`[data-field="name"]`), the validation error mapper (`[data-field="${fid}"]`), the error-clearing loops (`.ax-field-error`, `[aria-invalid]`), and any other `sectionsMount.querySelector` that may target `name` must query `form` instead; leave the network-warning lookup as is
- [X] T011 [US1] Add group and lead-strip styles to `ui/static/app.css` per contracts/layout.md §2–3: `.ax-form-group { display:flex; flex-direction:column; gap: var(--ax-space-9); min-width:0 }`, `.ax-form-group > .ax-form-section { margin-bottom: 0 }`, group heading margin `var(--ax-space-6)`, the base `.ax-grid-agent` (single-column `grid-template-areas: "runs" "job" "box"`, `gap: var(--ax-space-9)`, `align-items:start`) with the three `grid-area` assignments, and `container-type: inline-size; container-name: ax-content` on `.ax-content`; drop the `.ax-form-lead .ax-field { max-width … }` rule so the lead grid governs cell width. Tokens only, no colour or font literals
- [X] T012 [US1] Manually verify quickstart §3 and §5 on the running UI: card contents per harness (claude-code, api, pi, codex), lead strip read-only in edit and editable in create, harness switch keeps groups in place, inline validation error appears and is focused in the Container card, env secret warning still appears in the Environment card, unsaved-changes guard still fires; note results

**Checkpoint**: Grouping, lead strip, and toggle position complete; page is a single column of three labelled groups at every width.

---

## Phase 4: User Story 2 — Three columns on a wide screen (Priority: P1)

**Goal**: At a content-pane width of 1320px or more (1800px viewport) the groups sit side by side, Runs | Job | Box, with Job on a 1.4fr track and cards at natural height.

**Independent Test**: Open the edit screen at 1800px wide and confirm three columns, Job visibly wider, no stretched cards, no horizontal scroll (quickstart §4 row 1).

### Tests for User Story 2

- [X] T013 [US2] Extend the CSS presence checks in `ui/tests/test_api.py` (or the static-CSS helper spec 002 added there): `app.css` contains an `@container ax-content (min-width: 1320px)` block whose `.ax-grid-agent` rule declares `grid-template-areas: "runs job box"` and columns `minmax(0, 1fr) minmax(0, 1.4fr) minmax(0, 1fr)`. Confirm it fails before T014

### Implementation for User Story 2

- [X] T014 [US2] Add the three-column container query to `ui/static/app.css` directly after the base `.ax-grid-agent` block, exactly as in contracts/layout.md §2 (`min-width: 1320px`, areas `"runs job box"`, tracks `minmax(0, 1fr) minmax(0, 1.4fr) minmax(0, 1fr)`)
- [X] T015 [US2] Manually verify at 1800px viewport per quickstart §4: three columns in order, Job widest, Runs cards stacked from the top with empty space below, wide controls span their card, no horizontal scrollbar; also check 2560px still gives three columns with no page scroll

**Checkpoint**: Wide screens show the target layout; narrower screens still fall back to one column.

---

## Phase 5: User Story 3 — Two columns on a mid-width screen (Priority: P2)

**Goal**: Between 720px and 1319px of pane width (1440px viewport) Runs sits top-left with Box folded under it, and Job takes the right column for the full height.

**Independent Test**: Open the edit screen at 1440px wide and confirm the left column is Runs then Box and the right column is Job (quickstart §4 row 2).

### Tests for User Story 3

- [X] T016 [US3] Extend the CSS checks in `ui/tests/test_api.py`: `app.css` contains an `@container ax-content (min-width: 720px)` block whose `.ax-grid-agent` rule declares `grid-template-areas: "runs job" "box job"` and two `minmax(0, 1fr)` tracks, and that this block precedes the 1320px block in the file (so the wider query wins). Confirm it fails before T017

### Implementation for User Story 3

- [X] T017 [US3] Add the two-column container query to `ui/static/app.css` between the base block and the 1320px block, exactly as in contracts/layout.md §2 (`min-width: 720px`, areas `"runs job" "box job"`, tracks `minmax(0, 1fr) minmax(0, 1fr)`); Job spans both rows by area name, no explicit row spans
- [X] T018 [US3] Manually verify at 1440px viewport per quickstart §4: two columns, Runs over Box on the left with both headings, Job on the right beside both; then drag the width across roughly 1596px and 996px of viewport and confirm the layout snaps between three, two, and one columns with no intermediate state

**Checkpoint**: All three arrangements exist; the remaining story hardens the narrow case.

---

## Phase 6: User Story 4 — One column on a narrow screen (Priority: P2)

**Goal**: Below 720px of pane width (900px viewport) the groups stack Runs, Job, Box, headings intact, nothing clipped.

**Independent Test**: Open the edit screen at 900px wide and confirm the stack order and that an Environment card with three variables fits without horizontal scroll (quickstart §4 row 3).

### Tests for User Story 4

- [X] T019 [US4] Extend the CSS checks in `ui/tests/test_api.py`: the base `.ax-grid-agent` rule (outside any container query) declares `grid-template-areas: "runs" "job" "box"` and `align-items: start`, and `.ax-form-group` declares `min-width: 0`. Confirm they pass or fail as expected against T011's CSS

### Implementation for User Story 4

- [X] T020 [US4] Verify at 900px and at 600px viewport per quickstart §4 row 3 and fix any overflow in `ui/static/app.css`: the lead strip cells (template picker and name) wrap onto separate rows; env rows (key, value, remove) fit or wrap inside the Environment card; chip editors and the prompt picker stay within their card; no horizontal page scroll. Apply fixes only with `min-width: 0`, `minmax(0, …)`, or `flex-wrap`, never with fixed widths

**Checkpoint**: Every width from 600px to 2560px renders one definite arrangement with no horizontal scroll.

---

## Phase 7: User Story 5 — YAML files follow the same grouping (Priority: P3)

**Goal**: Files on disk read in the Runs, Job, Box order, and the written contract says so in one place.

**Independent Test**: Save an existing agent unchanged and confirm its file's headers and key order match contracts/schema-and-yaml.md §2 with values untouched (quickstart §6).

### Implementation for User Story 5

- [X] T021 [P] [US5] Amend `specs/001-agent-management-ui/contracts/agent-yaml.md` §2: replace the enumerated section list with a sentence that the order is defined in `specs/003-agent-form-layout/contracts/schema-and-yaml.md` §2, and update the example file's `# --- … ---` headers and key order in that document to the new grouping
- [X] T022 [P] [US5] Update `specs/001-agent-management-ui/contracts/http-api.md`: the `/api/schema` example gains `groups` and shows the new `sections` shape with `group`, pointing at `specs/003-agent-form-layout/contracts/schema-and-yaml.md` §1 for the full list
- [X] T023 [P] [US5] Relabel the applicability matrix rows in `specs/001-agent-management-ui/data-model.md` from the old section names (Identity, Model, Prompt & output, Workspace, Execution, Scheduling, Container resources, Environment) to the new card names, keeping the field lists and harness columns unchanged
- [X] T024 [US5] Manually verify quickstart §6 on the running UI: save `agents/repo-librarian-agentbox-fable.yaml` (or any real agent) without edits, run `git diff agents/`, confirm only moved lines and renamed headers; add a hand-written unmanaged key, save again, confirm it survives in the trailing Unmanaged block; then revert or commit the reordered file deliberately

**Checkpoint**: Contract, emitter, golden files, and real files all agree on the order.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Keep the design guide honest, clean up references to the old order, and run the whole quickstart.

- [X] T025 [P] Add an "Agent form layout" subsection under "## Layout & Grid System" in `ui/design-system/ARCHON-DESIGN-SYSTEM.md` describing `ax-grid-agent`: the three areas, the 720px and 1320px pane thresholds, the `1fr 1.4fr 1fr` tracks, `align-items: start`, and one sentence stating this layout is the deliberate exception to Grid Rule 1 ("no fixed breakpoints") because folding a third column under the first cannot be expressed with auto-fill; add a cross-reference to it from Grid Rule 1
- [X] T026 [P] Add a doc-accuracy test to `ui/tests/test_design_system_docs.py`: parse both `@container ax-content (min-width: <N>px)` values from `ui/static/app.css`, assert the guide's "Agent form layout" section mentions both numbers and the string `ax-grid-agent`, and assert the guide's Grid Rule 1 references the exception. Follow the file's existing `_section` helper style
- [X] T027 Update the `SECTIONS` comment block in `ui/schema.py` (currently "FR-002 order") to cite spec 003 FR-015 and note that `identity` renders in the lead strip while still being written first; confirm no other comment or docstring in `ui/` names the old section labels (`grep -rn "Prompt & output\|Container resources" ui/`)
- [X] T028 Run the full suite (`cd ui && ../.venv/bin/python -m pytest -q`) and the complete quickstart.md checklist (§1–§6) against the running `ui` service; record the passing count against the T001 baseline plus the tests added in T002, T003, T007, T013, T016, T019, and T026

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: after Setup; blocks every story. T002/T003 can be written in parallel before T004; T004 → T005 → T006 are strictly sequential
- **US1 (Phase 3)**: after Foundational. T007 → T008 → T009 → T010 → T011 → T012 (T008 template and T009/T010 JS could be done in either order, but T011's CSS must follow T008's markup)
- **US2 (Phase 4)**: after US1 T011 (needs the base `.ax-grid-agent` block to append to)
- **US3 (Phase 5)**: after US2 T014 (the 720px block must be inserted before the 1320px block)
- **US4 (Phase 6)**: after US3 T017
- **US5 (Phase 7)**: T021–T023 after Foundational only (markdown edits); T024 after US1 so the save goes through the new form
- **Polish (Phase 8)**: T025/T026 after US3 (thresholds must exist in CSS); T027 after Foundational; T028 last

### User Story Dependencies

- **US1**: independent once the schema lands
- **US2, US3, US4**: each adds one CSS block on top of the previous; they are sequential in the stylesheet but each is independently verifiable at its reference width
- **US5**: independent of the layout stories; depends only on the schema change

### Parallel Opportunities

- T002 and T003 (different test files) before T004
- T021, T022, T023 (three different markdown files) at any point after Foundational
- T025 and T026 (guide and its test) alongside US4 or US5

---

## Parallel Example: Foundational and US5

```bash
# Before touching schema.py, write the failing tests together:
Task: "Add schema integrity tests to ui/tests/test_schema.py"
Task: "Add an emitter order test to ui/tests/test_agents_store.py"

# After Foundational lands, the contract documents can be amended together:
Task: "Amend specs/001-agent-management-ui/contracts/agent-yaml.md §2"
Task: "Update specs/001-agent-management-ui/contracts/http-api.md /api/schema example"
Task: "Relabel the applicability matrix in specs/001-agent-management-ui/data-model.md"
```

---

## Implementation Strategy

### MVP First (Foundational + US1)

1. T001 baseline
2. T002–T006 schema, goldens, green suite
3. T007–T012 grouping, lead strip, single-column groups
4. **STOP and VALIDATE** with quickstart §3 and §5: every field in its new home, all behaviours intact. This is already a usable improvement: correct grouping in one column.

### Incremental Delivery

1. US2 (T013–T015): three columns on the wide monitor
2. US3 (T016–T018): two columns on the laptop
3. US4 (T019–T020): narrow hardening
4. US5 (T021–T024): contracts and on-disk verification
5. Polish (T025–T028): guide, test, cleanup, full quickstart

### Solo-dev note

This is one developer's work; the phases are an ordering, not a staffing plan. Commit after each checkpoint with a conventional message (`feat(ui): …`, `docs(spec): …`). The golden-file regeneration (T005) belongs in the same commit as the schema change (T004) so history never has a red suite.

---

## Notes

- [P] tasks touch different files and have no dependency on incomplete work
- Tests are written first within each story and must fail before the implementation task lands
- Every existing form behaviour (harness switch, template pre-fill, prompt create panel, secret warnings, error mapping, dirty guard, YAML preview) is preserved by keying on field ids, not sections; T010 is the one JS change that protects this
- Token discipline from specs 001/002 applies to every CSS task: the only literals allowed in the new CSS are the two thresholds and the track ratio
