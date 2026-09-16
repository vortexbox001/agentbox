# Feature Specification: Run Transparency — Conversation View and Context Snapshot

**Feature Branch**: `012-run-transparency`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "Open any run and see exactly what the agent did and exactly what it was given: a full chat-style history like a Claude Code session in VS Code, and a frozen snapshot of the agent's context at start — prompt, model, tools, instruction files, environment, workspace. Same view for every harness."

## Clarifications

### Session 2026-09-15

- Q: Should the native transcript also be redacted so grepping the whole run directory finds no secret? → A: Yes — redact `transcript.jsonl` as well; the entire run directory is secret-free.
- Q: What should the run page's Files section display? → A: The run's output artifacts (files the run wrote to its output location), browsable with preview/download.
- Q: When a run is pruned, are its output artifacts deleted too? → A: No — pruning removes only `events.jsonl` + `transcript.jsonl`; report, context, and output artifacts are all kept.
- Q: Which dimensions must the Runs list filter by? → A: Agent, status, and date range.
- Q: Can Compare diff any two runs, or only same-agent runs? → A: Any two runs; same-agent reruns are the primary use.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a run's conversation (Priority: P1)

An operator opens any completed run and reads a full, chat-style history of what the agent
did: each turn in order, every tool the agent called with its arguments, the result of each
call, and file edits shown as diffs. The view has the same shape no matter which harness
produced the run, so the operator does not have to learn a different layout per harness or
drop to the filesystem to read a raw transcript.

**Why this priority**: This is the core promise of the feature — turning an opaque run into
something an operator can actually read and understand. It delivers value on its own: even
without the context snapshot, comparison, or retention controls, an operator can finally see
what happened in a run through a uniform interface. It is the MVP.

**Independent Test**: Run one agent on each harness (api/pi, claude-code, codex), open each
run's Conversation view, and confirm the same threaded shape renders for all of them, with
tool calls, results, and file-edit diffs present and in faithful order.

**Acceptance Scenarios**:

1. **Given** a completed claude-code run that called several tools, **When** the operator
   opens the Conversation view, **Then** every tool call from the native transcript appears
   in order, each with its result, and a file edit is shown as a unified diff rendered as a
   diff (not raw text).
2. **Given** any completed run on any harness, **When** the operator opens the Conversation
   view, **Then** the layout, turn ordering, and interaction model are identical to every
   other harness's run.
3. **Given** a run with long tool calls and results, **When** the operator views the
   conversation, **Then** tool calls and results are collapsible and per-turn token counts
   and cost (where known) are shown.
4. **Given** a run whose conversation is long, **When** the operator searches within the
   conversation, **Then** matching turns/messages are located.
5. **Given** an agent that read a file containing a fake API key, **When** the operator
   views the conversation, **Then** the secret appears as `[REDACTED:api_key]` and searching
   the run directory on disk for the secret value finds nothing.
6. **Given** a harness that cannot produce a faithful result for a tool call, **When** the
   operator views that turn, **Then** the result is marked as missing rather than
   reconstructed or fabricated.

---

### User Story 2 - Inspect the starting context (Priority: P1)

An operator opens a run's Context view and sees a frozen snapshot of everything the agent
was given at launch: the exact prompt text as sent, any appended system-prompt text, the
model / effort / fallback model, the harness and version, the container image identity, the
tool allow/deny lists and permission mode, the MCP servers and the tools each exposed, every
instruction file the harness loaded (with full contents), the environment variable names (never
values), mounts and their modes, network, resource caps, working directory, and the file tree
of the workspace and output at start. For asset runs it also shows the asset key, partition,
variant, upstream handoff inputs, and attempt number. A completeness statement names anything
the harness does not disclose.

**Why this priority**: Knowing what an agent *did* (Story 1) is only half of transparency;
diagnosing a bad run almost always requires knowing what it was *given*. Captured at launch
and immutable, the snapshot is also the audit record for "under what configuration did this
run happen." It is independently valuable and testable even before comparison exists.

**Independent Test**: Open the Context view for a claude-code run and confirm it lists tools,
MCP servers, model, and the full contents of every loaded instruction file, with completeness
stating the vendor base system prompt is unavailable; open a pi run and confirm completeness
states the snapshot is complete.

**Acceptance Scenarios**:

1. **Given** a claude-code run, **When** the operator opens the Context view, **Then** it
   lists the tools, MCP servers and their exposed tools, the model, and the full contents of
   every loaded instruction file (e.g. CLAUDE.md, nested files), and completeness states the
   vendor base system prompt is not disclosed.
2. **Given** a pi/api run, **When** the operator opens the Context view, **Then** completeness
   states the snapshot is complete (nothing withheld by the harness).
3. **Given** any run, **When** the operator reads the Context view, **Then** environment
   variables appear as names only, with no values anywhere in the snapshot or on disk.
4. **Given** an asset run, **When** the operator opens the Context view, **Then** it shows the
   asset key, partition key, variant, upstream handoff inputs, and attempt number.
5. **Given** a run whose prompt or instruction files contained a secret, **When** the snapshot
   is written, **Then** the secret is replaced with `[REDACTED:<kind>]` and never written to
   disk in cleartext.

---

### User Story 3 - Browse and open runs (Priority: P2)

An operator opens a Runs area that lists past runs — agent, time, status, model, cost,
attempts — and filters the list to find the run they care about, then opens it. The list and
run pages are built entirely from run directories on disk, so they work even when the
orchestrator is stopped.

**Why this priority**: The conversation and context views (P1) need an entry point, but an
operator who has a run ID could in principle open a run page directly; the browsable,
filterable list is the everyday convenience layer. Reading from disk (independent of the
orchestrator) is what makes the viewer usable exactly when it is most needed — while
debugging an outage.

**Independent Test**: With the orchestrator stopped, open the Runs area and confirm it lists
runs from disk, filters work, and clicking a run opens its detail page.

**Acceptance Scenarios**:

1. **Given** several past runs on disk, **When** the operator opens the Runs area, **Then**
   each run is listed with agent, time, status, model, cost, and attempts.
2. **Given** the run list, **When** the operator applies a filter (e.g. by agent or status),
   **Then** the list narrows to matching runs.
3. **Given** the orchestrator is stopped, **When** the operator opens the Runs area and a run
   page, **Then** both render from disk without the orchestrator running.
4. **Given** a run, **When** the operator opens it, **Then** the page presents the run's
   conversation, its context snapshot, its report, and its output artifacts on one page — a
   transcript timeline (with a Readable/Raw-log toggle) beside a configuration rail that carries
   the context, report, and output artifacts — and the run's materialization/run metadata links
   to its run directory. (Amended: the design-system run-detail specimen composes these as a
   single scrolling page, not four tabs.)

---

### User Story 4 - Compare two runs (Priority: P3)

An operator selects two runs and compares their starting context, seeing exactly what
differed between them — for example, the same agent rerun after changing only its effort
should show that single difference and nothing else.

**Why this priority**: Comparison builds directly on the context snapshot (Story 2) and is a
powerful diagnostic ("why did this run behave differently?"), but it is a refinement on top of
being able to read a single run's context, so it comes after the core views.

**Independent Test**: Run an agent, change only its effort, rerun it, then Compare the two
runs and confirm the diff shows exactly that one difference.

**Acceptance Scenarios**:

1. **Given** two runs of the same agent that differ only in effort, **When** the operator
   compares them, **Then** the comparison shows exactly that one difference.
2. **Given** two runs, **When** the operator invokes Compare, **Then** the differences are
   drawn from the runs' context snapshots and presented field by field.

---

### User Story 5 - Control run retention (Priority: P3)

An operator opens a Settings page and chooses how long run directories are kept: forever (the
default) or pruned after N days. A nightly job enforces the policy, but the report and context
snapshot are always kept even when the conversation and native transcript are pruned. A run
whose conversation has been pruned still opens and shows its context and report with a clear
note that the conversation is no longer available.

**Why this priority**: Retention keeps disk usage bounded over time, which matters on a
constrained host, but it is operationally the least urgent slice — the system is fully usable
with the default "keep forever." It also introduces the first Settings page, laying groundwork
for later configuration sections.

**Independent Test**: Set retention to 1 day, back-date a run directory, run the prune job, and
confirm the conversation and native transcript are gone while the report and context remain and
the run page renders with a "conversation pruned" note.

**Acceptance Scenarios**:

1. **Given** the Settings page, **When** the operator sets retention to N days, **Then** the
   policy is persisted and enforced by the nightly prune job.
2. **Given** retention set to 1 day and a back-dated run directory, **When** the prune job
   runs, **Then** the normalized events and native transcript are removed while the report and
   context snapshot are retained.
3. **Given** a run whose conversation has been pruned, **When** the operator opens it, **Then**
   the Context and Report tabs render and the Conversation tab shows a "conversation pruned"
   note instead of history.
4. **Given** the default configuration, **When** no retention is set, **Then** runs are kept
   forever and nothing is pruned.

---

### Edge Cases

- **Timed-out or failed run**: The run page must still open and show whatever was captured
  (context, report, and any partial conversation), consistent with failed/timed-out runs being
  recorded rather than discarded.
- **Harness cannot produce a faithful tool result**: The event is recorded as missing and the
  view says so; nothing is reconstructed or inferred.
- **Secret in a tool result, prompt, or instruction file**: Redaction applies to tool results,
  prompt text, instruction files, and every other captured field — not just top-level messages.
- **Run directory partially written** (e.g. crash mid-run): The viewer renders the files that
  exist and does not fail the whole page because one file is absent.
- **Very large conversation or file tree**: The view remains navigable (collapsible sections,
  search) rather than rendering an unusable wall of text.
- **Two runs from different harnesses compared**: Comparison still presents field-by-field
  differences without implying a false equivalence between harness-specific fields.
- **Vendor base system prompt**: Never captured; completeness names it as undisclosed rather
  than guessing or omitting silently.

## Requirements *(mandatory)*

### Functional Requirements

**Run directory & capture**

- **FR-001**: Every run MUST write to a per-run directory identified by agent, date, and run
  ID, containing the normalized events, the native transcript, the context snapshot, and the
  run report.
- **FR-002**: A run's materialization/run metadata MUST link to that run's directory.
- **FR-003**: Each harness image MUST emit the normalized events from its own native stream;
  no per-harness parsing lives in the orchestrator.

**Normalized events**

- **FR-004**: Normalized events MUST use one schema across all harnesses, with event kinds for
  system, user, assistant, tool call, tool result, final, and error.
- **FR-005**: Each event MUST carry a timestamp and turn number, and MUST carry input/output
  token counts and cost where the harness reports them (distinguishing "not reported" from a
  real zero).
- **FR-006**: A tool-call event MUST carry the tool name and its arguments; a tool-result
  event MUST carry the result, and for file edits MUST carry a unified diff.
- **FR-007**: Events MUST preserve faithful order and content; nothing is summarized.
- **FR-008**: When a harness cannot produce a faithful tool result, the event MUST be recorded
  as missing rather than reconstructed.

**Context snapshot**

- **FR-009**: A context snapshot MUST be written at launch capturing: the effective prompt text
  as sent; any appended system-prompt text; model, effort, and fallback model; harness and
  version; container image identity (digest); tool allow/deny lists and permission mode; MCP
  servers and the tools each exposed; every instruction file the harness loaded, each with its
  path and full contents; environment variable names only; mounts and their modes; network;
  memory/CPU caps; and working directory.
- **FR-010**: The snapshot MUST include the file tree of the workspace and output locations at
  start, with paths and sizes.
- **FR-011**: For asset runs, the snapshot MUST additionally include asset key, partition key,
  variant, upstream handoff inputs, and attempt number.
- **FR-012**: The snapshot MUST include a completeness statement naming anything the harness
  does not disclose (e.g. the vendor base system prompt for claude-code and codex), and MUST
  state completeness where nothing is withheld.

**Redaction**

- **FR-013**: The normalized events, the context snapshot, and the native transcript MUST all
  pass through a shared secret heuristic before being written; matches MUST be replaced with
  `[REDACTED:<kind>]`. No file in the run directory retains a secret in cleartext.
- **FR-014**: Redaction MUST apply to tool results and to every captured field, not only
  top-level messages.
- **FR-015**: Environment variable values MUST NEVER be written to disk in any captured file.
- **FR-016**: After capture, a search of the run directory for a secret value present in the
  run MUST find no cleartext occurrence.

**Viewer**

- **FR-017**: The management UI MUST provide a Runs area listing runs with agent, time, status,
  model, cost, and attempts, filterable by agent, status, and date range.
- **FR-018**: The run list and run pages MUST be built from run directories on disk and MUST
  function while the orchestrator is stopped.
- **FR-019**: A run page MUST present the run's conversation, context snapshot, report, and output
  files together on a **single scrolling page** — a transcript timeline (with a Readable/Raw-log
  toggle) beside a configuration rail carrying the context, report, and output artifacts — rather
  than as four separate tabs. (Amended to match the adopted design-system run-detail specimen and
  US3 acceptance scenario 4; the "Conversation/Context/Report/Files" names below denote these
  regions of the one page, not tabbed panels.)
- **FR-019a**: The Files tab MUST show the output artifacts the run wrote to its output
  location, browsable with in-viewer preview and download.
- **FR-020**: The Conversation tab MUST render a threaded, chat-style history with collapsible
  tool calls and results, file edits shown as diffs, per-turn tokens and cost, and search — with
  the same shape for every harness.
- **FR-021**: The Conversation tab MUST mark missing tool results as missing rather than hiding
  the gap.
- **FR-022**: The Context tab MUST present the full context snapshot, including full instruction
  file contents and the completeness statement.
- **FR-023**: The viewer MUST provide a Compare action that diffs any two runs' context
  snapshots and presents the differences field by field; same-agent reruns are the primary use.
- **FR-024**: The viewer MUST be post-run only (no live streaming) and MUST NOT offer editing of
  run data.

**Settings & retention**

- **FR-025**: The management UI MUST provide a Settings page with a Retention section offering
  "keep forever" (default) or "prune after N days," persisted to instance configuration.
- **FR-026**: A nightly prune job MUST enforce the retention policy.
- **FR-027**: Pruning MUST remove only the normalized events and native transcript; the report,
  the context snapshot, and the run's output artifacts MUST always be kept.
- **FR-028**: A run whose conversation has been pruned MUST still open, rendering Context and
  Report and showing a "conversation pruned" note in place of the conversation.
- **FR-029**: The retention behaviour MUST be documented in the README.

### Key Entities *(include if feature involves data)*

- **Run directory**: The on-disk home for a single run (per agent, date, and run ID), holding
  the normalized events, native transcript, context snapshot, and run report. Immutable after
  the run; the unit of retention and the source of truth for the viewer.
- **Normalized event**: One entry in the uniform, harness-agnostic event stream (system / user
  / assistant / tool call / tool result / final / error), timestamped and turn-numbered, with
  optional token counts and cost, and — for tool calls/results — tool name, arguments, result,
  and file-edit diffs. May be marked missing.
- **Context snapshot**: The frozen record of everything the agent was given at launch (prompt,
  model config, harness, image, tools, MCP servers, instruction files, env var names, mounts,
  network, resource caps, working directory, workspace/output file tree, and asset-run details),
  plus a completeness statement.
- **Run report**: The structured per-run outcome record (status, tokens, turns, cost, files
  written, transcript path, error, notes) established previously and now co-located in the run
  directory.
- **Retention policy**: The operator-chosen rule governing how long run directories are kept,
  with the report and context always retained.
- **Run (viewer model)**: The list-level view of a run — agent, time, status, model, cost,
  attempts — assembled from the run directory for browsing and filtering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can determine exactly what an agent did and exactly what it was given
  for any run entirely through the viewer, without opening a shell on the host or reading raw
  files.
- **SC-002**: The Conversation view has an identical shape for runs from every harness — an
  operator familiar with one harness's run needs no relearning to read another's.
- **SC-003**: For a claude-code run, 100% of the tool calls present in the native transcript
  appear in the Conversation view, each with its result (or an explicit "missing" marker), and
  every file edit renders as a diff.
- **SC-004**: No secret value present in a run can be found anywhere in the run directory on
  disk after capture; secrets appear only as `[REDACTED:<kind>]` in the viewer, and environment
  variable values never appear at all.
- **SC-005**: Comparing two runs that differ by a single configuration change surfaces exactly
  that one difference and no spurious differences.
- **SC-006**: After a run directory is pruned under a 1-day retention policy, the run still
  opens and shows its context and report, with the conversation clearly marked as pruned.
- **SC-007**: The Runs area lists and opens runs while the orchestrator is stopped.
- **SC-008**: The Context view correctly states completeness per harness — undisclosed vendor
  base system prompt for claude-code/codex, complete for pi/api.

## Assumptions

- The instance data root and configuration directory established in prior work (`$AGENTBOX_DATA`
  and the `config/` directory) are the homes for run directories and instance settings
  respectively; run directories live under `$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`.
- The run report from spec 007 already exists and is simply co-located in the new run directory;
  this feature does not redefine its shape.
- The native transcript continues to be captured as it is today; this feature adds the
  normalized events, context snapshot, and directory layout around it.
- The existing secret-scan heuristic (`ui/secret_scan.py`) is the redaction mechanism, moved to
  a shared module so both capture and UI use it.
- The run-detail design-system template (`ui/design-system/templates/run-detail/`) already
  exists and is the basis for the run page; the viewer composes from the shared design system
  per the project's design-system principle.
- Retention settings live in `config/settings.yaml`, the same file later configuration sections
  will extend; the nightly prune job is registered by the orchestrator's job factory.
- "Same view for every harness" targets the harnesses in the system today (api/pi, claude-code,
  codex); future harnesses conform to the same normalized-event contract.
- Escalation attempts (a later feature) will reuse the same per-run/per-attempt directory
  structure; this spec establishes the layout but does not implement escalation.
- Capturing vendor base system prompts, live streaming, editing from the viewer, and aggregated
  cost dashboards are explicitly out of scope.
