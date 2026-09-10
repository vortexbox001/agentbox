# Quickstart: Automation Config

End-to-end validation that triggering lives in `automation/`, migrates losslessly, drives
both job schedules and asset automation conditions, and rejects bad entries by name. Run on
the Pi host. References [contracts/automation-format.md](contracts/automation-format.md),
[contracts/orchestrator-triggers.md](contracts/orchestrator-triggers.md), and
[contracts/ui-automation.md](contracts/ui-automation.md) for the exact rules.

## Prerequisites

- The stack builds and runs: `docker compose build && docker compose up -d`.
- `docker-compose.yml` mounts `./automation` read-only into `dagster-webserver` and
  `dagster-daemon`, and writable into `ui` (R1).
- Dagster UI reachable at `http://10.0.0.100:3000`; management UI reachable.
- The UI venv exists for the automated tests: `cd ui && ../.venv/bin/python -m pytest -q`.

## Scenario 1 — Run the migration (User Story 2, P1)

1. From the repo root: `python3 scripts/migrate-schedules.py`.
2. **Expect**: `automation/migrated.yaml` now contains `repo-librarian-agentbox:\n  cron:
   "30 2 * * *"` and no other agent (it is the only non-template with a non-empty schedule).
3. **Expect**: no `agents/*.yaml` — templates included — contains a `schedule` key; every
   file's header stamp reads `# agentbox-schema: 3` (SC-001).
4. **Expect**: no template contributes an entry (the two `_template-*` files that set a
   schedule and share the name `my-agent` are absent from `migrated.yaml`).
5. Run it again: `python3 scripts/migrate-schedules.py`.
6. **Expect**: zero file changes — `git status` is clean (SC-002, idempotent).

## Scenario 2 — Reload parity (User Story 2, P1)

1. Before migrating (on a checkout that still has schedules), note the schedules Dagster
   shows and which are toggled on.
2. After migration, reload the orchestrator.
3. **Expect**: every schedule that existed before exists after, on the same cron, with the
   same on/off state where Dagster can preserve it (`sched_repo_librarian_agentbox` on
   `30 2 * * *`) (FR-014, SC-003).

## Scenario 3 — Triggering lives in `automation/` (User Story 1, P1)

1. In `automation/migrated.yaml`, confirm `repo-librarian-agentbox` has its cron.
2. **Expect**: `agents/repo-librarian-agentbox.yaml` carries **no** triggering key (SC-007).
3. Change the entry to `on_demand: true`; reload.
4. **Expect**: `sched_repo_librarian_agentbox` is gone; the agent is still listed and runs
   by hand (AC — Story 1).

## Scenario 4 — Manage triggers from the Automation view (User Story 3, P2)

1. Open `/automation` in the management UI.
2. **Expect**: every non-template agent listed with its trigger ("on demand" or a cron).
3. Set an on-demand agent (e.g. `categorize-commits`) to a cron and save.
4. **Expect**: the entry is written to `automation/migrated.yaml`, the orchestrator reloads,
   and `sched_categorize_commits` appears — **paused** (FR-021).
5. Open any agent in the agent form. **Expect**: no Schedule card; the Runs column shows
   Enabled, Limits, and Produces only (FR-017).

## Scenario 5 — Asset-mode cron → automation condition (User Story 4, P2)

1. Add `produces: {asset: repo-review/agentbox, partition: daily}` (feature 004) to
   `repo-librarian-agentbox.yaml`; keep its cron entry in `automation/`.
2. Reload.
3. **Expect**: the orchestrator shows an **asset** with a cron-based **automation
   condition** — not a `ScheduleDefinition` — plus a paused `autocond_repo_librarian_agentbox`
   sensor (AC-1, FR-021).
4. Turn the `autocond_…` sensor on. **Expect**: at the cron tick the asset materializes the
   current day's partition (AC-2). Revert `produces` when done.

## Scenario 6 — Delete an entry, agent still runnable (User Story 5, P2)

1. Delete `repo-librarian-agentbox`'s entry from `automation/migrated.yaml`; reload.
2. **Expect**: the agent is still listed, has no schedule/condition, and launches by hand
   (SC-005 for this feature / Story 5). The Automation view shows it as "on demand".

## Scenario 7 — Reject bad entries by name (User Story 6, P3) + Null-Action check

1. **UI refusal**: in the Automation view, try to set a trigger for a non-existent agent or an
   invalid cron. **Expect**: the save is refused with a naming message; nothing is written
   (FR-009/FR-010).
2. **Reload failure**: hand-write `nope-not-an-agent:\n  cron: "0 0 * * *"` into an
   `automation/` file; reload. **Expect**: the code location fails to load with a message
   naming that entry and file (FR-010). Remove it to recover.
3. **Null-Action verification** (do once at build time): confirm the Dagster version in
   `orchestrator/Dockerfile` makes `AutomationCondition.on_cron` on a daily-partitioned root
   asset materialize the **current day's** partition (Scenario 5, step 4). If it does not,
   switch that asset's trigger to the documented fallback — a partition-filling schedule that
   targets the asset (`build_schedule_from_partitioned_job`, contract §4) — and record the
   switch in tasks.md.

## Automated tests

```bash
cd ui && ../.venv/bin/python -m pytest -q
```

Covers: schema has no `schedule` field/section and Enabled+Limits remain under Runs;
migration 2→3 drops `schedule`; emitter/golden files carry no `schedule` and stamp schema 3;
stray-`schedule` read logs a file-named warning; `automation_store` merge/validation/round-trip;
`GET/PUT /api/automation` (cron validation, unknown-agent refusal); the Automation page
renders. Orchestrator unit tests (stubbed launch) cover map merge, dup-key and unknown-agent
rejection, job→schedule vs asset→condition routing, and default-paused status. A dedicated
test drives `scripts/migrate-schedules.py` over a fixture agents dir for strip + write +
idempotency.
