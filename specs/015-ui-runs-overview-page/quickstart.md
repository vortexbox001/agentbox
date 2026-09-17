# Quickstart: Runs Overview Page — validation guide

Runnable checks that prove the feature end-to-end, one block per user story. Presentation and
read-path only — nothing here writes run data. References: [spec.md](./spec.md),
[contracts/runs-overview.md](./contracts/runs-overview.md),
[contracts/pagination-component.md](./contracts/pagination-component.md).

## Prerequisites

Repo-root venv per `AGENTS.md` → **Dev environment**:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r ui/requirements.txt dagster==1.13.21 dagster-pipes==1.13.21
```

The UI tests run through FastAPI's `TestClient` and read the runs tree from disk; a live Dagster is
not required for the suite (enrichment degrades to last-known). For manual, browser-level checks,
the full Compose stack (`ui`, `dagster-webserver`, …) is needed.

## Automated validation (authoritative — must all pass, SC-009)

```bash
.venv/bin/python -m pytest -q ui/tests            # routes, runs, dagster, conformance, ds-sync, docs
```

Run the whole `ui` suite — it is the gate. New/updated tests to expect:
- `test_runs.py` — status truth vs local fallback (last-known), the ten columns in order, Date/Time/
  Attempts gone, `q` substring over agent/model/target/run id, tab partition + counts over the
  filtered set, 30/page pagination, page-reset on tab/filter change, `—` cost vs `0`, Created label.
- `test_dagster.py` — `run_status` issues exactly one POST and degrades to `{"reachable": False}`.
- `test_conformance.py` / `test_design_system_sync.py` / `test_design_system_docs.py` — the new
  Pagination component is registered (manifest/bundle/readme) and everything stays tokens-only,
  macro-composed, no inline styles.

## US1 — True status at a glance (P1)

1. Point the UI at a data root with runs whose local `report.json` says `ok`, and a Dagster that
   records some as `FAILURE`/`STARTED`/`QUEUED`.
2. `GET /runs` → each row's **Status** reflects Dagster's outcome (failed shows the failure intent,
   not `ok`); an executing run shows *in progress*; a queued run shows *queued* (FR-001,
   AC1–AC3, SC-001).
3. Stop Dagster → `GET /runs` still returns `200`; every row shows its local status marked
   **last-known**; no dead Dagster links (FR-002, AC4, SC-002).
4. For a run whose report disagrees with Dagster while Dagster is reachable, Status is Dagster's
   outcome (FR-003, AC5).

## US2 — Partition and filter (P1)

1. With runs in mixed states, `GET /runs?tab=failed` → only failed/timed-out/cancelled runs; each
   tab badge shows its count over the filtered set (FR-005/FR-006, AC1).
2. `GET /runs?q=<agent|model|target|run-id fragment>` → the table narrows by case-insensitive
   substring on any of those fields (FR-009, AC2).
3. `GET /runs?tab=succeeded&q=foo&agent=bar&date_from=2026-09-01&date_to=2026-09-17&page=2` → copy
   the URL, reopen in a fresh client → identical view restored (FR-011, AC3, SC-004).
4. Confirm no Status dropdown remains; the tabs replace it (FR-007, AC4).

## US3 — Read the columns (P1)

1. Header reads exactly **Run, Status, Agent, Model, Target, Launched by, Checks, Created, Duration,
   Cost**; no Date, Time, or Attempts (FR-012/FR-013, AC1).
2. A run created 13:15 local on 17 Sep reads `Sep 17, 1:15 PM`, full timestamp on hover (FR-017,
   AC2, SC-005).
3. A run with unknown cost reads `—`, never `0` (FR-019, AC3); a real `$0` still shows a value.
4. An in-progress run's **Duration** shows elapsed-so-far, advancing on refresh (FR-018, AC4).
5. A scheduled / sensor-launched / manual run shows the schedule name / sensor name / manual launch
   in **Launched by**, matching Dagster (FR-015, AC5); **Target** matches Dagster's asset key or job
   name (FR-014).
6. **Agent** and **Model** use the Agents-overview mono treatment; the agent name links to
   `/agents/<agent>` (FR-020, AC6). **Checks** render like the Agents overview (FR-016).
7. A historical run missing Target/Launched by shows `—`, not a guess (FR-021, edge case).

## US4 — Jump to the same run in Dagster (P2)

1. With Dagster configured, the Run column shows a right-justified indigo link icon → opens
   `{dagster_url}/runs/<run_id>` in a new tab (FR-022, AC1); the run id links to `/runs/<run_id>`
   (FR-023, AC2).
2. With Dagster not configured, no icon is rendered and no dead link exists (FR-024, AC3).

## US5 — Pagination (P2)

1. With ≥ 31 matching runs, page 1 shows exactly 30 newest-first and pagination controls appear
   (FR-025, AC1, SC-006). Page 2 shows the remainder.
2. On page 2, changing tab or filter returns to page 1 (FR-027, AC2).
3. A copied `?…&page=2` URL reopens on page 2 with the same tab/filter (FR-028, AC3, SC-004).
4. Tab count badges reflect the whole filtered set, not the current page (FR-006, AC4).
5. A `?page=` past the last page resolves to a valid page, not an error (edge case).
6. The `pagination` macro is used (design-system-first, FR-034) — verified by the conformance/ds-sync
   suites above.

## US6 — Tidy navigation shell (P2)

1. The left nav reads **Runs**, a horizontal rule, then **Agents** (FR-029, AC1).
2. Exactly one **Settings** entry — the foot button opening the settings modal; `/settings` is not a
   nav destination (FR-030, AC2). The modal reaches every setting the old page offered — either
   inline or by linking to the retained `/settings` page (FR-031, AC3; staged per research R4).
3. The logo/wordmark links **home** in both expanded and collapsed nav (FR-032, AC4) and shows a
   visible focus ring on keyboard focus (AC5), in light and dark themes (SC-007/SC-008).

## Manual smoke (optional, needs the Compose stack)

```bash
docker compose up -d ui dagster-webserver dagster-daemon litellm
# open http://<host>:<ui port>/runs
```

Drive one run each to succeed / fail / time out / stay in progress, then eyeball US1–US6 above and
compare Target + Launched by against Dagster's own Runs page (Independent Tests in the spec).
