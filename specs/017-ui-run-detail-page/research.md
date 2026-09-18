# Phase 0 Research: Run Detail Page

Decisions that resolve the plan's Technical Context. Each is **Decision / Rationale / Alternatives
considered**. No open `NEEDS CLARIFICATION` remains — the spec's five "Decisions to confirm" were
already resolved in its Assumptions, and every remaining choice a plan must make is settled below and
noted back in [plan.md](./plan.md) → *Planning decisions*.

## R1 — Where the five sections are built, and how open/closed state persists

**Decision**: Build the five section view models **server-side** in `_run_detail_page`
(`ui/main.py:645`) at request time, from data the page already loads (`runs_store.read_run`,
`read_events` → `conversation_entries`, `read_output_files`, `read_transcript`). Each section carries
its title, default open/closed state (Summary/Output/Checks/Transcript open, Context closed — FR-002),
its body, and a **closed-state note** computed server-side (FR-009/FR-014/FR-018/FR-020/FR-034). The
open/closed **choice** is persisted **client-side only** in `run-detail.js` under a single
`localStorage` key — `agentbox.runDetail.sections` — that maps a section id to a boolean, **shared
across every `/runs/{id}` page** and **not keyed per run id** (clarification, FR-004). On load the
script applies saved state over the server defaults; when `localStorage` is unavailable or empty the
FR-002 defaults stand and no error is raised (edge case, FR-004).

**Rationale**: The notes must reflect real content ("4 passed · 1 warning", "0 files · 1 pull
request", "24 turns · 23 tool calls"), which is only known server-side, so the notes are rendered with
the page; that also lets the golden fixtures assert them (SC-010). Persisting the *choice* client-side
matches the clarified "shared per browser across all runs" model and mirrors how the app already keeps
view preferences (the theme toggle) in `localStorage`. A single shared key — not one per run id — is
the literal clarification and keeps the store tiny and predictable.

**Alternatives considered**:
- *Per-run persistence* (`…sections.<run_id>`): rejected — the clarification explicitly says the state
  is shared across all run detail pages, not stored per run id.
- *Server-side persistence (a cookie / settings file)*: rejected — the feature is read-path only and
  adds no stored data (FR-035); view chrome does not belong in the run record or server state.

## R2 — Rendering the final message (the Summary markdown subset)

**Decision**: Render the FR-007 subset with a **new, dependency-free** server-side helper
`ui/markdown.py:render_summary(text) -> Markup`. It escapes all input first, then recognises only:
paragraphs, `##`/`###` headings (emitted as small uppercase labels), `**bold**`, `` `inline code` ``,
`-`/`*` bullet lists, and bare/`[label](url)` URLs (emitted as links). Anything outside the subset —
tables, raw HTML, blockquotes, images — is emitted as its already-escaped plain text; **no raw HTML is
ever passed through** (FR-007, edge case). The `summary` design-system component supplies the visual
treatment (heading-as-label, code chip, list, link) via tokens.

**Rationale**: Adding a markdown *library* would import a large surface with its own HTML-passthrough
behaviour and a new pinned dependency (against the plan's "no new dependencies" and the repo's
no-bundler stance). A tiny whitelist renderer makes "no raw markup visible" a structural guarantee the
conformance and golden tests can assert byte-for-byte (SC-003, SC-010), and keeps the subset exactly
the one the spec names — nothing wider (Out of Scope: "Markdown rendering beyond the small subset").

**Alternatives considered**:
- *Client-side rendering in `run-detail.js`*: rejected — it would need a JS markdown parser (a new
  asset) and would make the rendered Summary invisible to the `TestClient` golden checks.
- *`markdown`/`markdown-it-py` with a sanitiser*: rejected — a dependency plus a sanitiser to re-close
  the HTML hole the library opens, for a five-construct subset.

## R3 — Summary source precedence and the rail move

**Decision**: The Summary content is chosen in order (FR-008): **(1)** `report.notes` (the agent's
final message the claude harness already stores as `report.notes` —
`images/agent-claude/wrapper.py:142`); **(2)** the final event's text from the event stream (the
`kind == "final"` entry `conversation_entries` produces); **(3)** neither → the **Summary foot line**
(status · turns · files written — three fields, distinct from the four-field Transcript foot line)
plus the note **"No final message was captured."** The `report.notes`
line is **removed from the rail's Usage block** (`_rail.html:91`) and does not appear in both places
(FR-006, spec Assumption, US3-AC4).

**Rationale**: This is the spec's exact fallback ladder and the exact "notes leave the rail" rule. The
foot-line fallback reuses the run foot that `detail.html:78` already renders, so a legacy run with no
message still answers "did it work" from status + turns.

**Alternatives considered**: keeping `report.notes` in the rail *and* the Summary (duplicated) —
rejected by FR-006/US3-AC4 ("the final-message notes no longer appear there").

## R4 — Produced-elsewhere: mining heuristics and ordering

**Decision**: Add `runs_store.produced_elsewhere(events) -> list[dict]`, a best-effort miner over the
**normalized event stream** (`events.jsonl`, schema in `images/lib/agent_events.py`: `kind`, `tool`,
`args`, `result`, `diff`, `missing`). Three additive heuristics (FR-011/FR-012):

- **Pull request** — a `tool_result` whose `result` contains a GitHub **pulls** URL (an `html_url`
  matching `https://github.com/…/pull/N`, the shape a GitHub API `201` returns). Identifier: the URL;
  Open action: the URL.
- **Commit** — a git commit/push `tool_result` whose `result` contains a **short SHA** (a 7–40 hex run
  after a commit/push marker). Identifier: the short SHA (mono); action: none required beyond the
  label, or the repo/commit URL when derivable.
- **File** — a **write/edit** `tool_call` (`tool` ∈ Write/Edit/MultiEdit/NotebookEdit) carrying a
  `file_path`/`path` arg inside the workspace. Identifier: the path (mono); action: Preview when the
  path is under a previewable location, else none.

Rows are **grouped by kind in the order pull requests → commits → files**, preserving **event-stream
order within each kind** (clarification, FR-012). The list is shown **only when `/output` produced no
artifacts** (US4, FR-011) and **only when evidence exists**; when the stream cannot be mined it is
simply absent and the Output section shows the file list or "No output artifacts" alone (FR-013, edge
case "older event stream without tool results").

**Rationale**: These are the exact heuristics the spec names as "additive and best-effort" with a
"null-action fallback." Mining the already-parsed event stream needs no new disk read and no new stored
data (FR-035). Grouping + within-kind event order is the clarified ordering. Gating on "no `/output`
artifacts" matches US4's scenario (a run that "wrote no files but opened a pull request").

**Alternatives considered**:
- *Always show produced-elsewhere alongside the file list*: rejected for the primary flow — US4 frames
  it as the empty-`/output` case; the edge case "output files that also opened a PR" is handled by
  still mining when asked, but the note counts both (FR-014). (Implementation keeps the miner pure so
  either policy is a one-line gate; the default follows US4.)
- *A new stored "artifacts" manifest*: rejected — violates read-path-only scope (FR-035).

## R5 — The Checks section source (reuse the 015 per-run read, extended additively)

**Decision**: The Checks section reads the run's checks from **`dagster.run_status([run_id])`** — the
same per-run check path the Agents overview relies on (`ui/dagster.py:559`, `_run_checks_by_id`), which
returns `{run_id: {…, "checks": [{name, status}]}}` (FR-016). Extend the check sub-selection
(`_ASSET_CHECKS_SUBQUERY`, line ~481, and its parse in `_run_checks_by_id`, line ~510) to **additively**
select each execution's **timestamp** and a **one-line detail** (the evaluation description, falling
back to its severity) so the section can render the recorded time (right-aligned) and the one-line
detail (FR-015); absent fields degrade to `—`. When Dagster is **unreachable** or returns **no checks**
for this run, the section shows **"No checks were configured for this agent."** and its note reads
**"—"** (FR-017). No new check types are introduced (FR-016/FR-035).

**Rationale**: FR-016 requires "the same check results already surfaced on the Agents overview" and
"MUST NOT introduce new check types" — reusing `run_status`'s check read satisfies both. The time and
one-line detail are the only fields the section needs beyond the overview's icon grid, and they live on
the same execution node, so an additive field-set to one existing GraphQL read supplies them with no
new round trip. Every failure arm already collapses to plain data (`_run_checks_by_id` returns `{}`),
so the page renders disk-only when Dagster is down — the empty state doubles as the unreachable state,
which is honest and best-effort. This is a **read**, so *Ephemeral Runs, Immutable Outputs* is intact.

**Alternatives considered**:
- *Read checks from a run-record file*: rejected — checks are asset-check evaluations that live in
  Dagster, not in the run directory; there is no on-disk check record to read, and adding one would
  change the run record (FR-035).
- *Distinguish "unreachable" from "no checks configured" with a separate banner*: rejected as scope —
  the spec's empty state is a single line; best-effort degradation to it is acceptable and matches how
  the overview treats an unreachable Dagster (Checks → `—`).

## R6 — `exit N` / `failed` derivation (the event schema has no exit field)

**Decision**: The normalized event schema (`images/lib/agent_events.py`) records `missing` but **no
exit code**. So the tool-card head marker is derived best-effort in the view model (FR-022):
- **`failed`** when the result is `missing` (already flagged by `conversation_entries`, e.g. a claude
  `is_error` result with no content — `images/agent-claude/wrapper.py:62`) **or** when the result text
  matches a **permission-refusal** marker.
- **`exit N`** only when the result text carries a **recognizable exit code** (e.g. a trailing
  `exit N` / `exit code: N` line some command results embed). Rendered right-aligned in mono.
- **neither** — a captured result with no exit code and no refusal shows only the description (spec
  edge case "no recorded exit code and a captured result").

A `failed`/`missing` OUT row reads in the failed/warning colour respectively (FR-027).

**Rationale**: The spec's own wording is conditional — `exit N` "when the harness recorded an exit
code." Because the harness does **not** record one in the event stream, honest behaviour is to show it
only when the result text actually carries it, show `failed` for the cases the stream *does* mark
(`missing`) plus the refusal marker, and otherwise show nothing — exactly the three cases FR-022 and
the edge case enumerate. Deriving this in the view model keeps it read-path only (no disk change).

**Alternatives considered**:
- *Adding an `exit` field to the event schema/harness output*: rejected — that changes the run record
  and the image contracts, which FR-035 and the feature scope forbid ("presentation and read-path
  only").
- *Always show `failed` when there is no exit code*: rejected — it would mislabel successful commands;
  the edge case requires "neither" for a captured result with no exit code.

## R7 — Clamp detection and the diff fallback

**Decision**: Clamp height is **fixed at 3 lines** (spec Assumption). The view model counts the visible
lines of each IN and OUT payload and sets `overflow = lines > 3`; the template renders the 3-line clamp
with a gradient fade and a **"Show all N lines"** link **only when `overflow`** (FR-024), and no fade /
no link otherwise (US2-AC3). `run-detail.js` toggles an `is-expanded` class on click (row or link),
flipping the link to **"Show less"** (FR-025); the control is keyboard-operable and carries
`aria-expanded` (FR-025). **Diff OUT rows render expanded by default** (never clamped) because the
diff's per-line colouring cannot survive a clamp cleanly (FR-026 fallback, edge case). The fade colour
resolves from the **background token**, never a literal (FR-036, SC-009).

**Rationale**: Counting lines server-side makes the fade/link deterministic and testable (SC-005) and
avoids a layout-measuring flash on the client. Fixing the clamp at 3 lines is the spec's rule (no
operator setting). Expanding diffs by default is the spec's explicit null-action fallback for the one
content type that cannot be clamped without corrupting its colouring.

**Alternatives considered**:
- *Client-side height measurement to decide the fade*: rejected — it flashes on load and is
  unassertable in `TestClient`; a server line count is exact.
- *Clamping diffs too*: rejected by FR-026 / the edge case — the fallback is to expand them.

## R8 — Six new components, design-system-first; existing macros untouched

**Decision**: Add the presentation the spec names as new components to the design system **first**
(FR-037): **Disclosure/section card** (`components/layout/Disclosure.jsx`), **IN/OUT tool card**
(`components/data/ToolCard.jsx`), **check row** (`components/data/CheckRow.jsx`), **produced-elsewhere
row** (`components/data/ProducedRow.jsx`), and **rendered summary** (`components/data/Summary.jsx`) —
each with a specimen card, a `_ds_manifest.json` entry, a rebuilt `_ds_bundle.js`, and `readme.md`
documentation — then expose each as a shared Jinja macro in `components/macros.html`, and only then use
them on `detail.html`. The **existing** `timeline`/`tool_call`/`diff_block`/`tool_out` macros are left
in place unchanged for the **compare page** (spec Assumption "the compare page is untouched"). The check
mark reuses the existing `ax-result` treatment + `CHECK_META` vocabulary the overviews use
(`agents-list.js:111`, `runs/list.html`), so `check_row` is a row *around* the existing mark, not a new
mark.

**Rationale**: Principle VII and FR-037 are explicit — a new component lands in the design system first
and the shared macro second; the manifest/bundle/readme trio is exactly what `test_design_system_sync.py`
and `test_design_system_docs.py` verify, so the components must be registered there or the suite fails
(SC-010). Reusing `ax-result` for the check mark honours FR-015's "same visual language as the Agents
overview" and avoids a second check vocabulary (FR-016). Leaving the old tool-call macros alone keeps
the compare page working while the new IN/OUT card serves the detail page (FR-037).

**Alternatives considered**:
- *Retrofit the existing `tool_call` macro into the IN/OUT card*: rejected — it would change the
  compare page's rendering, which the spec puts out of scope; the two can coexist until a later
  migration.
- *Skip the design-system registration and add macros only*: rejected — it violates VII/FR-037 and
  fails the sync/docs conformance tests.

## Section-note wording (adopted from the artboard)

Per the spec Assumption, the closed-state note phrasings are taken as specified and computed
server-side: Summary → **"final message from the agent"** (or the fallback note); Output →
**"N files · M pull request(s)"**, each part shown only when non-zero, **"0 files"** alone when nothing
was produced (FR-014); Checks → **"K passed · L warning(s)"** / **"P failed"**, **"—"** when none
(FR-018); Context → **"prompt · appended · N instruction file(s)"** counting the instruction files
(FR-020); Transcript → **"N turns · M tool calls"** (FR-034).
