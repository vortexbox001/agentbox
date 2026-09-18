# Phase 1 Data Model: Run Detail Page

Presentation model only. This feature **adds and changes no stored data** — it reads the run record
(`context.json`, `events.jsonl`, `transcript.jsonl`, `report.json`) and Dagster and shapes what
already exists into view models built at request time; none is persisted (FR-035; constitution
*Ephemeral Runs, Immutable Outputs*). Sources cite the current code so the plan does not re-derive
them.

## Entity: Section (as presented)

One collapsible unit of the main column. Five per page, in fixed order.

| Field | Meaning | Source / rule |
|-------|---------|---------------|
| `id` | `summary` \| `output` \| `checks` \| `context` \| `transcript` | Fixed set and order (FR-001). |
| `title` | Display title | Fixed. |
| `default_open` | Open on first load | `True` for summary/output/checks/transcript; `False` for context (FR-002). |
| `note` | Closed-state summary note (right-aligned, muted) | Computed server-side per section (see each entity below; FR-003/FR-009/FR-014/FR-018/FR-020/FR-034). |
| `body` | Rendered section content | The section's view model (below). |

**Persistence rule (client-side only, FR-004)**: `run-detail.js` stores a `{id: open}` map in
`localStorage["agentbox.runDetail.sections"]`, **shared across all `/runs/{id}` pages**, not keyed per
run id (clarification). On load, saved state overrides `default_open`; when `localStorage` is
unavailable/empty the defaults apply and no error is raised (edge case). Nothing about the section
model is written to the run record.

**Header disclosure (FR-003)**: each header is a focusable disclosure control with `aria-expanded`
reflecting state, toggled by click or Enter/Space, rendered by the `disclosure` macro (R8).

## Entity: Summary view model (US3, FR-007–FR-009)

| Field | Source | Notes |
|-------|--------|-------|
| `html` | `ui/markdown.render_summary(text)` | Safe subset HTML: paragraphs, `##`/`###` → uppercase labels, bold, inline code, bullet lists, URLs → links; all input escaped; **no raw HTML** (FR-007, R2). |
| `source` | precedence: `report.notes` → final event text → none (R3) | `report.notes` is the claude harness's stored final message (`images/agent-claude/wrapper.py:142`); the final event is the `kind=="final"` entry from `conversation_entries`. |
| `fallback` | present when `source is none` | The **run foot line** (status · turns · files written) + note **"No final message was captured."** (FR-008). |
| `note` | `"final message from the agent"` (or the fallback note) | Closed-state note (FR-009). |

The `report.notes` line is **removed from the rail** (`_rail.html:91`) — it lives only here (FR-006,
US3-AC4).

## Entity: Output view model (US4, FR-010–FR-014)

| Field | Source | Notes |
|-------|--------|-------|
| `files` | `runs_store.read_output_files(run_id)` | Each `{name, size, previewable}` → the existing `file_row` macro (name, size, Preview/Download), unchanged from the rail (FR-010). |
| `produced` | `runs_store.produced_elsewhere(events)` | Best-effort list, shown when `files` is empty and evidence exists (FR-011); grouped **PRs → commits → files**, event order within kind (FR-012, R4). |
| `note` | count of files + PRs | `"N files · M pull request(s)"`, each part only when non-zero, `"0 files"` alone when nothing produced (FR-014). |

### Produced-elsewhere item

| Field | Meaning | Rule |
|-------|---------|------|
| `kind` | `pull_request` \| `commit` \| `file` | Label rendered as **Pull request** / **Commit** / **File** (FR-012). |
| `identifier` | URL (PR), short SHA (commit), path (file) | Rendered in mono (FR-012). |
| `action` | Open (PR/commit URL) / Preview (file) / none | Present only when derivable (FR-012). |

Detection (best-effort, over normalized events — `images/lib/agent_events.py` schema):
- **pull_request**: a `tool_result` whose `result` contains a `https://github.com/…/pull/N` `html_url`.
- **commit**: a git `tool_result` whose `result` contains a short SHA (7–40 hex) after a commit/push
  marker.
- **file**: a write/edit `tool_call` (`tool` ∈ Write/Edit/MultiEdit/NotebookEdit) with a
  `file_path`/`path` arg.

When the stream cannot be mined, `produced` is empty and the section shows the file list or "No output
artifacts" alone (FR-013).

## Entity: Checks view model (US5, FR-015–FR-018)

Read best-effort from **`dagster.run_status([run_id])`** (`ui/dagster.py:559`) — the same per-run check
path the Agents overview uses (FR-016). Each check:

| Field | Source | Notes |
|-------|--------|-------|
| `name` | check `name` | (FR-015). |
| `status` | `_check_status(execution)` → `pass` \| `warn` \| `fail-blocking` \| `not-run` | Mapped to the existing `ax-result` mark + `CHECK_META` icon (FR-015/FR-016). |
| `detail` | evaluation description → severity (additive selection, R5) | One-line detail; `—` when absent. |
| `recorded` | execution timestamp (additive selection, R5) | Right-aligned recorded time; `—` when absent. |

| Section field | Rule |
|---------------|------|
| `checks` | list above; empty when Dagster is unreachable **or** no checks for the run. |
| `empty_text` | **"No checks were configured for this agent."** when `checks` is empty (FR-017). |
| `note` | **"K passed · L warning(s)"** / **"P failed"** counting outcomes; **"—"** when empty (FR-017/FR-018). |

No new check types (FR-016/FR-035). The empty state doubles as the Dagster-unreachable state (R5,
best-effort).

## Entity: Context view model (US6, FR-019–FR-020)

Reuses the existing **`runs/_context_card.html`** verbatim (prompt, appended system prompt, each
instruction file, with click-to-expand rows — `_context_card.html`), nested inside the Context section.

| Field | Source | Notes |
|-------|--------|-------|
| body | `_context_card.html` | Unchanged content and interaction (FR-019). |
| `note` | `"prompt · appended · N instruction file(s)"` | Counts `context.instruction_files` (FR-020). |

Harness, container, inputs, completeness stay in the rail (FR-019, US6-AC3).

## Entity: Tool card view model (US2, FR-021–FR-027)

Built by enriching each tool in the existing `conversation_entries(events)` output
(`runs_store.py:287`; each tool is `{tool, arg, result, diff, missing, state, exit}`). **Note**: the
`exit` key is a vestigial placeholder that `conversation_entries` always leaves `None` — the
normalized event schema (`images/lib/agent_events.py`) carries no exit code, so nothing populates it.
The `exit N` marker is therefore **derived by parsing the result text**, not read from this field (see
plan R6); the placeholder key is not the source of truth.

| Field | Source | Notes |
|-------|--------|-------|
| `name` | `tool` | Head line tool name (FR-021). |
| `description` | `arg` → file path (read/write/edit) → arg summary (`_arg_summary`) | Ellipsised on one line (FR-021/FR-023). |
| `marker` | `exit N` \| `failed` \| none | `failed` when `missing` or a permission-refusal marker; `exit N` only when the result carries a recognizable exit code; else none (FR-022, R6). Right-aligned mono. |
| `in_text` | the command / file path / arguments | `IN` row (FR-021). |
| `out_text` | `result` (or `diff`) | `OUT` row (FR-021). |
| `in_overflow` / `out_overflow` | `line_count > 3` | Drives the fade + "Show all N lines" link (FR-024, R7). |
| `in_lines` / `out_lines` | line counts | For the "Show all N lines" label (FR-025). |
| `is_diff` | `diff is not None` | Diff OUT rows render **expanded by default**, colouring preserved (FR-026, R7). |
| `out_intent` | `failed` → failed colour; `missing` → warning colour | (FR-027). |

**Clamp** is fixed at 3 lines (spec Assumption); `run-detail.js` toggles `is-expanded` per card and
flips the link to "Show less" (FR-025); the control is keyboard-operable with `aria-expanded`.

## Entity: Transcript view model (US7, FR-028–FR-034)

| Field | Source | Notes |
|-------|--------|-------|
| `entries` | `conversation_entries(events)` | Turn entries unchanged: gutter dot, role label (Task, Agent, Result, Error), meta (turn N · tokens), message text with line breaks (FR-031). |
| `result_dedup` | last assistant message == final event text → render once as **Result** | (FR-032). |
| `foot` | status · turns · files written · tool calls | At the bottom of the section (FR-033). |
| `raw_transcript` / `raw_truncated` | `read_transcript(run_id)` | The unchanged raw `transcript.jsonl` view, bounded to 512 KB (FR-030). |
| `note` | `"N turns · M tool calls"` | Closed-state note (FR-034). |

**Controls** (in the section header, FR-028/FR-030): the search box + match count; an outlined ghost
**Expand all / Collapse all output** toggle (view-only, resets on reload — FR-028); the **Readable /
Raw-log** control (moved out of page chrome — FR-030). **Search** (FR-029) matches message text **and**
tool IN/OUT content, hides non-matching entries, reports the count, and **auto-expands** a card that
matches only on clamped content, restoring it when the search is cleared (all client-side in
`run-detail.js`).

## Rail (unchanged except two removals)

`_rail.html` keeps **Configuration, Container, Inputs, Completeness, Asset run, Issue, Usage** in
order; only **Output artifacts** (→ Output section) and the **final-message notes**
(`report.notes` → Summary section) leave it (FR-006, US6-AC3). The six-stat header strip and the page
header (crumb, status tag, agent/date chips, View-in-Dagster) are untouched (FR-005).

## What is NOT added

No stored data, no new run-record fields, no `SCHEMA_VERSION` bump, no new check types, no cost data
for subscription harnesses, no new Python dependency (FR-035, Out of Scope). The only new Dagster read
detail is an **additive field selection** on an existing check query — a read, not a write (R5).
