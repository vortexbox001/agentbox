# Research: Automation Config

Phase 0 decisions. Each resolves a technical unknown implied by the spec and the
Constitution Check. No open NEEDS CLARIFICATION remain (the three material ambiguities were
settled in the spec's Clarifications session on 2026-09-10).

---

## R1 — Where `automation/` lives and how the orchestrator sees it

**Decision**: Add a repo-root `automation/` directory, mounted like `agents/` and
`prompts/`: read-only into both `dagster-webserver` and `dagster-daemon`
(`./automation:/opt/agentbox/automation:ro`) and writable into the `ui` service
(`./automation:/opt/agentbox/automation`). The orchestrator loads
`AUTOMATION_GLOB = /opt/agentbox/automation/*.yaml`; the UI gets an `AUTOMATION_DIR` env
mirroring `AGENTS_DIR`.

**Rationale**: `automation/` is the same *kind* of thing `agents/` and `prompts/` already
are — declarative config the orchestrator reads and the UI writes. Mirroring their mount
posture (ro for the orchestrator, rw for the UI) keeps the trust boundary identical: only
the UI writes, both Dagster services read. The daemon needs it too because it runs both the
schedules and the automation-condition sensors.

**Alternatives**: Put triggers under `agents/` or a single top-level file — rejected: the
spec fixes a `automation/` **directory** of one-or-more files, and keeping it a sibling of
`agents/` is the least surprising layout.

## R2 — Automation file format, merge, and validation

**Decision**: Each file's top level is a **map keyed by agent name** (clarification: entry
shape = A). The value is exactly one trigger:

```yaml
# automation/migrated.yaml
repo-librarian-agentbox:
  cron: "30 2 * * *"
some-other-agent:
  on_demand: true
```

Loading merges every file in `automation/` into one `{name → trigger}` map. Validation, in
this order:
1. **Duplicate agent key across files (or within one)** → raise, naming the agent and the
   files (FR-011).
2. **Unknown agent** (no `agents/*.yaml` declares that `name`) → raise, naming the entry and
   its file (FR-010) — this fails the reload.
3. **Both `cron` and `on_demand`** on one entry → raise (an entry declares exactly one
   trigger).
4. **Neither key** → treat as `on_demand` (assumption: a named-but-empty entry equals no
   entry; degrade to "not triggered" rather than fail the reload).
5. **Invalid `cron`** → raise, naming the entry (FR-009), using the same five-field / no-`@`
   -macro rule the old `schedule` field used.
An agent with no key anywhere defaults to on-demand (FR-006).

**Rationale**: A name-keyed map makes "at most one entry per agent" *within a file* a
structural property of YAML (duplicate mapping keys collapse), leaving only the
cross-file duplicate to check explicitly. Validating against the set of known agent names
turns a typo into a loud, named failure instead of a silent no-op. Failing the reload on an
unknown agent (rather than 004's skip-one) is what the spec asks for (FR-010) and is safe
because the UI refuses to write such an entry, so it only arises from a hand-edit the
operator wants to hear about.

**Alternatives**: A list of `{agent, cron}` records — rejected by the clarification. Silently
ignoring unknown-agent entries — rejected: FR-010 wants a naming failure.

## R3 — Job-mode trigger: a named, paused-by-default schedule

**Decision**: Split `build_job_and_schedule(cfg)` into `build_job(cfg)` (unchanged `@job`
named `agent_<name>`) and `build_schedule(job, cron)` →
`ScheduleDefinition(job=job, cron_schedule=cron, name=f"sched_{name}")`, where `job` is the
already-built job object (built once per agent and shared by the `jobs` list and its
schedule, so no duplicate `agent_<name>` job is created). No
`default_status` is set, so Dagster's default (`STOPPED`) makes a **new** schedule start
paused (FR-021). The schedule name stays `sched_<name>` — identical to today — so Dagster's
instigator state (the on/off toggle, keyed by name in `/data/dagster`) is preserved across
the reload for the one existing schedule (FR-014).

**Rationale**: Today's `build_job_and_schedule` already produced `sched_<name>` with no
`default_status`, i.e. paused-by-default and toggled from the UI ("Turn schedules on from
the UI", README). Keeping the name and the default identical is exactly what "same on/off
state where Dagster can preserve it" requires — the only thing that changes is *where the
cron comes from* (the `automation/` map instead of `cfg["schedule"]`).

**Alternatives**: `default_status=RUNNING` for migrated schedules — rejected: it would flip
paused schedules on and break parity; the instigator state already carries the prior
on/off, so nothing needs forcing.

## R4 — Asset-mode trigger: `on_cron` condition + a per-asset sensor for on/off

**Decision**: For an asset-mode agent (declares `produces`) with a `cron`, attach
`dagster.AutomationCondition.on_cron(cron)` to its asset (passed through `build_asset`), and
add one `AutomationConditionSensorDefinition(name=f"autocond_{name}",
target=AssetSelection.assets(key), default_status=DefaultSensorStatus.STOPPED)` per such
asset, registered in `Definitions(sensors=…)`. No sensor and no condition for an
`on_demand`/no-entry asset.

**Rationale**: An automation condition needs an automation-condition **sensor** in the
daemon to evaluate it. Dagster would otherwise supply a single *global* default sensor
covering every automation asset — one on/off switch for all of them. FR-021 wants an
asset's cron to be operator-toggleable *and paused by default, just like a job schedule* —
i.e. per-agent. A per-asset sensor named `autocond_<name>`, `STOPPED` by default, gives
exactly that: it appears in the UI next to the asset, starts paused, and turning it on
enables only that asset's cron. Because each automation asset is covered by exactly one
(its own) sensor, Dagster does not also attach the global default sensor to it.

**Alternatives**: Rely on the global `default_automation_condition_sensor` — rejected: one
switch for all assets is not the per-agent parity FR-021 asks for. Use a schedule that
materializes the asset instead of a condition — rejected as the *primary* path by FR-008
(that is the Null-Action fallback only, R5).

## R5 — Null Action: does `on_cron` target the right partition?

**Decision (primary path)**: `AutomationCondition.on_cron(cron)` on a
`DailyPartitionsDefinition` requests the **latest time-window partition** (the current day)
on each cron tick, and our produced assets are *root* assets (no upstream deps), so the
condition fires the current-day partition each tick with nothing to wait on. The primary
path (condition + per-asset sensor) therefore materializes the right partition, and the
Null Action does **not** trigger.

**Fallback (documented, per the spec's Null Action)**: if the Dagster version actually
installed in `orchestrator/Dockerfile` does not make `on_cron` target the correct partition
for a time-partitioned root asset, fall back to a **schedule that targets the asset** —
`build_schedule_from_partitioned_job(define_asset_job(f"materialize_{name}",
selection=AssetSelection.assets(key), partitions_def=daily))`, named `sched_<name>`,
`STOPPED` by default — which fills the partition automatically from the schedule tick. This
keeps per-agent on/off parity (it is a schedule, toggled per-schedule) and is the escape
hatch the spec sanctions.

**Verification task**: because Dagster is unpinned, the plan makes this a build-time check
(quickstart §7 / a tasks.md step): pin/confirm the installed Dagster version, then confirm
on the live UI that a daily-partitioned asset with an `on_cron` condition materializes the
current day's partition. If it does not, switch that one construction to the fallback and
record it. Job-mode agents and unpartitioned assets are unaffected either way.

**Rationale**: The spec's Null Action requires the plan to *say so* rather than silently
ship the wrong behavior. Root assets with time-window partitions are the simple, documented
case for `on_cron`; the fallback exists precisely for the version/edge where it isn't.

## R6 — Removing `schedule` from the schema (FR-001/002/003) and rehoming `enabled`

**Decision**: In `ui/schema.py`:
- Delete the `schedule` **field** (the `SchemaField("schedule", …)`).
- Delete the `{"id": "schedule", …}` **section** and move `enabled` into a Runs card:
  rename that section to `{"id": "status", "label": "Enabled", "group": "runs"}` holding
  only the `enabled` toggle. The Runs column then shows **Enabled**, **Limits**, and 004's
  **Produces** (FR-017).
- Remove `"schedule"` from `ALWAYS_WRITTEN`.
- Remove the `_is_unset` special-case (`return f.id != "schedule"`) so an empty string is
  simply unset again; remove the `if "schedule" in agent: _validate_schedule(...)` call.
- Keep `_validate_schedule`'s five-field cron logic as a reusable helper (the Automation
  API and the orchestrator both need the same rule — R2/Complexity).
- `SCHEMA_VERSION` 2 → 3 with `migrate_2_to_3(data)` that pops `schedule` from the dict.

In `ui/agents_store.py`: when a read file carried a `schedule` key (detected before/around
`apply_migrations` at the existing call site, where the path is known), log a warning naming
the file (FR-002). The emitter already writes only known fields, so with the field gone it
stops emitting `schedule` automatically; the golden files regenerate to a schema-3 header
with no `schedule` line.

**Rationale**: The schema is the single source of truth (form, emitter, comments, README).
Removing the field there removes it everywhere the UI touches, and the version bump +
key-dropping migration makes any lingering `schedule` (older files, hand-edits) load
cleanly with a named warning — exactly FR-002. Rehoming `enabled` keeps the promised Runs
column (Enabled + Limits) intact while deleting the Schedule card.

**Alternatives**: Keep `schedule` as a hidden/deprecated field — rejected: the spec says it
leaves the schema; a migration that drops it is cleaner than a tombstone.

## R7 — The orchestrator ignores a stray `schedule`

**Decision**: `definitions.py` and `factory.py` no longer read `cfg["schedule"]` at all.
If a loaded agent file still contains a `schedule` key, log a warning naming the file (the
orchestrator-side echo of FR-002) and proceed — the value is never turned into a trigger
(triggers come only from `automation/`).

**Rationale**: The orchestrator reads raw YAML (it does not run the UI's schema
migrations), so it must independently refuse to act on a stray key. A warning (not a
failure) matches the migration's "drop with a logged warning" and keeps a half-migrated repo
running.

**Alternatives**: Honor `schedule` if present as a fallback — rejected: it would keep two
sources of truth for triggering, the exact thing this feature removes.

## R8 — The Automation view (FR-015/016/017/020) and reuse of reload

**Decision**: A new `automation_store.py` in the UI reads/merges `automation/*.yaml` and
produces a per-agent view (`[{name, harness, mode: job|asset, trigger: {cron|on_demand}}]`)
over *every non-template* agent from `agents_store`, defaulting missing ones to on-demand.
`main.py` adds `GET /automation` (the page) and `GET/PUT /api/automation`. `PUT` validates
(agent must exist, cron must pass the shared rule, exactly one trigger), writes the whole
canonical `automation/migrated.yaml` (assumption: single UI-managed file), then calls the
existing `dagster.reload()` and returns its `{ok, message}`. The agent form's Schedule card
disappears for free once the schema drops the field/section (the form renders sections from
`/api/schema`); Enabled and Limits remain. Toggling a trigger never edits the agent file, so
the agent stays listed and hand-runnable (FR-020/Story 5).

**Rationale**: This reuses the machinery that already exists — schema-driven form,
`dagster.reload()`, the storage-error/validation-error handlers — so the Automation view is
a thin new surface, not a parallel stack. Writing the whole canonical file (rather than
surgically editing) keeps the writer simple and idempotent and matches how the UI already
regenerates agent files.

**Alternatives**: Fold triggers into the existing agent form under a different name —
rejected: the spec wants a *separate* Automation view, and mixing them back in re-couples
the two concerns. Scatter one agent's trigger across multiple files — rejected by the
single-canonical-file assumption.

## R9 — The one-off migration script (FR-012/013)

**Decision**: `scripts/migrate-schedules.py`:
1. For every `agents/*.yaml`: remove the `schedule:` line (textual removal preserves the
   file's other comments and formatting, which PyYAML round-tripping would destroy) and
   normalize its `# agentbox-schema:` stamp to 3 — bumping an existing stamp or prepending one
   to a hand-written file that lacks it, so `agents/` ends uniformly at schema 3.
2. For every **non-template** file (basename not starting with `_`) whose removed `schedule`
   was non-empty, add `‹name›:\n  cron: "‹value›"` to `automation/migrated.yaml`
   (manual-only `""` → no entry; the agent becomes on-demand).
3. **Idempotent**: a second run finds no `schedule:` lines and a stamp already at 3, and each
   target entry already present in `migrated.yaml`, so it writes nothing.

**Rationale**: Textual line-removal + a targeted stamp bump preserves the hand-authored
agent files (comments included) far better than load-and-redump, and is trivially
idempotent. Restricting *entries* to non-template files is the clarification's resolution
(templates share the placeholder name `my-agent`; writing entries for them would create a
duplicate-key/dangling conflict, FR-012) — while still stripping their `schedule` line
(FR-018) so no agent file, template or not, keeps the key (SC-001).

**Alternatives**: Re-emit each file through `agents_store` — rejected: it would rewrite
comments/ordering the operator wrote by hand and is heavier than a one-line strip. Write
entries for every file with a schedule — rejected: the `my-agent` template collision.
