# Implementation Plan: Explicit Asset/Job Model & Automation Shell Cleanup

**Branch**: `006-explicit-asset-job` | **Date**: 2026-09-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-explicit-asset-job/spec.md`

## Summary

Make an agent's nature explicit and operator-chosen. Today the orchestrator *infers*
the nature from the file — `produces` present ⇒ asset, otherwise ⇒ job, and the two are
mutually exclusive. This feature replaces the inference with two independent, checkbox-gated
declarations on the agent: an **asset** (the `produces:` block) and a **job** (a new `job:`
flag creating `agent_<name>`). At least one must be set. When both are set, `agent_<name>`
becomes the asset's *materializing* job (`define_asset_job`), so manual materialization, the
auto-condition, and the job schedule all feed one asset-materialization history; when only
the job is set, `agent_<name>` stays a plain op job (`build_job`, unchanged); when only the
asset is set, there is no `agent_<name>` job (manual Materialize only).

Triggering folds back **onto the agent** (undoing 005's external store). Each agent carries a
dedicated `triggers:` block with two optional crons — `asset_schedule` (drives an
`AutomationCondition.on_cron` on the asset) and `job_schedule` (drives a `ScheduleDefinition`
on `agent_<name>`). The standalone `automation/` directory, the `on_demand` keyword, and
005's `scripts/migrate-schedules.py` are retired. A new one-off
`scripts/migrate-automation-to-triggers.py` reads 005's `automation/migrated.yaml`, writes
each cron onto the correct agent's `triggers:` block (asset-mode cron → `asset_schedule`,
job-mode cron → `job_schedule`), then removes `automation/`. The orchestrator keeps **no**
legacy `automation/` load path. Schedule/sensor names stay `sched_<name>` / `autocond_<name>`
so Dagster preserves each carried-over trigger's prior on/off state across the reload
(FR-012/FR-014); new triggers stay paused-by-default (005's behavior).

The Automation page stays as the cross-agent trigger editor, now showing per agent exactly
the rows its kind entitles it to (asset-schedule, job-schedule, or both, grouped as one
unit), each editable on-demand ↔ cron independently, writing back onto the agent
definitions. Alongside it, three systemic UI fixes land: the app shell gets a truly fixed
sidebar + pinned top bar that survives phone width; every dropdown routes through the
existing shared custom-dropdown component (the Automation page's raw `<select>` is the last
hold-out); and every save/reload/error notice uses the one shared notice pattern from
`shell.js` (the Automation page's bespoke `.ax-banner` is retired), with the cron-shape
warning reserving its space so it never shifts the layout.

**Null Action (partition targeting)**: carried over verbatim from 005 research R5 —
`AutomationCondition.on_cron` on a `DailyPartitionsDefinition` targets the latest
(current-day) partition per tick, so the primary asset-schedule path materializes the right
partition. FR-015 hardens the documented fallback: when `on_cron` cannot target the correct
partition on the installed Dagster, the system falls back to a partition-filling schedule on
the asset's materializing job **and surfaces it in two places** — an orchestrator load-time
warning log and a marker on that agent's schedule row in the Automation page. A build-time
verification step (quickstart §8) gates which path ships.

## Technical Context

**Language/Version**: Python 3.12 (orchestrator `factory.py`/`definitions.py`; UI
`schema.py`/`agents_store.py`/`automation_store.py`/`main.py`/tests; the migration script).
Browser ES2020 modules (no build step) for the shell/dropdown/notice work. Same toolchain as
001–005.

**Primary Dependencies**: Dagster **1.13.21** (pinned by the orchestrator image). New/used
surface: `define_asset_job` (the both-kind materializing job — GA in 1.13),
`AssetSelection.assets`, the existing `AssetsDefinition.from_op`, `AutomationCondition.on_cron`,
`AutomationConditionSensorDefinition`, `ScheduleDefinition`, `DailyPartitionsDefinition`,
`Definitions(..., jobs=, schedules=, assets=, sensors=)`. FastAPI + Jinja + `httpx`
(reuse `ui/dagster.py:reload()`), `pyyaml`, `croniter` (UI-side cron guard, unchanged),
`pytest`/`TestClient` — all unchanged.

**Storage**: `agents/*.yaml` (single source of truth; no database) — the source of truth for
*both* an agent's nature (`produces:` block + `job:` flag) and its triggers (`triggers:`
block). The standalone `automation/` directory is **removed** by the one-off migration. Dagster
instigator (schedule/sensor on/off) state under `/data/dagster`, keyed by the unchanged
`sched_<name>` / `autocond_<name>` names.

**Testing**: `pytest` in `ui/tests/` for everything statically checkable — the schema exposes
the `job` flag and the `triggers` block; `validate` enforces at-least-one-of asset/job and
produces-required-when-asset; the emitter writes the `# --- Triggers ---` section and a `job:`
line; migration 3→4; `/api/schema` shape; the reworked Automation view markup (asset/job/both
rows, grouping, shared dropdown, shared notice, reserved warning space); `GET/PUT
/api/automation` new per-schedule shape; a `test_secret_scan`-style grep test asserting no raw
`<select>` and no `.ax-banner` save-notice remain (SC-004/SC-005). Orchestrator unit tests over
`factory`/`definitions` with a stubbed launch: asset-only → asset + no job; job-only → plain
job; both → asset + `agent_<name>` materializing job recording a materialization; `triggers`
routing (asset_schedule → on_cron+sensor, job_schedule → schedule); default-paused; no
`automation/` load path remains. A dedicated test for the new
`scripts/migrate-automation-to-triggers.py` (reads `migrated.yaml`, writes correct per-kind
key, removes `automation/`, idempotent) over a fixture repo. End-to-end firing + on/off
preservation + the partition Null-Action check are verified by the quickstart against live
Dagster (same posture as 001–005). The retired `test_migrate_schedules.py` is removed.

**Target Platform**: Docker Compose on the Raspberry Pi host (arm64, Debian/Bookworm).
Orchestrator = `dagster-webserver` + `dagster-daemon` (the daemon runs both schedules and the
automation-condition sensors); UI = the `ui` service. Dagster UI at `http://10.0.0.100:3000`.

**Project Type**: Web service (management UI) + orchestrator (Dagster code location). Two
packages, `orchestrator/` and `ui/`, plus a repo-root `scripts/` one-off. The `automation/`
data directory is retired.

**Performance Goals**: No new per-run cost. Load-time cost is reading the same handful of
agent YAML files and building one schedule/sensor per triggered agent (plus one
`define_asset_job` per both-kind agent) — negligible. The shell/notice/dropdown work is CSS +
a few lines of JS with no runtime cost.

**Constraints**:
- **Nature is explicit and at-least-one** (FR-001/FR-005): the form presents an Asset card
  and a Job card, each independently checkbox-gated; saving with neither is rejected with a
  naming message. Inference from `produces`-presence is gone.
- **Both ⇒ one materialization history** (FR-006): when both are set, `agent_<name>` is the
  asset's materializing job (`define_asset_job`), so manual/auto/scheduled runs all record
  against the same asset. Job-only stays a plain op job (FR-007); asset-only has no
  `agent_<name>` job.
- **Single launch op** (FR-008): the container launch is `make_run_op(cfg)`, shared byte-for-
  byte across asset-only, job-only, and both (004's Null-Action rule preserved).
- **Triggers only on the agent** (FR-009/FR-010): the orchestrator reads triggering **only**
  from the `triggers:` block; no `automation/` reader, no `on_demand` keyword remains
  anywhere (SC-008).
- **Lossless carry-over** (FR-011/FR-013/FR-014): every 005-scheduled agent keeps its cron on
  the right per-kind key; the set of live triggers is identical before and after.
- **On/off parity** (FR-012/FR-016): `sched_<name>` / `autocond_<name>` names are unchanged,
  so Dagster preserves each carried-over trigger's toggle; new triggers default paused;
  005's orchestrator routing and timezone handling are retained.
- **Partition Null-Action** (FR-015): `on_cron` first; documented fallback to a
  partition-filling job schedule, surfaced in the load log **and** on the Automation row.
- **Shared shell/components** (FR-021–FR-027): one fixed shell, one dropdown component, one
  notice pattern; no raw `<select>` and no bespoke save banner remain (SC-004/SC-005); the
  fixed shell holds at phone width without overlap (SC-006); cron-warning space is reserved
  (SC-007).

**Scale/Scope**: ~13 non-template agent files today; exactly two carry a 005 cron in
`automation/migrated.yaml` — `categorize-commits` (`30 2 * * *`, job-mode, `enabled: false`)
and `list-commits-pi-kimi` (`20 17 * * *`, **asset-mode**, `produces: repo-review/list-commits`,
`partition: daily`). So the carry-over exercises **both** target keys: `categorize-commits`'s
cron → `job_schedule`, `list-commits-pi-kimi`'s cron → `asset_schedule` (an `on_cron` on a
daily-partitioned asset — the exact Null-Action path). Feature touches: `orchestrator/factory.py`,
`orchestrator/definitions.py`, `docker-compose.yml` (drop the `automation/` mounts + env),
`ui/schema.py`, `ui/agents_store.py`, `ui/automation_store.py`, `ui/main.py`, the agent-form JS,
`automation.js`, `dropdown.js` (reuse), `shell.js` (reuse), `app.css`, `base.html`,
`automation/list.html`, `agents/form.html`, the golden files, the two scheduled agent files,
the five templates, `README.md`, `CLAUDE.local.md` (the debugging notes reference `automation/`),
the new `scripts/migrate-automation-to-triggers.py`, and tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Respected. This feature changes *how an agent's nature and
  triggers are declared and wired*, not what a container may do. `make_run_op` — the launch —
  is untouched; no new interface is granted to any agent.
- **II. Configuration over Code** — Central and reinforced. An agent's nature (asset/job/both)
  and its triggers are now both pure config on the agent file, discovered automatically at
  reload with no orchestrator code change (SC-002). Folding triggering back onto the agent
  restores "one auditable place" for everything about an agent.
- **III. Secrets Never in the Open** — Respected. The `triggers:` block holds only cron
  strings; no secret, command line, or credential is touched. The migration moves cron
  strings only.
- **IV. Uniform Interface, Diverse Runtimes** — Respected. The asset/job flags and the
  `triggers` vocabulary are harness-agnostic and identical across claude-code/pi/api/codex;
  adding a runtime does not touch them.
- **V. Ephemeral Runs, Immutable Outputs** — Unaffected. No change to how runs produce or
  store output; the both-kind materializing job records against the same asset the op already
  produced.
- **VI. Docs Track Reality** — Served. Schema re-stamped 3→4 and golden files regenerated;
  templates gain the `triggers` block and lose any `automation` mention; README's key table
  and Automation section are rewritten; `CLAUDE.local.md` debugging notes that reference
  `automation/` are corrected; the retired `automation/`, `on_demand`, and
  `migrate-schedules.py` leave the tree entirely (SC-008). Dangling/invalid triggers are
  rejected with naming messages at both the UI and the reload, so drift surfaces immediately.

**Result**: PASS. No violations; Complexity Tracking documents the two deliberate,
already-established cross-container duplications.

*Post-design re-check (after Phase 1)*: still PASS. The design adds no per-harness code path
(asset/job/both routing keys off the two explicit flags), introduces no secret to any file or
log, and leaves the launch op byte-for-byte unchanged. The both-kind path composes existing
Dagster primitives (`from_op` + `define_asset_job`) rather than re-implementing the launch.
The two cross-boundary duplications (the asset-key regex and the five-field cron rule, each
stated once per package and pinned by a shared-fixture test) are unchanged from 004/005 — see
Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/006-explicit-asset-job/
├── plan.md                        # This file
├── research.md                    # Phase 0: decisions R1–R12
├── data-model.md                  # Phase 1: agent nature (asset/job flags), triggers block, trigger entities
├── quickstart.md                  # Phase 1: end-to-end validation (incl. carry-over parity + Null-Action check)
├── contracts/
│   ├── agent-model.md             # agent YAML: asset flag, job flag, triggers block; validation; schema v4 + migration; emitter
│   ├── orchestrator-model.md      # asset/job/both → Dagster defs; triggers → schedule/on_cron+sensor; partition fallback; carry-over + legacy removal
│   └── ui-automation-and-shell.md # Automation page rows/grouping + GET/PUT /api/automation; shared dropdown; shared notice; fixed responsive shell
├── checklists/
│   └── requirements.md            # From /speckit-specify
└── tasks.md                       # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
scripts/
├── migrate-automation-to-triggers.py  # NEW one-off: read automation/migrated.yaml → write asset_schedule/
│                                       #   job_schedule onto each agent's `triggers:` block by kind; then
│                                       #   remove automation/; bump schema stamp 3→4; idempotent
└── migrate-schedules.py               # DELETE (005's one-off; superseded)

orchestrator/
├── factory.py            # EDIT: build_asset unchanged (from_op + on_cron); build_job unchanged (plain op job);
│                         #       NEW build_materializing_job(cfg, asset_def) → define_asset_job(agent_<name>,
│                         #       AssetSelection.assets(asset_def)); build_schedule works against either job
│                         #       object; keep is_valid_cron / cron_timezone / asset-key helpers
└── definitions.py        # EDIT: read nature from flags (produces ⇒ asset, job: true ⇒ job) not
                          #       produces-presence; route asset-only / job-only / both; read triggers from
                          #       cfg["triggers"] (asset_schedule/job_schedule); DROP load_automation,
                          #       AUTOMATION_GLOB, RejectAutomation, on_demand; keep RejectAgent skip-one-file;
                          #       partition Null-Action fallback + warning log (FR-015)

docker-compose.yml        # EDIT: remove the ./automation mounts (webserver, daemon, ui) and AUTOMATION_DIR env

agents/
├── categorize-commits.yaml     # EDIT (by migration): + triggers: { job_schedule: "30 2 * * *" }, + job: true, schema 4
├── list-commits-pi-kimi.yaml   # EDIT (by migration): + triggers: { asset_schedule: "20 17 * * *" }, schema 4
├── _template-claude-code.yaml  # EDIT: + `# --- Triggers ---` block + `job:` flag; drop any automation note
├── _template-pi.yaml           # EDIT: same
├── _template-codex.yaml        # EDIT: same
├── _template-api.yaml          # EDIT: same
└── _template-repo-librarian.yaml # EDIT: same

automation/               # DELETE the whole directory (migrated.yaml, .gitkeep) — retired (FR-010)

ui/
├── schema.py             # EDIT: + `job` bool field (Job group) and `asset_schedule`/`job_schedule` cron
│                         #       fields in a `triggers` block; ALWAYS_WRITTEN unchanged; SCHEMA_VERSION 3→4
│                         #       with migrate_3_to_4 (infer job:true when no produces; leave triggers empty —
│                         #       the script fills them); validate: at-least-one-of asset/job, produces
│                         #       required when asset, cron shape on triggers
├── agents_store.py       # EDIT: lift/emit the `triggers` block (like `produces`); emit the `job:` line and
│                         #       the `# --- Triggers ---` section
├── automation_store.py   # EDIT: per_agent_view reads triggers off each agent (asset_schedule/job_schedule)
│                         #       and reports per-kind rows; validate + write now edit agents/*.yaml via
│                         #       agents_store (not automation/); drop the migrated.yaml writer; keep the cron rule
├── main.py               # EDIT: GET /api/automation returns per-schedule rows; PUT writes triggers onto
│                         #       agent files + reload; notice payloads unchanged (client uses shared pattern)
├── static/
│   ├── automation.js     # EDIT: render asset/job/both rows grouped per agent; enhance every row <select>
│   │                     #       via dropdown.enhanceSelects; replace .ax-banner with shell.showStatus;
│   │                     #       reserve cron-warning space; partition-fallback marker on a row
│   ├── agent-form.js     # EDIT: render the Asset card + Job card with independent checkboxes and the two
│   │                     #       schedule fields; at-least-one-of client hint (server is authority)
│   ├── dropdown.js       # REUSE (no change): enhanceSelects is the one dropdown component
│   ├── shell.js          # REUSE (no change): showStatus/flashStatus is the one notice pattern
│   └── app.css           # EDIT: fixed sidebar + pinned top bar (ax-app height:100dvh; sidebar own scroll;
│                         #       sticky topbar; ax-content the scroller) + a phone-width shell rule; reserved
│                         #       cron-warning min-height; asset/job card + grouped-row styles
├── templates/
│   ├── base.html         # EDIT: shell markup tweaks for the fixed layout (no structural nav change)
│   ├── automation/list.html # EDIT: drop the bespoke #ax-automation-banner; container for grouped rows
│   └── agents/form.html  # EDIT (if needed): the two cards are rendered by agent-form.js into existing mounts
└── tests/
    ├── golden/*.yaml     # REGENERATE: schema-4 header, `job:` line, `# --- Triggers ---` block
    ├── test_schema.py    # EDIT: job field + triggers fields; migration 3→4; at-least-one-of + produces-required
    ├── test_agents_store.py # EDIT: emitter writes job + triggers; reader lifts triggers; round-trip
    ├── test_automation_store.py # EDIT: per-agent view yields per-kind rows off triggers; write edits agents/*.yaml
    ├── test_api.py       # EDIT: /api/schema has job+triggers; Automation renders grouped rows; GET/PUT round-trip
    ├── test_migrate_automation.py # NEW: replaces test_migrate_schedules.py (strip automation/, write triggers, idempotent)
    ├── test_migrate_schedules.py  # DELETE
    └── test_ui_consistency.py     # NEW (or fold into test_api): grep — no raw <select>, no .ax-banner save-notice (SC-004/SC-005)

README.md                 # EDIT: replace the Automation/`automation/` section with the per-agent triggers model;
                          #       document asset/job/both and the `triggers:` block; key-table rows
CLAUDE.local.md           # EDIT: the debugging notes reference automation/ — correct to the triggers model
```

**Structure Decision**: Keep the two packages separate, each owning its half, exactly as
004/005. The orchestrator owns turning nature + triggers into Dagster definitions (asset,
job, materializing job, schedule, on_cron condition + sensor); the UI owns authoring (the form
cards and the Automation page) and pre-save validation. The two cross-boundary rules — the
asset-key regex and the five-field cron rule — stay stated once per package and pinned by
shared-fixture tests (Complexity Tracking). The retired `automation/` data directory leaves
the tree; triggers rejoin `agents/*.yaml`, which the UI already mounts writable, so no new
mount is introduced.

## Complexity Tracking

No constitution violations. Two deliberate cross-boundary duplications continue unchanged from
004/005, each stated once per package (the two ship as separate containers with no shared
import) and pinned to its twin by a shared-fixture test:

| Duplication | Why Needed | Simpler Alternative Rejected Because |
|-------------|------------|--------------------------------------|
| Asset-key regex in `orchestrator/factory.py` and `ui/schema.py` | Both containers must accept/reject the same asset keys with no shared module | A shared package across two independently-built images is more machinery than a one-line regex + a pinning test |
| Five-field cron rule in `orchestrator/factory.py` and `ui/automation_store.py` | Orchestrator is the structural backstop (no `croniter`); the UI is the stricter authoring guard (`croniter.is_valid`) | Same as above — a tiny validator duplicated + tested is cheaper and clearer than a shared dependency |
