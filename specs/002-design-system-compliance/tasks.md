---

description: "Task list for Design System Compliance"
---

# Tasks: Design System Compliance

**Input**: Design documents from `/specs/002-design-system-compliance/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/components.md, quickstart.md

**Tests**: Included, but scoped. Per plan.md and research R7, `pytest` covers only what is statically checkable (token discipline, the corrected toggle tokens, the grid CSS, backing selects present, and design-guide accuracy). Interactive and visual fidelity (dropdown open/select/keyboard, toggle appearance, grid reflow) is verified by the quickstart browser checklist — this repo has no browser-automation harness.

**Organization**: Tasks are grouped by user story so each is an independently testable increment. Everything lives under `ui/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1–US4 from spec.md
- Every task names the exact file(s) it touches

## Path Conventions

Single `ui/` package: browser code in `ui/static/`, pages in `ui/templates/`, design reference in `ui/design-system/`, tests in `ui/tests/`. Run tests from `ui/` with the project venv: `cd ui && ../.venv/bin/python -m pytest -q`.

## Shared-file coordination (read before parallelizing)

Three files are touched by more than one story, so tasks that touch the same file are **sequential**, never `[P]` with each other:

- `ui/static/app.css` — US1 (dropdown block), US2 (toggle block), US3 (grid block)
- `ui/static/agent-form.js` — US1 (enhance selects), US3 (wrap sections in the grid)
- `ui/tests/test_api.py` — US1, US2, US3 static checks

US4 (the design guide and its own test file) is fully independent of the CSS/JS work and can run in parallel with any story.

---

## Phase 1: Setup

**Purpose**: Establish a known-good baseline before changing anything

- [X] T001 Run the current `ui` suite to record a green baseline (`cd ui && ../.venv/bin/python -m pytest -q`); note the passing count so regressions are obvious later

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None. This feature has no blocking foundational work — every story builds directly on the existing `ui/` package and the `--ax-*` tokens already in `ui/design-system/archon-tokens.css`.

**Checkpoint**: Proceed straight to the user stories. Respect the shared-file coordination note above.

---

## Phase 3: User Story 1 — Custom dropdown component (Priority: P1) 🎯 MVP

**Goal**: Every selectable field on the forms opens the reference's custom dropdown (an elevated panel with the selected option accent-highlighted) instead of the browser's native select popup, with all existing form behavior preserved.

**Independent Test**: Open the create and edit forms, open each selectable field, confirm the custom panel appears with the current value marked, choose an option and see the field update and the menu close, and confirm keyboard-only operation and Escape/outside-click dismissal.

### Tests for User Story 1

- [X] T002 [US1] Add a static check to `ui/tests/test_api.py` asserting the rendered create form (`GET /agents/new`) still contains backing `<select` controls and loads `/static/dropdown.js`; confirm it fails before implementation

### Implementation for User Story 1

- [X] T003 [US1] Create `ui/static/dropdown.js` exporting `enhanceSelect(select)`: build the `.ax-dropdown` wrapper, `.ax-dropdown-trigger` (label + chevron), and `.ax-dropdown-panel[role=listbox]` with an `.ax-dropdown-option[role=option]` per `<option>`; visually hide the backing `<select>` but keep it as the value store; on choice set `select.value`, dispatch a bubbling `change`, and close; make the function idempotent (skip an already-enhanced select) per contracts/components.md §1
- [X] T004 [US1] Add accessible keyboard + ARIA behavior to `ui/static/dropdown.js` (combobox/listbox pattern: `aria-haspopup`/`aria-expanded`/`aria-selected`/`aria-activedescendant`; Enter/Space/ArrowDown open, ArrowUp/ArrowDown/Home/End move the active option, Enter/Space choose, Escape/Tab close, printable-key type-ahead; label association so the control is announced) per research R2
- [X] T005 [US1] Add panel placement + dismissal to `ui/static/dropdown.js` (open downward, flip upward when short of space below within the viewport; max-height with internal scroll for long lists; close on Escape, outside click, and blur without changing the value) per research R3
- [X] T006 [US1] Add `.ax-dropdown` component styles to `ui/static/app.css` (trigger `bg-input`/`border-input`/`radius-md`, open border `--ax-cyan-border`, error border `--ax-error`; panel `bg-card`/`border-strong`/`radius-lg`/`shadow-lg`/`z-index: var(--ax-z-dropdown)`; option `radius-sm`, selected `--ax-cyan-bg`/`--ax-cyan`, unselected `--ax-text-mid`, hover `--ax-bg-card-hover`), tokens only, per contracts/components.md §1
- [X] T007 [US1] Wire enhancement in `ui/static/agent-form.js`: after each `renderForm`/harness switch, walk `#ax-form-sections select.ax-select` and call `enhanceSelect` on each; also enhance the static `#ax-template-select` on load (import from `/static/dropdown.js`)
- [X] T008 [US1] Manually verify preserved behaviors through the backing select (FR-003/FR-005/FR-006): harness switch shows/hides fields, network mismatch warning, template pre-fill, prompt picker's "Create new prompt…" reveal, and the validation error border all still work; note results against quickstart §3

**Checkpoint**: Every form select is a custom dropdown; all prior form behavior intact.

---

## Phase 4: User Story 2 — Toggle renders as specified (Priority: P1)

**Goal**: The enabled and reload toggles match the reference in both states — color, size, and thumb travel.

**Independent Test**: View a toggle off and on and compare against the `/design-system` reference toggle: off track muted/translucent with thumb at left, on track solid cyan with white thumb at right, matching size.

### Tests for User Story 2

- [X] T009 [US2] Add a static check to `ui/tests/test_api.py` asserting `ui/static/app.css` maps the checked toggle track to `--ax-cyan`, the checked thumb to `--ax-text-primary`, and the off thumb to `--ax-text-low`; confirm it fails before the fix

### Implementation for User Story 2

- [X] T010 [US2] Correct `.ax-toggle` in `ui/static/app.css` per contracts/components.md §2: off track `--ax-border-strong` / on `--ax-cyan`; off thumb `--ax-text-low` / on `--ax-text-primary`; track width `calc(var(--ax-space-9) + var(--ax-space-8))` (36) × height `var(--ax-space-9)` (20); thumb `var(--ax-space-8)` (16) with margin `var(--ax-space-1)`; on-thumb `translateX(var(--ax-space-8))`; transition `var(--ax-transition-fast)`; tokens only

**Checkpoint**: Toggles match the reference in both states.

---

## Phase 5: User Story 3 — Responsive form-grid layout (Priority: P2)

**Goal**: The create, edit, and detail form fields lay out in the `ax-grid-form` responsive grid, with intrinsically wide controls spanning the full row.

**Independent Test**: Open the create and edit screens at a wide viewport and confirm field pairs flow into multiple auto-filled columns with the reference gap; narrow the window and confirm columns reduce to one with no horizontal page scroll.

### Tests for User Story 3

- [X] T011 [US3] Add a static check to `ui/tests/test_api.py` asserting `ui/static/app.css` defines `.ax-grid-form` with `auto-fill` and `minmax(280px` and defines `.ax-field--wide` spanning `1 / -1`; confirm it fails before implementation

### Implementation for User Story 3

- [X] T012 [US3] Add `.ax-grid-form { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:var(--ax-space-10); }` and `.ax-field--wide { grid-column:1 / -1; }` to `ui/static/app.css` per contracts/components.md §3
- [X] T013 [US3] In `ui/static/agent-form.js` `renderForm`, wrap each section card's fields in an `.ax-grid-form` container, and add `.ax-field--wide` to the intrinsically wide fields (`env` map, `allowed_tools`/`disallowed_tools` lists, `append_system_prompt` textarea, and the prompt picker's create panel) per data-model.md

**Checkpoint**: Create/edit/detail screens use the form grid; the agents list stays a table.

---

## Phase 6: User Story 4 — Design-system guide stays accurate (Priority: P3)

**Goal**: `ARCHON-DESIGN-SYSTEM.md` documents the newly added dropdown styles and every grid pattern, matching the reference files.

**Independent Test**: Read the guide's component and layout sections and confirm both dropdown variants and every named grid pattern are documented, with nothing contradicting the reference.

### Tests for User Story 4

- [X] T014 [P] [US4] Create `ui/tests/test_design_system_docs.py` asserting `ui/design-system/ARCHON-DESIGN-SYSTEM.md` documents a Select/Dropdown component and every named grid pattern (`ax-grid-stats`, `ax-grid-cards`, `ax-grid-cards-lg`, `ax-grid-detail`, `ax-grid-split`, `ax-grid-form`); confirm it fails before the doc edit

### Implementation for User Story 4

- [X] T015 [P] [US4] Add a "Select / Dropdown" component section to `ui/design-system/ARCHON-DESIGN-SYSTEM.md` documenting both the native styled select (appearance-none + chevron, `bg-input`) and the custom dropdown component (elevated `bg-card` panel, `border-strong`, `shadow-lg`, accent-highlighted selection, `radius-sm` options) with tokens and states; verify the existing Toggle and Grid sections match the reference and fix any mismatch, per research R8

**Checkpoint**: The guide is accurate and its accuracy is machine-checked.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full validation and sign-off

- [X] T016 Run the full `ui` suite (`cd ui && ../.venv/bin/python -m pytest -q`) and confirm no regression from the T001 baseline, including token discipline (`test_no_literal_colours_or_fonts`); fix anything that fails
- [X] T017 Run the quickstart browser checklist (specs/002-design-system-compliance/quickstart.md §3–4) against `docker compose up -d --build ui`; record outcomes in the quickstart checkboxes and fix any visual/interaction gaps
- [X] T018 Regression check (FR-015): create and edit an agent through the updated UI and confirm the written `agents/<name>.yaml`, validation, and Dagster-reload behavior are unchanged from before the feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: none — no blocking work
- **User Stories (Phase 3–6)**: all can begin immediately after Setup, subject to the shared-file coordination note
- **Polish (Phase 7)**: after all desired stories are complete

### User Story Dependencies

- **US1 (P1)** → none; the MVP
- **US2 (P1)** → none; independent (touches only `app.css` toggle block + `test_api.py`)
- **US3 (P2)** → none functionally; shares `app.css` and `agent-form.js` with US1, so order those file edits after US1's
- **US4 (P3)** → none; fully independent (own doc + own test file)

### Within Each User Story

- Write the story's static test first and confirm it fails, then implement
- `dropdown.js` tasks (T003→T004→T005) are the same file: sequential
- `app.css` edits across US1/US2/US3 (T006, T010, T012) are the same file: sequential
- `agent-form.js` edits across US1/US3 (T007, T013) are the same file: sequential

### Parallel Opportunities

- US4 (T014, T015) runs in parallel with all CSS/JS work — different files
- US2's toggle fix (T009/T010) is independent of US1's `dropdown.js` (T003–T005); only the `app.css` and `test_api.py` writes must be ordered
- Within US1, the `dropdown.js` core/keyboard/placement are one file (sequential), but the `app.css` styling (T006) can proceed alongside the `dropdown.js` logic since they are different files

---

## Parallel Example

```bash
# US4 is fully independent of the CSS/JS stories — run it alongside US1:
Task: "T014 Create ui/tests/test_design_system_docs.py"     # US4 test (new file)
Task: "T015 Add Select/Dropdown section to ARCHON-DESIGN-SYSTEM.md"  # US4 doc (own file)

# Meanwhile US1's dropdown.js logic and its app.css block are different files:
Task: "T003 Create ui/static/dropdown.js (enhanceSelect core)"
Task: "T006 Add .ax-dropdown styles to ui/static/app.css"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → baseline green
2. Phase 3 US1 — the custom dropdown; **validate**: every form select opens the custom panel and all prior behavior holds
3. Demo: the biggest, most-visible fidelity gain lands first

### Incremental Delivery

1. US1 dropdown → the pervasive control is compliant
2. US2 toggle → the always-visible switch renders correctly
3. US3 form grid → the busiest screens reflow responsively
4. US4 guide → the reference doc is trustworthy again
5. Polish → full suite green, browser checklist signed off, no output regression

### Notes

- Commit after each task or logical group
- Token discipline (FR-014) applies to every CSS edit — no literal colors or fonts; use the tokens named in contracts/components.md
- `dropdown.js` is JavaScript, so the color-literal test does not scan it; still keep colors in `app.css` classes, not inline in JS
- This feature changes presentation and interaction only — no route, YAML, validation, or secret behavior changes (FR-015)
