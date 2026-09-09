# Feature Specification: Design System Compliance

**Feature Branch**: `002-design-system-compliance`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "I've udpated the design system reference files in /ui/design-system: I've added drop down styles and responsive grid layouts. do the following: make sure that ARCHON-DESIGN-SYSTEM.md is still up-to-date; fix all dropdowns in the site to be compliant with the custom dropdown component spec; fix the toggle on the site: it does not render as spec'ed; apply the ax-grid-cards layout to the agent detail page and the create/edit agent screens"

## User Scenarios & Testing *(mandatory)*

The agent management UI is meant to be a faithful rendering of the Archon design system. The reference files in `ui/design-system/` were updated with new dropdown styles and responsive grid layouts, and the running site has drifted from them: its dropdowns are plain browser selects, its enabled/reload toggle renders with the wrong colors, and its form and detail screens do not use the intended responsive form-grid layout. This feature brings the site back into compliance with the reference and keeps the human-readable design-system guide accurate.

### User Story 1 - Dropdowns match the custom dropdown component (Priority: P1)

Someone filling in an agent form opens any of the selectable fields (harness, enabled, effort, permission mode, network, the template picker, and the prompt picker) and sees the custom dropdown from the design reference rather than the browser's native select popup.

**Why this priority**: Dropdowns appear on every create and edit screen and are the most-used control in the product. A native select popup is the most visible break from the design language, so fixing it delivers the largest fidelity gain and touches every form the user meets.

**Independent Test**: Open the create-agent form and the edit-agent form, open each selectable field, and confirm the opened menu matches the custom dropdown component (an elevated panel with the selected option highlighted in the accent color and the rest in muted text), and that choosing an option updates the field and closes the menu.

**Acceptance Scenarios**:

1. **Given** the create-agent form, **When** the user opens the harness field, **Then** a custom menu panel appears anchored to the control, listing every choice, with the current value visibly marked as selected.
2. **Given** an open dropdown, **When** the user picks a different option, **Then** the menu closes, the control shows the new value, and the form registers the change (including marking the form unsaved where that applies).
3. **Given** an open dropdown, **When** the user clicks elsewhere or presses Escape, **Then** the menu closes with no change to the value.
4. **Given** a dropdown that carries a validation error, **When** the form is validated, **Then** the control still shows its error state clearly while keeping the custom dropdown appearance.
5. **Given** a keyboard-only user focused on a dropdown, **When** they use the keyboard to open it and move between options, **Then** they can select a value without a pointer.

---

### User Story 2 - Toggle renders as specified (Priority: P1)

Someone on an agent form looks at the "enabled" and "reload Dagster after saving" toggles and sees them rendered exactly as the design reference specifies in both the on and off states.

**Why this priority**: The toggle currently renders with the wrong colors (its on state does not match the reference), which is an obvious, always-visible defect on the primary forms. It is small in scope and high in visible impact.

**Independent Test**: View a toggle in its off state and its on state and compare against the reference toggle: the off track and thumb, and the on track and thumb, each match the reference's colors, sizes, and thumb position.

**Acceptance Scenarios**:

1. **Given** a toggle in the off state, **When** it is displayed, **Then** the track uses the muted/translucent surface and the thumb sits at the left in the muted thumb color.
2. **Given** a toggle in the on state, **When** it is displayed, **Then** the track uses the solid accent color and the thumb is the light/foreground thumb color, positioned at the right.
3. **Given** a toggle, **When** it is switched between states, **Then** the thumb slides between the two positions with the reference's transition, and the track and thumb colors swap accordingly.
4. **Given** the site's styling rules, **When** the toggle is implemented, **Then** its colors come from design tokens rather than hard-coded color literals.

---

### User Story 3 - Responsive form-grid layout on agent detail and create/edit screens (Priority: P2)

Someone working in the create/edit form or viewing an agent's detail screen sees its fields arranged in the reference's responsive form grid, so label-and-field pairs flow into multiple columns on wide screens and collapse to fewer columns as the window narrows.

**Why this priority**: This improves the density and responsiveness of the busiest screens, but the screens are already usable, so it ranks below the two rendering-correctness stories.

**Independent Test**: Open the agent detail/edit screen and the create form at a wide viewport and confirm the label-and-field pairs lay out in multiple auto-filled columns with the reference gap; narrow the viewport and confirm the columns reduce without a horizontal scrollbar.

**Acceptance Scenarios**:

1. **Given** a wide viewport, **When** the agent detail/edit screen renders, **Then** its label-and-field pairs are arranged in the `ax-grid-form` pattern (auto-filled columns at the reference minimum field width and gap).
2. **Given** a wide viewport, **When** the create agent screen renders, **Then** its label-and-field pairs use the same `ax-grid-form` layout.
3. **Given** any supported viewport width, **When** the screen is resized from wide to narrow, **Then** the number of columns decreases smoothly and the page never scrolls horizontally.
4. **Given** an odd number of fields in a section, **When** the grid renders, **Then** the remaining fields fill the row without stretching awkwardly beyond the layout rules.
5. **Given** the agents list and the template picker, **When** they render, **Then** they continue to use the `ax-grid-cards` pattern for their card objects, unchanged by this story.

---

### User Story 4 - Design-system guide stays accurate (Priority: P3)

A developer reading `ui/design-system/ARCHON-DESIGN-SYSTEM.md` finds it describes the current reference files, including the newly added dropdown styles and responsive grid layouts, so the guide can be trusted as the source of truth.

**Why this priority**: Documentation accuracy is required by the project constitution, but it does not change what an end user sees, so it is the lowest priority of the four.

**Independent Test**: Read the guide's component and layout sections and confirm every dropdown variant and grid pattern present in the reference files is documented, and that nothing documented is absent from the reference.

**Acceptance Scenarios**:

1. **Given** the updated reference files, **When** a reader consults the guide, **Then** the custom dropdown component and the native select styling are both described, matching what the reference shows.
2. **Given** the updated reference files, **When** a reader consults the guide's layout section, **Then** every named grid pattern in the reference (including the card grid) is listed with its column rule and gap.
3. **Given** the guide, **When** it is reviewed against the reference, **Then** it contains no component or layout claim that the reference files contradict.

---

### Edge Cases

- A dropdown with many options (for example the model or prompt lists) must remain usable: the menu should not run off-screen and should allow the full list to be reached.
- The prompt picker's "Create new prompt…" entry, which reveals extra inputs when chosen, must keep that behavior after the dropdown is converted to the custom component.
- A dropdown near the bottom of a scrolling form must still show its menu without being clipped by the surrounding card or the viewport edge.
- On very narrow viewports both the form grid and the card grid must fall back to a single column rather than overflowing.
- Read-only or disabled screens (for example an agent written by a newer schema, which shows no editable form) must not present interactive dropdowns or toggles that imply editability.
- The custom dropdown and toggle must keep the existing token-discipline rule: no literal color or font values in site styles.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every selectable field in the management UI (harness, enabled state where shown as a select, effort, permission mode, network, the template picker, and the prompt picker) MUST render using the custom dropdown component defined in the design reference rather than the browser's native select control.
- **FR-002**: The custom dropdown MUST present, when opened, an elevated menu panel anchored to its control that lists all available options, visually marks the currently selected option in the accent style, and shows unselected options in the muted style, matching the reference's surface, border, radius, elevation, and spacing.
- **FR-003**: Selecting an option MUST update the field's value, close the menu, and propagate the change to the rest of the form (validation, unsaved-state tracking, dependent field visibility) exactly as the current native selects do today.
- **FR-004**: The custom dropdown MUST be dismissible without changing the value by clicking outside it or pressing Escape, and MUST be operable by keyboard (open, move between options, choose, and dismiss) for accessibility.
- **FR-005**: The custom dropdown MUST preserve every behavior the current selects provide, including the harness switch that shows/hides fields, the template picker that pre-fills the form, and the prompt picker's "Create new prompt…" reveal.
- **FR-006**: A dropdown in a validation-error state MUST continue to signal the error while retaining the custom dropdown appearance.
- **FR-007**: The enabled and reload toggles MUST render their off state with the reference's muted/translucent track and muted thumb positioned at the left.
- **FR-008**: The toggles MUST render their on state with the reference's solid accent track and light/foreground thumb positioned at the right.
- **FR-009**: Switching a toggle MUST animate the thumb between the two positions using the reference's transition, swapping the track and thumb colors to match the target state.
- **FR-010**: The agent detail/edit screen MUST arrange its label-and-field pairs using the `ax-grid-form` layout (auto-filled columns at the reference minimum field width with the reference gap).
- **FR-011**: The create-agent screen MUST arrange its label-and-field pairs using the same `ax-grid-form` layout.
- **FR-012**: Screens using a responsive grid MUST remain responsive: columns reduce as the viewport narrows, collapsing to a single column at the smallest widths, and the page MUST NOT scroll horizontally at any supported width.
- **FR-012a**: The agents list and the template picker MUST continue to use the `ax-grid-cards` layout for their card objects; this feature does not restyle them beyond keeping them compliant with the reference.
- **FR-013**: `ui/design-system/ARCHON-DESIGN-SYSTEM.md` MUST be updated so that its component and layout sections accurately describe the current reference files, including the newly added dropdown styles and responsive grid layouts, with no claim the reference files contradict.
- **FR-014**: All new and changed site styling MUST use design tokens only, with no literal color or font values, preserving the existing token-discipline rule.
- **FR-015**: The visual and behavioral changes MUST NOT alter the data written to agent or prompt files, the validation rules, or any API contract; they are presentation-and-interaction changes only.

### Key Entities

- **Custom dropdown component**: The reference's selectable control — a trigger showing the current value and a chevron, plus an elevated menu panel of options with a highlighted selection. Applies to every enum and file-picker field in the forms.
- **Toggle component**: The reference's on/off switch — a pill track and a sliding thumb, with distinct on and off color pairings.
- **Form grid (`ax-grid-form`)**: The reference's named responsive grid whose cells are label-and-field pairs — auto-filled columns at the form-field minimum width with the form gap — used for the create, edit, and detail agent screens.
- **Card grid (`ax-grid-cards`)**: The reference's named responsive grid whose cells are self-contained cards — auto-filled columns at the compact-card minimum width with the card gap — used for the agents list and the template picker.
- **Design-system guide (`ARCHON-DESIGN-SYSTEM.md`)**: The human-readable description of the reference files that must track their current state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the create and edit agent screens, 100% of selectable fields open the custom dropdown component; none fall back to the browser's native select popup.
- **SC-002**: A reviewer comparing each dropdown, in both closed and open states, against the reference finds no discernible difference in surface, border, elevation, spacing, or selected-option treatment.
- **SC-003**: A reviewer comparing the enabled and reload toggles, in both on and off states, against the reference finds the track color, thumb color, thumb position, and size match in every state.
- **SC-004**: The agent detail/edit screen and the create screen render their fields as an auto-filled multi-column form grid at a wide viewport and reflow to fewer columns as the viewport narrows, with no horizontal page scroll at any width from the smallest supported phone width to a wide desktop; the agents list and template picker keep their card grid.
- **SC-005**: Every dropdown and toggle can be operated with keyboard only, and no site stylesheet or template introduces a literal color or font value.
- **SC-006**: A line-by-line review of `ARCHON-DESIGN-SYSTEM.md` against the reference files finds every dropdown variant and grid pattern documented and no contradicted claims.
- **SC-007**: Creating and editing an agent through the updated UI produces byte-identical files and the same validation and reload behavior as before the change.

## Assumptions

- "The custom dropdown component spec" refers to the reference's "Custom Dropdown (open)" component — a scripted control with an elevated options panel and an accent-highlighted selection — not merely a native `<select>` restyled with a custom chevron. Both variants exist in the reference; the wording ("custom dropdown component") points to the scripted one, and it is applied to every selectable field.
- Keyboard operability and basic assistive-technology semantics (a labeled control, options a keyboard user can reach and choose, and a state that conveys the current selection) are in scope for the custom dropdown, since replacing a native select otherwise removes accessibility the browser provided for free.
- The create/edit and detail screens use the `ax-grid-form` pattern for their fields, which is the reference's stated pattern for agent-configuration forms (a responsive multi-column grid whose cells are label-and-field pairs). The original request named `ax-grid-cards`, but both reference patterns are responsive column grids; `ax-grid-cards` cells are self-contained cards, which suits the agents list and template picker, while `ax-grid-form` cells are bare label-and-field pairs, which suits the forms. This was confirmed with the requester, so no guide/reference tension remains.
- The design reference expresses some off-state toggle colors as literal values (for example translucent white); to honor the site's token-only rule, the implementation will use the existing design tokens that carry those same values rather than the literals themselves.
- Scope is limited to the management UI screens already built (agents list, agent detail/edit, create form) and the design-system guide. The design canvas `.dc.html` reference files themselves are treated as the source of truth and are not modified by this feature.
- No change is made to agent YAML output, prompt files, validation, secret handling, or any API route; this feature is presentation and interaction only.
