# Feature Specification: Runs Overview Page

**Feature Branch**: `015-ui-runs-overview-page`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "Bring the Runs overview up to the standard of the Agents overview and Dagster's own Runs page: a tabbed header, a filter row, a table whose columns answer 'what ran, against what, who launched it, how did it go, what did it cost', a status that is actually true, and a one-click path to the same run in Dagster. Alongside it, tidy the shell: Runs leads the left-hand navigation, Settings appears once, and the logo takes you home. This is presentation and read-path work only; no agent schema or run-record changes."

## Clarifications

### Session 2026-09-17

- Q: How do the four tabs (All, In progress, Succeeded, Failed) partition runs whose status is queued, timed out, or cancelled? → A: In progress = running or queued; Succeeded = succeeded; Failed = failed, timed out, or cancelled (all non-success terminal states); All = every run.
- Q: How does the text filter match against agent, model, target, and run id? → A: Case-insensitive substring match on any of those fields.
- Q: For an in-progress run, does the Duration cell tick live per second, or show elapsed time as of page render? → A: Elapsed as of page render; it advances on refresh and no live per-second ticker is required.
- Q: When Dagster is reachable but has no record for a specific run (e.g. pruned or historical), what status shows for that row? → A: That row falls back to the local run record and is marked last-known, the same as when Dagster is unreachable.
- Q: Do the tab count badges count the whole run set or the currently filtered set? → A: The text-, agent-, and date-range-filtered set, computed before tab partition and before pagination.

### Session 2026-09-17 (analysis remediation)

Decisions made unattended while acting on the `/speckit-analyze` report (see
[analysis-report.md](./analysis-report.md)). Each resolves a cross-artifact inconsistency or gap and
is applied consistently across spec / plan / tasks / data-model / research / contracts.

- Q: FR-001 said `timed out` is "the real outcome Dagster records", but Dagster has no TIMEOUT
  RunStatus and records timeouts as `FAILURE`/`CANCELED` — so a timed-out run can never present as
  `timed out` while Dagster is reachable and wins (FR-003). How is `timed out` sourced? → A: The
  presented `timed out` status derives **only** from the local run record (`timeout`); it therefore
  appears only on a last-known row. While Dagster is reachable and holds a record, a timed-out run
  shows the terminal state Dagster records (failed or cancelled). FR-001, US1 (narrative + Independent
  Test), and SC-001 updated to say this; consistent with contract §D and research R8. (A1)
- Q: `unknown` status was in the contract §D / tasks presented set but absent from the data-model set
  and unmentioned by the FR-005 partition; where does an unknown-status run count? → A: `unknown` is
  part of the presented set; a run with an unknown status appears under **All only** (counted in the
  All badge, in none of the three sub-tab badges), so `all ≥ in_progress + succeeded + failed`. Added
  to FR-005, the data-model Run set, and the data-model Tab entity. (A2)
- Q: Research R1 promises the N=500 enrichment cap is "surfaced (a note), never silently truncated",
  but no requirement or task rendered a note. → A: Made the promise honest and requirement-backed:
  added **FR-035** requiring a visible cap note (rows beyond the cap shown last-known) and task T045
  to render it in `runs/list.html` (tokens/macros only) with a covering test. (A3)
- Q: SC-007 requires light/dark cross-overview parity but no automated task can observe rendered
  themes. → A: Theme parity is guaranteed by the tokens-only design system (both themes render from
  the same tokens by construction, enforced by `test_conformance.py`) and validated manually per
  quickstart; no pixel/theme assertion is added. Recorded as a verification note on T025. (A5)
- Q: Is accessibility specified for the added controls (tabs, filter, pagination) or only the logo? →
  A: a11y for the added controls is **inherited from the shared design-system macros** (covered by
  FR-033 conformance); the new pagination macro adds `aria-label="Pagination"`/`aria-disabled`. Added
  an accessibility note under the Design-system-conformance requirements. (A6)
- Q: Created/Duration are formatted browser-tz-side, but the server's first paint has no browser
  timezone while SC-005 asserts the exact literal `Sep 17, 1:15 PM`. → A: The row carries a
  machine-readable timestamp (epoch/ISO) plus a server-rendered label; `runs-list.js` re-localises it
  to the browser timezone on load, and SC-005's exact literal is evaluated in the operator's local
  timezone. Recorded in research R7. (A8)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a run's true status at a glance (Priority: P1)

An operator opens the Runs overview and, for every run in the list, sees the status that
actually reflects how the run ended: succeeded, failed, cancelled, still queued, or in
progress. The status shown matches what Dagster records for that run, not merely what the
run's own self-reported report claimed. (Dagster has no distinct timeout status, so a
`timed out` status is derived from the local run record and shown on a last-known row.) When
Dagster cannot be reached, the operator still sees a status derived from the local run record,
clearly marked as last-known so they know it may be stale.

**Why this priority**: The current list shows every row as `ok`, which is actively
misleading — an operator cannot tell a failed run from a successful one. A truthful status
is the single most important thing the overview must deliver; every other improvement is
secondary to the list telling the truth. It delivers value on its own even with no other
change to the page.

**Independent Test**: Trigger one run that succeeds, one that fails, and leave one in progress;
confirm each row's Status matches what Dagster shows for that run. Then stop Dagster and confirm
the page still loads with statuses derived from local records, each marked as last-known —
including a run whose local record reports a timeout, which then shows as `timed out` (Dagster
has no distinct timeout status, so `timed out` never comes from Dagster while it is reachable).

**Acceptance Scenarios**:

1. **Given** a run that Dagster recorded as failed, **When** the operator views the Runs
   overview, **Then** that run's Status reads as failed with the failed intent colour, not
   `ok`.
2. **Given** a run that is still executing, **When** the operator views the overview, **Then**
   its Status reads as in progress.
3. **Given** a run that is queued but not yet started, **When** the operator views the
   overview, **Then** its Status reads as queued.
4. **Given** Dagster is unreachable, **When** the operator views the overview, **Then** every
   row still shows a status taken from the local run record, and each such status is visibly
   marked as last-known.
5. **Given** a run whose self-reported report disagrees with Dagster's recorded outcome,
   **When** Dagster is reachable, **Then** the Status shown is Dagster's outcome.

---

### User Story 2 - Partition and filter runs to find what matters (Priority: P1)

An operator narrows a long list of runs down to the ones they care about. A tabbed header
partitions runs by state — All, In progress, Succeeded, Failed — each tab carrying a count
badge for the whole filtered set. Under the tabs, a filter control (a ghost Filter button
that reveals a text filter, matching the Agents overview) narrows the table by agent, model,
target, or run id, and the existing agent and date-range filters remain available through it.
Filter and tab state live in the URL, so a narrowed view can be bookmarked and shared.

**Why this priority**: Finding a specific run — or all failed runs — is the operator's most
common task on this page, and the current Status dropdown is a poorer tool than the tabbed,
filterable pattern already established on the Agents overview. Bringing the two overviews to
the same interaction model is core to the feature's promise that the two tables "read as one
system."

**Independent Test**: With runs in several states, click each tab and confirm the table shows
only runs in that state and the badge counts match; type into the filter and confirm the
table narrows by agent, model, target, and run id; copy the URL, open it fresh, and confirm
the tab, filter, and date range are restored.

**Acceptance Scenarios**:

1. **Given** runs in mixed states, **When** the operator selects the Failed tab, **Then** the
   table shows only failed runs and every tab's badge shows the count for the whole filtered
   set.
2. **Given** the filter control, **When** the operator types an agent name, model, target, or
   run id, **Then** the table narrows to matching runs.
3. **Given** a date-range and agent filter applied through the filter control, **When** the
   operator copies the page URL and reopens it, **Then** the same tab, text filter, agent,
   and date range are in effect.
4. **Given** the tabbed header, **When** the operator looks for the old Status dropdown,
   **Then** it is no longer present because the tabs replace it.

---

### User Story 3 - Read the run table's columns (Priority: P1)

An operator reads a run's row and learns, in one line, what ran, against what, who launched
it, how it went, and what it cost. The columns, in order, are: Run, Status, Agent, Model,
Target, Launched by, Checks, Created, Duration, Cost. The Agent and Model cells use the same
mono type treatment as the Agents overview and the agent name links to that agent. Created is
a single local-time timestamp like `Sep 17, 1:15 PM` with the full timestamp on hover.
Duration is elapsed run time, showing time so far for an in-progress run. Cost shows `—` when unknown,
never zero. Target is the run's target as Dagster lists it (asset key or job name); Launched
by is the schedule name, sensor name, or a manual launch. Checks shows the run's check results
the same way the Agents overview does.

**Why this priority**: The columns are the substance of the overview — the whole point of the
table is to answer these questions per run. This story depends on truthful status (Story 1)
but is itself a primary deliverable.

**Independent Test**: Compare a scheduled run, a sensor-launched run, and a manual run against
Dagster's Runs page and confirm Target and Launched by match; confirm a run created at 13:15
on 17 September reads `Sep 17, 1:15 PM`; confirm a run with unknown cost shows `—`; confirm
the Date, Time, and Attempts columns are gone.

**Acceptance Scenarios**:

1. **Given** the run table, **When** the operator reads the header, **Then** the columns are
   Run, Status, Agent, Model, Target, Launched by, Checks, Created, Duration, Cost in that
   order, and there are no separate Date, Time, or Attempts columns.
2. **Given** a run created at 13:15 local time on 17 September, **When** the operator reads the
   Created cell, **Then** it shows `Sep 17, 1:15 PM` and hovering reveals the full timestamp.
3. **Given** a run whose cost is unknown, **When** the operator reads the Cost cell, **Then**
   it shows `—`, not `0`.
4. **Given** an in-progress run, **When** the operator reads the Duration cell, **Then** it
   shows elapsed time so far.
5. **Given** a scheduled run, a sensor-launched run, and a manual run, **When** the operator
   reads Launched by, **Then** each shows the schedule name, the sensor name, or a manual
   launch respectively, matching Dagster.
6. **Given** the Agent and Model cells, **When** the operator compares them with the Agents
   overview, **Then** they use the same mono type treatment and the agent name links to that
   agent.

---

### User Story 4 - Jump to the same run in Dagster (Priority: P2)

An operator viewing a run wants to see it in Dagster. In the Run column, right-justified, a
link icon in the indigo colour ramp opens that run in Dagster in a new tab. The run id itself
still links to the AgentBox run page. When Dagster is not configured, the icon is not rendered
and no dead links appear.

**Why this priority**: A one-click path to Dagster is a strong convenience and closes the loop
between AgentBox and the orchestrator it wraps, but the overview is fully usable without it,
so it ranks below the core table and status work.

**Independent Test**: With Dagster configured, click the Run column's link icon and confirm
the correct run opens in Dagster in a new tab, and the run id opens the AgentBox run page;
with Dagster not configured, confirm the icon is absent and there are no dead links.

**Acceptance Scenarios**:

1. **Given** Dagster is configured, **When** the operator clicks the Run column's link icon,
   **Then** that exact run opens in Dagster in a new browser tab.
2. **Given** any run row, **When** the operator clicks the run id, **Then** the AgentBox run
   page for that run opens.
3. **Given** Dagster is not configured, **When** the operator views the Run column, **Then**
   no Dagster link icon is rendered and no dead link exists.

---

### User Story 5 - Page through many runs (Priority: P2)

An operator with many runs pages through them 30 at a time, newest first, using pagination
controls below the table. Tabs and filters apply before pagination, tab counts reflect the
whole filtered set, and the current page is part of the URL. Changing tab or filter returns
to page 1.

**Why this priority**: Pagination keeps the page usable as run history grows, but small
installations work without it, so it ranks with the Dagster link rather than with the core
table.

**Independent Test**: With 31 or more runs, confirm the first page shows 30 and the second
shows the rest; change tab or filter and confirm the view returns to page 1; copy a URL on
page 2 and reopen it to confirm the page is restored.

**Acceptance Scenarios**:

1. **Given** 31 or more runs match the current tab and filter, **When** the operator views the
   overview, **Then** the first page shows 30 runs newest first and pagination controls appear
   below the table.
2. **Given** the operator is on page 2, **When** they change the tab or the filter, **Then**
   the view returns to page 1.
3. **Given** the operator is on a specific page, **When** they copy the URL and reopen it,
   **Then** the same page is shown along with the tab and filter.
4. **Given** a filtered set, **When** the operator reads the tab count badges, **Then** the
   counts reflect the whole filtered set, not just the current page.

---

### User Story 6 - A tidy navigation shell (Priority: P2)

An operator moving around AgentBox finds a coherent shell: the left-hand navigation lists Runs
first, then a horizontal rule, then Agents. There is exactly one Settings entry — the one at
the bottom of the navigation that opens the settings modal — and `/settings` is no longer a
destination in the nav. The logo and wordmark at the top of the navigation link to the home
page in both expanded and collapsed states, with a visible keyboard focus state.

**Why this priority**: The shell tidy-up is real polish that makes the product feel finished,
but it is orthogonal to the Runs overview table itself and can ship independently, so it ranks
below the overview work.

**Independent Test**: Confirm the navigation reads Runs, rule, Agents; confirm there is exactly
one Settings entry and it opens the modal carrying every setting the old Settings page offered;
confirm the logo returns home from any page, including with the navigation collapsed, and shows
a visible focus state on keyboard focus.

**Acceptance Scenarios**:

1. **Given** the left-hand navigation, **When** the operator reads it top to bottom, **Then**
   it shows Runs, a horizontal rule, then Agents.
2. **Given** the primary navigation, **When** the operator looks for Settings, **Then** there
   is exactly one Settings entry — at the bottom — and it opens the settings modal.
3. **Given** the settings modal, **When** the operator opens it, **Then** it contains every
   setting the separate Settings page previously offered.
4. **Given** any page with the navigation expanded or collapsed, **When** the operator clicks
   the logo, **Then** the home page opens.
5. **Given** the logo, **When** the operator focuses it with the keyboard, **Then** a visible
   focus state appears.

---

### Edge Cases

- **Historical runs missing Target or Launched by.** If Target or Launched by cannot be
  obtained from Dagster for a historical run, the cell shows `—` rather than a guessed value;
  new runs are populated.
- **Dagster unreachable.** The page loads from local run records, statuses are marked
  last-known, and no Dagster link icons are rendered as dead links.
- **Run missing from Dagster while it is reachable.** If Dagster is reachable but has no record
  for a specific run (pruned or historical), that row's status falls back to the local run
  record and is marked last-known, the same as when Dagster is unreachable.
- **Zero runs in a tab.** A tab whose filtered set is empty shows a count of 0 and an empty
  table state rather than an error.
- **Run with no cost data.** Cost shows `—`, distinct from a run whose cost is a known `0`.
- **Settings consolidation exceeds a simple move.** If consolidating the Settings page into the
  modal needs more than relocating existing controls, the navigation change still ships with the
  modal linking to the existing Settings page, and full consolidation follows later.
- **Page number beyond the result set.** A URL pointing past the last page resolves to a valid
  page rather than an error.

## Requirements *(mandatory)*

### Functional Requirements

**Run status**

- **FR-001**: The Runs overview MUST show each run's status as its real outcome: succeeded, failed,
  cancelled, queued, or in progress as Dagster records it. Dagster has no distinct TIMEOUT status (it
  records a timeout as a failure or cancellation), so the presented `timed out` status derives only
  from the local run record and therefore appears only on a last-known row (per FR-002); while
  Dagster is reachable and holds a record, a timed-out run shows the terminal state Dagster records
  (per FR-003).
- **FR-002**: When Dagster is unreachable, or when Dagster is reachable but has no record for a
  specific run (e.g. a pruned or historical run), the overview MUST fall back to the status in
  the local run record and MUST mark that status as last-known.
- **FR-003**: When Dagster's recorded outcome and the run's self-reported report disagree, the
  overview MUST prefer Dagster's outcome while Dagster is reachable.
- **FR-004**: Status text and colours MUST use the existing run status tag intents.

**Tabbed header**

- **FR-005**: The page MUST present a tabbed header rendered with the shared tabs macro, with
  the tabs All, In progress, Succeeded, and Failed. The tabs MUST partition runs by status as
  follows: In progress covers running or queued runs; Succeeded covers succeeded runs; Failed
  covers all non-success terminal runs (failed, timed out, or cancelled); All covers every run. A
  run whose status cannot be resolved to any of these buckets (an `unknown` status) MUST appear
  under All only: it is counted in the All badge but in none of the In progress, Succeeded, or
  Failed badges. Consequently the All count MUST be ≥ the sum of the three sub-tab counts.
- **FR-006**: Each tab MUST carry a count badge reflecting that tab's members within the current
  text-, agent-, and date-range-filtered set — computed before the tab partition is applied and
  independent of pagination.
- **FR-007**: The tabbed header MUST replace the current Status dropdown, which MUST be removed.

**Filter row**

- **FR-008**: Under the tabs, the page MUST present a filter control matching the Agents
  overview — a ghost Filter button that reveals a text filter.
- **FR-009**: The text filter MUST narrow the table by agent, model, target, or run id, matching
  as a case-insensitive substring against any of those fields.
- **FR-010**: The existing agent and date-range filters MUST remain available through the
  filter control.
- **FR-011**: Tab, text filter, agent, date-range, and page state MUST be encoded in the URL so
  a view can be bookmarked and shared.

**Columns**

- **FR-012**: The table's columns MUST be, in order: Run, Status, Agent, Model, Target,
  Launched by, Checks, Created, Duration, Cost.
- **FR-013**: The separate Date and Time columns and the Attempts column MUST be removed.
- **FR-014**: Target MUST show the run's target exactly as Dagster's Runs page lists it (the
  asset key or job name).
- **FR-015**: Launched by MUST show what started the run: the schedule name, the sensor name,
  or a manual launch.
- **FR-016**: Checks MUST show the run's check results the same way the Checks column does on
  the Agents overview.
- **FR-017**: Created MUST show a single timestamp formatted like `Sep 17, 1:15 PM` in the
  operator's local time, with the full timestamp available on hover.
- **FR-018**: Duration MUST show elapsed run time, and for an in-progress run MUST show time so
  far as computed at page render; a live per-second ticker is not required, and the elapsed time
  advances on page refresh.
- **FR-019**: Cost MUST show `—` when the cost is unknown and MUST NOT render unknown cost as
  zero.
- **FR-020**: The Agent and Model cells MUST use the same mono type treatment as the same
  columns on the Agents overview, and the agent name MUST link to that agent.
- **FR-021**: When Target or Launched by cannot be obtained for a historical run, that cell
  MUST show `—` rather than a guessed value.

**Link to Dagster**

- **FR-022**: The Run column MUST include a right-justified link icon, in the indigo colour
  ramp, that opens that run in Dagster in a new tab.
- **FR-023**: The run id in the Run column MUST link to the AgentBox run page.
- **FR-024**: When Dagster is not configured, the Dagster link icon MUST NOT be rendered and no
  dead link MUST appear.

**Pagination**

- **FR-025**: The table MUST show 30 runs per page, newest first, with pagination controls
  below the table.
- **FR-026**: Tabs and filters MUST apply before pagination.
- **FR-027**: Changing the tab or the filter MUST return the view to page 1.
- **FR-028**: The current page MUST be part of the URL.

**Shell and navigation**

- **FR-029**: The left-hand navigation MUST list Runs first, then a horizontal rule, then
  Agents.
- **FR-030**: The Settings item MUST be removed from the primary navigation, leaving exactly one
  Settings entry — the one at the bottom that opens the settings modal — and `/settings` MUST NOT
  appear as a nav destination.
- **FR-031**: Every setting the separate Settings page offered MUST be reachable from the
  settings modal. If consolidation needs more than moving existing controls, the navigation
  change MUST still ship with the modal linking to the existing Settings page and full
  consolidation deferred.
- **FR-032**: The logo and wordmark at the top of the navigation MUST link to the home page in
  both the expanded and collapsed navigation, with a visible keyboard focus state.

**Design system conformance**

- **FR-033**: All new and changed presentation MUST follow the design system — tokens only, no
  inline styles, and every control composed from the shared macros.
- **FR-034**: Pagination MUST be added to the design system first and provided as a shared macro
  before it is used on this page.

> **Accessibility note (FR-032, FR-033)**: The interactive controls this feature adds — the tabbed
> header, the ghost-Filter control, and pagination — inherit their keyboard and ARIA behaviour from
> the shared design-system macros (the `tabs` macro and the new `pagination` macro, which carries
> `aria-label="Pagination"` and marks its disabled end control `aria-disabled`). No bespoke
> accessibility wiring is added beyond the logo keyboard focus state required by FR-032; a11y for the
> added controls is therefore covered by design-system conformance (FR-033).

**Enrichment bound**

- **FR-035**: When the filtered run set exceeds the enrichment cap (the most recent N = 500 runs are
  enriched from Dagster per render, so a single render stays bounded on a large history), the overview
  MUST surface a visible note that only the most recent N runs are enriched. Rows beyond the cap MUST
  be shown last-known (from the local run record) rather than silently truncated or omitted.

### Key Entities *(include if feature involves data)*

- **Run (as presented)**: A single orchestrated run as it appears in the overview. Presentation
  attributes: run id, true status (with a last-known marker when derived locally), agent, model,
  target, launched-by source, check results, created timestamp, duration, and cost. This feature
  reads these from Dagster and existing run records; it does not add or change stored run data.
- **Tab**: A partition of the filtered run set by state — All, In progress (running or queued),
  Succeeded (succeeded), Failed (failed, timed out, or cancelled) — each with a count of its
  members within the current text-, agent-, and date-range-filtered set.
- **Filter state**: The combination of active tab, text filter, agent, date range, and page,
  fully represented in the URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a set of runs deliberately driven to succeed, fail, and stay in progress, 100% of
  rows show the status Dagster records for that run; a run whose local record reports a timeout shows
  as `timed out` when its row is last-known (Dagster has no distinct timeout status).
- **SC-002**: With Dagster stopped, the overview still loads and every row shows a last-known
  status with no dead Dagster links.
- **SC-003**: An operator can locate a specific run by agent, model, target, or run id using the
  filter in a single narrowing action.
- **SC-004**: A copied overview URL, reopened in a fresh session, restores the same tab, filter,
  date range, and page 100% of the time.
- **SC-005**: A run created at 13:15 local time on 17 September reads exactly `Sep 17, 1:15 PM`,
  and a run with unknown cost reads exactly `—`.
- **SC-006**: With 31 or more matching runs, the first page shows exactly 30 runs and the second
  shows the remainder; changing tab or filter returns to page 1.
- **SC-007**: Viewed side by side in light and dark themes, the Runs and Agents overviews share
  the same tab header, the same filter control, and the same font in the Agent and Model
  columns.
- **SC-008**: The navigation shows Runs, a rule, then Agents; exactly one Settings entry exists
  and opens the modal; the logo returns home from any page including with the navigation
  collapsed.
- **SC-009**: The UI test suite passes in full, including design-system conformance (no literal
  colours or pixel values, no inline styles, no hand-rolled controls).

## Assumptions

- **Column order includes Status and Checks.** The source issues conflict — one column list
  omits Status and Checks while others require them. This spec keeps both, positioned as in
  FR-012; the exact position is a proposal open to adjustment during planning.
- **Tab set follows Dagster.** The source issue asks only for "a tabbed header"; this spec
  adopts All / In progress / Succeeded / Failed, modelled on Dagster's Runs page.
- **Home page is unchanged.** The logo links to the current home page; this spec does not change
  what the home page is, even though Runs now leads the navigation. Revisiting the home
  destination is out of scope here.
- **Read-path and presentation only.** No agent schema, run-record, or stored-run-data changes;
  the feature reads from Dagster and existing run records. This matches the constitution's
  "Ephemeral Runs, Immutable Outputs" — the overview only reads runs.
- **Existing shared macros and status intents are reused.** The tabs macro, the Agents
  overview's filter and Checks treatments, the mono type treatment, and the run status tag
  intents already exist and are reused rather than reinvented.
- **Settings consolidation may be staged.** If moving the Settings page into the modal is more
  than a relocation of controls, the navigation change ships first with the modal linking to the
  existing page (per FR-031).
