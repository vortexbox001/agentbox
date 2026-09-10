# Data Model: Automation Config

The entities this feature introduces or changes. No database — files under `agents/` and
`automation/` plus `ui/schema.py` are the model, and Dagster's instigator storage holds the
on/off state.

---

## Automation entry

One key/value pair in a file under `automation/`.

| Part | Shape | Rules |
|------|-------|-------|
| key | agent `name` (string) | MUST match the `name` of some `agents/*.yaml`; kebab-case (same rule as `name`). At most once across all `automation/` files. |
| value | mapping with exactly one trigger | Exactly one of `cron` or `on_demand` (see Trigger). A value with neither degrades to on-demand; with both it is rejected. |

Absence of a key for an agent is equivalent to `on_demand: true` (FR-006).

## Automation file

A YAML file under `automation/`. Top level is a **map keyed by agent name** (one entry per
key). Zero or more files may exist. `migrated.yaml` is the file the migration writes and the
UI's canonical write target.

```yaml
# automation/migrated.yaml
repo-librarian-agentbox:
  cron: "30 2 * * *"
```

**Cross-file rule**: an agent name appearing in two files (or twice in one) is the conflict
of FR-011 — rejected at load, naming the agent and files.

## Trigger

The when-it-runs value. Exactly one form:

| Form | Value | Meaning |
|------|-------|---------|
| `cron` | five-field cron string, e.g. `"30 2 * * *"` | Automatic. Validated: exactly five whitespace-separated fields; cron macros (`@daily`, …) unsupported — same rule the removed `schedule` field used. |
| `on_demand` | `true` | No automatic trigger. Runnable only by hand. The explicit spelling of the default. |

A `cron` trigger maps to a Dagster surface depending on the agent's mode:

| Agent mode | Trigger surface | Name | Default state |
|------------|-----------------|------|---------------|
| job (no `produces`) | `ScheduleDefinition(job=agent_<name>, cron_schedule=cron)` | `sched_<name>` | paused (Dagster default; migrated schedules keep prior on/off) |
| asset (`produces`, 004) | `AutomationCondition.on_cron(cron)` on the asset + `AutomationConditionSensorDefinition` targeting it | condition on the asset key; sensor `autocond_<name>` | paused (`DefaultSensorStatus.STOPPED`) |

Null-Action fallback (R5): if `on_cron` cannot target the right partition on the installed
Dagster, the asset surface becomes a partition-filling schedule that targets the asset,
named `sched_<name>`, paused by default.

## Agent definition (changed)

The existing `agents/*.yaml`, now describing the agent only.

- **Removed**: the `schedule` key. It is no longer in the schema, `ALWAYS_WRITTEN`, the
  emitter, the form, or the templates.
- **Schema version**: bumped 2 → 3. `migrate_2_to_3` drops any `schedule` key on read; the
  reader logs a warning naming the file when it does (FR-002).
- **Unchanged**: every other field, including `enabled` (rehomed to the Runs "Enabled"
  card), `timeout_seconds`/`max_turns` (Limits), and 004's `produces` (Produces).

State transitions for an agent's trigger (all via `automation/`, none touch the agent file):

```
no entry ──add cron──▶ scheduled/conditioned (paused) ──operator toggles──▶ running
   ▲  │                        │
   │  └────set on_demand───────┘
   └──────delete entry─────────┘        (agent stays listed & hand-runnable throughout)
```

## Per-agent trigger view (UI)

What `GET /api/automation` returns and the Automation view renders — one row per
non-template agent:

| Field | Source | Notes |
|-------|--------|-------|
| `name` | `agents_store` | the agent |
| `harness` | agent file | for display |
| `mode` | `"asset"` if the agent declares `produces` else `"job"` | drives which surface a cron becomes |
| `trigger` | merged `automation/` map, default `{on_demand: true}` | `{cron: "…"}` or `{on_demand: true}` |

## On/off (instigator) state

Not a file — Dagster's own storage under `/data/dagster`, keyed by the schedule/sensor
**name**. Preserved across reload because names are stable (`sched_<name>`,
`autocond_<name>`). This is the mechanism behind FR-014 ("same on/off state where Dagster
can preserve it"): a rename or a job→asset conversion is the case it cannot preserve.
