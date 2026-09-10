# Contract: Orchestrator trigger construction

How `definitions.py` + `factory.py` turn the merged `{name → trigger}` map into Dagster
objects. The launch op and the job/asset representation are unchanged from 004; this
contract covers only trigger wiring.

## §1 Load sequence (`definitions.py`)

1. Discover agents exactly as today (skip `enabled: false`; `produces` → asset via
   `build_asset`, else job via `build_job`).
2. Load + merge `automation/*.yaml` → `{name → trigger}` and validate per
   automation-format §3 (raise on dup key, unknown agent, both-triggers, bad cron).
3. Warn (do not fail) on any agent file still carrying a `schedule` key, naming the file (R7).
4. For each **enabled** agent:
   - **job-mode** → build the job once (`job = build_job(cfg)`), append it to `jobs`; if the
     agent has a `cron` trigger, `schedules.append(build_schedule(job, cron))` (same job object).
   - **asset-mode** with a `cron` trigger → build the asset with
     `AutomationCondition.on_cron(cron)` and `sensors.append(build_asset_automation_sensor(cfg))`.
5. `Definitions(jobs=jobs, schedules=schedules, assets=assets, sensors=sensors)`.

A disabled agent named by an entry is skipped at step 1; its entry attaches to nothing and
is **not** a dangling-agent error (the file exists).

## §2 `factory.py` surface

```
build_job(cfg)                     -> @job named agent_<name>            (was build_job_and_schedule, schedule removed)
build_schedule(job, cron)          -> ScheduleDefinition(job=job, cron_schedule=cron, name="sched_<name>",
                                                          execution_timezone=cron_timezone())
                                       # takes the ALREADY-BUILT job object (built once per agent, shared by the
                                       # jobs list and its schedule; a second job of the same name is rejected by Dagster)
                                       # no default_status => STOPPED (paused); migrated names preserve prior on/off
cron_timezone()                    -> os.environ["TZ"] or "UTC"  # crons run in the box's TZ, not UTC (both surfaces)
build_asset(cfg, file, automation_condition=None)
                                       -> AssetsDefinition.from_op(run op, keys_by_output_name, partitions_def,
                                                                   automation_condition=on_cron(cron) when given)
                                       # asset cron condition: AutomationCondition.on_cron(cron, cron_timezone())
build_asset_automation_sensor(cfg) -> AutomationConditionSensorDefinition(
                                          name="autocond_<name>",
                                          target=AssetSelection.assets(<key>),
                                          default_status=DefaultSensorStatus.STOPPED)
is_valid_cron(s)                   -> bool   # five fields, no @-macros (shared rule)
```

- `<name>` is `cfg["name"]` with hyphens → underscores (as today for jobs/ops/schedules).
- Names are stable across reloads so Dagster preserves on/off state (FR-014).

## §3 Default run state (FR-021)

| Surface | New trigger | Migrated trigger |
|---------|-------------|------------------|
| `sched_<name>` | paused (STOPPED default) | prior on/off preserved (same name) |
| `autocond_<name>` sensor | paused (STOPPED) | n/a — no assets exist pre-feature |

Turning `autocond_<name>` on enables **only** that asset's cron (per-asset sensor), matching
per-schedule toggling for jobs — the consistency FR-021 requires. Because each automation
asset is covered by its own sensor, Dagster does not also attach its global default
automation sensor to it.

## §4 Partitioned assets (Null Action)

Primary: `on_cron(cron)` on a `DailyPartitionsDefinition` root asset targets the current
day's partition per tick (R5). Fallback if the installed Dagster does not: `build_asset`'s
caller instead appends a schedule from `build_schedule_from_partitioned_job(
define_asset_job("materialize_<name>", AssetSelection.assets(key), partitions_def=daily))`,
named `sched_<name>`, STOPPED — the partition is filled from the tick. The choice is gated by
the build-time check in quickstart §7 and, if used, noted in tasks.md.

## §5 Unchanged

The container launch op, `agent_<name>` job naming, `run_<name>` op naming, output location,
and the 004 asset/materialization metadata are all untouched. Removing an agent's automation
entry removes only its schedule/sensor; the job/asset itself remains and is hand-runnable
(Story 5 / FR-020).
