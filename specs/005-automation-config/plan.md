# Implementation Plan: Automation Config

**Branch**: `005-automation-config` | **Date**: 2026-09-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-automation-config/spec.md`

## Summary

Separate *when* an agent runs from *what* it is. The `schedule` key leaves the agent
YAML schema entirely; triggering moves to a new top-level `automation/` directory whose
files are maps keyed by agent name, each key giving that agent one trigger — `cron: "…"`
or `on_demand: true`. An agent with no entry is on-demand by default.

The orchestrator reads `automation/`, merges the files into one `{name → trigger}` map,
and per agent decides the trigger surface: a **job-mode** agent with a `cron` becomes a
`ScheduleDefinition` (named `sched_<name>`, default paused); an **asset-mode** agent
(feature 004's `produces`) with a `cron` gets an `AutomationCondition.on_cron` on its
asset, made operator-toggleable and paused-by-default via a per-asset
`AutomationConditionSensorDefinition` (`autocond_<name>`). Keeping the schedule name
stable preserves each schedule's prior on/off state on reload (FR-014); brand-new
triggers start paused (FR-021).

A one-off `scripts/migrate-schedules.py` strips `schedule` from every agent file
(templates included) and writes each *non-template* agent's existing cron into
`automation/migrated.yaml` — idempotently. The management UI loses the Schedule card
(the Runs column keeps Enabled, Limits, and 004's Produces) and gains an **Automation**
view listing every agent with its trigger; saving writes `automation/migrated.yaml` and
reloads Dagster, refusing entries that name a non-existent agent or carry an invalid cron.

**Null Action (partition targeting)**: research R5 concludes `AutomationCondition.on_cron`
on a `DailyPartitionsDefinition` targets the latest time-window (current-day) partition
per tick, so the primary path materializes the right partition. If the installed Dagster
proves otherwise at build time, the documented fallback is a schedule that targets the
asset with the partition filled in (`build_schedule_from_partitioned_job`), named
`sched_<name>` — an implementation-time verification step gates this (quickstart §7).

## Technical Context

**Language/Version**: Python 3.12 (orchestrator `factory.py`/`definitions.py`; UI
`schema.py`/`agents_store.py`/`main.py`/`dagster.py`/tests; the migration script). Browser
ES2020 modules (no build step) for the new Automation view. Same toolchain as 001–004.

**Primary Dependencies**: Dagster — new surface: `AutomationCondition.on_cron`,
`AutomationConditionSensorDefinition`, `AssetSelection`, plus the existing
`ScheduleDefinition`, `DailyPartitionsDefinition`, `AssetsDefinition.from_op`,
`Definitions(..., sensors=…)`. Installed unpinned (`pip install dagster`); declarative
automation is GA in current Dagster — R5 records a build-time version check. FastAPI +
Jinja + `httpx` (reuse `ui/dagster.py:reload()`), `pyyaml`, `pytest`/`TestClient` — all
unchanged.

**Storage**: `agents/*.yaml` (single source of truth; no database) — the `schedule` key
is removed from it. New top-level `automation/*.yaml` directory of `{name → {cron|on_demand}}`
maps; `migrated.yaml` is the canonical file the migration and the UI write. Dagster
instigator (schedule/sensor on/off) state under `/data/dagster`, keyed by name.

**Testing**: `pytest` in `ui/tests/` for everything statically checkable — schema no
longer exposes `schedule` (section gone, `enabled`/`limits` remain under Runs), migration
2→3 drops the key, emitter/golden files carry no `schedule` line and stamp schema 3,
`/api/schema` shape, the Automation view markup, and `GET/PUT /api/automation`
(round-trip, cron validation, unknown-agent refusal). Orchestrator unit tests over
`factory`/`definitions` with a stubbed launch: automation-map merge, duplicate-key and
unknown-agent rejection, job→schedule vs asset→condition routing, default-paused status,
stray-`schedule` warning. A dedicated test for `scripts/migrate-schedules.py`
(strip + write + idempotency) over a fixture agents dir. End-to-end firing verified by the
quickstart against live Dagster (no orchestrator-integration harness — same posture as
001–004).

**Target Platform**: Docker Compose on the Raspberry Pi host (arm64, Debian). Orchestrator
= `dagster-webserver` + `dagster-daemon` (the daemon runs schedules **and** the automation
condition sensors); UI = the `ui` service. Dagster UI at `http://10.0.0.100:3000`.

**Project Type**: Web service (management UI) + orchestrator (Dagster code location). Two
packages: `orchestrator/` and `ui/`, plus a repo-root `scripts/` one-off and an
`automation/` data directory.

**Performance Goals**: No new per-run cost. Load-time cost is reading a handful of small
YAML files in `automation/` and building one schedule/sensor per triggered agent —
negligible.

**Constraints**:
- **Triggering only in `automation/`** (FR-001/FR-004): the agent schema carries no
  triggering key; the orchestrator reads triggers only from `automation/`. A stray
  `schedule` in an agent file is ignored and warned about, never acted on (FR-002).
- **On/off parity** (FR-014): schedule names stay `sched_<name>` so Dagster preserves the
  prior toggle across reload. New triggers default paused (FR-021).
- **Job/asset consistency** (FR-021): an asset's cron trigger is operator-toggleable and
  paused-by-default, mirroring a job schedule — achieved with a per-asset automation
  condition sensor rather than the single global default sensor.
- **Reload fails loudly on a dangling entry** (FR-010): an automation entry naming a
  non-existent agent raises at code-location load with a message naming the entry — a
  deliberate departure from 004's skip-one-file, because the UI already refuses to write one.
- **Null Action** (partition): use `on_cron`; if it cannot target the right partition on
  the installed Dagster, fall back to an asset-targeting schedule and say so (R5).
- **Backward compatibility**: after migration, the current agent set loads with zero
  triggering noise; the one real schedule today (`repo-librarian-agentbox`, `30 2 * * *`)
  survives with the same cron and prior on/off state (SC-003).

**Scale/Scope**: ~13 non-template agent files today; exactly one sets a non-empty schedule
(`repo-librarian-agentbox`). Two templates carry non-empty schedules and share the name
`my-agent` (the reason templates get their key stripped but contribute no entry, FR-012).
No agent declares `produces` yet, so the asset-condition path is exercised by the quickstart,
not by migration. Feature touches: `orchestrator/factory.py`, `orchestrator/definitions.py`,
`docker-compose.yml` (automation mount), `ui/schema.py`, `ui/agents_store.py`, `ui/main.py`,
`ui/dagster.py` (reuse), new UI template + JS for the Automation view, the golden files, the
agent templates, `README.md`, `scripts/migrate-schedules.py`, and tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Respected. Triggering is a host-side concern (when a container
  is launched); this feature moves *where the trigger is declared*, not what the container
  can do. No new interface is granted to any agent; the launch op is byte-for-byte unchanged.
- **II. Configuration over Code** — Central. Deciding when an agent runs is now a pure
  config edit (an `automation/` entry), discovered automatically at reload — no orchestrator
  code change to schedule an agent (SC-008). Separating triggering from the agent file makes
  each concern auditable in one place.
- **III. Secrets Never in the Open** — Respected. Automation files hold only agent names and
  cron strings; no secrets, no command lines, no credentials touched.
- **IV. Uniform Interface, Diverse Runtimes** — Reinforced. Removing `schedule` from the
  per-agent schema shrinks the surface agent authors see; the trigger vocabulary
  (`cron`/`on_demand`) is harness-agnostic and identical for job-mode and asset-mode agents
  (FR-021). Adding a runtime does not touch it.
- **V. Ephemeral Runs, Immutable Outputs** — Unaffected. No change to how runs produce or
  store output.
- **VI. Docs Track Reality** — Served. The README key table loses `schedule` and gains an
  Automation section (FR-019); templates lose their `schedule` line (FR-018); the schema is
  re-stamped and the golden files regenerated so form, emitter, comments, and README agree.
  Dangling/invalid entries are rejected with naming messages at both the UI and the reload
  (FR-009/FR-010) so drift surfaces immediately, not hours later.

**Result**: PASS. No violations; Complexity Tracking is intentionally empty.

*Post-design re-check (after Phase 1)*: still PASS. The design adds no per-harness code
path (job vs asset routing keys off the existing `produces` check), introduces no secret to
any file or log, and leaves the launch op untouched. The one cross-boundary duplication (the
cron-validation rule in both packages) is the same deliberate, tested pattern 004 used for
the asset-key regex — see Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-automation-config/
├── plan.md                       # This file
├── research.md                   # Phase 0: decisions R1–R9
├── data-model.md                 # Phase 1: automation entry/file, trigger, on/off state
├── quickstart.md                 # Phase 1: end-to-end validation guide (incl. Null-Action check)
├── contracts/
│   ├── automation-format.md      # automation/ file format, merge & validation rules, migration behavior
│   ├── orchestrator-triggers.md  # how a trigger becomes a ScheduleDefinition or an on_cron condition + per-asset sensor
│   └── ui-automation.md          # /automation page, GET/PUT /api/automation, agent-form Schedule-card removal
├── checklists/
│   └── requirements.md           # From /speckit-specify
└── tasks.md                      # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
automation/
└── migrated.yaml        # NEW (created by the migration; the UI's canonical write target):
                         #   map keyed by agent name → { cron: "…" }  (on-demand agents omitted)

scripts/
└── migrate-schedules.py # NEW: strip `schedule` (+ bump schema stamp) from every agents/*.yaml;
                         #      write each non-template agent's non-empty cron into automation/migrated.yaml;
                         #      idempotent (second run is a no-op)

orchestrator/
├── factory.py           # EDIT: build_job_and_schedule → build_job (no schedule param) + a
│                        #       build_schedule(job, cron) helper naming it sched_<name> (default STOPPED;
│                        #       takes the already-built job so no duplicate agent_<name> job is created);
│                        #       build_asset gains an optional automation_condition (on_cron) + a
│                        #       build_asset_automation_sensor(cfg) → AutomationConditionSensorDefinition
│                        #       (autocond_<name>, STOPPED, targets the asset); cron-validation helper
└── definitions.py       # EDIT: load automation/*.yaml → merged {name→trigger} map; validate
                         #       (unknown agent → raise naming the entry FR-010; dup key across files →
                         #       raise naming the files FR-011; invalid cron → raise); route each agent's
                         #       cron to a schedule (job) or an on_cron condition + sensor (asset); warn on a
                         #       stray `schedule` key; Definitions(jobs=, schedules=, assets=, sensors=)

docker-compose.yml       # EDIT: mount ./automation into dagster-webserver + dagster-daemon (ro) and
                         #       into ui (rw); add AUTOMATION_DIR env for the UI

agents/
├── _template-claude-code.yaml   # EDIT: remove the schedule line (FR-018)
├── _template-pi.yaml            # EDIT: same
├── _template-codex.yaml         # EDIT: same
├── _template-api.yaml           # EDIT: same
└── _template-repo-librarian.yaml# EDIT: same

ui/
├── schema.py            # EDIT: remove the `schedule` FIELD and rehome `enabled` (rename the
│                        #       "schedule" SECTION to a Runs "status" card holding only Enabled);
│                        #       drop "schedule" from ALWAYS_WRITTEN; drop the _is_unset schedule
│                        #       special-case and the schedule validation call; keep the cron-rule
│                        #       helper (reused by the Automation API); SCHEMA_VERSION 2→3 with
│                        #       migrate_2_to_3 that drops `schedule`
├── agents_store.py      # EDIT: on read, when a `schedule` key was present, log a warning naming
│                        #       the file (FR-002); emitter no longer writes schedule
├── main.py              # EDIT: add GET /automation page; GET/PUT /api/automation (read merged
│                        #       triggers per agent; validate + write migrated.yaml + reload)
├── automation_store.py  # NEW: read/merge automation/*.yaml, per-agent trigger view, validate, write
│                        #       migrated.yaml (canonical), shared cron-rule helper
├── templates/
│   ├── base.html        # EDIT: add an "Automation" nav link
│   └── automation/list.html # NEW: the Automation view shell
├── static/
│   ├── automation.js    # NEW: render the agent→trigger table, edit a trigger, save + reload
│   └── agent-form.js    # EDIT (if needed): nothing schedule-specific remains once the schema drops it
└── tests/
    ├── golden/*.yaml    # REGENERATE: schema-3 header, no schedule line
    ├── test_schema.py   # EDIT: no schedule field/section; enabled+limits under Runs; migration 2→3 drops schedule
    ├── test_agents_store.py # EDIT: emitter writes no schedule; stray-schedule read logs a file-named warning
    ├── test_api.py      # EDIT: /api/schema has no schedule; /automation renders; GET/PUT /api/automation
    └── test_automation_store.py # NEW: merge, per-agent view, validation, migrated.yaml write round-trip

scripts/
└── (see above)

README.md                # EDIT: remove the `schedule` key-table row; add an "Automation" section (FR-019)
```

**Structure Decision**: Keep the two packages separate and let each own its half, as in
004. The orchestrator owns turning a trigger into a Dagster schedule or automation
condition; the UI owns authoring (the Automation view) and pre-save validation. The
cron-validation rule is stated once per package (a small helper duplicated deliberately
across the container boundary — the two run in different containers with no shared import,
same rationale as 004's asset-key regex, R6/Complexity) and pinned by a test so the two
copies cannot drift. `automation/` is a first-class data directory alongside `agents/` and
`prompts/`, mounted read-only into the orchestrator and writable into the UI, exactly like
those.

## Complexity Tracking

No constitution violations; this section is intentionally empty. The one cross-boundary
duplication (the five-field cron-validation rule in both `orchestrator/` and the UI's
`automation_store.py`) is the same deliberate, tested choice 004 made for the asset-key
regex: the packages ship as separate containers with no shared module, so duplicating a
tiny validator is cheaper and clearer than introducing a shared package, and a test pins
both copies against the same accept/reject fixtures.
