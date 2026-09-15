# Contract: Viewer routes & disk-read

**Requirements**: FR-017–FR-024, SC-001..003, SC-007. **New modules**: `ui/runs_store.py`.
**New mount**: `$AGENTBOX_DATA` read-only into the ui service.

## Disk-read contract (FR-018 / SC-007)

The Runs list and run pages read run directories directly and MUST render with the orchestrator
stopped. Dagster is queried only, best-effort, to enrich list rows with live status when
reachable — never as a precondition.

`ui/runs_store.py`:
- `list_runs(agent=None, status=None, date_from=None, date_to=None) -> list[Run]` — one pass over
  `runs/<agent>/<date>/<run-id>/`, reading only `report.json` + `context.json` headers per run
  (never `events.jsonl`). Filters by agent, status, and date range (clarification).
- `read_run(run_id) -> RunDetail` — loads the four files, each optional; sets
  `conversation_available` from the presence of `events.jsonl`.
- `read_output_files(run_id) -> list[OutputFile]` — lists the run's `/output` artifacts for the
  Files tab (FR-019a), with in-viewer preview + download.

## Routes (server-rendered Jinja, mirroring the agents pages)

| Method | Path | Renders | Notes |
|--------|------|---------|-------|
| GET | `/runs` | `runs/list.html` | filterable list; FR-017. New nav item (reserved slot in `base.html`). |
| GET | `/runs/{run_id}` | `runs/detail.html` | tabs: Conversation, Context, Report, Files; FR-019. |
| GET | `/runs/compare?a=&b=` | `runs/compare.html` | field-by-field context diff of any two runs; FR-023. |
| GET | `/api/runs` | JSON | list rows for client-side filter/refresh. |
| GET | `/api/runs/{run_id}/events` | JSON | normalized events for the Conversation tab. |
| GET | `/api/runs/{run_id}/files/{path}` | file | preview/download an output artifact (path-safe, FR-019a). |

Path params run through the existing `_unsafe_name()` traversal guard.

## Tabs (FR-019, FR-019a, FR-020, FR-021, FR-022)

- **Conversation** — threaded, chat-style history rendered from `events.jsonl`: turns in order,
  collapsible tool calls + results, file edits as rendered diffs, per-turn tokens + cost, in-page
  search. **Identical shape for every harness** (SC-002). Missing tool results are marked as
  missing, not hidden (FR-021). Absent `events.jsonl` → "conversation pruned"/"conversation only"
  note (FR-028).
- **Context** — the full `context.json`: all fields, full instruction-file contents, and the
  completeness statement (FR-022, SC-008).
- **Report** — the spec-007 `report.json` fields + `notes` markdown.
- **Files** — the run's output artifacts, browsable with preview + download (FR-019a).

## Read-only (FR-024)

Post-run only; no live streaming and no editing of run data anywhere in the viewer.

## Design-system compliance

All pages compose design-system macros over tokens (no literals, no inline styles); new
components land in the design system first (see research R9 and `plan.md` Constitution Check).
