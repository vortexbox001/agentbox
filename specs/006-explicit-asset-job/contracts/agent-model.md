# Contract: Agent YAML — explicit asset/job nature + triggers block

Governs `ui/schema.py`, `ui/agents_store.py` (reader + emitter), and the file format the
orchestrator reads. Companion: [orchestrator-model.md](orchestrator-model.md),
[ui-automation-and-shell.md](ui-automation-and-shell.md).

## §1. The `job:` flag

- A new top-level boolean field `job`, in the **Job** group (a new `job` SchemaField, `type:
  bool`, applies to all harnesses).
- `job: true` ⇒ the agent has a Dagster job `agent_<name>`. `job: false`/absent ⇒ no job.
- Not in `ALWAYS_WRITTEN`; emitted as a real line whenever the agent has a job (so a job-only
  or both-kind file always shows `job: true`), and as a commented placeholder otherwise, so an
  author can opt in by uncommenting (same treatment as other optional booleans).

## §2. The `triggers:` block

- A dedicated nested block with its own `# --- Triggers ---` section, two optional keys:
  - `asset_schedule` — cron (5 fields, no `@`-macros); applies only when the agent is an asset.
  - `job_schedule` — cron; applies only when the agent has a job.
- Modeled as two `SchemaField`s, `type="cron"`, `block="triggers"`.
- **Reader** (`agents_store.read_agent`): lift `triggers` into flat `asset_schedule` /
  `job_schedule` managed fields (never routed to "Unmanaged"), exactly as `produces` is lifted
  into `asset`/`partition`. An absent block yields both fields unset.
- **Emitter** (`agents_store.emit_yaml` / `_triggers_block_lines`): re-nest the two flat fields
  into a `triggers:` block. Emit a **real** block when at least one schedule is set; emit the
  whole block **commented-out** (opt-in) when both are unset — mirroring `_produces_block_lines`.
  A schedule whose kind is off (e.g. `asset_schedule` on a non-asset agent) is **omitted**.
- `produces:` stays exactly as 004 defined it — asset identity only, no schedule inside it.

## §3. Validation (`schema.validate`)

Return a field→message map (empty = valid). New/changed rules:

1. **Nature invariant (FR-005)**: if neither the asset flag (a non-empty `produces.asset` /
   lifted `asset`) nor `job: true` is set, add an error keyed to a stable field (e.g. `job`)
   with message: *"the agent must be an asset, a job, or both."*
2. **Produces required when asset (FR-002)**: when the asset card is on but `asset` is empty,
   the existing empty-`asset` check fires ("an asset declaration must name an asset").
3. **Cron shape (FR-009)**: `asset_schedule` and `job_schedule`, when non-unset, must pass the
   five-field / no-`@`-macro rule (reuse the existing cron validator; `croniter.is_valid` as the
   stricter UI guard).
4. **Kind/schedule agreement**: `asset_schedule` set while the agent is not an asset, or
   `job_schedule` set while the agent has no job, is a validation error naming the offending
   field (prevents a dangling schedule the orchestrator would ignore). This is defense-in-depth
   with §2's emitter, which additionally *omits* an off-kind schedule: `validate` blocks such a
   value on save, while the emitter drops any that reaches it from a hand-edited file.

## §4. Schema version + migration

- `SCHEMA_VERSION = 4`.
- `migrate_3_to_4(data)`:
  - If `data` has **no** `produces` → set `data["job"] = True` (it was a job under the old
    model where job-ness = absence of produces).
  - If `data` **has** `produces` → do not set `job` (asset-only under the old model).
  - Do **not** create any `triggers` (a read-migration never fabricates schedules; the one-off
    carry-over script fills them — see orchestrator-model §5).
- `MIGRATIONS` gains `(4, migrate_3_to_4)`. Files at schema ≤3 load and are re-stamped to 4 on
  next save; a file stamped >4 raises `SchemaTooNew` (unchanged mechanism).

## §5. Emitted file shape (golden)

A both-kind pi agent emits, in order: header + `# agentbox-schema: 4`; `# --- Identity ---`;
`# --- Enabled ---`; `# --- Limits ---`; `# --- Produces ---` (real block, asset+partition);
`# --- Triggers ---` (real block with the set schedule(s)); the Job group's `job: true`;
`# --- Prompt ---` … through `# --- Container ---` as today. An asset-only agent emits the
`produces` block real, `triggers` with only `asset_schedule` (or commented if none), and `job`
commented/absent. A job-only agent emits `produces` commented-out, `triggers` with only
`job_schedule` (or commented), and `job: true`.

Determinism unchanged: the same definition always produces byte-identical text. Golden files in
`ui/tests/golden/` are regenerated for schema 4 with the new lines.

## §6. Backward/robustness

- Unknown keys are still preserved verbatim ("Unmanaged"); `triggers` and `job` are managed and
  never land there.
- A `triggers` value that is not a mapping is treated as empty (both schedules unset), the same
  defensive treatment `produces` gets.
- The retired `on_demand` keyword has no meaning in this schema; if it appears in a hand-edited
  file it is an unmanaged key (ignored by the orchestrator, which reads only `triggers`).
