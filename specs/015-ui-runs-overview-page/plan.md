# Implementation Plan: Runs Overview Page

**Branch**: `015-ui-runs-overview-page` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-ui-runs-overview-page/spec.md`

## Summary

Bring the Runs overview (`GET /runs`) up to the standard of the Agents overview: a shared-macro
tabbed header (All / In progress / Succeeded / Failed) with per-tab count badges, a ghost-Filter
control revealing a text filter (agent, model, target, run id) plus the existing agent and
date-range filters, a re-ordered column set (Run, Status, Agent, Model, Target, Launched by,
Checks, Created, Duration, Cost), a truthful status sourced from Dagster with a last-known
fallback, a one-click link to the same run in Dagster, and URL-encoded tab/filter/page state with
30-per-page pagination. Alongside it, tidy the shell so Runs leads the navigation, Settings appears
exactly once (the foot modal), and the logo links home. Pagination lands in the design system first
as a shared macro (FR-034).

The technical crux: the current overview is disk-only (`runs_store.list_runs`) and shows every row
as its self-reported status. This feature adds a **best-effort Dagster enrichment join** keyed on
the run id — which is already the Dagster run id and the run-directory name
(`runs/<agent>/<date>/<run-id>/`, confirmed in `orchestrator/run_capture.py` /
`factory.py:1249`). Enrichment supplies true status, Target, Launched by, and Checks; when Dagster
is unreachable or has no record for a run, the row falls back to the local record marked
last-known. This is presentation and read-path work only: **no agent schema, run-record, or
stored-run-data change**, consistent with the constitution's *Ephemeral Runs, Immutable Outputs*.

## Technical Context

The stable stack facts live in `AGENTS.md` → **Stack and tests** (Python 3.12; FastAPI + Jinja2 +
httpx + PyYAML on the UI, tested through `TestClient`; files-only storage; plain ES-module JS in
`ui/static/`, no bundler). This section records only what THIS feature adds or changes.

**Language/Version**: Python 3.12 (UI); plain ES-module JavaScript (`ui/static/`). No new language.

**Primary Dependencies**: No new dependencies. Reuses FastAPI/Jinja2/httpx already pinned in
`ui/requirements.txt`. Reuses the existing `ui/dagster.py` GraphQL client style (one bounded,
aliased/batched read, transport/parse failures collapsed to plain data).

**Storage**: Unchanged — files only. The overview reads the runs tree
(`$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`, mounted read-only) via `runs_store.list_runs`, and
enriches best-effort from Dagster's GraphQL. Nothing is written; `SCHEMA_VERSION` is untouched.

**New/changed surface (files this feature touches)**:
- `ui/dagster.py` — new `run_status(run_ids)` (single batched `runsOrError(filter:{runIds:[…]})`
  read → status + Target + Launched by + Checks per id; failure → `{"reachable": False, …}`).
- `ui/runs_store.py` — extend the list row with a `created` epoch/label helper and a `duration`
  helper computed at render; add model/target/run-id substring matching. No new disk reads on the
  hot path beyond the existing report + context headers.
- `ui/main.py` — rework `GET /runs`: tab partition, count badges over the filtered set, pagination
  (30/page), URL state (`tab`, `q`, `agent`, `date_from`, `date_to`, `page`); merge Dagster
  enrichment; drop the `status` dropdown query. Extend/replace `GET /api/runs`. Remove `/settings`
  from the nav (route may remain as the modal's fallback target per FR-031).
- `ui/templates/runs/list.html` — tabbed header + ghost-Filter toolbar + new column set + Dagster
  link icon; drop Date/Time/Attempts and the Status dropdown.
- `ui/templates/base.html` — nav order (Runs, rule, Agents), single Settings (foot), logo → home
  link with a visible focus state.
- `ui/static/runs-list.js` — tab/filter/pagination client behaviour and URL sync, modelled on
  `agents-list.js`.
- `ui/templates/components/macros.html` + `ui/static/app.css` + design-system source — a new
  **Pagination** component (FR-034): design system first (JSX specimen + manifest + bundle +
  readme), shared macro second.
- `ui/design-system/` — Pagination component source, specimen card, `_ds_manifest.json`,
  `_ds_bundle.js`, `readme.md`.
- Tests under `ui/tests/` (routes, runs, dagster, conformance, design-system sync).

**Target Platform**: Docker Compose on a Raspberry Pi (arm64); the `ui` service. Unchanged.

**Project Type**: Multi-package product tree; this feature is confined to the `ui/` package plus
the design system it owns.

**Performance/Constraints**: The overview MUST still render with the orchestrator stopped
(SC-002): disk is the source of truth, Dagster is best-effort and bounded by
`config.RELOAD_TIMEOUT_S`. Enrichment is one batched GraphQL read per page render (never one
request per run). See research R1 for the batch-vs-cap decision.

**Scale/Scope**: A single-box install; run history from tens to low thousands. Pagination shows 30
newest-first; tab counts cover the whole filtered set. Enrichment is capped (R1) so a very large
history cannot make a single render unbounded.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.3.0. Only the relevant principles gate this presentation/read-path feature.

| Principle | Gate | Verdict |
|-----------|------|---------|
| VII. One Design System | New Pagination component lands in the design system first, then the shared macro; every new/changed control (tabs, filter, table cells, link icon, pagination) is composed from shared macros; styling resolves from tokens only; no inline `style`/`<style>`; CSS lives in `app.css`. Conformance suite (`test_conformance.py`, `test_design_system_docs.py`, `test_design_system_sync.py`) enforces it (FR-033/FR-034, SC-009). | **PASS** — planned as design-system-first. |
| V. Ephemeral Runs, Immutable Outputs | Read-path only; the overview reads runs and never writes or mutates run data (spec Assumptions). | **PASS** |
| VI. Docs Track Reality | README + design-system readme updated for the new Pagination component and the nav/settings change; conformance/docs tests keep them honest. | **PASS** (tracked as a Phase-1 obligation) |
| I–IV (isolation, config-over-code, secrets, uniform harness) | Not engaged — no orchestrator, agent schema, harness, or secret surface changes. | **N/A** |

No violations. **Complexity Tracking is empty.**

**Post-design re-check**: After Phase 1, the design still adds exactly one design-system component
(Pagination), reuses existing macros/intents for everything else, writes no run data, and keeps the
page rendering disk-only when Dagster is down. Constitution Check still **PASS**; no entry needed in
Complexity Tracking.

## Planning decisions (made unattended)

Recorded here because planning ran without a human to confirm; each is the most reasonable reading
of the spec + repo. Full rationale in [research.md](./research.md).

1. **Enrichment is server-side and best-effort, computed before the tab partition** so tab
   membership and count badges reflect true Dagster status on first paint (FR-001/FR-005/FR-006),
   with a documented cap for very large filtered sets (R1). The page still renders disk-only when
   Dagster is unreachable, every row marked last-known (FR-002, SC-002).
2. **The join key is the run id**, which is both the run-directory name and the Dagster run id
   (verified). The Dagster link is `{public_dagster_url}/runs/{run_id}` in a new tab; omitted when
   Dagster is not configured (FR-022/FR-024) (R2).
3. **Text filter `q`** matches a case-insensitive substring against agent, model, target, and run
   id (FR-009); Target participates only when enrichment supplied it (R3).
4. **`/settings` route is retained as an unlinked fallback** for FR-031's staged path; it is removed
   from the nav and the foot modal is the single Settings entry (R4). Full consolidation of the
   Retention + Governors controls into the modal is **deferred** — the modal links to the existing
   `/settings` page — because those controls POST to server endpoints and moving them is more than a
   relocation, which FR-031 explicitly permits.
5. **Pagination is a design-system component** (`pagination` macro) added first, then used (FR-034)
   (R5).
6. **Column positions** for Status and Checks follow FR-012 exactly (the spec's open Assumption is
   resolved to FR-012's order).

## Project Structure

### Documentation (this feature)

```text
specs/015-ui-runs-overview-page/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — decisions R1–R6
├── data-model.md        # Phase 1 output — presented Run, Tab, Filter state, enrichment
├── quickstart.md        # Phase 1 output — runnable validation of every user story
├── contracts/
│   ├── runs-overview.md         # Page route, /api/runs, and the Dagster run_status read
│   └── pagination-component.md  # Design-system Pagination component + macro contract
├── checklists/
│   └── requirements.md  # (pre-existing) spec quality checklist
└── tasks.md             # /speckit-tasks output — NOT created here
```

### Source Code (repository root)

Confined to the `ui/` package and the design system it owns. No orchestrator, image, litellm, or
scripts changes.

```text
ui/
├── main.py                         # /runs rework: tabs, counts, pagination, URL state, enrichment merge; /api/runs
├── dagster.py                      # + run_status(run_ids): one batched runsOrError read (status/target/launched-by/checks)
├── runs_store.py                   # + created/duration helpers; model/target/run-id substring match
├── templates/
│   ├── base.html                   # nav order (Runs · rule · Agents), single Settings, logo→home + focus
│   ├── runs/list.html              # tabbed header, ghost Filter, new columns, Dagster link icon
│   └── components/macros.html      # + pagination(...) macro (design-system-first)
├── static/
│   ├── runs-list.js                # tab/filter/pagination behaviour + URL sync (modelled on agents-list.js)
│   └── app.css                     # pagination + any list styling (tokens only)
├── design-system/
│   ├── components/navigation/Pagination.jsx (+ specimen card)   # component source, design-system-first
│   ├── _ds_manifest.json           # register Pagination
│   ├── _ds_bundle.js               # rebuilt bundle
│   └── readme.md                   # document Pagination + usage
└── tests/
    ├── test_runs.py                # status truth, fallback/last-known, columns, filter, pagination, counts
    ├── test_dagster.py             # run_status batching + degrade-to-unreachable
    ├── test_conformance.py         # tokens-only / macro-composed / no inline styles
    └── test_design_system_sync.py  # manifest ↔ macro ↔ bundle parity for Pagination
```

**Structure Decision**: Single-package UI feature. All product code lives under `ui/`, matching the
repo's "management UI" home in `AGENTS.md`. The design system under `ui/design-system/` is extended
in place (Pagination), honouring Principle VII's design-system-first rule.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.
