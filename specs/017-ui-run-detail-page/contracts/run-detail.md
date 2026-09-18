# Contract: Run Detail — page render and the read helpers it depends on

The UI surface this feature reshapes: the `GET /runs/{id}` page and the read-path helpers that build
its five sections. All read-only; **no run data is written** (FR-035). File/line references are to the
current tree.

## §A — `GET /runs/{id}` (the run detail page)

**Route**: unchanged signature — `_run_detail_page(request, run_id)` (`ui/main.py:645`). Still
disk-first via `runs_store.read_run(run_id)`; renders `runs/detail.html`.

**Response**: `200 text/html`. The main column MUST render **exactly five collapsible sections** in
order — **Summary, Output, Checks, Context, Transcript** (FR-001) — each a bordered card with a
keyboard-operable disclosure header (chevron, title, right-aligned muted closed-state note,
`aria-expanded`, Enter/Space — FR-003). On first load Summary/Output/Checks/Transcript are **open** and
Context is **collapsed** (FR-002); saved per-browser state (shared across all `/runs/{id}`, one
localStorage key) overrides the defaults on the client (FR-004).

**Unchanged chrome** (FR-005/FR-006): the crumb, status tag, agent/date chips, "View in Dagster" link,
the six-stat strip (Status, Harness, Model, Turns, Tokens in, Cost), and the rail's Configuration /
Container / Inputs / Completeness / Asset run / Issue / Usage — in that order. Only the **Output
artifacts** block and the **final-message notes** (`report.notes`) leave the rail.

**Section bodies** (view models — see [data-model.md](../data-model.md)):
- **Summary**: `render_summary(...)` HTML, or the foot-line fallback + "No final message was captured."
  (FR-007/FR-008).
- **Output**: `file_row`s (FR-010); when no files, "No output artifacts" + the produced-elsewhere list
  (FR-011/FR-012), or the file list / "No output artifacts" alone when the stream cannot be mined
  (FR-013).
- **Checks**: check rows in the Agents-overview mark language, or "No checks were configured for this
  agent." (FR-015/FR-017).
- **Context**: the existing `_context_card.html`, unchanged (FR-019).
- **Transcript**: entries (FR-031), a single deduped Result (FR-032), the foot line (FR-033), the raw
  log (FR-030), plus the header controls (search + count, Expand/Collapse all, Readable/Raw-log —
  FR-028/FR-029/FR-030).

**Closed-state notes** (FR-009/FR-014/FR-018/FR-020/FR-034): "final message from the agent";
"N files · M pull request(s)" (each part only when non-zero, "0 files" alone otherwise); "K passed ·
L warning(s)" / "P failed" / "—"; "prompt · appended · N instruction file(s)"; "N turns · M tool
calls".

**Degradation**: the page MUST render with Dagster stopped — Checks then show the empty state and note
"—" (best-effort); everything else is disk-only (edge case, R5).

**Guarantees**
- The five sections and their order are stable regardless of content; an empty section renders its
  empty-state line and a note, never an error (edge case).
- No response path writes to the run directory or Dagster; `SCHEMA_VERSION` is untouched (FR-035).

## §B — `runs_store.produced_elsewhere(events: list[dict]) -> list[dict]`

Best-effort miner over the normalized event stream (schema: `images/lib/agent_events.py`).

**Returns** a list of `{kind, identifier, action}` grouped **`pull_request` → `commit` → `file`**,
event order within each kind (FR-012):
- **pull_request** — a `tool_result` `result` containing `https://github.com/…/pull/N`.
- **commit** — a git `tool_result` `result` containing a short SHA (7–40 hex) after a commit/push
  marker.
- **file** — a write/edit `tool_call` (`tool` ∈ Write/Edit/MultiEdit/NotebookEdit) with a
  `file_path`/`path` arg.

**Guarantees**
- Pure function; no disk read, no state; `[]` when nothing matches (FR-013).
- Additive/best-effort — an unrecognised result contributes no row and never raises (edge case).

## §C — Tool-card enrichment (over `conversation_entries`)

Each tool dict gains presentation fields without changing the stored events (data-model *Tool card*):
`description`, `marker` (`exit N` \| `failed` \| none — FR-022/R6), `in_text`/`out_text`,
`in_overflow`/`out_overflow` (`line_count > 3` — FR-024), `in_lines`/`out_lines`, `is_diff` (expanded
by default — FR-026), `out_intent` (failed/warning colour — FR-027). Clamp height is fixed at 3 lines.

**Guarantees**
- `overflow` is `False` for rows at or under 3 lines → no fade, no link (US2-AC3).
- `marker` is `failed` for a `missing`/refused result and `exit N` only when the result carries a
  recognizable exit code; otherwise absent (edge case).

## §D — `ui/markdown.render_summary(text: str) -> Markup`

The FR-007 subset renderer. **No dependency added.**

**Behaviour**
- Escapes all input first; emits only paragraphs, `##`/`###` headings (uppercase labels), `**bold**`,
  `` `inline code` ``, `-`/`*` bullet lists, and URLs as links.
- Content outside the subset renders as its escaped plain text; **no raw HTML is passed through**
  (FR-007, edge case).

**Guarantees**
- Given the reference run's final message (`## Summary`, a bold gate line, code spans, a bullet list),
  the output shows each as formatted text with no raw markdown markup (SC-003).
- Given input containing `<script>`/tables/raw HTML, none of it appears as live markup (SC-003, edge
  case).

## §E — `dagster.run_status(run_ids)` — additive check fields (read)

Reuses the existing per-run read (`ui/dagster.py:559`, `_run_checks_by_id:510`). The check
sub-selection (`_ASSET_CHECKS_SUBQUERY`) gains, additively, each execution's **timestamp** and a
**one-line detail** (evaluation description → severity), so each check dict becomes
`{name, status, detail, recorded}` (data-model *Checks*). Every existing failure arm still collapses to
plain data (`{}` / `{"reachable": False}`), so the Checks section degrades to its empty state and note
"—" when Dagster is unreachable (R5).

**Guarantees**
- No new GraphQL round trip — one field-set addition to an existing read.
- Absent `detail`/`recorded` degrade to `—`; no new check types (FR-016/FR-035).
- A read only — no write to Dagster or the run record.
