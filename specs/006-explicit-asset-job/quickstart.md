# Quickstart: Explicit Asset/Job Model & Automation Shell Cleanup

End-to-end validation that proves the feature works. Run from the repo root on the Pi host
(`10.0.0.100`). Prerequisites: the stack builds and the UI venv exists (`.venv/`, Python 3.12).

References: [spec.md](spec.md) · [plan.md](plan.md) · contracts/. Details live in the contracts;
this is a run guide, not an implementation.

---

## §1. Unit + contract tests (no containers)

```bash
cd ui && ../.venv/bin/python -m pytest -q
```

Expect green: schema (job field + triggers block, migration 3→4, at-least-one-of +
produces-required + cron shape), agents_store (emitter writes `job:` + `# --- Triggers ---`;
reader lifts `triggers`; round-trip), automation_store (per-agent per-kind rows; write edits
`agents/*.yaml`), api (`/api/schema` shape; Automation grouped rows; `GET/PUT /api/automation`),
`test_migrate_automation.py` (carry-over + directory removal + idempotency), and the consistency
grep test (no raw `<select>`, no `.ax-banner` save notice). Orchestrator tests over
`factory`/`definitions` with a stubbed launch pass for all three kinds and both trigger routes.

## §2. Run the carry-over migration (once)

```bash
python3 scripts/migrate-automation-to-triggers.py
```

Expect: `categorize-commits.yaml` gains `triggers: { job_schedule: "30 2 * * *" }` and
`job: true`; `list-commits-pi-kimi.yaml` gains `triggers: { asset_schedule: "20 17 * * *" }`;
both re-stamped `# agentbox-schema: 4`; the `automation/` directory is removed. Then:

```bash
python3 scripts/migrate-automation-to-triggers.py   # second run: "nothing to do"
git status                                            # automation/ gone; two agent files changed
# No runtime reader for the old store, and no on_demand keyword, remain. Exclude build caches
# (.pyc / .pytest_cache regenerate on every test run and are not source):
grep -rn "on_demand\|automation/" agents/ orchestrator/ ui/ scripts/ docker-compose.yml \
  --exclude-dir=__pycache__ --exclude-dir=.pytest_cache
```

The only matches this leaves are, by design, not a runtime reader (SC-008):
- `scripts/migrate-automation-to-triggers.py` (and its test) — the one-off carry-over must name
  the old `automation/migrated.yaml` it reads;
- `orchestrator/tests/test_definitions.py::test_no_automation_reader_or_on_demand_remains` — the
  guard test that *proves* no `load_automation` / `on_demand` remains in `definitions.py`, so it
  necessarily contains those literals;
- `ui/main.py` `"automation/list.html"` — the Automation *page's* Jinja template path (the page
  stays; only the standalone trigger store is gone).

## §3. Create each of the three kinds from the form (US1 / SC-002)

Start the stack (`docker compose up -d`) and open `http://10.0.0.100:8080` (UI). For each:

1. **Asset-only** — tick only the Asset card; set an asset key; leave both schedules blank;
   save. Confirm in Dagster the asset exists and is Materializable, and **no** `agent_<name>`
   job appears. Leaving the asset key empty must reject on save (Acceptance 1.1).
2. **Job-only** — tick only the Job card; save. Confirm `agent_<name>` is a plain launchable
   job and **no** asset exists (Acceptance 1.3).
3. **Both** — tick both cards; set an asset key; save; run `agent_<name>`. Confirm the run
   records a **materialization** of the asset, and that manual Materialize, the auto-condition,
   and a job schedule all target the same asset (Acceptance 1.4).
4. **Neither** — untick both; save. Confirm the save is rejected with "the agent must be an
   asset, a job, or both" (Acceptance 1.5 / SC-003).

## §4. Per-agent triggers load correctly (US2)

After the migration + a Dagster reload:

- `categorize-commits` (job-mode): a `sched_categorize_commits` schedule exists on cron
  `30 2 * * *` (Acceptance 2.1).
- `list-commits-pi-kimi` (asset-mode): the asset has an `on_cron` auto-condition on
  `20 17 * * *` via the `autocond_list_commits_pi_kimi` sensor — **not** a job schedule
  (Acceptance 2.2). This is the daily-partitioned Null-Action path (see §8).
- Any agent with no schedule set has no automatic trigger and stays runnable by hand
  (Acceptance 2.5).

## §5. Carry-over is lossless + preserves on/off (US2 / SC-001 / FR-014)

**Before** the migration (on a checkout still carrying `automation/`), record the live
instigators and their paused/running state from Dagster:

```bash
curl -s http://localhost:3000/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ schedulesOrError { ... on Schedules { results { name scheduleState { status } } } } sensorsOrError { ... on Sensors { results { name sensorState { status } } } } }"}' \
  | python3 -m json.tool
```

**After** the migration + reload, run the same query. The set of `sched_*` / `autocond_*` names
and their statuses MUST be identical — names and crons are unchanged (research R6/R7), so a
trigger that was running stays running and a paused one stays paused (FR-012). No agent that was
scheduled before silently stops (SC-001).

## §6. Automation page — rows, grouping, independence (US3)

Open `/automation`:

- An asset-only agent shows only an asset-schedule row; a job-only agent only a job-schedule
  row; a both-kind agent shows both rows **grouped** as one unit (Acceptance 3.1/3.2).
- Toggle one row on-demand → cron, enter a value, Save & reload. Confirm the change is written
  to that agent's `triggers:` block (check the file), Dagster reloads, and the trigger is live
  (Acceptance 3.3). For a both-kind agent, confirm the other schedule is unchanged (3.4).
- Confirm the success notice appears (Acceptance 3.5) and is the **shared** notice (§7).

## §7. Shared shell, dropdown, notice (US4)

- **Fixed shell**: scroll a long page (e.g. Agents) — the sidebar and top bar stay put; only the
  content scrolls (SC-006). Shrink to ~400px — nothing overlaps or hides content; the layout
  stays usable (Acceptance 4.1/4.2).
- **Dropdown**: `grep -rn "<select" ui/templates ui/static` shows only shared-component usage;
  the Automation row dropdown looks and behaves like the agent-form dropdowns (SC-004 /
  Acceptance 4.3).
- **Notice**: trigger a save on both the agent form and the Automation page — the two notices are
  visually identical (SC-005 / Acceptance 4.4).
- **No layout shift**: type into a cron field on the Automation page so the shape warning toggles
  — the row does not shift (SC-007 / Acceptance 4.5).

## §8. Null-Action: partition targeting check (FR-015)

Verify against the installed Dagster (1.13.21) that `AutomationCondition.on_cron` on the
daily-partitioned `list-commits-pi-kimi` asset targets the **current-day** partition when its
`autocond_*` sensor is turned on and the cron fires:

- If it targets the correct partition → the primary path ships; no fallback marker appears.
- If it cannot → confirm the orchestrator logs a load-time warning naming the agent/asset **and**
  the Automation page shows a fallback marker on that agent's asset row, and that the
  partition-filling job schedule fills the partition instead (FR-015). Both surfaces must appear;
  neither alone is sufficient.

## §9. Docs track reality (Constitution VI)

- `README.md`: the Automation/`automation/` section is replaced by the per-agent triggers model
  (asset/job/both + `triggers:` block); key-table rows reflect `job` and `triggers`.
- `CLAUDE.local.md`: debugging notes no longer reference `automation/`.
- Templates carry the `# --- Triggers ---` block and the `job:` flag; golden files are schema 4.
- No `automation/` directory, no `on_demand`, no `scripts/migrate-schedules.py` remain (SC-008).
