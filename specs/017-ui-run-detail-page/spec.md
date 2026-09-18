# Feature Specification: Run Detail Page

**Feature Branch**: `207-ui-run-detail-page` — the feature directory is
`specs/017-ui-run-detail-page/`; the `207-…` branch and the `017-…` directory refer to this one
feature (`207` is a transposition of `017` in the `015 → 016 → 017` sequence), as reconciled in
`plan.md` "Directory/branch note" and `tasks.md`.

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Make the run detail page answer the operator's questions in the order they ask them — did it work, what did it produce, did the checks pass, what was it given, and only then, what exactly happened — and stop the transcript from drowning the page. Replace the raw-conversation main column of `/runs/{id}` with five collapsible sections — Summary, Output, Checks, Context, Transcript — and give the transcript a compact IN/OUT tool card (clamped, expand-on-click) modelled on the Claude VS Code extension. Presentation and read-path work only; the run record on disk (`context.json`, `events.jsonl`, `transcript.jsonl`, `report.json`) does not change."

## Clarifications

### Session 2026-09-18

- Q: Are section open/closed states remembered per individual run, or shared across every run detail page in that browser? → A: Shared per browser across all runs — one set of section open/closed states applies to every `/runs/{id}` page (not stored per run id).
- Q: When a search term matches only content inside a clamped tool card, does that card reveal the match? → A: Yes — a tool card that matches only on its clamped IN or OUT content auto-expands while the search is active and returns to its prior clamped state when the search is cleared.
- Q: Is the "Expand all / Collapse all output" toggle state remembered across visits? → A: No — it is view-only and resets to the default (all cards clamped) on reload; only per-section open/closed state persists.
- Q: How can the collapsible section headers and expandable tool rows be operated without a mouse? → A: They are keyboard-operable disclosure controls that expose their open/closed state to assistive technology (focusable, toggled with Enter/Space, `aria-expanded` reflecting state), reusing the design system's disclosure pattern.
- Q: When several Produced-elsewhere items exist, in what order are they listed? → A: Grouped by kind — pull requests, then commits, then files — and in event-stream order within each kind.

### Session 2026-09-18 (analysis remediation)

Decisions recorded while acting on the `/speckit-analyze` findings (`analysis-report.md`) with no
human available to confirm. Each is the most reasonable reading of the spec + plan + repo and is
applied consistently across `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, and the contracts.

- Q: When a run has BOTH `/output` artifacts AND minable produced-elsewhere evidence (a PR / commit),
  does the Produced-elsewhere list appear alongside the file rows? (finding I1) → A: No. Produced-
  elsewhere is scoped to the **no-output-artifacts** case, consistent with FR-011, User Story 4, plan
  decision R4, the data model, and task T034 — the list appears only when the run wrote no `/output`
  files. The earlier edge case that claimed "both appear and the note counts both" was the lone
  outlier and is corrected. The closed-state note (FR-014) therefore reads "N files" when artifacts
  exist and "0 files · M pull request(s)" only when there are none.
- Q: Do diff OUT rows always render expanded, or only when clamped diff colouring would be unreadable?
  (finding A1) → A: **Always expanded.** The conditional phrasing ("if diff colouring cannot survive
  the clamped OUT row cleanly") is resolved to the unconditional rule the plan (R7), data model, and
  tasks T013/T016 already implement: a diff OUT row renders expanded by default while non-diff cards
  clamp to the FR-024 clamp height.
- Q: What is the full check-status vocabulary, and how are `fail-blocking` and `not-run` reflected in
  the Checks note? (finding U1) → A: The vocabulary is **pass / warn / fail-blocking / not-run** — the
  values `ui/dagster.py:_check_status` actually returns, matching the Agents overview and already used
  by the data model and the CheckRow component. The closed-state note counts passed / warning / failed
  / not-run, each part shown only when non-zero, with a `fail-blocking` check counted as "failed". A
  `not-run` check is still a recorded check, so it participates in the count and does **not** trigger
  the "—" empty note; "—" appears only when the run has zero recorded checks.
- Q: Where does the "Harness" label belong — the header stat strip or the rail? (finding A2) → A:
  Both surface it, distinctly. "Harness" is one of the six header stats (FR-005); the harness *detail*
  lives inside the rail's **Configuration** block (FR-006). "Harness remains in the rail" in User
  Story 6 refers to that Configuration detail, not a second, separate placement.

### Session 2026-09-18 (analysis remediation — residual findings)

Decisions recorded while acting on the second `/speckit-analyze` pass (`analysis-report.md`, four LOW
residual findings), unattended. Each is applied consistently across `spec.md`, `plan.md`, `tasks.md`,
and `data-model.md`.

- Q: The term "run foot line" named two different renderings — the Summary fallback (three fields:
  status · turns · files written) and the Transcript foot (four fields: … · tool calls). What is the
  canonical naming? (finding I1) → A: Disambiguate by name. The three-field variant is the **Summary
  foot line** (FR-008); the four-field variant is the **Transcript foot line** (FR-033). The underlying
  rule was never in conflict — only the shared name was ambiguous — so the values are unchanged; every
  occurrence in `spec.md`/`plan.md`/`data-model.md` now uses the specific name and cross-notes that the
  Summary variant omits `· tool calls`.
- Q: Plan decision R7 still justified expanded diff OUT rows with the superseded conditional clause
  ("because diff colouring cannot survive the clamp cleanly"). Should the plan match the spec's
  unconditional rule? (finding A1) → A: Yes. R7's rationale is rewritten to state the unconditional
  design choice (diff OUT always renders expanded so colouring is never clamped), matching FR-026 and
  the earlier A1 clarification. Behaviour unchanged; only the plan's "why" wording is aligned.
- Q: SC-002, SC-005 (runtime half) and SC-007 have no automated coverage (no JS test harness). How is
  their acceptance tracked? (finding C1) → A: The quickstart.md US1–US7 manual walk-through (T058) is a
  **required** acceptance gate, not optional: it is the sole sign-off for those client-only criteria,
  and acceptance is incomplete until both T057 (automated `pytest`) and T058 (manual) pass. T057/T058
  now state this dependency explicitly.
- Q: The feature directory (`017-…`) and git branch (`207-…`) disagree. (finding N1) → A: No artifact
  edit. This is already documented and cross-referenced in `spec.md`, `plan.md`, and `tasks.md`; `207`
  is a transposition of `017`. Left as-is pre-merge; reconciling the branch/directory names is a
  post-merge housekeeping step, out of scope for the artifacts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a run's outcome in the order the questions arise (Priority: P1)

An operator opens `/runs/{id}` to understand a run. Instead of landing on a raw conversation
transcript, the main column now reads as an ordered stack of five collapsible sections —
**Summary**, **Output**, **Checks**, **Context**, **Transcript** — that answer, in turn, "did it
work, what did it produce, did the checks pass, what was it given, and only then, what exactly
happened". Summary, Output, Checks and Transcript open by default; Context is collapsed by default.
Each section header shows a chevron, a title, and, while the section is closed, a right-aligned muted
one-line note that summarises the section's contents so the operator can decide whether to open it.
The choice of which sections an operator keeps open or closed is remembered in that browser so it
persists across visits.

**Why this priority**: The reorganisation is the feature's core promise. Today the page opens on the
raw conversation, the agent's final message is a footer line, and there is no view of checks at all —
so the page answers the operator's questions in the wrong order or not at all. The sectioned layout
is what makes every other improvement legible, and it delivers value on its own.

**Independent Test**: Open a completed run and confirm the main column is five sections in the order
Summary, Output, Checks, Context, Transcript; confirm Summary, Output, Checks and Transcript are open
and Context is closed on first load; confirm each closed section shows a one-line summary note in its
header; collapse a section, reload, and confirm the state is remembered; open the same run in a fresh
browser profile and confirm the default open/closed states apply.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the operator opens its detail page, **Then** the main column
   presents exactly five collapsible sections in the order Summary, Output, Checks, Context,
   Transcript.
2. **Given** the run detail page on first load in a browser, **When** the operator reads the
   sections, **Then** Summary, Output, Checks and Transcript are open and Context is collapsed.
3. **Given** a collapsed section, **When** the operator reads its header, **Then** it shows a chevron,
   the section title, and a right-aligned muted note summarising the section's contents.
4. **Given** the operator collapses Context (or opens it), **When** they reload the page, **Then**
   the section keeps the state they left it in.
5. **Given** a browser with no saved state, **When** the operator opens the page, **Then** the
   default open/closed states apply.
6. **Given** the header and stat strip, **When** the operator compares them with today's page,
   **Then** the crumb, status tag, agent and date chips, "View in Dagster" link, and the six-stat
   strip (Status, Harness, Model, Turns, Tokens in, Cost) are unchanged.

---

### User Story 2 - Read tool calls without the transcript drowning the page (Priority: P1)

An operator scrolling the Transcript reads each tool invocation as a compact card rather than a wall
of raw output. Every tool call renders as a card with a head line — the tool name, the agent's own
description of the call, and, right-aligned, an exit code (`exit N`) when one was recorded or `failed`
when the result is missing or was a permission refusal — over a box with two labelled rows, `IN` (the
command, file path, or arguments) and `OUT` (the result). Both rows are clamped to a few visible lines
with a fade when there is more, and clicking a row — or a `Show all N lines` link — expands the card;
clicking again collapses it. The operator can also expand or collapse every card on the page at once
from the transcript toolbar.

**Why this priority**: "Stop the transcript from drowning the page" is half the feature's intent.
Today every Bash result is printed in full, so a single noisy command buries everything else. The
clamped IN/OUT card is what makes a long transcript scannable, and it is independently valuable even
without the other sections.

**Independent Test**: Open a run with a tool call whose output is many lines and confirm the OUT row
shows only a few lines with a fade and a `Show all N lines` link; click the row and confirm it
expands and a `Show less` link appears; open a tool call with a few lines of output and confirm no
fade and no link; use the toolbar control to expand every card, then collapse a single card on its
own; open a refused write and confirm `failed` shows in the head and the OUT row reads in the failed
colour.

**Acceptance Scenarios**:

1. **Given** a tool call whose IN or OUT content is more than the clamp height, **When** the operator
   reads its card, **Then** that row shows only the clamp height in visible lines with a fade at the
   bottom and a `Show all N lines` link below the box.
2. **Given** a clamped card, **When** the operator clicks the row or the `Show all N lines` link,
   **Then** the card expands to full height and the link becomes `Show less`; clicking again collapses
   it.
3. **Given** a tool call whose rows are at or under the clamp height, **When** the operator reads its
   card, **Then** neither row fades and no expand link is shown.
4. **Given** a tool call the harness recorded an exit code for, **When** the operator reads the head
   line, **Then** it shows `exit N`, right-aligned in mono; a call whose result is missing or was a
   permission refusal shows `failed` instead and its OUT row reads in the failed colour.
5. **Given** the transcript toolbar, **When** the operator clicks `Expand all output`, **Then** every
   card on the page expands and the control becomes `Collapse all output`; an individual card can
   still be collapsed on its own while "all" is on.
6. **Given** a tool call whose result is a diff, **When** the operator reads the OUT row, **Then** the
   diff colouring is preserved inside the row.
7. **Given** a tool call recorded as missing, **When** the operator reads the OUT row, **Then** it
   shows the missing marker text in the warning colour.

---

### User Story 3 - Read the agent's final message as formatted text (Priority: P1)

An operator opens the Summary section and reads the agent's final message — its own account of what it
did — as formatted prose rather than a raw markdown string. Headings render as small labels, and bold,
inline code, bullet lists and links render as themselves. When the run captured no final message, the
Summary falls back to the best available source and tells the operator what it is showing.

**Why this priority**: The agent's final message is the single most useful thing on the page for "did
it work", yet today it sits as a footer line or a raw string at the bottom of the rail. Promoting it
to a readable Summary at the top is central to answering the operator's first question.

**Independent Test**: Open a run whose report carries a final message with a heading, a bold line, code
spans and a bullet list, and confirm the Summary renders each as formatted text; open a run whose
report has no notes but whose event stream has a final message and confirm the Summary shows that
text; open a legacy run with neither and confirm the Summary shows the Summary foot line and the note
"No final message was captured."

**Acceptance Scenarios**:

1. **Given** a run whose final message contains headings, bold, inline code, bullet lists and URLs,
   **When** the operator reads the Summary, **Then** each renders as formatted text (headings as small
   uppercase labels, links as links), and content outside the supported subset renders as plain text
   with no raw markup passed through.
2. **Given** a run whose report has no final message but whose event stream carries one, **When** the
   operator reads the Summary, **Then** it shows the event's final text.
3. **Given** a run with neither a report message nor an event message, **When** the operator reads the
   Summary, **Then** it shows the Summary foot line (status · turns · files written) and the note
   "No final message was captured."
4. **Given** the Summary now carries the final message, **When** the operator looks in the rail's
   Usage block, **Then** the final-message notes no longer appear there.

---

### User Story 4 - See what the run produced, including outside /output (Priority: P2)

An operator opens the Output section to learn what the run produced. When the run wrote output
artifacts, they appear as file rows (name, size, Preview / Download) exactly as the rail lists them
today. When the run wrote no output files, the section does not stop at "No output artifacts": it also
shows a **Produced elsewhere** list of what the run created outside `/output`, derived from the run's
own event stream — pull requests opened, commits pushed, and files written inside the workspace — each
with a kind label, an identifier, and an Open / Preview action. The section's closed-state note counts
what was produced.

**Why this priority**: "What did it produce" is the operator's second question. Moving artifacts out
of the rail into a first-class Output section, and surfacing the PRs and commits a run created outside
`/output`, tells the operator what a run actually accomplished — but the page is still usable if this
lands after the core layout and summary.

**Independent Test**: Open a run with output files and confirm they appear as file rows; open a run
that wrote no files but opened a pull request and pushed a commit, and confirm the Output section shows
"No output artifacts" followed by a Produced elsewhere list with the pull request and the commit, each
with an Open action; confirm the section note counts files and pull requests.

**Acceptance Scenarios**:

1. **Given** a run with output artifacts, **When** the operator opens Output, **Then** each artifact
   appears as a file row with name, size, and Preview / Download, as the rail shows today.
2. **Given** a run with no output artifacts whose event stream shows an opened pull request, a pushed
   commit, and a file written in the workspace, **When** the operator opens Output, **Then** it shows
   "No output artifacts" followed by a Produced elsewhere list with a Pull request row, a Commit row
   (short SHA), and a File row, each with an Open / Preview action.
3. **Given** a run whose event stream contains no minable produced-elsewhere evidence, **When** the
   operator opens Output, **Then** it shows the file list or "No output artifacts" alone, as today.
4. **Given** the Output section, **When** the operator reads its closed-state note, **Then** it counts
   what was produced (e.g. "0 files · 1 pull request"), showing each part only when non-zero.

---

### User Story 5 - See whether the run's checks passed (Priority: P2)

An operator opens the Checks section to learn whether the run's checks passed. Each recorded check
appears in the same visual language as the Checks column on the Agents overview — a status mark and
icon (pass / warn / fail-blocking / not-run), the check name, a one-line detail, and the time the
check was recorded, right-aligned.
When a run has no recorded checks, the section says so. The closed-state note counts the outcomes.

**Why this priority**: "Did the checks pass" is the operator's third question and today the detail page
has no view of checks at all. Surfacing them closes a real gap, but it depends on the sectioned layout
being in place.

**Independent Test**: Open a run with several checks and confirm each renders with its status mark
(pass / warn / fail-blocking / not-run), name, one-line detail, and recorded time, matching the Agents
overview treatment; confirm the
section note reads the outcome count (e.g. "4 passed · 1 warning"); open a run with no configured
checks and confirm the empty-state line shows and the note reads "—".

**Acceptance Scenarios**:

1. **Given** a run with recorded checks, **When** the operator opens Checks, **Then** each check shows
   a status mark and icon (pass / warn / fail-blocking / not-run), its name, a one-line detail, and the
   time it was recorded, right-aligned, in the same visual language as the Agents overview.
2. **Given** a run with checks of mixed outcomes, **When** the operator reads the closed-state note,
   **Then** it counts the outcomes across the full vocabulary (e.g. "4 passed · 1 warning", "2 failed",
   "3 passed · 1 not run"), with a `fail-blocking` check counted as "failed".
3. **Given** a run with no recorded checks, **When** the operator opens Checks, **Then** it shows "No
   checks were configured for this agent." and the note reads "—".

---

### User Story 6 - See what the agent was given (Priority: P2)

An operator opens the Context section to review exactly what the agent was given: the prompt, the
appended system prompt, and each instruction file, with rows collapsed and click-to-expand, exactly as
the "Context given to the agent" card renders today. The section's note counts the instruction files.
This section is collapsed by default because it answers a later question than outcome, output and
checks.

**Why this priority**: "What was it given" is a question operators ask when a run surprises them, so it
belongs on the page — but below outcome, output and checks, which is why it moves into a section that
is collapsed by default.

**Independent Test**: Open a run and expand the Context section; confirm it shows the prompt, appended
system prompt, and each instruction file with click-to-expand rows exactly as today; confirm the
section note counts the instruction files; confirm harness, container, inputs and completeness are NOT
here — they remain in the rail.

**Acceptance Scenarios**:

1. **Given** a run, **When** the operator opens Context, **Then** it shows the prompt, appended system
   prompt, and each instruction file with click-to-expand rows, exactly as the context card renders
   today.
2. **Given** the Context section, **When** the operator reads its note, **Then** it states the count of
   instruction files.
3. **Given** the configuration rail, **When** the operator reads it, **Then** Configuration, Container,
   Inputs, Completeness, Asset run, Issue and Usage remain in that order, and only the final-message
   notes and the output artifacts have left it.

---

### User Story 7 - Search and skim the transcript (Priority: P2)

An operator uses the Transcript section to find and read what exactly happened. A search box narrows
the transcript to entries whose text matches — now including the IN and OUT content of tool cards, not
only message text — and reports the match count. The Readable / Raw-log control lives inside the
Transcript section and switches to the unchanged raw view and back. Turn entries keep their role
labels and line breaks, the duplicate final message renders once as a Result, and the Transcript foot
line sits at the bottom of the section.

**Why this priority**: Search and the raw-log toggle are how an operator drills into "what exactly
happened". Moving them into the Transcript section and widening search to tool content complete the
transcript's job, but they refine a section that is already usable.

**Independent Test**: Search for a term that appears only inside a tool call's IN row and confirm the
matching entries stay and the rest hide, with a match count; clear the search and confirm all entries
return; switch the Readable / Raw-log control to the raw view and back and confirm the raw
`transcript.jsonl` view is unchanged; confirm the last assistant message and the final event render as
a single Result entry; confirm the Transcript foot line sits at the bottom of the Transcript.

**Acceptance Scenarios**:

1. **Given** the transcript search box, **When** the operator types a term that appears only inside a
   tool card's IN or OUT content, **Then** the matching entries remain, non-matching entries hide, and
   the match count reports the number matching.
2. **Given** an active search, **When** the operator clears the box, **Then** every entry returns.
3. **Given** the Readable / Raw-log control inside the Transcript header, **When** the operator
   switches to Raw log, **Then** the unchanged `transcript.jsonl` view is shown, and switching back
   returns to the readable view.
4. **Given** a run whose last assistant message and final event carry the same text, **When** the
   operator reads the transcript, **Then** that text renders once, as a Result entry.
5. **Given** turn entries, **When** the operator reads them, **Then** each keeps its gutter dot, role
   label (Task, Agent, Result, Error), meta (turn N · tokens) and message text with its line breaks
   preserved.
6. **Given** the Transcript section, **When** the operator scrolls to its end, **Then** the run foot
   line (status · turns · files written · tool calls) appears there.

---

### Edge Cases

- **Run with a final message that uses unsupported markdown.** Content outside the supported subset
  (e.g. tables, raw HTML) renders as plain text; no raw markup is passed through.
- **Older event stream without tool results.** When a run's events cannot be mined for
  produced-elsewhere rows, the Output section shows the file list or "No output artifacts" alone, as
  today — the Produced elsewhere list is simply absent.
- **A tool call with no recorded exit code and a captured result.** The head line shows neither
  `exit N` nor `failed`; only the description is shown.
- **A diff result longer than the clamp height.** Diff cards expand by default while other cards
  clamp — a diff OUT row always renders expanded so its colouring is preserved (see Clarifications,
  finding A1).
- **A run with output files that also opened a pull request.** The file rows appear and the note
  reads "N files"; the Produced-elsewhere list is scoped to the no-output-artifacts case (FR-011) and
  is not shown when the run wrote `/output` files (see Clarifications, finding I1).
- **A section whose contents are empty.** The section still renders with its empty-state line and a
  note (e.g. Checks reads "—", Output reads "0 files").
- **First visit with no saved section state.** The default open/closed states apply; no error occurs
  when localStorage is unavailable — the page falls back to defaults.

## Requirements *(mandatory)*

### Functional Requirements

**Page structure**

- **FR-001**: The `/runs/{id}` main column MUST present five collapsible sections in this order:
  Summary, Output, Checks, Context, Transcript.
- **FR-002**: On first load in a browser, Summary, Output, Checks and Transcript MUST be open and
  Context MUST be collapsed.
- **FR-003**: Each section MUST render as a bordered card with a full-width header carrying a chevron
  that indicates open/closed state, the section title, and a right-aligned muted note that summarises
  the section's contents while it is closed. The header MUST be a keyboard-operable disclosure control
  that exposes its open/closed state to assistive technology (focusable, toggled with Enter/Space,
  `aria-expanded` reflecting state), using the design system's disclosure pattern.
- **FR-004**: Each section's open/closed state MUST be remembered per browser and restored on the next
  visit; when no saved state exists, the defaults in FR-002 MUST apply, and unavailable persistence
  MUST fall back to the defaults without error. The remembered state is shared per browser across all
  `/runs/{id}` pages — it is not keyed per run id — so a section left open or closed applies to every
  run detail page.
- **FR-005**: The page header and stat strip MUST be unchanged: the crumb, status tag, agent and date
  chips, the "View in Dagster" link, and the six-stat strip (Status, Harness, Model, Turns, Tokens in,
  Cost).
- **FR-006**: The configuration rail MUST keep Configuration, Container, Inputs, Completeness, Asset
  run, Issue and Usage, in that order; only the final-message notes (which become the Summary section)
  and the output artifacts (which become the Output section) MUST leave the rail. The harness detail
  remains inside the rail's Configuration block; this is distinct from the "Harness" stat in the header
  strip (FR-005), which is unchanged — the harness surfaces in both places, not one instead of the
  other.

**Summary section**

- **FR-007**: The Summary section MUST render the agent's final message as formatted text using a small,
  safe markdown subset — paragraphs, `##`/`###` headings as small uppercase labels, bold, inline code,
  bullet lists, and URLs as links — with no raw HTML pass-through; content outside the subset MUST
  render as plain text.
- **FR-008**: When the run's report has no final message, the Summary MUST fall back to the final
  event's text from the event stream; when neither exists, it MUST show the Summary foot line
  (status · turns · files written) and the note "No final message was captured."
- **FR-009**: The Summary section's closed-state note MUST describe its contents (e.g. "final message
  from the agent").

**Output section**

- **FR-010**: The Output section MUST list the run's output artifacts as file rows (name, size,
  Preview / Download), using the same file-row treatment the rail uses today.
- **FR-011**: When the run has no output artifacts, the Output section MUST show "No output artifacts"
  and then a "Produced elsewhere" list derived best-effort from the run's own event stream: pull
  requests opened (a GitHub API `201` carrying an `html_url` in a tool result), commits pushed (a git
  commit/push result with a short SHA), and files written in the workspace by a write tool call.
- **FR-012**: Each Produced-elsewhere row MUST show a kind label (Pull request, Commit, File), the
  identifier in mono, and an Open / Preview action. A row MUST appear only when the event stream
  contains the evidence for it; detection is additive and best-effort. Rows MUST be grouped by kind in
  the order pull requests, then commits, then files, and MUST preserve event-stream order within each
  kind.
- **FR-013**: When the event stream cannot be mined for produced-elsewhere evidence, the Output section
  MUST show the file list or "No output artifacts" alone, as today.
- **FR-014**: The Output section's closed-state note MUST count what was produced — the file count
  always, and the pull-request count only in the no-output-artifacts case where the Produced-elsewhere
  list is shown (FR-011) — displaying each part only when non-zero and "0 files" alone when nothing was
  produced. When the run wrote `/output` files the note reads "N files"; "0 files · M pull request(s)"
  appears only when there were no output artifacts.

**Checks section**

- **FR-015**: The Checks section MUST show the run's recorded check results in the same visual language
  as the Checks column on the Agents overview: a status mark and icon drawn from the full check-status
  vocabulary — pass / warn / fail-blocking / not-run (the values the shared check read produces) — the
  check name, a one-line detail, and the time the check was recorded, right-aligned.
- **FR-016**: The check data MUST come from the run's recorded checks — the same check results already
  surfaced on the Agents overview — and MUST NOT introduce new check types.
- **FR-017**: When a run has no recorded checks, the Checks section MUST show "No checks were configured
  for this agent." and its closed-state note MUST read "—".
- **FR-018**: The Checks section's closed-state note MUST count outcomes across the full status
  vocabulary — passed, warning, failed, and not-run — showing each part only when non-zero and counting
  a `fail-blocking` check as "failed" (e.g. "4 passed · 1 warning", "2 failed", "3 passed · 1 not run").
  A `not-run` check is still a recorded check, so it participates in the count and does NOT trigger the
  empty "—" note; the "—" note (FR-017) is shown only when the run has zero recorded checks.

**Context section**

- **FR-019**: The Context section MUST contain the "Context given to the agent" card exactly as it
  renders today — the prompt, the appended system prompt, and each instruction file, with rows collapsed
  and click-to-expand — and nothing else; harness, container, inputs and completeness remain in the
  rail.
- **FR-020**: The Context section's closed-state note MUST state the count of instruction files.

**Transcript section — tool cards**

- **FR-021**: Every tool invocation in the Transcript MUST render as a tool card with a head line (tool
  name, the agent's description of the call, ellipsised on one line) and a box with two rows labelled
  `IN` and `OUT`: `IN` holds the command / file path / arguments, `OUT` holds the result.
- **FR-022**: The tool card head line MUST show, right-aligned in mono, `exit N` when the harness
  recorded an exit code, or `failed` when the result is marked missing or is a permission refusal.
- **FR-023**: The agent's description in the head line MUST use the call's own description, falling back
  to the file path for read/write/edit calls or to the arg summary the transcript produces today.
- **FR-024**: Each IN and OUT row MUST be clamped to a fixed clamp height of 3 visible lines with a
  gradient fade at the bottom whenever the row exceeds the clamp height; rows at or under the clamp
  height MUST NOT fade and MUST NOT show an expand link.
- **FR-025**: Clicking either row, or the "Show all N lines" link under the box, MUST expand the card to
  full height; clicking again MUST collapse it, and while expanded the link MUST read "Show less". The
  row/link expand control MUST be keyboard-operable and expose its expanded state to assistive
  technology (focusable, toggled with Enter/Space, `aria-expanded`).
- **FR-026**: A tool result that is a diff MUST preserve its diff colouring inside the OUT row; a diff
  OUT row MUST render expanded by default (so its colouring is preserved) while non-diff cards clamp to
  the FR-024 clamp height.
- **FR-027**: A tool result recorded as missing MUST render the missing marker text as the OUT row
  content in the warning colour, and a failed result's OUT row MUST read in the failed colour.

**Transcript section — controls and entries**

- **FR-028**: The transcript toolbar MUST keep the search box and match count and MUST add an outlined
  ghost "Expand all output" / "Collapse all output" control that toggles every tool card on the page;
  individual card toggles MUST continue to work while "all" is on. The expand-all/collapse-all state is
  view-only and MUST NOT persist across visits — it resets to the default (cards clamped) on reload;
  only per-section open/closed state (FR-004) persists.
- **FR-029**: The transcript search MUST hide entries whose text does not match the query, report the
  count of matching entries, and MUST also match the IN and OUT content of tool cards, not only message
  text. A tool card that matches only on its clamped IN or OUT content MUST auto-expand while the search
  is active so the match is visible, and MUST return to its prior clamped state when the search is
  cleared.
- **FR-030**: The Readable / Raw-log control MUST move into the Transcript section header and no longer
  be page-level chrome; the raw `transcript.jsonl` view MUST be unchanged.
- **FR-031**: Turn entries MUST be unchanged: gutter dot, role label (Task, Agent, Result, Error), meta
  (turn N · tokens) and message text with line breaks preserved.
- **FR-032**: The last assistant message and the final event that carry the same text MUST render once,
  as a single Result entry.
- **FR-033**: The Transcript foot line (status · turns · files written · tool calls) MUST appear at the
  bottom of the Transcript section. (It carries `· tool calls` as a fourth field; the Summary foot line
  in FR-008 omits that field — see the Clarifications note on foot-line naming.)
- **FR-034**: The Transcript section's closed-state note MUST summarise its contents (e.g. "24 turns ·
  23 tool calls").

**Scope and data**

- **FR-035**: This feature MUST be presentation and read-path only: it MUST NOT change the run record on
  disk (`context.json`, `events.jsonl`, `transcript.jsonl`, `report.json`), MUST NOT add new check
  types, and MUST NOT add cost data for subscription harnesses.

**Design-system conformance**

- **FR-036**: All new and changed presentation MUST follow the design system — styling resolved from
  tokens only, no literal colours or pixel values, no inline styles, and every control composed from the
  shared macros; the fade colour MUST follow the background token, never a literal.
- **FR-037**: The new components (the section card and header, the IN/OUT tool card, the check row, the
  produced-elsewhere row, and the rendered summary) MUST land in the design system first and be provided
  as shared macros before they are used on this page; the existing tool-call rendering stays available
  for the compare page until it is migrated.

### Key Entities *(include if feature involves data)*

- **Run detail view**: A single run as presented at `/runs/{id}` — header, stat strip, configuration
  rail, and the five main-column sections. Read entirely from the existing run record files; this
  feature adds no stored data.
- **Section**: One collapsible unit of the main column — Summary, Output, Checks, Context, or
  Transcript — with a title, a default open/closed state, a per-browser state persisted and shared
  across all run detail pages, a closed-state summary note, and a body.
- **Tool card**: The presentation of one tool invocation — tool name, description, exit/failed marker,
  and an IN row and OUT row, each clampable and expandable.
- **Produced-elsewhere item**: A thing the run created outside `/output`, mined best-effort from the
  event stream — a pull request (with URL), a commit (with short SHA), or a workspace file — shown only
  when the evidence is present.
- **Check result (as presented)**: One recorded check for the run — outcome (pass / warn / fail-
  blocking / not-run), name, one-line detail, and recorded time — read from the same source the Agents
  overview reads.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reference run, the page opens with Summary, Output, Checks and Transcript expanded
  and Context collapsed, and the main column is exactly five sections in the specified order.
- **SC-002**: An operator who collapses or opens a section and reloads the page finds it in the state
  they left it 100% of the time; a fresh browser profile applies the defaults.
- **SC-003**: The reference run's Summary reads as formatted text — the `## Summary` heading as a label,
  the bold gate line, code spans, and the verification list — with no raw markdown markup visible.
- **SC-004**: On a run that wrote no files but opened a pull request and pushed a commit, the Output
  section lists the pull request and the commit under Produced elsewhere and the note reads "0 files ·
  1 pull request".
- **SC-005**: A tool call with more output than the clamp height shows the clamp height in lines plus a
  fade and a "Show all N lines" link; clicking expands it and shows "Show less"; a tool call at or under
  the clamp height shows no fade and no link.
- **SC-006**: A refused write renders with `failed` in its head line and its OUT row in the failed
  colour.
- **SC-007**: Searching for a term that appears only inside a tool card's IN or OUT content keeps the
  matching entries, hides the rest, and reports the match count; clearing the search restores every
  entry.
- **SC-008**: A run with no recorded checks shows "No checks were configured for this agent." with the
  note "—"; a run whose report has no final message shows the final event text; a legacy run with
  neither shows the Summary foot line and the "No final message was captured." note.
- **SC-009**: Viewed in light, dark and Indigo themes, the section borders, the IN/OUT box ground and
  fade, the muted OUT text, and the check marks all read correctly, with the fade colour following the
  background token.
- **SC-010**: The UI test suite passes in full, including design-system conformance (no literal colours
  or pixel values, no inline styles, every control from the shared macros), and the golden run fixtures
  render every section.

## Assumptions

- **Section notes wording is adopted from the artboard.** The closed-state note phrasings ("4 passed ·
  1 warning", "0 files · 1 pull request", "24 turns · 23 tool calls", "final message from the agent",
  "prompt · appended · 1 instruction file") are taken as specified from the proposed artboard; exact
  wording is open to refinement during planning.
- **Clamp height is fixed at 3 lines.** The artboard exposes the clamp as a 2–12 tweak, but this spec
  fixes it at 3 lines as the rule and does not add an operator-facing setting; that could follow later.
- **Produced elsewhere is built now, best-effort.** The heuristics (PR = GitHub `201` with `html_url`,
  commit = git result with short SHA, file = workspace write) ship as part of this feature, additive and
  best-effort, with the null-action fallback of showing the file list alone when events cannot be mined.
- **Summary shows only the final message.** The Summary does not repeat the stat strip's figures
  (duration, cost); the header stat strip already carries them, so a closed page still answers "did it
  work and what did it cost" from the strip.
- **The final-message notes leave the rail entirely.** The report `notes` block moves out of the rail's
  Usage section into the Summary section and is not duplicated in the rail.
- **Existing shared macros, treatments and data sources are reused.** The file-row macro, the Agents
  overview's Checks treatment and mono type, the run status intents, the context card, and the raw-log
  view already exist and are reused rather than reinvented.
- **The compare page is untouched.** The existing tool-call rendering stays for the compare page until a
  later migration; this feature does not change the compare page.
- **Reference content is the run the proposed artboard is built from** (`speckit-open-pr`, 2026-09-18),
  used for the acceptance checks; no run data beyond the existing record files is required.

## Out of Scope

- Changes to the Runs overview (015) and the compare page.
- New run data beyond what the existing record files hold — in particular, no new check types and no
  cost data for subscription harnesses.
- Streaming updates for in-progress runs.
- Editing or re-running from the detail page.
- Markdown rendering beyond the small subset named in FR-007.
