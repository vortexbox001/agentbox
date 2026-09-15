---

description: "Task list for feature 011 — Shell, User Settings Modal, and Tabbed Agents List"
---

# Tasks: Shell, User Settings Modal, and Tabbed Agents List

**Input**: Design documents from `/specs/011-shell-settings-agents-list/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED — the spec explicitly requires test work (FR-024 sync test; SC-006 negative
gates; conformance/consistency/api suites extended; Automation tests removed). Test tasks are
therefore first-class, not optional.

**Organization**: Tasks are grouped by user story. Shared assets (design-system sync bring-level,
indigo tokens, sprite, macros) are Foundational because every story consumes them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All paths are repo-relative from `/home/vortex/GitHub/agentbox/`

## Path Conventions

Single-project server-rendered UI under `ui/`. Tests live in `ui/tests/`, run with
`cd ui && ../.venv/bin/python -m pytest -q`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working baseline before any change.

- [ ] T001 Confirm the existing suite is green as a baseline: run `cd ui && ../.venv/bin/python -m pytest -q` and note the current pass count (do not change any file). If `.venv/` is missing, recreate per `CLAUDE.local.md` (`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r ui/requirements.txt`).
- [ ] T002 Verify the Dagster GraphQL field/union names before coding the activity read: one throwaway `curl` to `{DAGSTER_URL}/graphql` to confirm `pipelineRunsOrError`/`Runs`, `instigationStateOrError`/`instigationSelector`, `assetChecksOrError` evaluation shape, and `scheduleSelector`/`sensorSelector` arg names (research R1/R2). Record the resolved names as a comment block in `specs/011-shell-settings-agents-list/contracts/dagster-activity.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Deck-clearing (Automation removal) and the shared design-system assets every user
story renders against (sprite + icons, indigo tokens, brought-level `app.css`/`dropdown.js`,
extended macros).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Automation removal (FR-022, research R8, contract §E)

- [ ] T003 Remove the Automation page and its dedicated files: delete `ui/templates/automation/list.html`, `ui/static/automation.js`, `ui/automation_store.py`, `ui/tests/test_automation_store.py`, and `ui/tests/test_migrate_automation.py` (keep the `schedule_pill` macro and the schema `asset_schedule`/`job_schedule` fields — they are shared).
- [ ] T004 Remove the Automation routes and imports from `ui/main.py`: `GET /automation`, `GET`/`PUT /api/automation`, and the `automation_store`/`AutomationError` imports.
- [ ] T005 Remove the Automation nav entry from `ui/templates/base.html` and drop the two automation-specific assertions in `ui/tests/test_ui_consistency.py`.

### Shared design-system assets (FR-010, FR-023, FR-025, FR-026)

- [ ] T006 [P] Add the indigo accent colour ramp as tokens under both the Light and Dark theme scopes in `ui/design-system/tokens/` (WCAG AA in both themes; not a theme value — FR-010).
- [ ] T007 [P] Add the missing icons to the sprite in both `ui/static/icons.svg` and `ui/design-system/static/icons.svg`: `filter`, `settings`, `check-circle`, `warn-tri`, `x-circle`, `overview`, `runs`, `clock`, `sensor`, `search` (FR-023).
- [ ] T008 Inline the icon sprite once in `ui/templates/base.html` (hidden `<svg>` of `<symbol>`s) and make every `<use href>` document-relative (`#id`), dropping the `/static/icons.svg#id` absolute refs in `base.html` and `ui/static/dropdown.js` (research R3, FR-023) — depends on T007.
- [ ] T009 Bring `ui/static/app.css` level with `ui/design-system/static/app.css` (944 vs 850): indigo-ramp usage, tabbed-list/toolbar/modal/pill/check-grid/run-history classes, and token-based classes replacing every mock inline style (em-dash cell colour, mono link colour, dropdown list reset) so served templates carry no inline `style` (FR-023, FR-026) — depends on T006, T007.
- [ ] T010 [P] Bring `ui/static/dropdown.js` level with `ui/design-system/static/dropdown.js` (403 vs 344), reusing the listbox behaviour the settings theme dropdown needs (FR-023, research R5).
- [ ] T011 [P] Extend `ui/templates/components/macros.html` (signatures back-compatible, FR-025): `schedule_pill` gains the type-driven icon (clock=job, sensor=asset), `select` passes through per-option icon / trailing note / sticky filter-row data, and `tabs` renders the `.ax-tab-count` span from `items[].count`.

**Checkpoint**: Automation gone; sprite, indigo tokens, brought-level CSS/JS, and macros ready.

---

## Phase 3: User Story 1 - Agents page answers the four glance questions (Priority: P1) 🎯 MVP

**Goal**: Rebuild the agents page as a tabbed, full-bleed 8-column list that renders store-backed
columns (1–5) + tabs + counts + toolbar server-side and fills the Dagster-derived columns (6–8)
after first paint.

**Independent Test**: Load `/agents` with the example config; tabs/counts/toolbar and columns 1–5
render server-side; columns 6–8 fill after first paint; tab/filter/show-disabled narrow rows;
`?tab=scheduled` reloads onto the Scheduled tab.

### Implementation for User Story 1

- [ ] T012 [P] [US1] Extend `ui/agents_store.py` `list_agents()` rows with `is_asset`, `is_job`, `crons` (list of `{type, expr, dagster_name}`), and `checks` (list of `{name}`), reusing the existing `dagster_job`/`dagster_asset` naming helpers so `dagster_name` matches the factory registration (contract agents-list-view §A, data-model §1).
- [ ] T013 [P] [US1] Create `ui/cron_text.py` — one shared cron-to-text helper (e.g. "Every day at 7:00 AM") in the box's timezone, and expose it to Jinja (research R6, FR-016).
- [ ] T014 [US1] Add `activity(agents) -> dict` to `ui/dagster.py`: one aliased GraphQL POST (short timeout, one client) returning per-agent `latest_run`, `history` (≤10, newest-first), `checks` (`{name, status}`), and `schedules` (`{dagster_name: {running}}`); map every transport/Dagster error to `{"reachable": False, "agents": {}}` and null unknown fields — never one request per agent, never a disk scan (contract dagster-activity §A, FR-019, SC-005) — depends on T002, T012.
- [ ] T015 [US1] Rebuild `ui/templates/agents/list.html`: no page header, full-bleed table sorted by name, `tabs` macro (All/Assets/Jobs/Scheduled/Disabled with server counts), toolbar (Filter + Show-disabled checkbox left, New-agent primary button right), 8 columns (Name mono link, Harness, Model truncated w/ title, Kind badges, Schedules/Sensors pills+icon+cron label, Latest run, Checks, Run history), "No agents yet" card below the toolbar, and preserved parse-error / name-mismatch row treatment (contract §B, FR-012/013/014/015/018/020) — depends on T009, T011, T012, T013.
- [ ] T016 [US1] Add the list context to `GET /agents` in `ui/main.py` (rows + server-computed tab counts) and add `GET /api/agents/activity` returning the contract §C payload from `dagster.activity(...)`, always HTTP 200 (contract §C, FR-013/019) — depends on T012, T014.
- [ ] T017 [US1] Create `ui/static/agents-list.js`: after first paint fetch `/api/agents/activity` once and fill columns 6–8 + each pill's toggle state (Latest-run status dot + relative time + Dagster link; Checks icons wrapping four per row, titled; Run-history ≤10 bars newest-at-right); client-side tab/filter/show-disabled narrowing; `?tab=` URL sync (default All, survives reload); show-disabled `localStorage` flag; "Run data unavailable" warning on `reachable:false` (contract §D, FR-013/014/017/020) — depends on T016.

### Tests for User Story 1

- [ ] T018 [P] [US1] Extend `ui/tests/test_api.py`: `GET /api/agents/activity` returns 200 with the contract payload when Dagster is stubbed reachable, and `{"reachable": false, "agents": {}}` on the degradation path (use the `dagster_stub` fixture).
- [ ] T019 [P] [US1] Extend `ui/tests/test_agents_store.py` for the new row fields (`is_asset`, `is_job`, `crons`, `checks`) and correct tab-count derivation (asset+job counts in both; on-demand excluded from Scheduled).
- [ ] T020 [US1] Extend `ui/tests/test_ui_consistency.py`: the rebuilt list's tabs, toolbar buttons, show-disabled checkbox, table, and pills carry their design-system classes (FR-026, SC-006).

**Checkpoint**: The agents page answers the four glance questions independently (SC-001/002/005).

---

## Phase 4: User Story 2 - Revised sidebar and foot on every page (Priority: P2)

**Goal**: Every served page shows a divided nav linking only to Agents, a Dagster status block in
the indigo accent, and a foot offering Hide navigation + Settings; collapses cleanly to 68px.

**Independent Test**: Load each page (agents list, new/edit form, 404); foot shows Dagster block +
keyline + Hide navigation + Settings with no theme buttons; collapse to 68px and back with no
overflow; collapsed foot link's accessible name reads "Show navigation".

### Implementation for User Story 2

- [ ] T021 [US2] Update `ui/templates/base.html`: primary nav = Agents only, below the retained `.ax-nav-divider` keyline; foot = Dagster status block + keyline + "Hide navigation" (collapse icon) + "Settings" (gear icon); remove the `.ax-theme-control` three-button radiogroup; keep `#ax-modal-root` and the pre-paint theme/sidebar head script (contract shell-and-modal §A/§B/§F, FR-001/002/003) — depends on T008.
- [ ] T022 [US2] Update `ui/static/shell.js`: foot "Hide navigation"/"Show navigation" accessible-name toggle on collapse (persistence `agentbox.sidebar` unchanged), remove the radiogroup theme handler, keep the Dagster status poll (contract §B, FR-004) — depends on T021.
- [ ] T023 [US2] Apply the indigo accent classes to the Dagster connection points — the foot Dagster status block, and (in `ui/templates/agents/list.html` / `ui/static/app.css`) the Latest-run + Run-history links and the schedule/sensor toggle checked track — non-Dagster elements keep the theme accent (contract §C, FR-010) — depends on T009, T021.

### Tests for User Story 2

- [ ] T024 [US2] Extend `ui/tests/test_ui_consistency.py` (and `ui/tests/test_api.py` for render): the foot on every page shows the Dagster block, keyline, Hide-navigation, and Settings with no theme radiogroup, and the collapsed foot link exposes the "Show navigation" accessible name (SC-004).

**Checkpoint**: The revised shell frames every page (SC-004).

---

## Phase 5: User Story 3 - User settings modal with theme control (Priority: P2)

**Goal**: A `role="dialog"` "User settings" modal in `#ax-modal-root` with a Preferences section
and a theme dropdown (Light/Dark/Use system setting) that applies and persists immediately, with
correct focus/keyboard; the same chrome restyles the confirm/dirty-form modal.

**Independent Test**: Open Settings, switch Light/Dark (applies without reload, survives reload),
pick Use system setting (follows OS flip), Escape closes dropdown then modal with focus returned;
the dirty-form confirm modal shows the new square keylined chrome.

### Implementation for User Story 3

- [ ] T025 [US3] Add the settings modal markup to `ui/templates/base.html` `#ax-modal-root`: `role="dialog"` / `aria-modal="true"` labelled "User settings", square keylined chrome, one Preferences section, one Theme row with a right-aligned custom listbox dropdown (Light, Dark, Use system setting — each with a lead icon; no "Dagster Indigo"), and a single primary "Done" (no Save) — all styling via classes (contract §D, FR-005/006/007) — depends on T011, T021.
- [ ] T026 [US3] Create `ui/static/settings.js`: open from the Settings foot link into `#ax-modal-root`, move focus in and trap Tab, close returns focus to the Settings link; theme dropdown reuses `dropdown.js` listbox behaviour; choosing an option stamps/clears `data-theme` on `<html>` immediately and writes `localStorage["agentbox.theme"]` ∈ {light,dark,system}; Escape closes an open panel first then the modal; Done and backdrop click also close, no Save (contract §D/§E, FR-008/009/011) — depends on T010, T025.
- [ ] T027 [US3] Restyle the existing confirm/dirty-form modal with the new square keylined chrome (`ui/templates/agents/form.html` confirm modal + the modal classes in `ui/static/app.css`) — FR-006, US3 scenario 7 — depends on T009.

### Tests for User Story 3

- [ ] T028 [US3] Repoint `test_theme_control_is_accessible_icon_buttons` in `ui/tests/test_ui_consistency.py` from the removed foot radiogroup to the modal theme dropdown (`role="listbox"`/`role="option"`, labelled, iconed options) (FR-003, SC-006).

**Checkpoint**: The settings modal replaces the inline theme control at parity (SC-003).

---

## Phase 6: User Story 4 - Live schedule toggles from the list (Priority: P3)

**Goal**: Flip a schedule/sensor on or off from the list via a write endpoint; degrade to a
disabled, state-reflecting control when the agent is disabled, Dagster is down, or state is unknown.

**Independent Test**: Flip a pill toggle and confirm Dagster shows it running; flip back; stop
Dagster and reload — pills disabled with an explanatory title while columns 1–5 still render.

### Implementation for User Story 4

- [ ] T029 [US4] Add `set_instigation(kind, name, running) -> {"ok", "running", "message"}` to `ui/dagster.py`: POST `startSchedule`/`stopRunningSchedule` or `startSensor`/`stopSensor` with the selector; treat `PythonError`/`UnauthorizedError`/GraphQL `errors` as `ok: false` (contract dagster-activity §B, FR-021) — depends on T002.
- [ ] T030 [US4] Add the `POST /api/schedules/toggle` endpoint (body `{name, kind, running}`) in `ui/main.py`, returning `set_instigation(...)`, always HTTP 200 (contract §B) — depends on T029.
- [ ] T031 [US4] Extend `ui/static/agents-list.js`: pill toggle POSTs to the endpoint and updates to the returned state; render the toggle disabled with an explanatory title ("Turn on from Dagster" when the mutation is unavailable) when the agent is disabled, Dagster is unreachable, or state is unknown — no state change attempted (contract §C, FR-016/021) — depends on T017, T030.

### Tests for User Story 4

- [ ] T032 [US4] Extend `ui/tests/test_api.py`: `POST /api/schedules/toggle` returns the new running state on success and the `ok:false` degradation signal when the mutation errors/is unauthorised (via `dagster_stub`).

**Checkpoint**: Live schedule toggles work and degrade cleanly (SC-002 degradation path).

---

## Phase 7: User Story 5 - Design system stays in sync (Priority: P3)

**Goal**: A test fails the build when a served shared asset and its design-system copy diverge
beyond one documented substitution; rendered pages keep DS classes and carry no inline styles.

**Independent Test**: Edit `ui/design-system/static/app.css` without editing `ui/static/app.css`
and confirm the sync test fails; insert an inline `style` into the list template and confirm the
no-inline-styles test fails.

### Implementation for User Story 5

- [ ] T033 [P] [US5] Create `ui/tests/test_design_system_sync.py`: compare `ui/static/app.css`, `ui/static/dropdown.js`, and `ui/static/icons.svg` byte-for-byte against their `ui/design-system/static/` siblings after applying one named icon-href normalisation constant (documented in a comment), failing on any other divergence (contract design-system-sync §A, FR-024, SC-006) — depends on T008, T009, T010.
- [ ] T034 [US5] Confirm `ui/tests/test_conformance.py` passes on the new tree (`test_no_inline_styles_in_app_templates`, `test_no_literal_*`, `test_no_named_colours_in_css`, `test_no_stray_font_family`, `test_no_external_urls`); move any remaining mock inline styles to token classes in `ui/static/app.css`, and confirm `test_design_system_docs.py` (manifest⇄macro) still passes (FR-026, SC-006/007).

**Checkpoint**: The served and design-system copies cannot silently drift (SC-006).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docs and full end-to-end validation.

- [ ] T035 [P] Add README.md sections for the tabbed list view, the settings modal, the foot links, and the indigo Dagster accent; keep `ui/design-system/readme.md` named as the source of truth (FR-027).
- [ ] T036 Run the full suite green: `cd ui && ../.venv/bin/python -m pytest -q`. Then run the quickstart negative gates and revert each: sync test fails on a design-system-only edit; `test_no_inline_styles_in_app_templates` fails on an inserted `style="…"`; the conformance colour/px tests fail on an inserted literal (SC-006).
- [ ] T037 [P] Offline validation (SC-007): with egress blocked, reload every page and confirm fonts, icons, and the inlined sprite render and no request leaves the box.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–7)**: All depend on Foundational.
  - US1 (P1) is the MVP and is fully independent.
  - US2 (P2) and US3 (P2) are independent of US1; US3's modal open-target lives in the shell
    `base.html` that US2 edits, so US3 tasks that touch `base.html` (T025) follow T021.
  - US4 (P3) depends on US1's `agents-list.js` (T017) and list rendering.
  - US5 (P3) depends on the Foundational bring-level work (T008/T009/T010).
- **Polish (Phase 8)**: Depends on all desired stories.

### Key cross-task dependencies

- T008 (inline sprite) ← T007 (icons added).
- T009 (served app.css) ← T006 (indigo tokens) + T007 (icons).
- T014 (dagster.activity) ← T002 (field verify) + T012 (store rows for names).
- T015 (list template) ← T009 (classes) + T011 (macros) + T012 (rows) + T013 (cron text).
- T016 (list context + activity endpoint) ← T012 + T014.
- T017 (agents-list.js) ← T016.
- T021 (base.html shell) ← T008. T022/T023 ← T021.
- T025 (settings modal markup) ← T011 + T021. T026 (settings.js) ← T010 + T025.
- T030 (toggle endpoint) ← T029. T031 (toggle UI) ← T017 + T030.
- T033 (sync test) ← T008 + T009 + T010.

### Same-file serialization (do NOT parallelize these)

- `ui/templates/base.html`: T008 → T021 → T025.
- `ui/static/app.css`: T009 → T023 → T027 → T034.
- `ui/main.py`: T004 → T016 → T030.
- `ui/static/agents-list.js`: T017 → T031.
- `ui/tests/test_ui_consistency.py`: T005 → T020 → T024 → T028.
- `ui/tests/test_api.py`: T018 → T032.

---

## Parallel Opportunities

- **Foundational**: T006, T007, T010, T011 are `[P]` (distinct files); T008/T009 follow them.
- **US1**: T012 and T013 are `[P]` (distinct files); tests T018 and T019 are `[P]` (distinct files).
- **Across stories after Foundational**: US2, US3, and US5 groundwork can proceed alongside US1 by
  separate developers, respecting the `base.html` and `app.css` serialization above.

### Parallel Example: Foundational shared assets

```bash
# After Automation removal (T003–T005), launch the independent shared-asset tasks together:
Task T006: "Add indigo accent ramp tokens in ui/design-system/tokens/"
Task T007: "Add missing icons to ui/static/icons.svg and ui/design-system/static/icons.svg"
Task T010: "Bring ui/static/dropdown.js level with the design-system copy"
Task T011: "Extend schedule_pill/select/tabs in ui/templates/components/macros.html"
```

### Parallel Example: User Story 1 data layer

```bash
Task T012: "Extend agents_store.list_agents() rows with is_asset/is_job/crons/checks"
Task T013: "Create ui/cron_text.py shared cron-to-text helper"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup (T001–T002).
2. Phase 2 Foundational (T003–T011) — Automation gone, shared assets ready.
3. Phase 3 User Story 1 (T012–T020).
4. **STOP and VALIDATE**: the agents page answers the four glance questions against the example
   config (SC-001/002/005). Deploy/demo — this is the headline value.

### Incremental Delivery

1. Foundation → MVP (US1) → demo.
2. Add US2 (revised shell/foot) → validate on every page (SC-004).
3. Add US3 (settings modal) → validate theme apply/persist + focus (SC-003).
4. Add US4 (live schedule toggles) → validate flip + degradation.
5. Add US5 (sync test + conformance) → drift guard green (SC-006).
6. Polish (docs + full-suite + offline).

### Notes

- `[P]` = different files, no incomplete dependency.
- Missing data is unknown, not zero: null → em-dash / disabled control everywhere.
- The page must never fail to render because Dagster is down (columns 1–5 always ship).
- Commit after each task or logical group; stage `specs/011-.../` artifacts with the work.
