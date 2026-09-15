# Feature Specification: Shell, User Settings Modal, and Tabbed Agents List

**Feature Branch**: `011-shell-settings-agents-list`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Shell, user settings modal, and tabbed agents list from the delivered mocks" — fulfil the placeholder of brief 011 in `specs/000-briefs-revised.md` now that the design-system mocks are delivered. Presentation and shell work on top of completed 009 (design system) and 010 (file layout). No agent schema changes; two new read-only Dagster GraphQL reads (latest runs, asset checks). Shared contracts in 000-briefs-revised.md apply (paths, missing data is unknown not zero, Dagster owns run state).

## Overview

The served management UI must catch up to the updated design system in three visible places and one supporting place:

1. **The left navigation and its foot** — a divided nav that links only to pages that exist (Agents), a Dagster status block styled in Dagster's own indigo accent, and two foot links (Hide navigation, Settings) that replace the old collapse toggle and inline theme control.
2. **A user-settings modal** — a dialog that replaces the inline theme control, offering a single Preferences section with a theme dropdown (Light, Dark, Use system setting), applied and persisted immediately.
3. **The agents page rebuilt as a tabbed, full-bleed list** — tabs with live counts, a toolbar (filter, show-disabled, new agent), and an eight-column table that answers, at a glance, *what each agent is, when it runs, how its last run went, and whether its checks passed*. Run-derived columns are filled after first paint from a single bounded Dagster read and degrade gracefully when Dagster is unreachable.
4. **Design-system sync** — the served `app.css`, `dropdown.js`, and icon sprite are brought level with their design-system counterparts, and a test prevents the design system from silently running ahead again.

After this feature, every served page uses the revised shell; the agents page answers the four glance questions; and the design-system copies of the shared assets are no longer ahead of what is served.

## Clarifications

### Session 2026-09-15

- Q: Should the schedule/sensor pill toggle start/stop the Dagster schedule via a write endpoint, or be read-only? → A: Live write endpoint — a new POST calls Dagster's start/stop mutation and degrades to a disabled "Turn on from Dagster" control when the mutation is unavailable.
- Q: Is "Dagster Indigo" a selectable page theme? → A: No — there is no indigo theme. Indigo is an added accent colour ramp on the existing Light and Dark themes, used to mark the elements that link to or toggle Dagster (the Dagster "connection points"). The theme choices remain Light, Dark, and Use system setting.
- Q: What does the primary nav link to now? → A: Agents only; the Automation page is deleted.
- Q: Do partitioned asset agents show per-partition run history? → A: No — every agent shows the ten most recent runs of its Dagster job, newest at right.
- Q: With the Automation page deleted, where does editing an agent's cron schedule go? → A: It already lives in the agent create/edit form (the schema-driven Triggers section); deleting the standalone Automation page loses nothing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agents page answers the four glance questions (Priority: P1)

An operator opens the agents page and, without clicking into any single agent, understands what each agent is (kind, harness, model), when it runs (schedules/sensors with human-readable timing), how its last run went (status and relative time), and whether its checks passed (per-check result icons), plus a compact ten-run history bar. They can narrow the list by tab (All / Assets / Jobs / Scheduled / Disabled), by a text filter, and by a show-disabled toggle, and land directly on a tab via a shareable URL.

**Why this priority**: This is the headline value of the feature — the page turns a five-column card table into an at-a-glance operations view. It is independently demonstrable with the example config and delivers value even if the shell and modal work slipped.

**Independent Test**: Load the agents page with the example config and confirm the tabs, counts, toolbar, and eight columns render server-side; confirm run-derived columns fill in after first paint; confirm tab/filter/show-disabled narrow the visible rows; confirm `?tab=scheduled` reloads onto the Scheduled tab.

**Acceptance Scenarios**:

1. **Given** the example config, **When** the operator loads the agents page, **Then** the page renders with no page header, a full-bleed edge-to-edge table sorted by name, and tabs All / Assets / Jobs / Scheduled / Disabled each showing a count computed from the store (Assets = agents producing an asset; Jobs = agents with `job: true`; an agent that is both counts in both; Scheduled = agents with at least one cron; Disabled = `enabled: false`).
2. **Given** an agent that is both an asset and a job, **When** its row renders, **Then** the Kind cell shows two badges (asset + job) and the Schedules/Sensors cell shows two pills.
3. **Given** an on-demand agent with no cron, **When** its row renders, **Then** its Schedules/Sensors cell shows an em-dash placeholder and it is excluded from the Scheduled tab count.
4. **Given** the default view, **When** the operator has not enabled "Show disabled agents", **Then** disabled agents are hidden from every tab except Disabled; enabling the toggle reveals them everywhere and the choice persists across reloads.
5. **Given** the operator selects a tab, **When** the page reloads or the URL is shared, **Then** the same tab is active (reflected as `?tab=<name>`, default All).
6. **Given** the Filter control is activated, **When** the operator types text, **Then** visible rows narrow by case-insensitive substring over name, harness, and model; an empty field applies no filter.
7. **Given** an asset agent with declared checks whose latest materialization had one passing and one failed non-blocking check, **When** its Checks cell fills, **Then** it shows a green pass icon and a yellow warning icon, each with the check name and status in its title; a failed blocking check shows red; not-yet-run shows grey; agents without checks show an em-dash.
8. **Given** any agent's Latest-run cell has run data, **When** it fills, **Then** it shows a status dot plus relative time ("2 hours ago", "running now") and the text links to that run in Dagster; the Run-history cell shows up to ten bars newest-at-right, green for success, red for failure, neutral for empty or in-progress, each bar titled with the run's status and time.
9. **Given** a parse-error agent and a name-mismatch agent, **When** their rows render, **Then** the existing error-badge / name-mismatch-badge treatment is preserved inside the new table (parse-error message spans the data columns).

---

### User Story 2 - Revised sidebar and foot on every page (Priority: P2)

On every served page the operator sees a navigation whose links go only to pages that exist, a Dagster status block in Dagster's colour, and a foot offering "Hide navigation" and "Settings". Collapsing the sidebar leaves a clean 68px rail with no overflow.

**Why this priority**: The shell frames every page and is a prerequisite for the settings modal (the Settings link opens it), but the page still functions without it, so it ranks below the headline agents view.

**Independent Test**: Load each page (agents list, new/edit form, 404) and confirm the foot shows the Dagster block, a keyline, Hide navigation, and Settings, with no theme buttons; collapse to 68px and back with no overflow; confirm the collapsed foot link's accessible name reads "Show navigation".

**Acceptance Scenarios**:

1. **Given** any served page, **When** it renders, **Then** the primary nav shows only Agents, below the divider keyline (the divider is retained so the "objects" group lands where the mock places it), with no dead or disabled placeholder links for pages that do not yet exist.
2. **Given** the foot, **When** it renders in any theme, **Then** it shows, top to bottom: the Dagster status block styled with the indigo translucent fill and indigo text (a Dagster-branded element that keeps Dagster's colour in every theme, behaviour unchanged — dot state ok/down/unknown, opens Dagster in a new tab), a keyline, a "Hide navigation" link with the collapse icon, and a "Settings" link with the gear icon; no theme radiogroup appears.
3. **Given** the operator activates "Hide navigation", **When** the sidebar collapses, **Then** it becomes the 68px rail (persistence key `agentbox.sidebar` unchanged), foot links centre their icons and hide labels, the brand shows only its mark, the Dagster block keeps only its dot, nothing overflows, and the collapsed link's accessible name becomes "Show navigation".
4. **Given** the collapsed state persisted, **When** the operator reloads, **Then** the sidebar is still collapsed.
5. **Given** the Light or Dark theme, **When** any element that links to or toggles Dagster renders (the foot Dagster status block, the Latest-run and Run-history links, the schedule/sensor toggles), **Then** it uses the indigo accent ramp to signal the Dagster connection point, in both themes; non-Dagster elements keep the theme's own accent.

---

### User Story 3 - User settings modal with theme control (Priority: P2)

The operator opens Settings from the foot, sees a Preferences section with a Theme dropdown offering Light, Dark, and Use system setting, and picks a theme that applies and persists immediately with no Save step. Keyboard and focus behave correctly, and the same modal chrome restyles the existing confirm/dirty-form modal.

**Why this priority**: Replaces the removed inline theme control; needed for parity with the removed control, but the pages remain usable without it, so it shares P2 with the shell.

**Independent Test**: Open Settings, switch between Light and Dark, confirm the change applies without reload and survives reload; pick Use system setting and confirm the UI follows an OS theme flip; confirm Escape closes the dropdown then the modal, focus returns to Settings; confirm the dirty-form confirm modal shows the new square keylined chrome.

**Acceptance Scenarios**:

1. **Given** the operator activates Settings, **When** the modal opens, **Then** it is a dialog (role="dialog", modal, labelled "User settings") rendered into the shared modal root, with square corners, the default-background surface, full-bleed keylines on the header and actions rows, one Preferences section, one Theme row with a dropdown, and a single primary "Done" action (no Save).
2. **Given** the Theme dropdown, **When** it renders, **Then** its options are Light, Dark, and Use system setting, each with a lead icon, and the trigger shows the current option's icon as its lead glyph.
3. **Given** the operator selects Light or Dark, **When** the selection is made, **Then** the theme switches immediately without reload, the preference persists, and a reload keeps it.
4. **Given** the operator selects "Use system setting", **When** the OS theme is flipped, **Then** the UI follows the OS light/dark preference live.
5. **Given** the modal is open with the dropdown panel open, **When** the operator presses Escape once, **Then** the dropdown panel closes and the modal stays open; a second Escape closes the modal and focus returns to the Settings foot link.
6. **Given** the modal is open, **When** the operator presses Done, Escape (with no open panel), or clicks the backdrop, **Then** the modal closes with no separate save.
7. **Given** a dirty agent form, **When** the confirm/dirty-form modal appears, **Then** it uses the new square keylined chrome (this restyle is intended).

---

### User Story 4 - Live schedule toggles from the list (Priority: P3)

From the agents list, the operator flips a schedule or sensor on or off without leaving the page, and the change is reflected in Dagster; when Dagster is down or the agent is disabled, the toggle is a clearly disabled, state-reflecting control with an explanatory title.

**Why this priority**: This is the only behaviour addition in the brief; the rest of the page is read-only. It is valuable but not required for the page to answer the four glance questions, so it ranks last.

**Independent Test**: Flip a pill toggle and confirm Dagster's schedule page shows it running; flip back; stop Dagster and reload and confirm the pills are disabled with a title, and Latest run / Checks / Run history show em-dashes while columns 1–4 still render with the warning alert visible.

**Acceptance Scenarios**:

1. **Given** an enabled agent with a schedule while Dagster is reachable, **When** the operator flips its pill toggle, **Then** the schedule's instigation state changes in Dagster (start/stop) and the pill reflects the new running/stopped state.
2. **Given** the agent is disabled, or Dagster is down, or the state is unknown, **When** the pill renders, **Then** the toggle is disabled with an explanatory title and does not attempt a state change.
3. **Given** Dagster is unreachable, **When** the page loads, **Then** columns 1–4 render from the store, columns 5–8 degrade to em-dashes / disabled toggles, and a warning alert reads "Run data unavailable: Dagster is not reachable"; the page never fails to render because Dagster is down.

---

### User Story 5 - Design system stays in sync (Priority: P3)

The served shared assets match the design-system copies, and a test fails the build if the design-system copy is edited without the served copy, so the two cannot drift again. Rendered pages keep their design-system classes and carry no inline styles.

**Why this priority**: Internal quality and drift prevention; invisible to operators but protects the constitution's One Design System principle. Lowest priority because it does not change what an operator sees.

**Independent Test**: Edit `ui/design-system/static/app.css` without editing `ui/static/app.css` and confirm the new sync test fails; insert an inline `style` attribute into the list template and confirm the no-inline-styles test fails; confirm the theme-control accessibility assertion now targets the modal dropdown.

**Acceptance Scenarios**:

1. **Given** the served and design-system copies of the shared assets, **When** the sync test runs, **Then** it passes when they agree within the one documented substitution and fails when the design-system copy diverges beyond it.
2. **Given** any rendered page, **When** conformance tests run, **Then** every select, button, and table carries its design-system class, no template carries an inline style, and inserting a literal colour/typeface/pixel value still fails the conformance tests.
3. **Given** the sprite is required to render offline, **When** egress is blocked and a page reloads, **Then** fonts, icons, and the sprite all render and no request leaves the box.

---

### Edge Cases

- **Dagster reachable but slow or partial**: if the single bounded activity read cannot return latest runs and asset-check results for all agents within its short timeout, the page ships columns 1–5 live and renders columns 6–8 as em-dashes with the "Run data unavailable" warning; it never scans run directories on disk to fabricate data.
- **Start/stop mutation unavailable or unreliable**: the pill toggle renders as a disabled, state-reflecting control titled "Turn on from Dagster", matching the existing "starts paused, turn on from Dagster" wording.
- **Empty store**: the existing "No agents yet" card renders inside the list view below the toolbar.
- **Agent with more than four checks**: check result icons wrap (four per row).
- **In-progress run**: the Latest-run cell shows "running now" and the corresponding run-history bar is neutral, not green or red.

## Requirements *(mandatory)*

### Functional Requirements

#### Sidebar and foot (all pages)

- **FR-001**: Every served page MUST render the revised shell: a primary nav linking only to pages that exist (Agents) below a divider keyline (the divider is retained so the group lands where the mock places it), with no dead or disabled placeholder links for pages that do not yet exist.
- **FR-002**: The foot MUST show, in order, the Dagster status block (styled in Dagster's indigo colour in every theme, with unchanged ok/down/unknown dot polling and open-in-new-tab behaviour), a keyline, a "Hide navigation" link with the collapse icon, and a "Settings" link with the gear icon.
- **FR-003**: The inline three-button theme radiogroup MUST be removed from the foot, and its accessibility assertion MUST move to the settings modal's theme dropdown.
- **FR-004**: "Hide navigation" MUST collapse the sidebar to the existing 68px rail using the existing persistence (`agentbox.sidebar`); when collapsed, foot links centre their icons and hide labels, the brand shows only its mark, the Dagster block keeps only its dot, nothing overflows, and the link's accessible name becomes "Show navigation".

#### User settings modal

- **FR-005**: The system MUST provide a user settings dialog rendered into the shared modal root, with role="dialog", modal semantics, and the accessible label "User settings", opened from the Settings foot link.
- **FR-006**: The modal MUST use the new chrome (square corners, default-background surface, full-bleed keylines on header and actions rows, padded body) and MUST contain one Preferences section, one Theme row with a right-aligned dropdown, and a single primary "Done" action with no Save; the same chrome MUST also apply to the existing confirm/dirty-form modal.
- **FR-007**: The Theme dropdown MUST offer Light, Dark, and Use system setting, each with a lead icon; the trigger MUST show the current option's icon as its lead glyph.
- **FR-008**: Choosing a theme MUST apply it immediately without reload and persist it immediately; Done, Escape (with no open dropdown panel), and a backdrop click MUST all just close the modal.
- **FR-009**: The theme preference MUST be stored in `localStorage["agentbox.theme"]` as one of {light, dark, system}; the pre-paint script MUST resolve all three and stamp the dark theme attribute (or none for light) with no visible flash, keeping today's behaviour. No indigo theme value exists, and no theme setting is added to `config/settings.yaml`.
- **FR-010**: Indigo MUST NOT be a selectable theme. Instead, an indigo accent colour ramp MUST be added to both the Light and Dark themes and applied to the elements that link to or toggle Dagster — the foot Dagster status block, the per-agent Latest-run and Run-history links, and the schedule/sensor toggles — so those Dagster connection points read as indigo in every theme while non-Dagster elements keep the theme's own accent.
- **FR-011**: Opening the modal MUST move focus into it and trap Tab within it while open; closing MUST return focus to the Settings foot link. Escape MUST close an open dropdown panel first and the modal second.

#### Agents page (tabbed list)

- **FR-012**: The agents page MUST render as the tabbed full-bleed list with no page header (page title retained only in the document title), rendered server-side.
- **FR-013**: The page MUST show tabs All / Assets / Jobs / Scheduled / Disabled with counts computed server-side from the store (Assets = agents producing an asset; Jobs = agents with `job: true`, counting an agent that is both in both; Scheduled = agents with at least one cron regardless of Dagster on/off state; Disabled = `enabled: false`). Tab choice MUST filter rows client-side, reflect in the URL as `?tab=<name>`, survive reload, and default to All.
- **FR-014**: The toolbar MUST provide a Filter control and a "Show disabled agents" checkbox on the left and a primary "New agent" button on the right (moved from the old page header). "Show disabled agents" MUST default off, persist in localStorage, and when off hide disabled agents from every tab except Disabled. The Filter MUST narrow visible rows by case-insensitive substring over name, harness, and model; an empty field applies no filter.
- **FR-015**: The table MUST be full-bleed and horizontally scrollable inside the list view when narrower than its columns, sorted by name, with columns in order: Name (mono link to the edit page, preserving the name-mismatch badge and parse-error row treatment), Harness (mono text), Model (mono text truncated with full value in title), Kind (asset and/or job badges), Schedules/Sensors, Latest run, Checks, Run history.
- **FR-016**: The Schedules/Sensors cell MUST render one schedule pill per configured cron using a type-driven icon (clock for a job schedule, sensor for an asset schedule) and a human-readable label ("Every day at 7:00 AM") in the box's timezone via one shared cron-to-text helper; on-demand agents show an em-dash. Each pill's compact toggle MUST reflect Dagster's instigation state and, when permitted, flip it via a write endpoint; the toggle MUST be disabled with an explanatory title when the agent is disabled, Dagster is down, or the state is unknown.
- **FR-017**: The Latest-run cell MUST show a status dot plus relative time with the text linking to that run in Dagster, and an em-dash when no run is known or Dagster is unreachable. The Checks cell MUST show, for asset agents with declared checks, one result icon per check from the latest materialization (green pass, yellow failed-non-blocking, red failed-blocking with error/timeout counting as failed, grey not-yet-run), four per row wrapping, each titled with check name and status, and an em-dash for agents without checks. The Run-history cell MUST show up to ten bars newest-at-right (green success, red failure, neutral for empty/in-progress), each titled with the run's status and time.
- **FR-018**: The old Status column and the old Dagster (runs button) column MUST be removed; enabled/disabled is conveyed by row style, the Disabled tab, and the show-disabled checkbox; the per-agent Dagster deep link survives via the Latest-run and Run-history cells.
- **FR-019**: Columns 1–4 (Name, Harness, Model, Kind) MUST come from the store at render time and never wait on Dagster. Columns 5–8 MUST be filled after first paint from a single activity read that, for all agents in one call, returns per-schedule instigation state, latest run (id, status, start/end), the last ten run statuses, and latest-materialization asset-check results; the read MUST issue a bounded number of GraphQL requests (target: one aliased query, never one per agent), use a short timeout, and return null (unknown) fields rather than guessing.
- **FR-020**: When Dagster is unreachable, columns 5–8 MUST degrade to em-dashes / disabled toggles and the page MUST show a warning alert reading "Run data unavailable: Dagster is not reachable"; the page MUST never fail to render because Dagster is down. The "No agents yet" card MUST render inside the list view below the toolbar when the store is empty.
- **FR-021**: The write endpoint that flips a schedule/sensor MUST call Dagster's start/stop mutation and look up runs and assets by the same job name / asset key the factory registers (following the existing store naming helpers). If the mutation cannot be authorised or is unreliable, the toggle MUST render as a disabled, state-reflecting control titled "Turn on from Dagster".
- **FR-022**: The standalone Automation page and its route, template, page-specific store, and script MUST be removed, along with its nav entry. Editing an agent's schedule remains available in the agent create/edit form (the schema-driven Triggers section), which already writes each agent's `triggers:` block; no scheduling function is lost. Tests specific to the removed Automation page MUST be removed or repointed accordingly.

#### Design system sync

- **FR-023**: The served `app.css`, dropdown script, and icon sprite MUST be brought level with their design-system counterparts using one recorded mechanism for icon resolution (recommended: inline the sprite once in the base template and make dropdown icon references document-relative), and the icons missing from the sprite (filter, settings, check-circle, warn-tri, x-circle, overview, runs, plus clock, sensor, search) MUST be added.
- **FR-024**: A test MUST fail when a served shared asset and its design-system copy diverge beyond the one documented substitution, so the design system cannot silently run ahead again.
- **FR-025**: The shared macros MUST be extended per the mocks: the schedule-pill macro gains the type-driven icon; the select macro passes through the per-option icon, trailing note, and sticky filter-row data; the tabs macro renders a tab count. No new manifest component is required (the Dropdown card is a form of Select).
- **FR-026**: All placeholder values the mocks express as inline styles (em-dash cell colour, mono link colour, dropdown list reset) MUST become token-based classes in the stylesheet; served templates MUST carry no inline `style` attributes or `<style>` blocks (constitution VII).
- **FR-027**: The served pages MUST render offline with egress blocked (fonts, icons, sprite) and MUST make no external request. The project README MUST gain short sections for the tabbed list view, the settings modal, the foot links, and the indigo Dagster accent.

### Key Entities *(include if feature involves data)*

- **Agent (store view)**: the render-time facts for a row — name, harness, model, kind (asset and/or job), enabled flag, configured crons (each with type: job schedule or asset schedule, and cron expression), declared checks, and any parse-error or name-mismatch state. Source: the agents store; never waits on Dagster.
- **Agent activity (Dagster view)**: the run-derived facts for a row, fetched in one bounded call — per-schedule/sensor instigation state (running/stopped/unknown), latest run (id, status, start/end), last ten run statuses, and latest-materialization asset-check results (per check: name, status pass/fail-non-blocking/fail-blocking/not-run). Null fields mean unknown.
- **Theme preference**: one of {light, dark, system}, stored per-browser in localStorage; resolves to a stamped theme attribute (dark or none for light); not persisted server-side. (Indigo is an accent ramp within these themes, not a theme value.)
- **UI view state**: the operator's transient list choices — active tab (in URL), filter text (transient), and show-disabled flag (localStorage); none persisted server-side.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the agents page alone, an operator can determine each agent's kind, schedule timing, last-run outcome, and check results without opening any individual agent — verified against the example config for an asset+job agent, an on-demand agent, a disabled agent, and an agent with mixed check results.
- **SC-002**: The agents page renders its store-backed columns (1–4), tabs with correct counts, and toolbar within the normal page load even when Dagster is unreachable, and shows the "Run data unavailable" warning instead of failing.
- **SC-003**: Selecting a theme in the settings modal changes the accent, links, focus ring, checkbox tint, and primary button with no page reload, and the choice survives a reload; "Use system setting" follows an OS theme flip live.
- **SC-004**: Every served page (agents list, new/edit form, 404) shows the revised foot in both light and dark with no theme buttons and with the Dagster connection points in the indigo accent, collapses to a 68px rail and back with no overflow, and the collapsed foot link's accessible name reads "Show navigation".
- **SC-005**: The run-derived columns for all agents are populated by a single bounded activity read (one aliased GraphQL query, never one per agent) with a short timeout.
- **SC-006**: The design-system sync test fails when a design-system shared asset is edited without its served counterpart; the no-inline-styles and design-system-class conformance tests still pass on the new tree and still fail on an inserted literal or inline style; the theme-accessibility assertion targets the modal dropdown.
- **SC-007**: With egress blocked, every page renders fonts, icons, and the sprite with no request leaving the box.

## Assumptions

The brief's five open questions were resolved in the Clarifications section; the remaining items below are reasonable defaults for details the brief did not raise.

- **A1 (Nav contents, Q1 — resolved)**: The nav links to Agents only; the Automation page is removed (see Clarifications). Overview and Runs are added when their pages exist (012/023).
- **A2 (Filter, Q2)**: The Filter control is a working inline text filter over name, harness, and model. Alternative: a clearly marked non-interactive placeholder until a richer faceted filter is designed.
- **A3 (Live schedule toggles, Q3 — resolved)**: The pill toggle starts/stops the Dagster schedule or sensor through a new write endpoint; when the mutation is unavailable it degrades to a disabled, state-reflecting control.
- **A4 (Run history, Q4 — resolved)**: Run history is the ten most recent runs of the agent's Dagster job (asset agents: runs that materialized the asset), newest at right; partitioned asset agents use the same treatment (no per-partition history).
- **A5 (Indigo, Q5 — resolved)**: Indigo is not a selectable theme; it is an accent ramp added to the Light and Dark themes and applied to Dagster connection points (see Clarifications and FR-010).
- **A6**: The `system` theme keeps today's behaviour (follow `prefers-color-scheme`, live update on OS change); the mock's "default to dark unless the OS says light" is treated as practically equivalent and not a required change.
- **A7**: The schedule/sensor toggle's checked-track uses the indigo Dagster accent by design (it toggles Dagster functionality, so it is a Dagster connection point), which is consistent across both themes.
- **A8 (Instigator kind)**: A `job_schedule` is registered as a Dagster **schedule** (`sched_<stem>`) and an `asset_schedule` as a Dagster **sensor** (`autocond_<stem>`, an `AutomationConditionSensorDefinition`), per `orchestrator/factory.py`. The list's pill toggle therefore start/stops a schedule for job crons and a sensor for asset crons; both are cron-driven for the human-readable label. The single mapping (store `type` → icon, `dagster_name`, and toggle `kind`) is pinned in `contracts/dagster-activity.md §0`.

## Dependencies

- Completed 009 (design system) and 010 (file layout); the design-system mocks, tokens, stylesheet, dropdown script, and icon sprite delivered under `ui/design-system/`.
- Dagster's existing GraphQL API for read-only latest-run and asset-check reads and for the start/stop instigation mutation; the agents store's existing job-name / asset-key naming helpers.
- Shared contracts in `specs/000-briefs-revised.md` (paths, missing data is unknown not zero, Dagster owns run state) and constitution principle VII (One Design System; CSS in dedicated stylesheets, no inline styles in application templates).

## Out of Scope

- Overview and Runs pages and their nav entries (012/023); run detail pages and transcript viewing (012).
- Editing cron expressions from the agents table (this stays in the agent edit form's Triggers section).
- A theme setting in `config/settings.yaml`; server-side persistence of tab/filter/show-disabled choices.
- Sensors beyond the asset-schedule instigator Dagster already registers.
- Rebuilding the agent form beyond the shared macro and icon changes.
- Mobile layout.
- Porting the superseded `AgentsList.dc.html` (the tabbed list replaces it for the agents page).
