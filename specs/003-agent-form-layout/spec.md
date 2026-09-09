# Feature Specification: Agent Form Layout

**Feature Branch**: `003-agent-form-layout`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "spec out the changes to the layout we've just been discussing, including the 3, 2, and 1 column layouts"

## Overview

The agent create and edit screens currently show eight full-width cards stacked in one column, grouped the way the YAML file happens to be written (Identity, Model, Prompt & output, Workspace, Execution, Scheduling, Container resources, Environment). On a wide screen most of each card is empty, and the grouping does not match how an operator thinks about an agent.

This feature regroups the fields into three conceptual columns and lays them out responsively:

- **Runs** — whether and when the agent runs, and how long a run may take. This column is the one most often revisited after an agent exists, and it is reserved to hold a compact recent-runs list in a later release.
- **Job** — what the agent does: the prompt it processes, the directories it reads and writes, the environment it receives, and the tools it may use.
- **Box** — what runs it: the harness and model, and the container it runs in.

The same grouping is used for the written YAML file, so an agent definition reads in the same order on disk as on screen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fields regrouped into Runs, Job, and Box (Priority: P1)

An operator opens an existing agent and sees its settings grouped into three labelled column groups, Runs, Job, and Box, each holding a small number of cards whose fields belong together conceptually. The name of the agent sits above the groups as a lead strip, and the "Reload Dagster after saving" toggle sits at the top right of the content pane, directly under the Save button.

**Why this priority**: The regrouping is the substance of the feature. Without it the responsive layout has nothing coherent to arrange, and the operator's confusion about where a setting lives is not addressed.

**Independent Test**: Open the edit screen for a claude-code agent and confirm every field appears exactly once, in the card and column group listed in FR-002 through FR-004, with the lead strip and the reload toggle in their specified positions. Repeat for the create screen and for one agent of each other harness.

**Acceptance Scenarios**:

1. **Given** an existing claude-code agent, **When** its edit screen renders, **Then** the Runs group shows a Schedule card (Enabled, Schedule) and a Limits card (Timeout, Max turns); the Job group shows Prompt (Prompt file, Append system prompt), Directories (Workspace, Wipe workspace, Output directory), Environment (Env file, Environment variables), and Tools & permissions (Permission mode, Allowed tools, Disallowed tools, MCP config); the Box group shows Harness & model (Harness, Model, Effort, Fallback model) and Container (Network, Memory, CPUs).
2. **Given** an existing api agent, **When** its edit screen renders, **Then** cards whose fields do not apply to that harness are absent (no Tools & permissions, no Directories), the Limits card shows only Timeout, and the Harness & model card shows Max tokens in place of Effort and Fallback model.
3. **Given** the edit screen, **When** it renders, **Then** the agent's name appears in a lead strip above the column groups, read-only, and no Identity card exists.
4. **Given** the create screen, **When** it renders, **Then** the "Start from template" picker and an editable Name field appear in the lead strip above the column groups, and the column groups use the same cards as the edit screen.
5. **Given** either screen, **When** it renders, **Then** the "Reload Dagster after saving" toggle is at the top right of the content pane, directly under the Save button, and no longer at the bottom of the form.
6. **Given** either screen, **When** the operator changes the harness, **Then** cards and fields appear or disappear according to the new harness while the three column groups and the lead strip stay in place.

---

### User Story 2 - Three columns on a wide screen (Priority: P1)

On a wide monitor the operator sees Runs, Job, and Box side by side as three columns, Runs on the left, Job in the middle and wider than the other two, Box on the right. Cards stack top to bottom inside each column, and a short column does not stretch its cards to match a tall neighbour.

**Why this priority**: The single-column stretch across a wide screen is the complaint that prompted this feature. Three columns is the target presentation on the operator's primary display.

**Independent Test**: Open the edit screen at an 1800px-wide window and confirm three column groups sit side by side with Job visibly wider than Runs and Box, every card is fully visible without horizontal scrolling, and each column's cards are stacked from the top with no card stretched to fill empty space.

**Acceptance Scenarios**:

1. **Given** a viewport at least 1800px wide, **When** the screen renders, **Then** Runs, Job, and Box appear side by side in that left-to-right order.
2. **Given** the three-column layout, **When** widths are compared, **Then** the Job column is wider than the Runs and Box columns, which are equal to each other.
3. **Given** the three-column layout, **When** the Runs column holds fewer or shorter cards than Job, **Then** the Runs cards remain their natural height, stacked from the top, with empty space below them rather than stretched cards.
4. **Given** the three-column layout, **When** a card's fields render, **Then** they use the existing responsive form grid inside the card, so a narrow column shows one field per row and wide controls (prompt picker, tool lists, environment variables, append system prompt) span the full card width.
5. **Given** the three-column layout at the widest supported width, **When** the screen renders, **Then** the page never scrolls horizontally.

---

### User Story 3 - Two columns on a mid-width screen (Priority: P2)

On a laptop-sized window the layout folds to two columns: Runs stays at the top left, Box folds underneath Runs in the left column, and Job takes the right column for its full height. Runs stays first because schedule changes and run checks are the most common reason to revisit an agent.

**Why this priority**: The operator's secondary display is laptop-width. Two columns is the layout most sessions will see there, so it must be deliberate rather than an accident of wrapping.

**Independent Test**: Open the edit screen at a 1440px-wide window and confirm the left column shows the Runs cards followed by the Box cards, the right column shows the Job cards, and nothing scrolls horizontally.

**Acceptance Scenarios**:

1. **Given** a viewport between the two-column and three-column thresholds (for example 1440px wide), **When** the screen renders, **Then** exactly two columns are shown.
2. **Given** the two-column layout, **When** the left column is inspected, **Then** it holds the Runs cards followed by the Box cards, each keeping its own group heading.
3. **Given** the two-column layout, **When** the right column is inspected, **Then** it holds only the Job cards and extends alongside both Runs and Box.
4. **Given** the two-column layout, **When** the window is widened past the three-column threshold, **Then** Box moves out to its own third column without any card changing its content or order within its group.

---

### User Story 4 - One column on a narrow screen (Priority: P2)

On a narrow window or a phone the three groups stack vertically in the order Runs, Job, Box, each group keeping its heading and its cards in order.

**Why this priority**: Narrow-width correctness is required by the design system and by the previous feature's responsiveness rule, but a phone is not the operator's normal way of editing an agent, so it ranks below the two wider layouts.

**Independent Test**: Open the edit screen at a 900px-wide window and confirm the groups appear one after another in the order Runs, Job, Box, at full content width, with no horizontal scrolling.

**Acceptance Scenarios**:

1. **Given** a viewport narrower than the two-column threshold (for example 900px), **When** the screen renders, **Then** the groups stack in a single column in the order Runs, Job, Box.
2. **Given** the single-column layout, **When** a card with the widest controls (environment variables with several rows) renders, **Then** each row fits within the card without clipping or horizontal scrolling.
3. **Given** the single-column layout, **When** the lead strip renders, **Then** the name field and, on the create screen, the template picker wrap onto separate rows rather than overflowing.

---

### User Story 5 - YAML files follow the same grouping (Priority: P3)

An operator opening an agent file on disk finds its keys grouped under the same headings and in the same order as the screen: Runs, Job, Box.

**Why this priority**: Keeping the file and the form in the same order removes one source of confusion, but the file is already valid and readable today, so this is the lowest-value story.

**Independent Test**: Save an agent from the edit screen, open the written file, and confirm the section comment headers and key order match the groups and cards in FR-002 through FR-004.

**Acceptance Scenarios**:

1. **Given** an agent saved from the form, **When** the written file is read, **Then** its keys appear grouped by the new cards in the order Schedule, Limits, Prompt, Directories, Environment, Tools & permissions, Harness & model, Container, with the name first.
2. **Given** an agent file written under the previous grouping, **When** it is loaded into the form and saved again without changes, **Then** the file is regrouped into the new order and its values are unchanged.
3. **Given** an agent file with keys the form does not manage, **When** it is saved, **Then** those keys are still preserved in the trailing unmanaged section exactly as before.

---

### Edge Cases

- A harness whose applicable fields leave a card empty (for example the api harness has no tools fields) must omit that card entirely rather than showing an empty card. A column group is never empty: every harness has at least one Schedule field, one Prompt field, and the Harness field.
- Switching harness on the create screen must not leave a stale card behind or reorder cards; the cards for the new harness are rebuilt in the fixed order.
- A validation error on a field must still be shown inline at that field regardless of which column the field now lives in, and the first error must still be scrolled into view and focused after a failed save.
- At exactly the column thresholds the layout must resolve to one definite arrangement; no width may produce overlapping or half-wrapped columns.
- The unsaved-changes guard, the YAML preview, and the secret-detection warnings must behave identically to today; only the position of fields changes.
- The "Recent runs" card and the "Image" field discussed for later releases are not part of this feature. The Runs column must not show a placeholder for them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The create and edit screens MUST arrange agent settings in three named column groups, in this fixed order: Runs, Job, Box. Each group MUST render a visible heading with its name.
- **FR-002**: The Runs group MUST contain, in order: a Schedule card (enabled, schedule) and a Limits card (timeout_seconds, max_turns).
- **FR-003**: The Job group MUST contain, in order: a Prompt card (prompt_file, append_system_prompt), a Directories card (workspace, wipe_workspace, output_dir), an Environment card (env_file, env), and a Tools & permissions card (permission_mode, allowed_tools, disallowed_tools, mcp_config).
- **FR-004**: The Box group MUST contain, in order: a Harness & model card (harness, model, effort, fallback_model, max_tokens) and a Container card (network, memory, cpus).
- **FR-005**: The agent name MUST appear in a lead strip above the column groups rather than inside a card. On the edit screen it is read-only; on the create screen it is editable and the "Start from template" picker shares the lead strip. The existing Identity card is removed.
- **FR-006**: The "Reload Dagster after saving" toggle MUST sit at the top right of the content pane, directly under the Save button, on both screens.
- **FR-007**: A card MUST be omitted when none of its fields apply to the selected harness. Field visibility per harness is unchanged from today.
- **FR-008**: On a wide viewport (at least 1800px, and at every wider width) the three groups MUST render side by side as three columns in the order Runs, Job, Box, with the Job column wider than the other two and Runs and Box equal in width.
- **FR-009**: On a mid-width viewport (1440px is the reference width) the groups MUST render as two columns: Runs followed by Box stacked in the left column, and Job alone in the right column, spanning the full height of the left column.
- **FR-010**: On a narrow viewport (900px and narrower) the groups MUST render as a single column in the order Runs, Job, Box.
- **FR-011**: The exact widths at which the layout changes between one, two, and three columns are chosen during planning, subject to: three columns only when each column can hold a card at least as wide as the design system's minimum form-field width plus card padding; two columns only when both columns can; otherwise one column. The transitions MUST be definite, with no width producing an intermediate or overlapping arrangement.
- **FR-012**: Cards MUST keep their natural height. A column's cards stack from the top and MUST NOT stretch to match the height of a taller neighbouring column.
- **FR-013**: Inside every card the fields MUST continue to use the existing responsive form grid, including the rule that wide controls span the full card width.
- **FR-014**: The page MUST NOT scroll horizontally at any supported viewport width.
- **FR-015**: The written YAML file MUST group its keys by the same cards and in the same order as FR-002 through FR-004, with the name key first, using the card names as its section comment headers. Unmanaged keys continue to be preserved in a trailing section.
- **FR-016**: The regrouping MUST NOT change field labels, help text, validation rules, defaults, harness-specific field availability, the unsaved-changes guard, the YAML preview, the secret-detection warnings, or any API contract. Only the position and grouping of fields change.
- **FR-017**: The design-system guide MUST document the three-column agent layout as a named layout pattern, including its one-, two-, and three-column arrangements, so that the guide continues to describe the running site.
- **FR-018**: The prior specification's fixed section order (spec 001, FR-002) MUST be superseded by this feature's grouping, and the README and any quickstart text that lists the old section names MUST be updated to the new ones.

### Key Entities

- **Column group**: One of Runs, Job, or Box. A named, ordered container of cards with a visible heading. Groups decide where a card is placed at each viewport width.
- **Card**: A titled set of related fields inside a group. A card's fields lay out in the existing form grid. A card exists only when at least one of its fields applies to the selected harness.
- **Lead strip**: The row above the groups holding the agent name and, on the create screen, the template picker.
- **Layout arrangement**: The mapping of groups to columns at a given viewport width: three columns (Runs | Job | Box), two columns (Runs over Box | Job), or one column (Runs, Job, Box).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At an 1800px-wide window, an operator sees all three groups side by side with no card stretched and no horizontal scrolling; the content area's empty space, measured as the largest vertical gap inside any card, is no taller than one field row.
- **SC-002**: At a 1440px-wide window the operator sees exactly two columns with Runs above Box on the left and Job on the right; at a 900px-wide window exactly one column in the order Runs, Job, Box.
- **SC-003**: Every field that applied to a harness before this feature still appears exactly once for that harness after it, for all four harnesses.
- **SC-004**: An operator asked to change an agent's schedule or timeout finds the field without scrolling on an 1800px-wide window and within one screen height on a 1440px-wide window.
- **SC-005**: Saving an agent with no edits produces a file whose values are unchanged and whose sections follow the new order, and reloading that file into the form shows the same values.
- **SC-006**: All existing automated checks for the form, the YAML writer, and design-system compliance pass after the change, with the section-order checks updated to the new order.

## Assumptions

- The edit screen is the agent detail page: there is no separate read-only detail view, so this feature covers create and edit only.
- Column group headings (Runs, Job, Box) are shown as visible labels. With three columns of similar cards the headings are what make the conceptual split legible.
- The Job column is wider than the other two because it holds every wide control (prompt picker, tool lists, environment variable rows). The ratio is chosen during planning; the requirement is only that Job is visibly wider and the other two are equal.
- The layout needs explicit width thresholds. The design system prefers intrinsic auto-fill grids, but "fold the third column under the first" cannot be expressed that way, so two thresholds are a deliberate, documented exception.
- The Runs column is intentionally short until a compact recent-runs list is added in a later release. That list is out of scope here, as is the container image field discussed for the Container card.
- The "Reload Dagster after saving" toggle is already at the top of the form directly under Save; this feature keeps it there and fixes the position in the requirements.
- The written YAML regroups on the next save of each agent. This is accepted as a one-time reordering; values are unchanged.
- Timeout applies to every harness and stays in Limits rather than in Container, so the Limits card exists for all harnesses even though Max turns applies only to claude-code.
- Max tokens applies only to the api harness and sits in the Harness & model card because it is a model parameter.
