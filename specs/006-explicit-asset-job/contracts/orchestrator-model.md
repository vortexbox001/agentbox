# Contract: Orchestrator — nature + triggers → Dagster definitions

Governs `orchestrator/factory.py` and `orchestrator/definitions.py`. Companion:
[agent-model.md](agent-model.md).

## §1. Reading nature (replaces produces-presence inference)

`definitions.discover` classifies each enabled agent by two explicit flags:

- **is_asset** = the file has a valid `produces` block (asset key present). Unchanged detection,
  but it is now one of two independent flags, not a mode selector.
- **is_job** = `cfg.get("job") is True`.

An enabled agent with **neither** flag is rejected by name and skipped (a `RejectAgent`, like a
bad `produces` block) — the UI refuses to save such a file, so its only source is a hand-edit;
it costs only itself, not the whole reload.

## §2. Building the three kinds

| Kind | Definitions registered |
|------|------------------------|
| Asset-only (`is_asset && !is_job`) | `build_asset(cfg, file, cron=asset_schedule)` → one `AssetsDefinition`. No job. |
| Job-only (`is_job && !is_asset`) | `build_job(cfg)` → one plain `@job` `agent_<name>`. |
| Both (`is_asset && is_job`) | `build_asset(cfg, file, cron=asset_schedule)` **and** `build_materializing_job(cfg, asset_def)`. |

- `build_asset` is unchanged from 005 (wraps `make_run_op(cfg)` via `from_op`; attaches
  `AutomationCondition.on_cron(asset_schedule)` when set; `DailyPartitionsDefinition` when
  `partition: daily`).
- `build_job` is unchanged from 005 (plain op job).
- **NEW** `build_materializing_job(cfg, asset_def)` →
  `dagster.define_asset_job(name="agent_<name>", selection=AssetSelection.assets(asset_def))`.
  This is the both-kind `agent_<name>`: its runs materialize the asset (FR-006). The launch op
  is not re-implemented — the asset already wraps `make_run_op(cfg)` (FR-008).

The single launch op `make_run_op(cfg)` is shared byte-for-byte across all three kinds.

## §3. Reading triggers (replaces the `automation/` store)

Triggering is read **only** from `cfg["triggers"]`:

- `asset_schedule` (when the agent is an asset): attach `AutomationCondition.on_cron` to the
  asset (via `build_asset`'s `cron` arg) and register a paused per-asset sensor
  `build_asset_automation_sensor(cfg, asset_def)` named `autocond_<name>`
  (`DefaultSensorStatus.STOPPED`).
- `job_schedule` (when the agent has a job): register `build_schedule(job_def, cron)` named
  `sched_<name>` on the agent's job object (the plain op job or the materializing job). No
  `default_status` ⇒ new schedule starts paused.
- Absent/blank schedule ⇒ no trigger of that kind; the agent remains runnable by hand (asset:
  Materialize; job: manual launch).

`build_schedule` takes the **same job object** registered in `jobs`, so exactly one
`agent_<name>` exists per agent (a duplicate would make Dagster reject the `Definitions`).

## §4. Partition Null-Action fallback (FR-015)

Primary path: `on_cron` on a `DailyPartitionsDefinition` targets the latest (current-day)
partition per tick (005 R5). If a build-time check shows this cannot target the correct
partition on the installed Dagster:

1. Fall back to a **partition-filling `ScheduleDefinition` on the asset's materializing job**
   (define that job for an asset-only agent if the fallback is needed), named `sched_<name>`.
2. Emit an orchestrator **load-time warning log** naming the agent and asset.
3. Set a `fallback` marker on that agent's asset row, surfaced by `GET /api/automation` and
   rendered on the Automation page (see ui-automation-and-shell §2).

The quickstart §8 build-time check decides which path ships; the primary path is the default.

## §5. Retiring the legacy automation path (FR-010, SC-008)

Remove entirely from `definitions.py`: `load_automation`, `_normalize_trigger`,
`AUTOMATION_GLOB`, `RejectAutomation`, and the unknown-agent/dup-key automation checks (those
concerns move to per-agent validation and the UI). Remove every `on_demand` reference. The
module header is rewritten to describe the per-agent `triggers:` model. There is **no**
runtime reader for `automation/`.

`docker-compose.yml`: remove the three `./automation` mounts (webserver, daemon, ui) and the
`AUTOMATION_DIR` env; `automation/` no longer exists.

## §6. On/off state preservation (FR-012/FR-014/FR-016)

- Schedule name stays `sched_<name>`; sensor name stays `autocond_<name>`. Dagster keys
  instigator state by name, so a carried-over trigger keeps its prior paused/running state
  across the reload; a brand-new trigger starts paused.
- Timezone handling is unchanged: `cron_timezone()` (the box `TZ`, else UTC) applied to both
  `ScheduleDefinition.execution_timezone` and `AutomationCondition.on_cron(cron_timezone=…)`.
- `Definitions(jobs=jobs, schedules=schedules, assets=assets, sensors=sensors)` — same
  aggregation as 005, now with materializing jobs among `jobs`.

## §7. The one-off carry-over migration

`scripts/migrate-automation-to-triggers.py` (replaces `scripts/migrate-schedules.py`):

1. Read `automation/migrated.yaml` (005's store).
2. For each `name: {cron: "…"}` entry, open `agents/<name>.yaml`, decide kind by `produces`
   presence, and write the cron onto `triggers.asset_schedule` (asset-mode) or
   `triggers.job_schedule` (job-mode). Job-mode agents also get `job: true`.
3. Bump each touched file's `# agentbox-schema:` stamp to 4.
4. Remove the `automation/` directory.

Idempotent: with `automation/` gone, a re-run reports nothing to do. Errors (a named agent that
does not exist) are printed and skipped, not silently dropped. A dedicated test
(`test_migrate_automation.py`) covers strip + per-kind write + directory removal + idempotency
over a fixture repo.

## §8. Test surface (stubbed launch, no containers)

- Kind routing: asset-only → asset present, no `agent_<name>` job; job-only → plain job, no
  asset; both → asset + `agent_<name>` materializing job whose selection is the asset.
- Trigger routing: `asset_schedule` → `on_cron` on the asset + a paused `autocond_<name>`
  sensor; `job_schedule` → a paused `sched_<name>` schedule on the agent's job.
- Neither-flag agent → rejected by name, other agents still load.
- No `automation/` reader remains (grep/import-level assertion); `on_demand` gone.
- Names `sched_<name>` / `autocond_<name>` unchanged (state-preservation guard).
