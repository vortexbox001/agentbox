# Implementation Plan: Event-Driven Triggers — Asset Dependency Graph

**Branch**: `013-event-driven-triggers` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-event-driven-triggers/spec.md`

## Summary

Turn Agentbox's implicit "watch a folder" arrangement into an explicit, declared dependency
graph. An asset agent gains `produces.depends_on:` — a list of upstream asset keys — and two new
asset-kind triggers, `triggers.on_upstream: true` and `triggers.on_missing: true`, both living
behind the one paused `autocond_<name>` sensor that already toggles `asset_schedule` (spec 006).
`on_upstream` materializes the downstream when any declared upstream materializes and passes its
**blocking** checks (spec 008); `on_missing` materializes the current/latest expected partition
when it has never been produced. Partitioned upstream/downstream map one-to-one by kind (daily →
daily, identity `TimeWindowPartitionMapping`).

When a downstream fires, its container is handed what changed: at launch, for **each** declared
upstream it receives an env var `AGENTBOX_UPSTREAM_<KEY>` (the asset key upper-snaked) pointing at
a **read-only** JSON file listing that upstream's latest matching-partition materialization —
output paths, report metadata, and materialization time — or a file with null/empty fields when
that upstream has no matching-partition materialization (FR-012a). The file is built from the
upstream's latest materialization event read off the Dagster instance and mounted `:ro`.

Two instance-level governors in `config/settings.yaml` bound automated chaining:
`max_runs_per_hour` (default 12, a rolling 60-minute window) and `max_chain_depth` (default 5).
Every automated run carries a `chain_depth` — a root automated run is depth 1, each downstream is
its automated upstream's depth + 1 — computed from the upstream materializations' recorded depth
(no Dagster launch-tag injection needed, since automation-condition runs are Dagster-managed). A
run that would breach either limit is refused, logged to the daemon log, and skipped without
consuming a per-hour slot; manual runs bypass both. Both governors are editable on the Settings
page (a new card beside Retention) and persist to `settings.yaml`, which the orchestrator reads
directly (the same file the prune job's retention block already uses).

`depends_on` is validated at load: an entry naming a non-existent asset key is rejected naming the
key; a cycle (direct or transitive) is rejected naming the assets in it. Consistent with the
established resilient loader (spec 006 FR-010), rejection **skips the offending assets** (and any
that transitively depend on them) with a named daemon-log message while every unrelated agent
still loads — reconciling US4's "reload fails … naming the assets" with the one-bad-file-costs-
only-itself invariant; the form's pre-save validation additionally blocks authoring a cycle or a
dangling reference so the operator is told immediately.

**Decisions taken unattended** (recorded in [research.md](research.md); no human was available to
clarify): `on_upstream` wiring uses Dagster deps + `AutomationCondition.any_deps_updated()`
(R1); partitioned `on_upstream` uses the daily→daily identity mapping with a documented fallback
to unpartitioned-only surfaced in a load warning + README (R2); `on_missing` uses
`missing() & in_latest_time_window()` (R3); cycle/dangling rejection follows the skip-and-log
loader rather than aborting the whole code location (R5); `chain_depth` is derived from upstream
materialization metadata rather than injected tags (R7).

## Technical Context

**Language/Version**: Python 3.12 — orchestrator (`factory.py`, `definitions.py`, a new
`governors.py` reader) and UI (`schema.py`, `agents_store.py`, `settings_store.py`, `main.py`,
tests). Browser ES2020 modules (no build step) for the form's Depends-on card, the two new
trigger toggles, and the Settings governors card. Same toolchain as 004–012.

**Primary Dependencies**: Dagster **1.13.21** (pinned by the orchestrator image). New surface
used: `AutomationCondition.any_deps_updated`, `AutomationCondition.missing`,
`AutomationCondition.in_latest_time_window`, `AutomationCondition.in_progress`, condition
composition (`|`, `&`, `~`); asset `deps` (via `AssetsDefinition.from_op(..., deps=…)` and
`AssetSpec(deps=…)` on the checked-asset path); `TimeWindowPartitionMapping` (identity daily→daily);
`context.instance.get_latest_materialization_event` / `get_event_records` +
`context.instance.add_run_tags` / `get_run_records` for the handoff query and the rolling-window
count. Existing: `AutomationCondition.on_cron`, `AutomationConditionSensorDefinition`,
`AssetsDefinition.from_op`, `define_asset_job`, `DailyPartitionsDefinition`, Dagster Pipes.
FastAPI + Jinja + `httpx` (reuse `ui/dagster.py:reload()`), `pyyaml`, `croniter`,
`pytest`/`TestClient` — all unchanged.

**Storage**: `agents/*.yaml` (single source of truth; no database) holds `produces.depends_on`
and the two new `triggers` flags. `config/settings.yaml` gains a `governors:` block
(`max_runs_per_hour`, `max_chain_depth`), written by the UI and read by the orchestrator — the
same file that already carries `retention:`. Dagster instigator (sensor on/off) state under
`$DAGSTER_HOME`, keyed by the unchanged `autocond_<name>` name so on_upstream/on_missing inherit
the asset's existing sensor toggle. Per-run upstream handoff JSON files live in an ephemeral
per-run dir under `$AGENTBOX_DATA` (host==container mount), mounted read-only at `/upstreams` and
`--rm`-cleaned like the pipes/staging dirs.

**Testing**: `pytest` in `ui/tests/` for everything statically checkable — schema exposes
`depends_on` (list, under `produces`) and `on_upstream`/`on_missing` (bools, under `triggers`);
`validate` enforces `depends_on` entries match the asset-key regex and the two trigger flags
apply only to assets; the emitter writes `depends_on` under `produces:` and the two flags under
`triggers:`; migration 6→7; `/api/schema` shape; the form's Depends-on card and the two trigger
toggles render; `settings_store` governor read/validate/write + the `POST /api/settings/governors`
round-trip and its 400s; a parity test pinning the governor defaults (12/5) between UI and
orchestrator. Orchestrator unit tests over `factory`/`definitions` with a stubbed launch and a
`DagsterInstance.ephemeral()`: `depends_on` → asset `deps`; the OR-composed automation condition
per trigger set behind one `autocond_<name>` sensor; cycle + dangling-key rejection (naming the
assets/keys, cascade to dependents, unrelated agents still load); the handoff builder (env-var
naming, matching-partition selection, latest-of-many, the null/empty "no materialization" file,
`:ro` mount); `chain_depth` derivation (root=1, upstream automated depth+1, manual upstream ⇒ 1);
governor enforcement (per-hour rolling window refusal, depth refusal, refused run leaves the
partition unmaterialized and does not consume a slot, manual bypass). End-to-end firing, handoff
read-back, blocking-check gating, and the partitioned-`on_upstream` build-time check are verified
by the quickstart against live Dagster (same posture as 006/008/012).

**Target Platform**: Docker Compose on the Raspberry Pi host (arm64, Debian/Bookworm).
Orchestrator = `dagster-webserver` + `dagster-daemon` (the daemon runs the automation-condition
sensors); UI = the `ui` service. Dagster UI at `http://10.0.0.100:3000`.

**Project Type**: Web service (management UI) + orchestrator (Dagster code location). Two
packages, `orchestrator/` and `ui/`. No new data directory; the handoff dir reuses the existing
`$AGENTBOX_DATA` host==container mount.

**Performance Goals**: No new per-run compute. Load-time cost adds a graph build + cycle check
over ~13 agent files (linear) and one OR-composed automation condition per triggered asset —
negligible. Per automated launch: one latest-materialization query per declared upstream (small,
indexed by Dagster) to build handoff files + derive `chain_depth`, and one bounded
`get_run_records` count for the rolling window. All on the order of milliseconds.

**Constraints**:
- **Explicit graph, not folder-watching** (FR-001): `produces.depends_on` is the only dependency
  declaration; there is no change-watching path anywhere.
- **One sensor for all asset-kind triggers** (FR-005/FR-009/FR-010): `on_upstream`, `on_missing`,
  and the existing `asset_schedule` OR-compose into one `AutomationCondition` on the asset toggled
  by the single paused `autocond_<name>` sensor; new triggers start paused.
- **Blocking-check gating** (FR-006): a downstream does not fire on an upstream materialization
  whose blocking check failed — enforced by Dagster's dep-update semantics (a failed blocking
  check fails the upstream step, so no successful materialization greens the partition; the
  orchestrator already records such a run as an AssetObservation, not a materialization).
- **Daily→daily identity mapping** (FR-007): partitioned upstream/downstream map one-to-one by
  the same kind; non-identity mappings are out of scope. Fallback: if the mapping proves
  unreliable on the installed Dagster, `on_upstream` is restricted to unpartitioned assets and the
  restriction is logged + stated in the README (spec Assumptions / R2).
- **on_missing is latest-partition only** (FR-008): `missing() & in_latest_time_window()` — today
  for daily, the single partition when unpartitioned; never backfills history; never re-fires once
  the partition exists.
- **Read-only handoff, one var per upstream** (FR-011/FR-012/FR-012a/FR-013): every declared
  upstream yields exactly one `AGENTBOX_UPSTREAM_<KEY>` env var pointing at a `:ro` JSON file;
  latest matching-partition materialization or an explicit null/empty "no materialization" file.
- **Governors bound automation only** (FR-014/FR-016/FR-017): `max_runs_per_hour` (rolling 60 min)
  and `max_chain_depth` refuse-log-skip an automated run; only launched runs count toward the
  window; manual runs bypass both.
- **chain_depth on every automated run** (FR-015): root = 1; each downstream = its automated
  upstream's depth + 1; a manual upstream contributes 0.
- **Settings persist + editable** (FR-018): both governors edit on the Settings page and persist
  to `config/settings.yaml`, read by the orchestrator on reload.
- **Load-time safety** (FR-002/FR-003): dangling `depends_on` and cycles are rejected at load with
  the offending keys/assets named, before any automation runs.
- **Docs track reality** (FR-021): the README documents `depends_on`, the two triggers, the
  handoff env var + file, and the two governors; schema re-stamped 6→7 with golden files
  regenerated; agent templates gain the new commented fields.

**Scale/Scope**: ~13 non-template agent files; the graph and cycle check are trivial at this size.
Feature touches: `orchestrator/factory.py`, `orchestrator/definitions.py`, a new
`orchestrator/governors.py`, `ui/schema.py`, `ui/agents_store.py`, `ui/settings_store.py`,
`ui/main.py`, `ui/static/agent-form.js`, `ui/static/settings.js`, `ui/templates/agents/form.html`,
`ui/templates/agents/list.html`, `ui/templates/settings/page.html`, the golden files, the agent
templates, `README.md`, and tests in both packages. No compose change (the handoff dir reuses the
existing `$AGENTBOX_DATA` mount).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Respected and reinforced. The upstream handoff is mounted **read-only**
  (`:ro`), so a downstream can read what an upstream produced but cannot modify it (FR-013,
  Constitution V). No new network reach or credential is granted; the handoff carries only paths
  and report metadata the run already recorded. The launch op (`make_run_op`) is otherwise
  unchanged; governors only ever *reduce* how much runs.
- **II. Configuration over Code** — Central. `depends_on`, `on_upstream`, `on_missing`, and both
  governors are pure declarative config (agent YAML + `settings.yaml`), discovered at reload with
  no orchestrator code change per agent (SC-001). The dependency graph is auditable in the agent
  files.
- **III. Secrets Never in the Open** — Respected. `depends_on`, the trigger flags, and the
  governors hold no secrets; the handoff file lists output paths + report metadata (already
  redacted at capture, spec 012), never credentials. No secret reaches a command line or log.
- **IV. Uniform Interface, Diverse Runtimes** — Respected. `depends_on`, the triggers, the
  `AGENTBOX_UPSTREAM_<KEY>` handoff convention, and the governors are harness-agnostic and
  identical across claude-code/pi/api/codex; adding a runtime touches none of them.
- **V. Ephemeral Runs, Immutable Outputs** — Reinforced. The handoff is the *only* way a
  downstream reads a prior run's output, and it is read-only (FR-013) — exactly the "agents never
  read or modify prior runs' output except through an explicit handoff" rule. Each run still
  produces its own uniquely identified output.
- **VI. Docs Track Reality** — Served. README gains `depends_on`, the two triggers, the handoff
  env var/file, and the governors; schema re-stamped 6→7 + golden files regenerated; the partition
  fallback and cycle/dangling rejection are surfaced in the daemon log for the headless operator.
- **VII. One Design System** — Served. The Depends-on card, the two trigger toggles, and the
  Settings governors card are composed from the shared Jinja macros (`toggle`, `text_input`,
  `card`, `button`) and design-system tokens — no literal colours/px, no inline styles, no raw
  `<select>` (per the agentbox-design skill).

**Result**: PASS. No violations. The cross-container duplications (asset-key regex; five-field
cron rule; governor defaults 12/5; run-directory/handoff filename constants) each stay stated once
per package and are pinned by shared-fixture parity tests — see Complexity Tracking.

*Post-design re-check (after Phase 1)*: still PASS. The design adds no per-harness code path (the
handoff and triggers are one shared mechanism), introduces no secret to any file or log, mounts
the handoff read-only, and leaves the container launch byte-for-byte unchanged apart from the
added `:ro /upstreams` mount and the `AGENTBOX_UPSTREAM_<KEY>` env vars. `on_upstream`/`on_missing`
compose existing Dagster automation-condition primitives rather than re-implementing scheduling.

## Project Structure

### Documentation (this feature)

```text
specs/013-event-driven-triggers/
├── plan.md                         # This file
├── research.md                     # Phase 0: decisions R1–R10
├── data-model.md                   # Phase 1: depends_on, the two triggers, handoff record,
│                                    #   governors, chain_depth, the dependency graph
├── quickstart.md                   # Phase 1: end-to-end validation (firing, handoff, blocking-
│                                    #   check gating, cycle rejection, governors, partition check)
├── contracts/
│   ├── agent-model.md              # agent YAML: depends_on + on_upstream/on_missing; validation;
│   │                               #   schema v7 + migration 6→7; emitter
│   ├── orchestrator-model.md       # depends_on → deps; triggers → composed AutomationCondition;
│   │                               #   handoff builder; chain_depth; governors; cycle/dangling load
│   ├── ui-settings-and-form.md     # Depends-on card + trigger toggles; Settings governors card;
│   │                               #   GET/POST /api/settings/governors
│   └── upstream-handoff.schema.json # the AGENTBOX_UPSTREAM_<KEY> JSON file shape
├── checklists/
│   └── requirements.md             # From /speckit-specify (already present)
└── tasks.md                        # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
orchestrator/
├── factory.py            # EDIT: build_asset / _build_checked_asset accept depends_on → asset deps
│                         #       (from_op deps= / AssetSpec deps=) with daily→daily identity
│                         #       partition mapping; NEW compose_automation_condition(cfg) OR-joins
│                         #       on_cron / any_deps_updated / (missing & in_latest_time_window)
│                         #       & ~in_progress; build_asset_automation_sensor built whenever ANY
│                         #       asset-kind trigger exists; NEW _upstream_handoff(cfg, context)
│                         #       writes one :ro JSON per upstream + returns {env, mount}; wire the
│                         #       vars/mount into _build_agent_cmd + _launch_env_names/_launch_mounts;
│                         #       NEW governor gate + chain_depth derivation at op start (both op
│                         #       bodies); record chain_depth + automated flag in build_metadata
├── definitions.py        # EDIT: read produces.depends_on; build the asset-key→file graph over all
│                         #       pending_assets; reject dangling refs (name the key) and cycles
│                         #       (name the assets), cascade to dependents, log + skip, others load;
│                         #       pass depends_on into build_asset; create the sensor for any asset
│                         #       with any asset-kind trigger
├── governors.py          # NEW: load_governors() reads config/settings.yaml governors block with
│                         #       defaults (max_runs_per_hour=12, max_chain_depth=5); the twin of
│                         #       ui/settings_store governor defaults (parity test)
└── tests/
    ├── test_factory.py       # EDIT/NEW: deps, composed condition, handoff builder, chain_depth,
    │                         #   governor refusal, sensor-for-any-trigger
    ├── test_definitions.py   # EDIT: cycle + dangling rejection, cascade, resilience
    ├── test_governors.py     # NEW: settings read + defaults
    └── test_paths_parity.py  # EDIT: pin governor defaults + handoff filename twin

ui/
├── schema.py             # EDIT: + depends_on (list, block="produces", ASSET_KEY_RE per item) and
│                         #       on_upstream/on_missing (bool, block="triggers"); validate deps
│                         #       keys + trigger-applies-only-to-asset; SCHEMA_VERSION 6→7 with
│                         #       migrate_6_to_7 (identity — additive); to_public unchanged in shape
├── agents_store.py       # EDIT: lift/emit produces.depends_on and triggers.on_upstream/on_missing
├── settings_store.py     # EDIT: + read_governors / validate_governors / write_governors
│                         #       (preserve other keys), DEFAULT_GOVERNORS = {12, 5}
├── main.py               # EDIT: + GET (in /settings page context) and POST /api/settings/governors
│                         #       (validate → persist → 400 on bad); Settings page passes governors
├── static/
│   ├── agent-form.js     # EDIT: add "depends_on" + "on_upstream"/"on_missing" to the asset card
│   │                     #       grid; render depends_on as a list control; toggles for the two
│   │                     #       triggers; collect()/omit rules mirror asset-card gating
│   ├── settings.js       # EDIT: init the governors card (two number inputs, save via fetch,
│   │                     #       shared status)
│   ├── agents-list.js    # EDIT (if needed): recognize the two new trigger kinds for the
│   │                     #       schedules/sensors column narrowing
│   └── app.css           # EDIT (if needed): governors card / depends-on list layout via tokens
├── templates/
│   ├── agents/form.html  # EDIT: the Depends-on fields render into the asset card (JS-driven);
│   │                     #       no structural change beyond the mount
│   ├── agents/list.html  # EDIT: schedule/sensor column shows on_upstream/on_missing pills
│   └── settings/page.html# EDIT: + a governors card (shared macros) beside the retention card
└── tests/
    ├── test_schema.py        # EDIT: depends_on + two triggers; migration 6→7; validation
    ├── test_agents_store.py  # EDIT: emit/lift depends_on + the two flags; round-trip
    ├── test_settings.py      # EDIT: governor read/validate/write + API round-trip + 400s
    ├── test_api.py           # EDIT: /api/schema shape; form renders card + toggles; governors API
    ├── test_conformance.py   # EDIT (if needed): golden coverage of the new fields
    └── golden/*.yaml         # REGENERATE: schema-7 header + the new commented fields

examples/config/               # EDIT: agents/_template-*.yaml gain commented `depends_on:` under
                              #   produces and `on_upstream:`/`on_missing:` under triggers (the
                              #   seeded templates; real agents live under $AGENTBOX_CONFIG at
                              #   runtime); settings.yaml gains a commented `governors:` block
                              #   documenting the two limits + defaults

README.md                     # EDIT: document depends_on, on_upstream/on_missing, the handoff env
                              #   var + file, the two governors, and the partition fallback
```

**Structure Decision**: Keep the two packages separate, each owning its half, exactly as 004–012.
The orchestrator owns turning `depends_on` + the triggers into Dagster deps and a composed
automation condition, building the read-only handoff, deriving `chain_depth`, and enforcing the
governors read from `settings.yaml`. The UI owns authoring (the Depends-on card, the two trigger
toggles, the Settings governors card) and pre-save validation. The cross-boundary rules stay
stated once per package (asset-key regex, five-field cron, governor defaults 12/5, handoff/run-dir
filename constants) and are pinned by shared-fixture parity tests (Complexity Tracking). No new
data directory: the per-run handoff dir reuses the existing `$AGENTBOX_DATA` host==container mount,
the same boundary the pipes/staging dirs already rely on.

## Complexity Tracking

No constitution violations. The deliberate cross-boundary duplications continue the 004–012
discipline — each stated once per package (the two ship as separate images with no shared import)
and pinned to its twin by a shared-fixture parity test:

| Duplication | Why Needed | Simpler Alternative Rejected Because |
|-------------|------------|--------------------------------------|
| Asset-key regex in `orchestrator/factory.py` and `ui/schema.py` (now also validating each `depends_on` entry) | Both containers must accept/reject the same asset keys with no shared module | A shared package across two independently-built images is more machinery than a one-line regex + a pinning test |
| Five-field cron rule in `orchestrator/factory.py` and `ui/schema.py` | Unchanged from 006; the two triggers add no cron of their own | — |
| Governor defaults (`max_runs_per_hour=12`, `max_chain_depth=5`) in `orchestrator/governors.py` and `ui/settings_store.py` | The orchestrator enforces from `settings.yaml`; the UI authors/validates it — each needs the same fallback when the file omits the block | A shared module across two images is heavier than two constants pinned by a parity test; the *file* is the single source of the live value, only the default is duplicated |
| Handoff filename/env-var convention in `orchestrator/factory.py` (writer) mirrored by the README/docs | The container consumes `AGENTBOX_UPSTREAM_<KEY>`; the convention must be documented verbatim where authors read it | The convention is a one-line transform; pinning it by a test + documenting it once is cheaper than a shared config surface |
