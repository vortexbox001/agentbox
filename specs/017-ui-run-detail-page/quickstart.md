# Quickstart: Run Detail Page — validation guide

Runnable checks that prove the feature end-to-end, one block per user story. Presentation and
read-path only — nothing here writes run data (FR-035). References: [spec.md](./spec.md),
[contracts/run-detail.md](./contracts/run-detail.md),
[contracts/design-system.md](./contracts/design-system.md), [data-model.md](./data-model.md).

## Prerequisites

Repo-root venv per `AGENTS.md` → **Dev environment**:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r ui/requirements.txt dagster==1.13.21 dagster-pipes==1.13.21
```

The UI tests run through FastAPI's `TestClient` and read the runs tree from disk; a live Dagster is
**not** required (the Checks section degrades to its empty state when Dagster is unreachable). For
manual, browser-level checks, the full Compose stack (`ui`, `dagster-webserver`, …) is needed.

## Automated validation (authoritative — must all pass, SC-010)

```bash
.venv/bin/python -m pytest -q ui/tests   # runs, runs_store, dagster, conformance, ds-sync, ds-docs
```

Run the whole `ui` suite — it is the gate. New/updated tests to expect:
- `test_runs.py` — five sections in order; the FR-002 open/closed defaults; Summary markdown +
  fallback ladder (report.notes → final event → foot line + "No final message was captured.");
  produced-elsewhere rows and grouping; the closed-state notes; the rail no longer carries output
  files or `report.notes`.
- `test_runs_store.py` — `produced_elsewhere` PR/commit/file detection and grouping; tool-card clamp
  overflow (> 3 lines) and `exit`/`failed` derivation; the note builders.
- `test_dagster.py` — the additive check fields (time + one-line detail) parse; Checks degrade to `—`
  when Dagster is unreachable.
- `test_conformance.py` / `test_design_system_sync.py` / `test_design_system_docs.py` — the five new
  components are registered (manifest/bundle/readme) and everything stays tokens-only, macro-composed,
  no inline styles, no literal colours/pixels (the fade follows the background token).

Point the UI at a data root with the reference run (`speckit-open-pr`, 2026-09-18, spec Assumptions)
for the manual checks below:

```bash
AGENTBOX_DATA=/path/to/data .venv/bin/uvicorn ui.main:app --port 8000
```

## US1 — Sectioned layout, defaults, and per-browser persistence (P1)

1. Open `/runs/{id}`. Confirm the main column is **exactly five sections** in order: Summary, Output,
   Checks, Context, Transcript (SC-001).
2. On first load confirm Summary/Output/Checks/Transcript are **open** and Context is **collapsed**;
   each closed section shows a chevron, title, and a right-aligned muted note (FR-002/FR-003).
3. Collapse Context (or open it), reload, and confirm the state is remembered (SC-002). Open a
   **different** run and confirm the same open/closed choice applies (shared per browser, not per run
   — FR-004).
4. Open in a fresh browser profile → the defaults apply; disable localStorage → defaults still apply,
   no error (FR-004, edge case).
5. Compare the header + stat strip with today's page: crumb, status tag, agent/date chips, "View in
   Dagster", and the six stats are unchanged (FR-005).

## US2 — IN/OUT tool cards (P1)

1. Find a tool call whose OUT is many lines: confirm it shows **3 lines** with a fade and a **"Show
   all N lines"** link; click the row → it expands and the link reads **"Show less"**; click again →
   collapses (SC-005).
2. Find a tool call at/under 3 lines: no fade, no link (US2-AC3).
3. Use the transcript toolbar **Expand all output** → every card expands, control reads **Collapse all
   output**; collapse a single card while "all" is on (FR-028). Reload → cards are clamped again
   (view-only, non-persistent).
4. Open a refused write → head shows **`failed`** and the OUT row reads in the failed colour (SC-006);
   a `missing` result shows the missing marker in the warning colour (FR-027).
5. Open a diff result → diff colouring is preserved in the OUT row (FR-026).

## US3 — Summary as formatted text (P1)

1. On the reference run confirm the Summary renders the `## Summary` heading as an uppercase label, the
   bold gate line, code spans, and the bullet list — **no raw markdown markup visible** (SC-003).
2. A run whose report has no notes but whose event stream has a final message → the Summary shows the
   event's text (FR-008).
3. A legacy run with neither → the Summary shows the foot line + "No final message was captured."
   (SC-008).
4. Confirm the rail's Usage block no longer shows the final-message notes (US3-AC4).

## US4 — Output, including produced elsewhere (P2)

1. A run with output files → each appears as a `file_row` (name, size, Preview/Download) (FR-010).
2. A run that wrote no files but **opened a PR and pushed a commit** → Output shows "No output
   artifacts" then a **Produced elsewhere** list with a Pull request row and a Commit row (short SHA),
   each with an Open action (SC-004); the note reads **"0 files · 1 pull request"** (FR-014).
3. A run whose stream has no minable evidence → the file list / "No output artifacts" alone (FR-013).

## US5 — Checks (P2)

1. A run with recorded checks → each row shows a pass/warn/fail mark + icon, name, one-line detail, and
   recorded time (right-aligned), matching the Agents overview mark language (FR-015); the note counts
   outcomes, e.g. **"4 passed · 1 warning"** (FR-018).
2. A run with no recorded checks (or Dagster stopped) → "No checks were configured for this agent." and
   the note reads **"—"** (SC-008, R5).

## US6 — Context (P2)

1. Expand Context → the prompt, appended system prompt, and each instruction file appear with
   click-to-expand rows exactly as today (FR-019).
2. The note counts instruction files, e.g. **"prompt · appended · 1 instruction file"** (FR-020).
3. Confirm harness/container/inputs/completeness remain in the rail, in order (US6-AC3).

## US7 — Search and skim the transcript (P2)

1. Search a term that appears **only inside a tool card's IN or OUT** → matching entries stay,
   non-matching hide, match count reports the number; the matching card **auto-expands**; clearing the
   search restores every entry and the card's clamped state (SC-007, FR-029).
2. Switch **Readable / Raw-log** (now in the Transcript header) → the unchanged `transcript.jsonl` view
   shows, and back (FR-030).
3. Confirm the last assistant message and the final event render **once**, as a Result (FR-032), and
   the run foot line sits at the bottom of the Transcript (FR-033).

## Theme check (SC-009)

View the page in **light, dark, and Indigo** themes: section borders, the IN/OUT box ground and fade,
the muted OUT text, and the check marks all read correctly, with the fade colour following the
background token.
