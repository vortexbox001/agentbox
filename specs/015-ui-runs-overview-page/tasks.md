---
description: "Task list for Runs Overview Page (015)"
---

# Tasks: Runs Overview Page

**Input**: Design documents from `/specs/015-ui-runs-overview-page/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: INCLUDED. The spec makes the passing `ui` suite a success criterion (SC-009) and the
quickstart names the specific new/updated tests as authoritative
(`test_runs.py`, `test_dagster.py`, `test_conformance.py`, `test_design_system_sync.py`,
`test_design_system_docs.py`). Test tasks therefore ship with each story.

**Organization**: Grouped by user story so each is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task serves (US1–US6)
- Every task lists an exact product-tree file path (AGENTS.md → "Where each kind of file goes").

## Path Conventions

Single-package UI feature — all product code lives under `ui/` plus the design system it owns
(`ui/design-system/`). No orchestrator, image, litellm, or scripts changes. Tests sit under
`ui/tests/`. Never write against `config/` or `/data/…` (instance config/state, not product files).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working surface; no new dependencies (plan Technical Context).

- [ ] T001 Confirm the repo-root venv is present and the `ui` suite is green as a baseline: run
  `python3.12 -m venv .venv && .venv/bin/pip install -r ui/requirements.txt dagster==1.13.21 dagster-pipes==1.13.21`
  then `.venv/bin/python -m pytest -q ui/tests` (record the pre-change pass; AGENTS.md → Dev environment).
- [ ] T002 [P] Verify the reusable assets this feature depends on already exist so no new ones are
  invented: the `#external` and `#filter` icons in `ui/static/icons.svg`, the `tabs` macro
  (`ui/templates/components/macros.html:115`), the `run_status_tag` macro
  (`macros.html:161`), `_fmt_cost` (`ui/main.py:358`), and the Agents-overview ghost-Filter pattern
  (`ui/templates/agents/list.html:45-53`). Note any missing asset as a blocking follow-up.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The server-side read path every P1 story needs — the Dagster enrichment read, the
status-normalisation table, the runs_store presentation helpers, and the `GET /runs` /
`GET /api/runs` filter→enrich→count→partition→paginate pipeline. **No status/tab/column story can
begin until this phase is complete.**

**⚠️ CRITICAL**: US1, US2, US3 all consume this pipeline.

- [ ] T003 Add the status-normalisation mapping (contract §D, research R8) as a helper in
  `ui/dagster.py` (e.g. `_present_status(dagster_status, local_status) -> str`) that folds Dagster
  `RunStatus` (`QUEUED`/`NOT_STARTED`/`STARTING`/`STARTED`/`SUCCESS`/`FAILURE`/`CANCELED`/`CANCELING`)
  and local report statuses (`ok`/`failed`/`timeout`/`running`/`unknown`) into the presented set
  {`succeeded`, `failed`, `timed_out`, `cancelled`, `queued`, `in_progress`, `unknown`}, plus a
  `_status_tab(present) -> str` mapping presented status → tab bucket (`in_progress`, `succeeded`,
  `failed`) and a `_status_intent(present)` for the `run_status_tag` intent.
- [ ] T004 Implement `run_status(run_ids: list[str]) -> dict` in `ui/dagster.py` (contract §C,
  research R6): exactly one GraphQL POST `runsOrError(filter:{runIds:[…]}, limit:N)` selecting
  `runId, status, startTime, endTime, assetSelection{path}, pipelineName, tags{key value}` and the
  asset-check sub-selection, parsed with the existing `_check_status`/`_parse_checks` helpers.
  Return `{"reachable": bool, "runs": {run_id: {status, start_time, end_time, target, launched_by,
  checks}}}`; collapse every `httpx.HTTPError`/`ValueError`/`PythonError`/non-`Runs` arm to
  `{"reachable": False, "runs": {}}` (never raise). Bound by `config.RELOAD_TIMEOUT_S`. Derive
  `target` from `assetSelection.path` (join with `/`) else `pipelineName`; `launched_by` from
  `dagster/schedule_name` → schedule, `dagster/sensor_name` → sensor, else manual.
- [ ] T005 [P] Extend `ui/runs_store.py` with presentation helpers used by the row builder: a
  `created` epoch accessor plus an ISO string (from the existing `started` epoch on the store row),
  and a `duration_seconds(started, ended)` helper. Do NOT add disk reads on the hot path beyond the
  existing report + context headers (plan). Keep `date`/`started_time`/`attempts` in the dict but
  they are no longer rendered (data-model "Removed from the row").
- [ ] T006 [P] Extend the row/list filtering in `ui/runs_store.py` (or a `main.py` helper) so the
  text filter `q` matches a case-insensitive substring over agent, model, run id — and target once
  enrichment supplies it (FR-009, research R3). An em-dash target never matches.
- [ ] T007 Rework `GET /runs` in `ui/main.py` (`_runs_list_page`, contract §A) to the pipeline:
  parse URL state `tab`/`q`/`agent`/`date_from`/`date_to`/`page` (unknown `tab` → `all`; `page` ≥ 1,
  clamped to last valid page); apply text+agent+date filter; enrich the filtered set via
  `dagster.run_status` (capped at N=500 newest, research R1) merging true status/target/launched-by/
  checks and marking un-enriched rows `last_known`; compute per-tab counts over the filtered set
  **before** partition; partition by `tab`; sort newest-first; paginate 30/page. Drop the old
  `status` dropdown query param (ignore if present, FR-007). Pass `tabs`/`counts`/`pages`/`page`/
  `reachable`/`base_query`/`dagster_url` to the template.
- [ ] T008 Rework `GET /api/runs` in `ui/main.py` (`_api_runs`, contract §B) to accept the same
  params and return `{runs:[…], counts:{…}, page, pages, reachable}`, each row carrying the
  data-model *Run (as presented)* fields (`run_id, status, last_known, agent, model, target,
  launched_by, checks, created, created_iso, duration, cost_usd, dagster_url`). MUST return
  `reachable:false` + last-known rows rather than failing when Dagster is down.
- [ ] T009 [P] Add `test_dagster.py` coverage: `run_status` issues **exactly one** POST (assert call
  count), parses status/target/launched-by/checks, omits run ids absent from `results`, and degrades
  to `{"reachable": False, "runs": {}}` on transport/parse/`PythonError` arms (contract §C
  guarantees).
- [ ] T045 [US1] Surface the enrichment-cap note (FR-035, research R1). In `ui/main.py` (T007) flag
  when the filtered set exceeds N=500 so only the most-recent N are enriched (rows beyond the cap
  stay last-known, never dropped); in `ui/templates/runs/list.html` render a visible note ("Showing
  the most recent 500 runs enriched from Dagster; older rows show last-known status.") composed from
  tokens/macros only — no inline style. Add a `test_runs.py` case: with >500 filtered rows the note
  renders and the older rows are present and last-known (not truncated). Depends on T007 (cap flag)
  and the reworked template (T014/T019).

**Checkpoint**: Foundation ready — the page renders enriched rows disk-first; user-story rendering
can proceed.

---

## Phase 3: User Story 1 - Read a run's true status at a glance (Priority: P1) 🎯 MVP

**Goal**: Every row shows the real Dagster outcome (succeeded/failed/timed out/cancelled/queued/in
progress); when Dagster is unreachable or has no record, the row falls back to the local record
marked last-known.

**Independent Test**: Drive one succeed/fail/timeout run and leave one in progress; confirm each
row's Status matches Dagster. Stop Dagster; confirm the page still loads with last-known statuses.

- [ ] T010 [US1] Render the true presented status in `ui/templates/runs/list.html` via the
  `run_status_tag` macro using the normalised intent from T003 (replaces the current
  everything-maps-to-`ok` inline dict at `list.html:51`) (FR-001/FR-004).
- [ ] T011 [US1] Render the last-known marker on rows where `last_known` is true — a visible
  badge/`title` alongside the status tag that keeps the mapped intent but signals staleness (FR-002,
  research R8, checklist CHK003). Styling via tokens/macros only (no inline style).
- [ ] T012 [US1] Ensure Dagster's outcome wins over the run's self-reported report while reachable,
  and that a run id Dagster has no record for is treated as last-known (already wired in T007;
  verify the merge precedence in `ui/main.py`) (FR-003, edge case).
- [ ] T013 [P] [US1] Add `test_runs.py` cases: a run Dagster records `FAILURE` shows failed intent
  (not `ok`); an executing run shows in-progress; a queued run shows queued; with Dagster stopped
  every row is last-known and the page returns `200`; a report-vs-Dagster disagreement resolves to
  Dagster while reachable (AC1–AC5, SC-001/SC-002).

**Checkpoint**: US1 fully functional and independently testable — the list tells the truth.

---

## Phase 4: User Story 2 - Partition and filter runs to find what matters (Priority: P1)

**Goal**: Tabbed header (All / In progress / Succeeded / Failed) with per-tab count badges over the
filtered set; a ghost-Filter control revealing a text filter plus the retained agent + date-range
filters; tab/filter state in the URL.

**Independent Test**: Click each tab → only that state's runs, badges match; type into the filter →
narrows by agent/model/target/run id; copy the URL and reopen → tab/filter/date restored.

- [ ] T014 [US2] Replace the toolbar in `ui/templates/runs/list.html` with the shared `tabs` macro
  header (All / In progress / Succeeded / Failed, each with a `counts`-driven badge) modelled on
  `ui/templates/agents/list.html:45-53`, and **remove the Status `<select>` dropdown** (FR-005/FR-006/
  FR-007).
- [ ] T015 [US2] Add the ghost **Filter** button + hidden text input (placeholder `Filter runs…`),
  keeping the existing agent `select` and `date_from`/`date_to` inputs revealed by the filter control
  (FR-008/FR-010), composed from shared macros only.
- [ ] T016 [US2] Rewrite `ui/static/runs-list.js` modelled on `ui/static/agents-list.js`: toggle the
  filter input, filter-as-you-type (case-insensitive substring over agent/model/target/run id),
  switch tabs, and keep `tab`/`q`/`agent`/`date_from`/`date_to`/`page` in the URL via
  `history.replaceState`, degrading to full navigation when history is unavailable; refresh rows from
  `GET /api/runs` without a full reload (FR-009/FR-011, research R3).
- [ ] T017 [US2] Ensure changing tab, text filter, agent, or date range resets `page` to 1 — client
  on control change (T016) and server clamp (T007) (FR-027; verified again in US5).
- [ ] T018 [P] [US2] Add `test_runs.py` cases: `?tab=failed` returns only failed/timed-out/cancelled
  rows; badges count the whole filtered set (before partition, independent of page); `?q=<fragment>`
  narrows by agent/model/target/run id; a full `?tab=&q=&agent=&date_from=&date_to=&page=` URL
  round-trips identically; no Status dropdown remains in the rendered HTML (AC1–AC4, SC-003/SC-004).

**Checkpoint**: US1 + US2 work independently — operators can partition and find runs.

---

## Phase 5: User Story 3 - Read the run table's columns (Priority: P1)

**Goal**: Columns in order — Run, Status, Agent, Model, Target, Launched by, Checks, Created,
Duration, Cost — with mono Agent/Model (agent links to `/agents/<agent>`), `Sep 17, 1:15 PM` Created
with full timestamp on hover, elapsed Duration, `—`-for-unknown Cost, and Target/Launched by/Checks
from enrichment (`—` when unobtainable). Date/Time/Attempts columns gone.

**Independent Test**: Compare a scheduled/sensor/manual run's Target + Launched by against Dagster;
confirm a 13:15 run reads `Sep 17, 1:15 PM`; unknown cost reads `—`; Date/Time/Attempts absent.

- [ ] T019 [US3] Rebuild the `<thead>`/`<tbody>` of `ui/templates/runs/list.html` to the ten columns
  in FR-012 order and **remove Date, Time, and Attempts** (FR-013). Preserve the run-id link to
  `/runs/{run_id}` (FR-023).
- [ ] T020 [US3] Render Agent and Model with the Agents-overview mono treatment and link the agent
  name to `/agents/{agent}` (FR-020); Model shows `—` when absent.
- [ ] T021 [US3] Render Target and Launched by from enrichment — asset key or job name exactly as
  Dagster lists it (FR-014); schedule name / sensor name / manual launch (FR-015); `—` when
  enrichment could not supply either for a historical run, never a guess (FR-021).
- [ ] T022 [US3] Render Checks the same way the Agents overview does (reuse its Checks cell treatment
  driven by `_check_status`) (FR-016).
- [ ] T023 [US3] Render Created as `Sep 17, 1:15 PM` in operator-local time with the full ISO
  timestamp on `title=` hover, and Duration as elapsed run time (`end−start`, or `now−start` for
  in-progress; `—` when unknown; no live ticker) — local-time formatting done template/JS-side
  against the browser tz (FR-017/FR-018, research R7, SC-005).
- [ ] T024 [US3] Render Cost via `_fmt_cost` so unknown shows `—` and a real `0` still shows a value
  (FR-019).
- [ ] T025 [P] [US3] Add `test_runs.py` cases: header is exactly the ten columns in order with no
  Date/Time/Attempts; a 13:15-on-17-Sep run's Created reads `Sep 17, 1:15 PM`; unknown cost reads
  `—` while `$0` shows a value; an in-progress Duration shows elapsed-so-far; agent cell links to
  `/agents/<agent>`; Target/Launched by fall back to `—` when enrichment is absent (AC1–AC6,
  SC-005/SC-007).

> **SC-007 theme-parity verification note (A5)**: SC-007's light/dark cross-overview parity is not
> asserted by a pixel/theme test (the TestClient cannot observe rendered themes). It is guaranteed
> **by construction** — both overviews render from the same design-system tokens, enforced by
> `test_conformance.py` (tokens-only, macro-composed) — and validated **manually** per quickstart.
> T025 verifies the shared column set / mono treatment / agent link that SC-007 also names.

**Checkpoint**: All three P1 stories complete — the overview is a truthful, filterable, readable
table. **MVP boundary.**

---

## Phase 6: User Story 4 - Jump to the same run in Dagster (Priority: P2)

**Goal**: A right-justified indigo `#external` link icon in the Run column opens
`{public_dagster_url}/runs/{run_id}` in a new tab; the run id still links to the AgentBox run page;
no icon (and no dead link) when Dagster is not configured.

**Independent Test**: With Dagster configured, the icon opens the correct run in a new tab and the id
opens the AgentBox page; with Dagster not configured, the icon is absent.

- [ ] T026 [US4] Add the right-justified `#external` link icon to the Run column in
  `ui/templates/runs/list.html`, `href="{{ r.dagster_url }}" target="_blank" rel="noopener"`, in the
  indigo/accent ramp, rendered **only when `r.dagster_url` is set** (FR-022/FR-024). `dagster_url` is
  built from `public_dagster_url(request)` + run id in `ui/main.py` (T007/T008).
- [ ] T027 [P] [US4] Style `.ax-run-dagster-link` (indigo ramp, right-justified) in
  `ui/static/app.css` using tokens only — no literal colours/pixels, no inline style (FR-033).
- [ ] T028 [P] [US4] Add `test_runs.py` cases: with Dagster configured the row contains a
  `target="_blank"` link to `{dagster_url}/runs/{run_id}` and the id links to `/runs/{run_id}`; with
  Dagster not configured no such icon/link is rendered (AC1–AC3).

**Checkpoint**: US4 complete — one-click path to Dagster, no dead links.

---

## Phase 7: User Story 5 - Page through many runs (Priority: P2)

**Goal**: 30 runs/page newest-first with pagination controls; tabs/filters apply before pagination;
tab counts reflect the whole filtered set; current page is in the URL; changing tab/filter returns to
page 1. **Pagination lands in the design system first (FR-034), then a shared macro, then the page.**

**Independent Test**: With ≥31 matching runs, page 1 shows 30 and page 2 the rest; change tab/filter
→ page 1; copy a page-2 URL and reopen → page 2 restored; a `?page=` past the end resolves to a valid
page.

### Design-system-first (FR-034 — blocks the macro and the page use)

- [ ] T029 [US5] Add the Pagination component source under
  `ui/design-system/components/navigation/`: `Pagination.jsx`, `Pagination.d.ts`,
  `Pagination.prompt.md`, and a `pagination.card.html` specimen — matching the `Tabs.*` file set in
  the same folder (contract §A.1–A.2).
- [ ] T030 [US5] Register Pagination in `ui/design-system/_ds_manifest.json` (a `components` entry
  `{"name":"Pagination","sourcePath":"components/navigation/Pagination.jsx"}` and a matching
  `startingPoints` entry: section `Components`, subtitle, viewport) and rebuild
  `ui/design-system/_ds_bundle.js` so the manifest↔bundle parity check holds (contract §A.3–A.4).
- [ ] T031 [P] [US5] Document Pagination in `ui/design-system/readme.md`: purpose, anatomy
  (Prev · indicator · Next), first/last-page disabling, and that page state lives in the URL
  (contract §A.5).

### Shared macro (second)

- [ ] T032 [US5] Add `pagination(page=1, pages=1, base_query="", attrs={})` to
  `ui/templates/components/macros.html` (contract §B): a `<nav class="ax-pagination"
  aria-label="Pagination">` with a shared-button-styled Prev link to `?{base_query}&page={page-1}`
  (`aria-disabled`/non-navigating on page 1), a `Page {page} of {pages}` indicator, and a Next link
  (`aria-disabled` on the last page). Works without JS; `pages` always ≥ 1.
- [ ] T033 [P] [US5] Style `.ax-pagination` and its parts in `ui/static/app.css` using tokens only —
  the accent ramp for active/hover, no literal colours/pixels/`font-family`, no inline style
  (contract §C, FR-033).

### Use on the page

- [ ] T034 [US5] Use the `pagination` macro below the table in `ui/templates/runs/list.html` when
  `pages > 1`, passing `page`, `pages`, and `base_query` (tab + filters) so Prev/Next preserve view
  state (FR-025/FR-028).
- [ ] T035 [US5] Enhance pagination in `ui/static/runs-list.js` — intercept Prev/Next and sync the
  `page` param via `history`, but do not require JS for correctness (contract §B, FR-028).
- [ ] T036 [P] [US5] Add `test_runs.py` cases: ≥31 matching rows → page 1 has 30 newest-first and
  pagination renders; page 2 has the remainder; changing tab/filter returns to page 1; a copied
  `?…&page=2` URL reopens on page 2; `?page=` past the end clamps to a valid page; badges reflect the
  whole filtered set (AC1–AC4, SC-006).
- [ ] T037 [P] [US5] Extend `test_design_system_sync.py` and `test_design_system_docs.py` (and
  confirm `test_conformance.py`) so Pagination is covered by manifest↔bundle↔macro parity and the
  readme requirement (contract §D, SC-009).

**Checkpoint**: US5 complete — history scales; Pagination is a first-class design-system component.

---

## Phase 8: User Story 6 - A tidy navigation shell (Priority: P2)

**Goal**: Left nav reads Runs · rule · Agents; exactly one Settings entry (the foot modal button),
`/settings` no longer a nav destination; the logo links home in expanded and collapsed nav with a
visible keyboard focus state.

**Independent Test**: Nav reads Runs, rule, Agents; one Settings entry opens the modal; the logo
returns home from any page including collapsed, with a visible focus ring.

- [ ] T038 [US6] Reorder the primary nav in `ui/templates/base.html` to Runs first, then the
  `.ax-nav-divider` keyline, then Agents, and **remove the Settings nav item** (`base.html:63-66`) so
  the foot button (`#ax-settings-link`) is the single Settings entry; `/settings` is no longer a nav
  destination (FR-029/FR-030). The foot modal links to the retained `/settings` page for the
  server-backed controls per the staged path (FR-031, research R4).
- [ ] T039 [US6] Wrap the brand mark/lockup (`base.html:42-48`) in a home link (`href="/"`) active in
  both expanded and collapsed nav, with a visible keyboard focus state styled via tokens in
  `ui/static/app.css` (FR-032).
- [ ] T040 [P] [US6] Update tests (`ui/tests/test_ui_consistency.py` and/or `test_api.py`): nav order
  is Runs · rule · Agents; exactly one Settings entry and no `/settings` nav link; the logo is an
  `href="/"` link present when collapsed; keep the `/settings` route reachable (still `200`) as the
  modal's fallback (AC1–AC5, SC-008).

**Checkpoint**: US6 complete — the shell reads as one finished product.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Docs track reality (constitution VI) and the whole gate is green (SC-009).

- [ ] T041 [P] Update `README.md` — the Runs overview section (new columns, tabs, filter, Dagster
  link, pagination) and the nav/Settings change (constitution VI, plan Constitution Check).
- [ ] T042 [P] Confirm `ui/design-system/readme.md` and the served gallery reflect Pagination
  end-to-end (thumbnail + starting point render) — cross-check with T031 (constitution VI).
- [ ] T043 Run the full gate `.venv/bin/python -m pytest -q ui/tests` and fix any failure — routes,
  runs, dagster, conformance, ds-sync, docs must all pass (SC-009).
- [ ] T044 Walk quickstart.md US1–US6 blocks against the running app (or TestClient where a live
  Dagster is not needed) and confirm each acceptance criterion (quickstart Automated validation +
  per-story blocks).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1, US2, US3, US5** (the enrichment read,
  status mapping, and the `GET /runs` pipeline they all render from).
- **US1 (Phase 3)**: depends on Foundational. MVP core.
- **US2 (Phase 4)**: depends on Foundational; independent of US1 rendering (shares the pipeline).
- **US3 (Phase 5)**: depends on Foundational; column cells consume enrichment from Phase 2.
- **US4 (Phase 6)**: depends on Foundational (`dagster_url` from T007/T008); independent of US1–US3.
- **US5 (Phase 7)**: depends on Foundational (server pagination in T007); the design-system-first
  sub-phase (T029–T031) blocks the macro (T032) which blocks page use (T034) and the sync tests
  (T037).
- **US6 (Phase 8)**: independent of the table work — depends only on Setup; can proceed in parallel.
- **Polish (Phase 9)**: depends on all shipped stories.

### User Story Dependencies

- US1, US2, US3 are all P1 and all render from the same reworked `list.html` + Phase-2 pipeline; they
  are independently testable but touch overlapping files (`list.html`, `main.py`, `runs-list.js`), so
  sequence them US1 → US2 → US3 within one worker to avoid file conflicts.
- US4, US5, US6 are P2 and largely orthogonal (US6 is fully orthogonal).

### Within Each User Story

- Rendering/behaviour before its tests within a story is fine; the story is complete only when its
  tests pass. Foundational tests (T009) precede US rendering that relies on the read.

### Parallel Opportunities

- Phase 1: T002 ∥ T001.
- Phase 2: T005 ∥ T006 (different helpers) after T003/T004; T009 ∥ once `run_status` exists.
- US6 (Phase 8) can run fully in parallel with the table stories (different files: `base.html`).
- Within US5, T031 (readme) ∥ T029/T030 authoring; T033 (css) ∥ T032 (macro).
- All `[P]` test tasks (T013, T018, T025, T028, T036, T037, T040) run in parallel once their
  implementation lands.

---

## Parallel Example: Foundational read path

```bash
# After T003 (status mapping) and T004 (run_status) land:
Task T005: "created/duration helpers in ui/runs_store.py"
Task T006: "q substring match over agent/model/target/run id"
Task T009: "test_dagster.py: run_status one-POST + degrade-to-unreachable"
```

## Implementation Strategy

### MVP First (P1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 (truthful status) →
4. Phase 4 US2 (tabs + filter) → 5. Phase 5 US3 (columns). **STOP and VALIDATE**: the overview is
truthful, filterable, and readable — ship the MVP.

### Incremental Delivery

Add US4 (Dagster link), US5 (pagination + design-system Pagination), and US6 (nav shell) as
independent P2 increments, each validated on its own, then Phase 9 polish. US6 can ship any time.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Design-system-first is non-negotiable for Pagination (FR-034, constitution VII): T029–T031 before
  T032 before T034.
- Read-path only — no agent schema, run-record, or stored-run-data change; `SCHEMA_VERSION`
  untouched (plan, constitution V).
- Enrichment is one batched Dagster read per render, capped at N=500 (research R1); the page MUST
  render with Dagster stopped (SC-002).
- Commit after each task or logical group; run `ui/tests` before pushing.
