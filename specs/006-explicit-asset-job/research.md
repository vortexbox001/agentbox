# Phase 0 Research: Explicit Asset/Job Model & Automation Shell Cleanup

All Technical-Context unknowns are resolved below. Each item is a decision, its rationale, and
the alternatives rejected. Nothing is left as NEEDS CLARIFICATION.

---

## R1 — The both-kind materializing job (`agent_<name>` for an asset)

**Decision**: When an agent declares **both** an asset and a job, build the asset exactly as
today (`build_asset` → `AssetsDefinition.from_op(make_run_op(cfg), …)`) and build
`agent_<name>` as an **asset job** via
`dagster.define_asset_job(name="agent_<name>", selection=AssetSelection.assets(asset_def))`.
Register both the asset and this job in `Definitions`. Manual Materialize, the `on_cron`
auto-condition, and a `job_schedule` on `agent_<name>` then all execute the same underlying op
and record one asset materialization (FR-006).

**Rationale**: `define_asset_job` is GA in the pinned Dagster 1.13.21. It creates a job whose
run materializes the selected asset(s) — precisely "the asset's materializing job." It reuses
the asset's op (no second launch definition), keeping 004's single-op rule (FR-008) intact and
naming the compute step `run_<name>` as before. It gives the operator a launchable
`agent_<name>` in the Dagster jobs list whose runs appear in the asset's materialization
history — the unified history the spec requires.

**Alternatives considered**:
- *A plain op job (`build_job`) that also happens to write the asset dir* — rejected: its runs
  would **not** record an asset materialization (no asset binding), breaking FR-006's "one
  unified history" and Acceptance Scenario 1.4.
- *Two separate ops (one for the asset, one for the job)* — rejected: violates FR-008's single
  shared launch op and duplicates the launch logic.
- *A schedule/sensor that targets the asset directly without a named job* — rejected: the spec
  requires a launchable, hand-runnable `agent_<name>` (US1 Independent Test).

## R2 — Asset-only has no `agent_<name>` job

**Decision**: An asset-only agent (asset flag on, job flag off) registers **only** the
`AssetsDefinition`; no `agent_<name>` job is created. The operator runs it via Dagster's
**Materialize** button; the UI's per-agent "Dagster job" link, which points at
`/jobs/agent_<name>`, is replaced for asset-only agents by an asset link
(`/assets/<key path>`) — the store already computes `dagster_job`/`dagster_url`, so this is a
kind-aware URL choice, not new plumbing.

**Rationale**: Matches Acceptance Scenario 1.2 ("no `agent_<name>` job exists for it") and
avoids a confusing empty job. Materialization is the asset's native run trigger.

**Alternatives considered**: *Always create `agent_<name>` even for asset-only* — rejected:
contradicts the spec and clutters the jobs list with a job that duplicates Materialize.

## R3 — Job-only is unchanged

**Decision**: A job-only agent (job flag on, asset flag off) uses `build_job(cfg)` exactly as
today — a plain `@job` named `agent_<name>` wrapping `make_run_op(cfg)`, whose runs record **no**
asset materialization (FR-007). No behavior change from 005 for this path.

**Rationale**: This is the established, tested path; the only difference is that "job-ness" now
comes from the explicit `job:` flag rather than from the *absence* of `produces`.

## R4 — Modeling nature + triggers in the YAML/schema

**Decision**:
- **Asset flag** = presence of a valid `produces:` block (asset key + partition), unchanged
  from 004. The form's "make agent an asset" checkbox toggles the block's presence.
- **Job flag** = a new top-level `job: true|false` boolean (schema field, Job group). The
  form's "create agent job" checkbox toggles it. Default is **derived on migration** (see R11),
  not a blanket default, so existing agents keep their current nature.
- **Triggers** = a dedicated nested block:
  ```yaml
  # --- Triggers ---
  triggers:
    asset_schedule: "20 17 * * *"   # optional; on_cron auto-condition; blank/absent = none
    job_schedule: "30 2 * * *"      # optional; ScheduleDefinition on agent_<name>; blank/absent = none
  ```
  Modeled in `schema.py` as two `cron`-type fields with `block="triggers"`, mirroring how
  `asset`/`partition` use `block="produces"`. `agents_store` lifts the block into flat
  `asset_schedule`/`job_schedule` fields on read and re-nests them on emit (the exact pattern
  already used for `produces`).

**Rationale**: Resolved directly by the spec's Clarifications §2026-09-10 (one dedicated
`triggers:` mapping, its own section, two optional keys). Reusing the `produces` block
machinery in `agents_store` (lift-on-read / nest-on-emit) means no new emitter concept — just a
second block. Keeping `produces:` purely about asset identity (no schedule inside it) preserves
004's contract and gives a clean 1:1 map to the form's two schedule fields and the Automation
page's two rows.

**Alternatives considered**:
- *Put schedules back inside `produces:` and add a `job:` sub-key there* — rejected by the
  clarification: it would overload `produces` and break the 1:1 mapping.
- *A single `schedule:` that means different things by kind* — rejected: 005's ambiguity is
  exactly what this feature removes; two named keys are unambiguous.

## R5 — Partition targeting for `on_cron` + Null-Action fallback (FR-015)

**Decision**: Carry 005 R5 forward verbatim as the primary path: `AutomationCondition.on_cron`
on a `DailyPartitionsDefinition` targets the latest (current-day) partition per tick. **Harden
the fallback**: if a build-time check (quickstart §8) shows `on_cron` cannot target the correct
partition on the installed Dagster, fall back to a **partition-filling `ScheduleDefinition` on
the asset's materializing job** (which R1 already builds for the both case; for an asset-only
agent that needs the fallback, the fallback additionally defines that materializing job so the
schedule has a target). Surface the fallback in **two** places (FR-015):
1. An orchestrator **load-time warning log** naming the agent and asset (auditable per
   Constitution VI in the headless system).
2. A **visible marker/notice on that agent's schedule row** in the Automation page — carried in
   the `GET /api/automation` row payload as a `fallback` field the row renders.

**Rationale**: The spec's clarification demands "Both" surfaces. The log satisfies the headless
auditability requirement; the row marker satisfies the operator-facing requirement. Reusing the
materializing job as the fallback target keeps one launch op and one history.

**Alternatives considered**: *Silently drop the trigger* — rejected by FR-015. *Only log, or
only mark the row* — rejected: the clarification says both.

## R6 — Preserving on/off state across the store move (FR-012/FR-014)

**Decision**: Keep schedule and sensor **names identical** to 005 — `sched_<name>` for a
`ScheduleDefinition` and `autocond_<name>` for a per-asset
`AutomationConditionSensorDefinition`. Dagster keys instigator (paused/running) state by name
under `/data/dagster`, so moving *where the cron is declared* (from `automation/` to the agent's
`triggers:` block) changes nothing about the name and therefore preserves each trigger's prior
toggle across the reload. New triggers set no `default_status` on a schedule (starts paused) and
`DefaultSensorStatus.STOPPED` on a sensor (starts paused) — 005's paused-by-default behavior.

**Rationale**: This is the same mechanism 005 relied on to preserve state through *its*
migration; the name is the contract with Dagster's state store, and it is unchanged. It makes
FR-014 ("the set of live triggers before and after is identical") true by construction, not by
data copying.

**Alternatives considered**: *Rename to `trigger_<name>`/`sched_asset_<name>`* — rejected:
would reset every existing trigger to paused, silently stopping agents that were running (violates
SC-001/FR-012).

## R7 — The one-off carry-over migration + retiring the legacy path (FR-010/FR-011)

**Decision**: Add `scripts/migrate-automation-to-triggers.py`, run once in this change. It:
1. Reads `automation/migrated.yaml` (005's canonical store).
2. For each entry, reads the named `agents/<name>.yaml`, determines the agent's kind
   (asset-mode ⇔ has `produces`), and writes the cron onto the correct key —
   `produces` present → `triggers.asset_schedule`, else → `triggers.job_schedule` (FR-013).
   Job-mode agents also get `job: true` written (they were jobs under 005). Asset-mode agents
   keep `job` absent/false unless they already had a job nature (none do today).
3. Bumps each touched file's `# agentbox-schema:` stamp to 4.
4. Removes the `automation/` directory entirely.
Idempotent: a second run finds no `automation/`, so it reports nothing to do. Delete 005's
`scripts/migrate-schedules.py` and its test. Remove the orchestrator's `load_automation`,
`AUTOMATION_GLOB`, `RejectAutomation`, and every `on_demand` reference — the orchestrator reads
triggering **only** from `cfg["triggers"]` (FR-010, SC-008).

**Rationale**: The clarification specifies a one-off script (not runtime auto-migration) that
writes onto the per-agent blocks and then removes `automation/`, with the orchestrator carrying
no legacy load path. Writing through the same file the schema emitter produces (via
`agents_store`, or a careful in-place edit that preserves the schema-4 shape) keeps the files
UI-consistent (FR-023 posture: hand-edit and UI stay in agreement).

**Alternatives considered**:
- *A runtime shim in the orchestrator that reads `automation/` if present* — rejected by the
  clarification (no legacy load path).
- *Hand-edit the two files instead of a script* — rejected: FR-011 requires a verifiable,
  idempotent, re-runnable migration, and the script is the auditable record of the carry-over.

## R8 — Fixed sidebar + pinned top bar that survives phone width (FR-023/024/025)

**Decision**: Change the shell so the **content region is the only scroller**:
- `.ax-app` becomes `height: 100dvh` (from `min-height: 100vh`) so the grid fills the viewport
  exactly and does not grow the page.
- `.ax-sidebar` gets `overflow-y: auto` (its own scroll if the nav ever exceeds the viewport)
  and stays put because the grid column is fixed height.
- `.ax-topbar` becomes `position: sticky; top: 0; z-index` above content so it pins over the
  scrolling `.ax-content` (which already has `overflow-y: auto; flex: 1`).
- Add **one viewport media query** (`@media (max-width: 640px)`) that collapses `.ax-app` to a
  single column (`grid-template-columns: 1fr`), turns the sidebar into a top strip (horizontal
  nav, not overlapping content), and keeps the top bar sticky — so nothing overlaps or hides
  content at phone width (FR-025/SC-006).

**Rationale**: The shell lives **outside** the `ax-content` container, so its responsiveness
must use a viewport media query, not the container queries the form grid uses (003). `100dvh`
(dynamic viewport height) avoids the mobile-browser URL-bar jump that `100vh` causes. Making
`ax-content` the sole scroller is the standard app-shell pattern and the smallest change to the
existing grid.

**Alternatives considered**:
- *`position: fixed` sidebar + margin on main* — rejected: fixed positioning fights the existing
  grid and is harder to keep from overlapping at phone width.
- *A container query for the shell* — rejected: the shell is not inside an inline-size container;
  viewport width is the right axis for it.

## R9 — One shared dropdown everywhere (FR-026/SC-004)

**Decision**: The Automation page's per-row trigger `<select>` (built raw in `automation.js`)
must be enhanced through the existing shared component: give each row select
`class="ax-select"` and call `dropdown.enhanceSelects(container)` after rendering rows (and
re-enhance rows added later). A grep test asserts no `<select>` remains un-enhanced (no
`ax-select` without an `enhanceSelect(s)` path) in templates/scripts.

**Rationale**: `dropdown.js` already exports `enhanceSelects(root)` and is idempotent; the
Automation page is the last place still rendering a bare `<select>`. Reuse, not reinvention —
"shared component" means one implementation used everywhere (spec Assumptions).

**Alternatives considered**: *Style the raw `<select>` to match* — rejected explicitly by
FR-026 ("no raw select control may remain to be restyled later").

## R10 — One shared notice pattern + reserved cron-warning space (FR-021/022/027/SC-005/SC-007)

**Decision**:
- Replace the Automation page's bespoke `#ax-automation-banner` (`.ax-banner`) with the shared
  notice from `shell.js` — `showStatus({message, ok, retry})` (the same call the agent form's
  save uses, rendered in the fixed `#ax-status-region`). This makes the Automation save notice
  pixel-identical to the agent-save notice (FR-021/SC-005). The partition-fallback *marker*
  (R5) stays a per-row indicator (it is row state, not a save notice).
- Reserve the cron-shape warning's space: the `.ax-field-error` slot under each cron input gets
  a fixed `min-height` (one line) so toggling `hidden` shows/hides text **within** reserved
  space and never reflows the row (FR-022/SC-007).

**Rationale**: `shell.js` already owns the app-wide notice (`showStatus`/`flashStatus`/toast);
the Automation page predates its reuse. Reserving space is the standard no-layout-shift
treatment for inline validation.

**Alternatives considered**: *Keep `.ax-banner` but restyle it to match* — rejected by
FR-027 ("a single shared notice pattern app-wide"). *Absolutely-position the warning* —
rejected: reserving flow space is simpler and accessible.

## R11 — Schema migration 3→4 + validation rules (FR-002/FR-005)

**Decision**: `SCHEMA_VERSION` 3→4 with `migrate_3_to_4(data)`:
- If the file has **no** `produces` block → set `job: true` (it was a job under the old model).
- If it **has** `produces` → leave `job` absent/false (it was asset-only under the old model).
- Do **not** invent triggers here — the carry-over script (R7) fills `triggers` from
  `automation/migrated.yaml`; a plain read-migration must not fabricate schedules (mirrors 005's
  `migrate_2_to_3` restraint).

New `validate()` rules:
- **At-least-one-of** (FR-005): reject when neither the asset (a non-empty `produces.asset`) nor
  `job: true` is set, with the message "the agent must be an asset, a job, or both."
- **Produces-required-when-asset** (FR-002): if the asset checkbox is on (a `produces` block is
  intended) the asset key is mandatory — already enforced by the existing empty-`asset` check;
  extend it to fire when the asset card is on.
- **Cron shape** on `asset_schedule`/`job_schedule` (five fields, no `@`-macros), reusing the
  existing cron rule.

**Rationale**: The migration must preserve each existing agent's *current* nature exactly so no
agent silently changes kind on upgrade; inferring `job:true` only for non-`produces` files does
that. Fabricating triggers on read is out of scope for a migration and is the script's job.

**Alternatives considered**: *Default `job: true` for every file* — rejected: it would turn
today's asset-mode `list-commits-pi-kimi` into a both-kind agent unintentionally.

## R12 — Verifying the carry-over is lossless (FR-014)

**Decision**: Verification is operational (quickstart §5), not a new UI feature: before the
migration, record the set of enabled instigators in Dagster (the `sched_*` schedules and
`autocond_*` sensors and their running/paused state) via the GraphQL API or the Dagster UI;
after the migration + reload, confirm the same set with the same states. Because names are
unchanged (R6) and the crons are copied unchanged (R7), the sets match by construction; the
check is a guard, not a data transform. The two-agent fixture (`categorize-commits` job cron,
`list-commits-pi-kimi` asset cron) exercises both kinds.

**Rationale**: FR-014 asks that the operator *can confirm* identical live triggers, not that a
new report be built. The instigator list is the ground truth Dagster already exposes.

**Alternatives considered**: *A bespoke "trigger diff" endpoint* — rejected: unnecessary
machinery for a one-time migration; the existing Dagster surface answers the question.

---

## Resolved unknowns summary

| Unknown | Resolution |
|---------|------------|
| How does "both" become one materialization history? | `define_asset_job(agent_<name>, selection=asset)` over the same op (R1) |
| Does asset-only get an `agent_<name>` job? | No — Materialize only; UI links to the asset (R2) |
| Where do the two schedules live in YAML? | A dedicated `triggers:` block, keys `asset_schedule`/`job_schedule` (R4) |
| Partition targeting + how to surface fallback? | `on_cron` primary; fallback job schedule; log + Automation row marker (R5) |
| How is prior on/off state kept? | Unchanged `sched_<name>`/`autocond_<name>` names (R6) |
| How is 005 data carried over and the old path retired? | One-off script writes triggers + removes `automation/`; no legacy reader (R7) |
| How is the shell made fixed + responsive? | `100dvh` grid, sticky topbar, content-only scroll, one phone-width media query (R8) |
| How is the dropdown unified? | Enhance the Automation `<select>` via `dropdown.enhanceSelects` (R9) |
| How is the notice unified + no layout shift? | `shell.showStatus` on Automation; reserved cron-warning min-height (R10) |
| Schema bump + new validation? | v4, `migrate_3_to_4` infers `job` from `produces` absence; at-least-one-of + produces-required (R11) |
| How is losslessness verified? | Compare Dagster instigator set/state before vs after; names+crons unchanged (R12) |
