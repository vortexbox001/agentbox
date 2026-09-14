# Feature Specification: Design System Migration

**Feature Branch**: `009-design-system-migration`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Replace the Archon design system (dark-only, cyan/magenta, Playfair serif, --ax-* tokens) with the AgentBox design system (Dagster-derived, light+dark, navy/teal/lime, Inter + Source Code Pro, 240px collapsible sidebar, no top bar, Lucide icons), so the management UI looks like a sibling of Dagster and the design system lives in the repo for humans and coding agents. Visual and structural migration only; no feature behaviour changes. Runs before spec 011."

## Clarifications

### Session 2026-09-13

- Q: Should meeting a specific colour-contrast standard be an explicit acceptance criterion? → A: WCAG 2.1 AA in both light and dark themes.
- Q: How should the "no request leaves the box" guarantee be verified? → A: Static grep of served CSS/HTML for external URLs (automated); runtime "block egress and reload" remains a manual pre-release check.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Management UI reads as a sibling of Dagster (Priority: P1)

An operator who works in both the Dagster UI (:3000) and the management UI opens each
existing management page — agents list, agent create/edit form, automation list, and the
404 page — and finds a visual language that matches Dagster: the same 240px collapsible
left sidebar with no top bar, the same Inter body / Source Code Pro mono typography, the
same neutral surface and border grays, and the same red/yellow/green status semantics.
Only the brand accent differs (teal, where Dagster uses blurple). The operator can switch
between light and dark themes, and the choice persists.

**Why this priority**: This is the whole point of the migration — a coherent operator
experience where the management UI does not look like a different product. Without it the
feature delivers nothing. It is also the largest, most visible slice and can ship on its own.

**Independent Test**: Open every existing page in both light and dark mode. Confirm the
sidebar, typography, surfaces, borders, and status colours match the Dagster reference;
confirm the theme toggle switches and persists; confirm no page still shows the old
dark-only cyan/magenta/serif Archon styling.

**Acceptance Scenarios**:

1. **Given** the migrated UI in a fresh browser with OS set to dark, **When** the operator
   loads any page, **Then** the page renders in dark theme with the new tokens and no
   flash of the wrong theme before first paint.
2. **Given** any page, **When** the operator opens the theme control in the sidebar foot
   and picks Light, Dark, or System, **Then** the theme changes without a full reload and
   the choice is remembered on the next visit.
3. **Given** the theme control set to System, **When** the operator changes the OS theme,
   **Then** the UI follows the OS theme without a reload flash.
4. **Given** any migrated page, **When** the operator inspects the rendered CSS, **Then**
   no `--ax-*` token resolves and no serif (Playfair) font is loaded.
5. **Given** the management UI and the Dagster UI side by side in dark mode, **When**
   compared, **Then** sidebar width, font, surface/border gray scale, and status
   red/yellow/green match, and only the accent colour differs.

### User Story 2 - Every page is built from shared component macros (Priority: P1)

A UI page composes shared components (buttons, inputs, selects, checkboxes, toggles,
badges, status dots, alerts, spinners, tabs, cards, dialog, table) rather than defining
its own control styling. When the design system changes, updating one shared component
updates every page that uses it. The agent create/edit form — the most control-dense
screen — renders every one of its selects, toggles, checkboxes, inputs, and buttons from
these shared components, and its existing behaviour (keyboard navigation, validation error
states) is preserved.

**Why this priority**: Consistency and future maintainability are the durable value; ad
hoc per-page styling is what created the drift this migration fixes. It is co-equal with
Story 1 because a "sibling of Dagster" look that is reimplemented page by page will drift
again immediately.

**Independent Test**: Render each page and confirm every `<select>`, `<button>`, and
`<table>` carries the design-system class rather than being bare. On the agent form,
exercise the dropdown keyboard scenarios (open, arrow, select, Escape) and trigger a
validation error; confirm both still work.

**Acceptance Scenarios**:

1. **Given** any rendered page, **When** the markup is inspected, **Then** every select,
   button, and table carries the design-system class and no page defines its own button
   or card styling.
2. **Given** the agent form, **When** the operator navigates a select with the keyboard
   (open, arrow keys, select, Escape), **Then** the behaviour matches the pre-migration
   dropdown from spec 002.
3. **Given** the agent form with an invalid field, **When** the form is submitted, **Then**
   the validation error state renders through the shared component styling.
4. **Given** the shared component set, **When** compared against the design-system
   component manifest, **Then** every listed component has a corresponding macro.

### User Story 3 - The design system lives in the repo for humans and agents (Priority: P2)

A human contributor or a coding agent working on the UI can find one authoritative,
in-repo source of the visual language and the component reference, and a skill that points
Claude Code at it automatically. The design-system bundle is served in-app as a developer
reference, and a governing "Design" principle records the rule that new work uses the
system's tokens and macros.

**Why this priority**: This keeps the migration from decaying — it is how spec 011 and
later work stay on the system. It depends on Stories 1 and 2 existing but is not needed to
demonstrate the visual result, so it is P2.

**Independent Test**: Open the served design-system reference in the app. Start a Claude
Code session in the repo and confirm the design skill is listed; ask it to add a card and
confirm the produced markup uses the shared card component. Confirm the README, AGENTS.md,
and constitution describe the new location and rule.

**Acceptance Scenarios**:

1. **Given** the app is running, **When** the operator opens the design-system path, **Then**
   the developer reference app is served (not the old Archon doc).
2. **Given** a Claude Code session in the repo, **When** skills are listed, **Then** the
   design skill appears and its instructions point at the in-repo README.
3. **Given** that session is asked to add a card, **When** it produces markup, **Then** the
   markup uses the shared card component rather than bespoke styling.
4. **Given** the project docs, **When** read, **Then** README, AGENTS.md, and the
   constitution describe the design-system location and the "use tokens and macros" rule.

### User Story 4 - The UI works with no internet access (Priority: P2)

The management UI runs on a self-hosted box that may have no egress. Fonts and icons must
render, and no page may make an outbound request, when the network is unavailable.

**Why this priority**: The deployment target is an isolated box; a design that depends on
Google Fonts or a CDN would silently degrade there. It is P2 because it constrains how
Stories 1–2 are delivered rather than being a separate visible surface.

**Independent Test**: Block egress and reload every page. Confirm fonts and icons still
render and that no request leaves the box (no googleapis / unpkg / cdn URL is requested).

**Acceptance Scenarios**:

1. **Given** the box has no internet, **When** any page loads, **Then** it renders correctly
   and issues no outbound request.
2. **Given** the served CSS and HTML, **When** inspected, **Then** no googleapis, unpkg, or
   cdn URL appears and icons resolve from a local sprite.
3. **Given** self-hosting the brand fonts is blocked by licence, **When** the UI loads,
   **Then** it renders with the system-font fallback stack and still makes no outbound
   font request (see Assumptions — null action).

### Edge Cases

- **First paint before script runs**: the theme must be resolved before first paint so no
  wrong-theme flash occurs, even on the initial load with no stored preference.
- **No stored theme preference**: the UI defaults to the OS preference.
- **Stored preference is System, OS theme changes mid-session**: the UI follows without a
  reload flash.
- **Retired magenta uses**: the two former magenta uses (queued status, template identity)
  must map onto the new badge intents (queued → gray, template/scheduled → lime) with no
  orphaned magenta reference remaining.
- **Sidebar collapse state**: collapsing to the narrow width and back is preserved across
  navigation and reloads.
- **Deliberately non-conforming markup**: an inserted literal colour, literal pixel value,
  `--ax-*` token, or external font URL must be caught by the automated checks.
- **Font licence blocker**: if brand fonts cannot be self-hosted, the fallback stack renders
  and the Google Fonts import is never restored in served CSS.

## Requirements *(mandatory)*

### Functional Requirements

#### Design-system bundle in the repo

- **FR-001**: The repository MUST contain the AgentBox design-system bundle in place of the
  Archon files, with the retired Archon artefacts (the Archon doc, its token file, the
  three specimen files, and its support script) removed.
- **FR-002**: The design-system README MUST be the single human-readable source of truth for
  the visual language, and the token files MUST be the machine-readable source.
- **FR-003**: The design-system directory MUST continue to be served in-app, and the served
  design-system path MUST open the developer reference app.

#### Shared component set

- **FR-004**: The UI MUST provide one shared, reusable component for each design-system
  component listed in the bundle's component manifest (button, text input, select,
  checkbox, toggle, badge, status dot, alert, spinner, tabs, card, dialog, table).
- **FR-005**: Each shared component's parameters MUST mirror the corresponding design-system
  component contract.
- **FR-006**: Pages MUST compose these shared components; no page may define its own button
  or card styling.
- **FR-007**: The responsive form-grid layout used by the agent form MUST be preserved,
  re-expressed on the new spacing scale.

#### Tokens, theme, and shell

- **FR-008**: All styling MUST be expressed through the new design-system tokens
  (colour, type, space, radius, shadow, transition, nav-width, icon). No `--ax-*` token may
  remain in served CSS, templates, or JS.
- **FR-009**: The theme MUST support Light, Dark, and System, selectable from a control in
  the sidebar foot, persisted locally, and applied before first paint with no wrong-theme
  flash; the base template MUST NOT hard-code dark.
- **FR-010**: The shell MUST have no top bar. Navigation MUST be a 240px collapsible sidebar
  (with a defined collapsed width) whose collapse state persists, containing the brand block
  and the theme control alongside the Dagster link.
- **FR-011**: Page title, breadcrumb, and page actions MUST live in a page header at the top
  of the content area (the location the top bar formerly occupied).
- **FR-012**: The Dagster status link, status region, toast region, and modal root MUST
  retain their existing behaviour, restyled on the new system.
- **FR-013**: All serif typography MUST be removed, including the former italic-serif
  "thinking" treatment, replaced by the design system's body/mono split.
- **FR-014**: The retired magenta accent MUST be removed; its two former uses MUST map to
  the queued (gray) and scheduled/template (lime) badge intents.

#### No-egress rendering

- **FR-015**: Brand fonts (Inter, Source Code Pro) MUST be self-hosted locally, with the
  external font import replaced by a local one, so the UI renders correctly with no internet.
- **FR-016**: Icons MUST resolve from a locally vendored Lucide sprite with no runtime CDN
  reference.
- **FR-017**: No served CSS or HTML may reference an external font, icon, or asset URL
  (no googleapis, unpkg, or cdn host).

#### Copy

- **FR-018**: UI text MUST follow the design system's content rules: sentence case, no emoji,
  lowercase status text, numeric counts in mono, relative timestamps under a day, and page
  titles of one or two words.

#### Governance, docs, and skill

- **FR-019**: A design skill MUST be present under the repo's skills directory pointing at
  the in-repo README, so a coding agent working on the UI picks it up automatically.
- **FR-020**: Project docs (README, AGENTS.md) MUST describe the new design-system location
  and the "sibling of Dagster / use tokens and macros" rule.
- **FR-021**: The project constitution MUST gain a "Design" principle requiring every screen
  to use design-system tokens and component macros, forbidding literal colours/fonts/pixel
  values in app styling and templates, and requiring new components to be added to the
  design system first and the shared component set second.

#### Automated conformance checks

- **FR-022**: An automated check MUST fail when served CSS/templates contain a literal
  colour, a literal pixel value (outside the token and font files), any `--ax-*` token, any
  external font/CDN URL, or any font-family declared outside the font file — and MUST pass
  on the migrated tree.
- **FR-023**: An automated check MUST verify the design-system docs reference the new README
  and that every component in the bundle's manifest has a corresponding shared component.
- **FR-024**: An automated check MUST verify that every select, button, and table in rendered
  pages carries the design-system class rather than being bare.

#### Behaviour preservation

- **FR-025**: No feature behaviour may change. The keyboard behaviour of the spec 002
  dropdown and all form validation states MUST be preserved through the migration.

#### Accessibility

- **FR-026**: Text and interactive-UI colour contrast MUST meet WCAG 2.1 AA in both the
  light and dark themes.

### Key Entities

- **Design token**: a named design value (colour, type step, space step, radius, shadow,
  transition, nav width, icon size) that all styling references instead of a literal.
- **Component macro**: a shared, reusable UI control whose parameters mirror a design-system
  component contract; the single definition every page composes.
- **Theme**: one of Light, Dark, or System; the resolved theme determines which token values
  apply and is persisted per viewer.
- **Design-system bundle**: the in-repo authoritative set of README, tokens, component
  references, guidelines, reference app, and assets that humans and agents consult.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing pages (agents list, agent create/edit, automation list, 404)
  render correctly in both light and dark themes with no `--ax-*` token resolving and no
  serif font loading.
- **SC-002**: A side-by-side comparison with the Dagster UI in dark mode matches on sidebar
  width, font, surface/border gray scale, and status red/yellow/green, with only the accent
  colour differing.
- **SC-003**: No served CSS or HTML references an external font, icon, or asset URL
  (verified by automated static grep for googleapis / unpkg / cdn hosts); as a manual
  pre-release check, every page renders fonts and icons and issues zero outbound requests
  with egress blocked.
- **SC-004**: 100% of design-system components in the manifest have a corresponding shared
  component, and 100% of selects, buttons, and tables in rendered pages carry the
  design-system class.
- **SC-005**: The conformance checks fail on a deliberately inserted literal colour, literal
  pixel value, and `--ax-*` token, and pass on the migrated tree.
- **SC-006**: All pre-existing UI behaviour still passes — the spec 002 dropdown keyboard
  scenarios and form validation states are unchanged.
- **SC-007**: A Claude Code session in the repo lists the design skill and, asked to add a
  card, produces markup using the shared card component.
- **SC-008**: The theme toggle switches Light/Dark/System without a reload flash, follows the
  OS in System mode, and persists across visits; the sidebar collapses and restores and its
  state persists.
- **SC-009**: Text and interactive-UI colour contrast meets WCAG 2.1 AA in both light and
  dark themes on every existing page.

## Assumptions

- **Users** are operators of the self-hosted box and the humans and coding agents who work
  on the UI; there is no external/public audience.
- **Deployment target** is an isolated Raspberry Pi that may have no internet egress; the
  design must render fully offline.
- **Server-rendered UI**: the UI is server-rendered templates, so each design-system
  component is re-expressed as a shared template macro rather than shipped as-is; the bundle's
  component references are the implementer's guide, not runtime code.
- **Font licence — null action**: if self-hosting Inter / Source Code Pro under a
  licence-compatible path is blocked, the effective rendering keeps the system-font fallback
  stack, the font-face file stays in place with an explanatory comment, and the external
  font import is never restored in served CSS. The brand fonts then load only when the box
  has internet. This is recorded in the plan.
- **Theme persistence** uses local browser storage only; a server-side theme setting is out
  of scope and arrives with the Settings page in spec 011.
- **Sequencing**: this migration lands before spec 011 so that 011's larger new surfaces
  (Runs, Settings) are built on the new system rather than migrated afterward.

## Out of Scope

- New pages or features (spec 011 and later build on this migration).
- Replacing Inter / Source Code Pro with Geist.
- A server-side theme setting in orchestrator settings.
- Porting the React reference kit to server-rendered templates beyond what the existing
  pages need.
- Mobile layout.
- Automated runtime (headless-browser) egress testing — offline rendering is a manual
  pre-release check; automated conformance is the static grep for external URLs.
