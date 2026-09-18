# Implementation Plan: Run Detail Page

**Branch**: `207-ui-run-detail-page` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-ui-run-detail-page/spec.md`

> Directory/branch note: the feature lives in `specs/017-ui-run-detail-page/` while the git branch is
> `207-ui-run-detail-page` (the spec's own header). Both names refer to this one feature.

## Summary

Replace the raw-conversation main column of `/runs/{id}` with an ordered stack of **five collapsible
sections** — **Summary, Output, Checks, Context, Transcript** — that answer the operator's questions
in the order they arise ("did it work, what did it produce, did the checks pass, what was it given,
and only then, what exactly happened"), and give the transcript a compact **IN/OUT tool card**
(clamped to 3 lines, expand-on-click) modelled on the Claude VS Code extension. Summary, Output,
Checks and Transcript open by default; Context is collapsed by default; each section's open/closed
state is remembered per browser, shared across every `/runs/{id}` page. The Summary renders the
agent's final message as a small safe markdown subset; the Output section adds a best-effort
**Produced elsewhere** list (pull requests, commits, workspace files) mined from the run's own event
stream when no `/output` artifacts exist; the Checks section surfaces the run's recorded checks in the
Agents-overview visual language; Context reuses today's context card; Transcript keeps search (now
also matching tool IN/OUT content) and the Readable/Raw-log toggle, moved into the section header.

The technical crux: this is **presentation and read-path only**. The run record on disk
(`context.json`, `events.jsonl`, `transcript.jsonl`, `report.json`) does not change (FR-035,
constitution *Ephemeral Runs, Immutable Outputs*). The five sections are view models built at request
time in `ui/main.py` from data the page already reads (`runs_store.read_run/read_events/
conversation_entries/read_output_files/read_transcript`). Two things are genuinely new: (a) a
best-effort **produced-elsewhere miner** over the normalized event stream, and (b) the **Checks
section**, which reuses the existing `dagster.run_status(run_ids)` per-run check read (already built
for feature 015) with an additive selection of each check's recorded time and one-line detail — a
read, never a write. Six new presentation components (section-card disclosure, IN/OUT tool card, check
row, produced-elsewhere row, rendered summary) land in the design system **first** and as shared
macros **second** (FR-037, Principle VII); the existing `tool_call`/`timeline` macros stay untouched
for the compare page (spec Assumptions).

## Technical Context

The stable stack facts live in `AGENTS.md` → **Stack and tests** (Python 3.12; FastAPI + Jinja2 +
httpx + PyYAML + croniter on the UI, tested through `TestClient`; files-only storage; plain ES-module
JS in `ui/static/`, no bundler, no `package.json`). This section records only what THIS feature adds
or changes.

**Language/Version**: Python 3.12 (UI); plain ES-module JavaScript (`ui/static/`). No new language,
no bundler, no `package.json`.

**Primary Dependencies**: **No new dependencies.** The Summary markdown subset (FR-007) is rendered
by a small, dependency-free server-side helper (`ui/markdown.py`) — no markdown library is added, so
the "safe subset, no raw HTML pass-through" rule is enforced by construction. Reuses FastAPI/Jinja2
already pinned in `ui/requirements.txt` and the existing `ui/dagster.py` GraphQL client convention
(one bounded read whose transport/parse failures collapse to plain data).

**Storage**: Unchanged — files only. The page reads the run directory
(`$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`, mounted read-only) via `runs_store`; the Checks
section reads Dagster best-effort. **Nothing is written; `SCHEMA_VERSION` is untouched; no run-record
file changes** (FR-035). Section open/closed state and expand-all are browser-side only (localStorage)
— no server persistence.

**New/changed surface (files this feature touches)**:
- `ui/main.py` — rework `_run_detail_page` (currently lines 645–690): build the five section view
  models (Summary/Output/Checks/Context/Transcript), compute each section's closed-state note, render
  the Summary markdown, mine produced-elsewhere from the event stream, and fetch the run's checks
  best-effort via `dagster.run_status([run_id])`. Remove the final-message notes and the output-file
  list from the rail's context (they become the Summary and Output sections). No route signature
  change; still disk-first.
- `ui/runs_store.py` — add read-path helpers: `produced_elsewhere(events)` (best-effort PR/commit/
  file miner, FR-011/FR-012), tool-card enrichment on the existing `conversation_entries` output
  (clamp line counts, `exit N`/`failed` derivation, FR-022/FR-024), and the section-note builders
  (FR-009/FR-014/FR-018/FR-020/FR-034).
- `ui/markdown.py` — **new**, dependency-free renderer for the FR-007 subset (paragraphs,
  `##`/`###` headings → uppercase labels, bold, inline code, bullet lists, URLs → links); escapes all
  text, passes through no raw HTML, renders the unsupported remainder as plain text.
- `ui/dagster.py` — extend the check sub-selection (`_ASSET_CHECKS_SUBQUERY` / `_run_checks_by_id`) to
  additively pull each execution's **timestamp** and a **one-line detail** (evaluation description /
  severity) so the Checks section can show a recorded time and detail (FR-015); additive and
  best-effort — absent fields degrade to `—`, and the whole Checks read still degrades to `—` when
  Dagster is unreachable. No new query; one field-set addition to an existing read.
- `ui/templates/runs/detail.html` — replace the two-view main column with the five section cards built
  from the new `disclosure`/section macro; move the Readable/Raw-log toggle and the search box into
  the Transcript section header.
- `ui/templates/runs/_rail.html` — remove **Output artifacts** and the **final-message notes** (the
  `report.notes` line) from the rail; keep Configuration, Container, Inputs, Completeness, Asset run,
  Issue and Usage in order (FR-006/FR-019/US6-AC3).
- `ui/templates/runs/_context_card.html` — reused verbatim inside the Context section (FR-019).
- `ui/templates/components/macros.html` — add shared macros for the six new components
  (design-system-first): `disclosure`/`section_card`, `tool_card` (IN/OUT), `check_row`,
  `produced_row`, `summary`. The existing `timeline`/`tool_call`/`diff_block`/`tool_out` macros stay
  for the compare page (FR-037).
- `ui/static/run-detail.js` — section disclosure toggles with keyboard + `aria-expanded` (FR-003),
  per-browser section persistence shared across `/runs/{id}` (FR-004), IN/OUT clamp/expand + the
  expand-all/collapse-all toolbar control (view-only, non-persistent — FR-025/FR-028), search over
  message + tool IN/OUT content with auto-expand-on-match (FR-029), and the relocated raw-log toggle
  (FR-030).
- `ui/static/app.css` — styles for the five new components, tokens only; the clamp fade colour
  resolves from the background token (FR-036, SC-009).
- `ui/design-system/` — the six new components' source (`.jsx` + specimen cards), `_ds_manifest.json`
  registration, rebuilt `_ds_bundle.js`, and `readme.md` documentation (FR-037, SC-010).
- `README.md` — refresh the run-detail description (five sections, IN/OUT card, produced-elsewhere)
  so docs track reality (Principle VI).
- Tests under `ui/tests/` — `test_runs.py`, `test_runs_store.py`, `test_dagster.py`,
  `test_conformance.py`, `test_design_system_sync.py`, `test_design_system_docs.py`, plus a run
  fixture that exercises every section (SC-010).

**Target Platform**: Docker Compose on a Raspberry Pi (arm64, Debian Bookworm); the `ui` service.
Unchanged.

**Project Type**: Multi-package product tree; this feature is confined to the `ui/` package plus the
design system it owns. No orchestrator, image, litellm, or scripts change.

**Performance/Constraints**: The page MUST still render with the orchestrator/Dagster stopped — disk
is the source of truth, and the Checks section degrades to its empty state when Dagster is unreachable
(bounded by `config.RELOAD_TIMEOUT_S`, exactly as the overview's enrichment). Clamp detection, the
produced-elsewhere miner, and the Summary renderer are pure functions over data already loaded — no
extra disk reads on the hot path. The raw transcript remains bounded to 512 KB (existing
`read_transcript`).

**Scale/Scope**: A single run's detail page. Event streams range from a handful to a few thousand
entries; the miner and clamp helpers are linear over the entries already parsed. Clamp height is fixed
at 3 lines (spec Assumption); no operator-facing setting is added.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.3.0. Only the relevant principles gate this presentation/read-path feature.

| Principle | Gate | Verdict |
|-----------|------|---------|
| VII. One Design System | The six new presentation components land in the design system first (source + specimen + manifest + bundle + readme), then as shared macros, then on the page; every new/changed control is macro-composed; styling resolves from tokens only (the clamp fade follows the background token); no inline `style`/`<style>`; app CSS lives in `app.css`. Enforced by `test_conformance.py`, `test_design_system_sync.py`, `test_design_system_docs.py` (FR-036/FR-037, SC-009/SC-010). | **PASS** — planned design-system-first. |
| V. Ephemeral Runs, Immutable Outputs | Read-path only. The page reads the run record and Dagster and never writes or mutates run data; the additive Dagster check-field selection is a read; no `/output` write; `SCHEMA_VERSION` untouched (FR-035). | **PASS** |
| VI. Docs Track Reality | README run-detail section and the design-system readme updated for the five sections, the IN/OUT card, and produced-elsewhere; the docs/conformance tests keep them honest. | **PASS** (tracked as a Phase-1 obligation) |
| I–IV (isolation, config-over-code, secrets, uniform harness) | Not engaged — no orchestrator, agent schema, harness, container, or secret surface changes. | **N/A** |

No violations. **Complexity Tracking is empty.**

**Post-design re-check**: After Phase 1, the design adds exactly the components the spec names
(section disclosure, IN/OUT tool card, check row, produced-elsewhere row, rendered summary), reuses
existing macros/intents/data sources for everything else (file row, `ax-result` check mark, run status
intents, the context card, the raw-log view, `dagster.run_status`), writes no run data, adds no
dependency, and keeps the page rendering disk-only when Dagster is down. Constitution Check still
**PASS**; Complexity Tracking stays empty.

## Planning decisions (made unattended)

Recorded here because planning ran without a human to confirm; each is the most reasonable reading of
the spec + repo. Full rationale in [research.md](./research.md).

1. **Sections are server-built view models; open/closed state is client-only.** `ui/main.py` shapes
   the five sections and their closed-state notes at request time; `run-detail.js` persists open/closed
   in `localStorage` under **one shared key** (`agentbox.runDetail.sections`), not keyed per run id
   (clarification), and falls back to the FR-002 defaults when persistence is unavailable — no error
   (R1).
2. **The Summary markdown subset is rendered server-side by a dependency-free helper** (`ui/markdown.py`)
   that escapes all input, emits only the FR-007 subset, and never passes raw HTML through. This makes
   the "no raw markup" guarantee structural and lets the golden fixtures assert the rendered output
   (R2).
3. **Summary source precedence**: `report.notes` → final event text → the Summary foot line
   (status · turns · files written) + "No final message was captured." (FR-008). The Summary foot line
   is the three-field variant — distinct from the four-field Transcript foot line (FR-033). The
   `report.notes` line therefore leaves the rail's Usage block entirely (FR-006, spec Assumption) (R3).
4. **Produced-elsewhere is mined best-effort from the normalized event stream** with null-action
   fallback (R4): a **pull request** = a tool result containing a GitHub pulls `html_url`; a **commit**
   = a git result containing a short SHA; a **file** = a write/edit tool call's `file_path`. Rows are
   grouped **pull requests → commits → files**, event order within each kind (clarification/FR-012).
   The list appears only when `/output` had no artifacts (US4) and only when evidence exists; otherwise
   the section shows the file list or "No output artifacts" alone (FR-013).
5. **Checks come from `dagster.run_status([run_id])`**, the same per-run read the Agents overview uses
   (FR-016), extended additively to pull each check's recorded **time** and **one-line detail**; when
   Dagster is unreachable or reports no checks for the run, the section shows "No checks were configured
   for this agent." and the note reads "—" (FR-017). Best-effort and read-only; no new check types (R5).
6. **`exit N` / `failed` is derived best-effort** because the normalized event schema carries no exit
   field (`images/lib/agent_events.py`): `failed` when the result is `missing` or matches a permission-
   refusal marker; `exit N` only when the result text carries a recognizable exit code; otherwise the
   head shows only the description (spec edge case) (R6). (`conversation_entries` does expose an `exit`
   key on each tool dict, but it is a vestigial placeholder always left `None` — nothing populates it —
   so it is not the source of the marker; see data-model.md "Tool card view model".)
7. **Clamp is fixed at 3 lines, detected server-side**: the view model counts IN/OUT lines and flags
   `overflow` (> 3) so the template renders the fade and the "Show all N lines" link deterministically;
   `run-detail.js` toggles the expanded state. **Diff OUT rows render expanded by default** — an
   unconditional design choice (not a condition triggered only when clamped colouring would be
   unreadable) so diff colouring is never clamped, matching the spec's unconditional FR-026 rule and
   the Session 2026-09-18 clarification (finding A1) (R7).
8. **The six new components are design-system-first** (R8); the existing `tool_call`/`timeline` macros
   are left in place for the compare page (FR-037, spec Assumption). Section-note wording is adopted
   from the artboard (spec Assumption): "final message from the agent"; "0 files · 1 pull request";
   "4 passed · 1 warning"; "prompt · appended · N instruction file(s)"; "N turns · M tool calls".

## Project Structure

### Documentation (this feature)

```text
specs/017-ui-run-detail-page/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — decisions R1–R8
├── data-model.md        # Phase 1 output — the five sections + tool-card/produced/check view models
├── quickstart.md        # Phase 1 output — runnable validation of every user story
├── contracts/
│   ├── run-detail.md            # GET /runs/{id} render contract + the produced-elsewhere/summary/checks reads
│   └── design-system.md         # the five new design-system components + macro contracts
├── checklists/
│   └── requirements.md  # (pre-existing) spec quality checklist
└── tasks.md             # /speckit-tasks output — NOT created here
```

### Source Code (repository root)

Confined to the `ui/` package and the design system it owns. No orchestrator, image, litellm, or
scripts changes.

```text
ui/
├── main.py                         # _run_detail_page rework: five section view models + notes; rail trimmed
├── runs_store.py                   # + produced_elsewhere(); tool-card clamp/exit derivation; section-note builders
├── markdown.py                     # NEW: dependency-free FR-007 subset renderer (escape-all, no raw HTML)
├── dagster.py                      # check sub-selection gains time + one-line detail (additive, best-effort)
├── templates/
│   ├── runs/detail.html            # five section cards; raw-log toggle + search moved into Transcript header
│   ├── runs/_rail.html             # Output artifacts + final-message notes removed; rest unchanged/in order
│   ├── runs/_context_card.html     # reused verbatim inside the Context section
│   └── components/macros.html      # + disclosure/section_card, tool_card (IN/OUT), check_row, produced_row, summary
├── static/
│   ├── run-detail.js               # disclosure + persistence (shared key), clamp/expand-all, search over IN/OUT, raw toggle
│   └── app.css                     # new-component styling, tokens only (fade follows background token)
├── design-system/
│   ├── components/layout/Disclosure.jsx (+ specimen)     # section card + collapsible header
│   ├── components/data/ToolCard.jsx (+ specimen)         # IN/OUT clamped tool card
│   ├── components/data/CheckRow.jsx (+ specimen)         # check result row (reuses ax-result mark)
│   ├── components/data/ProducedRow.jsx (+ specimen)      # produced-elsewhere row
│   ├── components/data/Summary.jsx (+ specimen)          # rendered final-message subset
│   ├── _ds_manifest.json           # register the five new components + specimens
│   ├── _ds_bundle.js               # rebuilt bundle
│   └── readme.md                   # document the new components + usage
└── tests/
    ├── test_runs.py                # five sections + order + defaults; produced-elsewhere; summary fallback; notes
    ├── test_runs_store.py          # produced_elsewhere miner; clamp/exit derivation; note builders
    ├── test_dagster.py             # check-field additions parse; Checks degrade to — when unreachable
    ├── test_conformance.py         # tokens-only / macro-composed / no inline styles for the new markup
    ├── test_design_system_sync.py  # manifest ↔ macro ↔ bundle parity for the five new components
    └── test_design_system_docs.py  # readme documents the five new components

README.md                           # run-detail section refreshed (Principle VI)
```

**Structure Decision**: Single-package UI feature. All product code lives under `ui/`, matching the
repo's "management UI" home in `AGENTS.md`; the design system under `ui/design-system/` is extended in
place with the five new components, honouring Principle VII's design-system-first rule. The compare
page and its `tool_call`/`timeline` macros are deliberately left untouched.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.
