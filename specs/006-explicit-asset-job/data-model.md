# Phase 1 Data Model: Explicit Asset/Job Model & Automation Shell Cleanup

There is no database. `agents/*.yaml` + `ui/schema.py` *is* the data model (research R11 of
004). This document describes the entities this feature adds or changes and their rules.

---

## Entity: Agent definition (changed)

The single declarative description of an agent (`agents/<name>.yaml`). It now carries its
nature **explicitly** and its triggers **on itself**.

| Aspect | Representation | Rules |
|--------|----------------|-------|
| Identity | `name` (kebab-case) | Unchanged. Becomes `agent_<name>` (hyphens→underscores) where a job exists. |
| **Asset flag** | presence of a valid `produces:` block | On ⇒ the agent is a tracked Dagster asset. Off ⇒ no asset. Toggled by the form's "make agent an asset" checkbox. |
| Asset identity | `produces.asset` (key), `produces.partition` (`none`\|`daily`) | Unchanged from 004. `asset` mandatory when the asset flag is on (FR-002). `produces:` stays purely about asset identity — no schedule inside it. |
| **Job flag** | `job: true \| false` (new top-level bool) | On ⇒ a Dagster job `agent_<name>` exists. Off ⇒ no job. Toggled by the form's "create agent job" checkbox. |
| **Triggers** | `triggers:` block (new) with `asset_schedule`, `job_schedule` | Both optional crons; blank/absent = no trigger of that kind. See *Triggers block* below. |
| Schema stamp | `# agentbox-schema: 4` | Bumped this feature; `migrate_3_to_4` on read (R11). |
| Everything else | prompt, dirs, env, tools, harness/model, container | Unchanged from 003/004. |

### Nature invariant (FR-005)

At least one of {asset flag, job flag} MUST be true. Saving with neither is rejected with:
"the agent must be an asset, a job, or both."

### The three kinds

| Kind | asset flag | job flag | Dagster result |
|------|:---------:|:--------:|----------------|
| **Asset-only** | ✓ | ✗ | `AssetsDefinition` only; runs via Materialize; **no** `agent_<name>` job (R2) — unless the FR-015 partition fallback applies, which adds a materializing job. |
| **Job-only** | ✗ | ✓ | Plain op `@job` `agent_<name>` (R3); no asset materialization. |
| **Both** | ✓ | ✓ | `AssetsDefinition` **plus** `agent_<name>` = its materializing job via `define_asset_job` (R1); one unified materialization history. |

---

## Entity: Triggers block (new)

A dedicated nested mapping on the agent, its own `# --- Triggers ---` section:

```yaml
# --- Triggers ---
triggers:
  asset_schedule: "20 17 * * *"   # optional
  job_schedule: "30 2 * * *"      # optional
```

| Field | Type | Applies when | Meaning | Rules |
|-------|------|--------------|---------|-------|
| `asset_schedule` | cron (5 fields) | asset flag on | Drives `AutomationCondition.on_cron` on the asset (+ paused per-asset sensor `autocond_<name>`) | Blank/absent = no auto-condition. Five fields, no `@`-macros. Ignored/invalid if the agent is not an asset. |
| `job_schedule` | cron (5 fields) | job flag on | Drives a `ScheduleDefinition` (`sched_<name>`) on `agent_<name>` | Blank/absent = manual/launchable only. Five fields, no `@`-macros. Ignored/invalid if the agent has no job. |

**Schema modeling**: two `SchemaField`s of `type="cron"` with `block="triggers"`, mirroring how
`asset`/`partition` use `block="produces"`. `agents_store` lifts the block into flat
`asset_schedule`/`job_schedule` fields on read and re-nests on emit (same lift/nest machinery as
`produces`).

**On/off state**: each live trigger carries a paused/running state held by Dagster, keyed by the
instigator name (`sched_<name>` / `autocond_<name>`). Names are unchanged from 005, so a
carried-over trigger keeps its prior state; a brand-new trigger starts paused (R6).

**Partition fallback flag** (derived, not stored): when an asset's `asset_schedule` cannot use
`on_cron` for its partition, the orchestrator falls back to a job schedule and marks it — a
load-log line plus a `fallback` field on the Automation row (R5/FR-015). Not persisted in the
YAML; it is a runtime property of the wiring.

---

## Entity: Agent job `agent_<name>` (clarified)

A job the operator can launch by hand or on a schedule. Two forms:

- **Plain op job** (job-only agent): `build_job(cfg)` — a `@job` wrapping `make_run_op(cfg)`.
  Runs record no asset materialization.
- **Materializing job** (both-kind agent): `define_asset_job("agent_<name>", AssetSelection.assets(asset_def))`.
  Runs record a materialization of the agent's asset.

Asset-only agents have **no** `agent_<name>` job — *except* when the FR-015 partition fallback is taken, which introduces a materializing `agent_<name>` job solely to carry the partition-filling schedule.

---

## Entity: Automation page row (changed)

One agent may now contribute **one or two** rows (previously exactly one), grouped as a unit:

| Field | Source | Notes |
|-------|--------|-------|
| `name`, `harness`, `enabled` | agent file | Unchanged. |
| `kinds` | asset flag / job flag | `["asset"]`, `["job"]`, or `["asset","job"]` — decides which schedule rows appear (FR-017). |
| `asset_schedule` row | `triggers.asset_schedule` | Present iff asset flag on. Editable on-demand ↔ cron (FR-018). |
| `job_schedule` row | `triggers.job_schedule` | Present iff job flag on. Editable on-demand ↔ cron (FR-018). |
| `fallback` | orchestrator wiring | Optional marker on the asset row when the partition fallback was applied (R5/FR-015). |

For a both-kind agent the two rows are grouped visually as one agent with two triggers (FR-019).
Editing one row never alters the other (FR-020).

---

## Entity: Shared UI components (clarified — one implementation each)

| Component | One implementation | Used by |
|-----------|--------------------|---------|
| Custom dropdown | `ui/static/dropdown.js` `enhanceSelect(s)` | Agent form (already), **Automation page (now)** — every `<select>` (FR-026/SC-004). |
| Notice / banner | `ui/static/shell.js` `showStatus`/`flashStatus`/`toast` | Agent form (already), **Automation page (now)** — every save/reload/error notice (FR-021/FR-027/SC-005). |
| App shell | `.ax-app` grid + fixed sidebar + sticky top bar (`app.css` + `base.html`) | Every page (FR-023/024/025). |

---

## State transitions

- **Create/edit** an agent: the form's two checkboxes set the asset flag (produces block) and
  the `job:` flag; the two schedule fields set the `triggers` block. Save validates the nature
  invariant and cron shapes, writes the file, reloads Dagster.
- **Kind change on edit** (edge case): unticking the Asset card removes `produces` **and** its
  `asset_schedule`, so the `on_cron` condition/sensor is gone after reload (no lingering live
  trigger); likewise unticking the Job card removes the job and its `job_schedule`. The emitter
  omits a schedule whose kind is off.
- **Carry-over** (one-off): 005 crons in `automation/migrated.yaml` move to the correct
  per-kind key; `job: true` is added to job-mode agents; `automation/` is removed (R7).
