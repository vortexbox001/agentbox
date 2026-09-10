# Feature Specification: Automation Config

**Feature Branch**: `005-automation-config`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "When an agent runs is a separate concern from what it is. Move all triggering into its own config so an agent file describes the agent only. Remove `schedule` from the agent YAML schema; add an `automation/` directory whose entries name an agent and one trigger (`cron` or `on_demand`); a one-off `scripts/migrate-schedules.py` moves existing schedules into `automation/migrated.yaml`; the management UI's Schedule card moves to a new Automation view; the README loses `schedule` and gains an Automation section."

## Clarifications

### Session 2026-09-10

- Q: How should each automation entry be structured inside the `automation/` files? → A: A top-level map keyed by agent name, with the trigger as the value (e.g. `repo-librarian-agentbox:\n  cron: "30 2 * * *"`); one key per agent makes "at most one entry per agent" structural.
- Q: After a cron trigger is set and the orchestrator reloads, does the agent run automatically or start paused until turned on? → A: Migrated triggers keep their prior on/off state (FR-014); a brand-new trigger starts paused until an operator turns it on (matching today's "turn schedules on from the UI"); an asset's automation condition follows the same operator-controlled on/off so job and asset modes stay consistent.
- Q: How should the migration treat template files (`_template-*.yaml`), which carry non-empty schedules and share the placeholder name `my-agent`? → A: Strip the `schedule` key from templates (per FR-018) but write no `migrated.yaml` entry for them; only non-template agent files (filename not starting with `_`) contribute automation entries — avoiding a duplicate/dangling `my-agent` entry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Triggering lives in `automation/`, not the agent file (Priority: P1)

An operator decides when an agent runs by adding an entry to a file in the
`automation/` directory — not by editing the agent's definition. An entry names
an agent and gives it exactly one trigger: a `cron` expression for automatic runs,
or `on_demand: true` for no automatic trigger. An agent with no entry anywhere in
`automation/` is on-demand by default. After reload, a job-mode agent with a `cron`
entry has a schedule on that cron, and the agent's own YAML contains no triggering
information at all.

**Why this priority**: This is the core of the feature — the separation of "when it
runs" from "what it is." Without it, nothing else has a place to read triggers from.
It delivers the central value (an agent file that describes only the agent) on its
own.

**Independent Test**: Write an `automation/` entry giving an existing job-mode agent
a `cron` value, reload, and confirm a schedule on that cron appears for the agent
while the agent's YAML carries no `schedule` (or any other trigger) key. Change the
entry to `on_demand: true`, reload, and confirm the schedule is gone and the agent
is runnable only by hand.

**Acceptance Scenarios**:

1. **Given** an `automation/` entry naming a job-mode agent with `cron: "30 2 * * *"`, **When** the orchestrator reloads, **Then** a schedule for that agent exists on cron `30 2 * * *`.
2. **Given** an `automation/` entry naming an agent with `on_demand: true`, **When** the orchestrator reloads, **Then** no schedule exists for that agent and it can still be run by hand.
3. **Given** an agent named in no `automation/` file, **When** the orchestrator reloads, **Then** the agent has no automatic trigger (on-demand) and remains runnable by hand.
4. **Given** any agent definition, **When** it is loaded, **Then** the agent's own YAML contains no triggering key — triggering is read only from `automation/`.

---

### User Story 2 - Existing schedules migrate with full parity (Priority: P1)

An operator runs `scripts/migrate-schedules.py` once against the current repo. Every
agent that currently sets a schedule gets an entry in `automation/migrated.yaml` with
the same cron, and the `schedule` key is stripped from every agent file. Running the
script again changes nothing. After reload, every schedule that existed before still
exists, on the same cron, with the same on/off state wherever the orchestrator can
preserve it.

**Why this priority**: The move is only safe if it is lossless. Operators must be able
to run one script and trust that no scheduled agent silently stops running. This is
the guarantee that makes adopting the feature a non-event, so it ships with P1.

**Independent Test**: On a repo with agents that set schedules, run the migration; diff
the agent files to confirm each `schedule` value now lives in `automation/migrated.yaml`
under that agent's name with the identical cron and no `schedule` key remains in any
agent file; run the migration a second time and confirm zero changes; reload the
orchestrator and confirm the same set of schedules on the same crons.

**Acceptance Scenarios**:

1. **Given** the current repo where some agents set `schedule`, **When** `scripts/migrate-schedules.py` runs, **Then** each such agent gains an `automation/migrated.yaml` entry with the same cron and its `schedule` key is removed.
2. **Given** the migration has already run, **When** it runs again, **Then** no file changes (idempotent).
3. **Given** an agent whose `schedule` was empty / manual-only, **When** the migration runs, **Then** it produces no automatic-trigger entry for that agent (it becomes on-demand, unchanged in effect).
4. **Given** the migrated repo, **When** the orchestrator reloads, **Then** every schedule that existed before the migration exists after it, on the same cron, and retains its prior on/off state wherever the orchestrator can preserve it.

---

### User Story 3 - Manage triggers from the Automation view (Priority: P2)

An operator opens a new "Automation" view in the management UI. It lists every agent
with its current trigger (a cron expression or "on demand"), and lets the operator
edit that trigger. Saving writes the change into `automation/` and reloads the
orchestrator. The agent form no longer carries the Schedule card; its Runs column now
holds only Enabled and Limits.

**Why this priority**: The declarative-config promise (Constitution II) means changing
when an agent runs should not require hand-editing YAML. It depends on the format and
orchestrator behavior existing (Stories 1–2), so it follows them, but it is what makes
the feature usable by operators who work through the UI.

**Independent Test**: Open the Automation view, confirm it lists agents with their
triggers; change one agent from on-demand to a cron value and save; confirm the change
is written under `automation/`, the orchestrator reloads, and the schedule appears.
Separately, open an agent in the agent form and confirm the Schedule card is gone while
Enabled and Limits remain in the Runs column.

**Acceptance Scenarios**:

1. **Given** the Automation view, **When** it loads, **Then** it lists every agent with its current trigger (cron expression or "on demand").
2. **Given** the Automation view, **When** the operator sets an agent's trigger to a cron value and saves, **Then** the entry is written under `automation/` and the orchestrator reloads with the new schedule.
3. **Given** the Automation view, **When** the operator sets an agent's trigger to on-demand and saves, **Then** the agent's automatic trigger is removed under `automation/` and the orchestrator reloads without a schedule for it.
4. **Given** the agent form, **When** the operator opens any agent, **Then** the Schedule card is absent and the Runs column shows only Enabled and Limits.

---

### User Story 4 - Asset-producing agents are triggered by a cron automation condition (Priority: P2)

An operator gives a cron entry to an agent that also declares `produces` (feature 004),
making it asset-mode. After reload, the orchestrator shows that asset with a cron-based
automation condition rather than a job schedule, and the asset materializes at the cron
time.

**Why this priority**: Feature 004 turns some agents into assets; those agents must be
schedulable too, but through the asset's automation condition rather than a
`ScheduleDefinition`. It depends on both the automation format (Stories 1–2) and 004,
so it is P2.

**Independent Test**: Add `produces` and a `cron` automation entry to one agent, reload,
and confirm the orchestrator presents an asset with an automation condition (not a
schedule) for that agent, and that it materializes at the cron time.

**Acceptance Scenarios**:

1. **Given** an asset-mode agent (declares `produces`) with a `cron` automation entry, **When** the orchestrator reloads, **Then** the asset carries a cron-based automation condition and no `ScheduleDefinition` is created for it.
2. **Given** that asset with its automation condition turned on (FR-021), **When** the cron time arrives, **Then** the asset materializes (the correct partition, if partitioned — see Null Action).
3. **Given** an asset-mode agent with an `on_demand` entry or no entry, **When** the orchestrator reloads, **Then** the asset has no automation condition and materializes only by hand.

---

### User Story 5 - Deleting an entry leaves the agent runnable, just not triggered (Priority: P2)

An operator deletes an agent's entry from `automation/` (or sets it to on-demand) and
reloads. The agent is still listed and still runnable by hand — it simply has no
automatic trigger.

**Why this priority**: The reverse of Story 1: removing a trigger must never remove the
agent. This reversibility is what lets operators pause automation without deleting work.
It depends on the format existing, so it is P2.

**Independent Test**: Delete an agent's automation entry, reload, and confirm the agent
still appears in the orchestrator and can be launched by hand, with no schedule and no
automation condition.

**Acceptance Scenarios**:

1. **Given** an agent with a `cron` automation entry, **When** the entry is deleted and the orchestrator reloads, **Then** the agent is still present and runnable by hand, with no schedule or automation condition.
2. **Given** the deleted-entry agent, **When** the operator inspects the automation view, **Then** the agent shows as on demand.

---

### User Story 6 - A bad automation entry is rejected by name (Priority: P3)

An automation entry that names an agent which does not exist fails the reload with a
message that names the offending entry, and the management UI refuses to save such an
entry. A valid repo is never taken down by one bad line.

**Why this priority**: A dangling entry that silently did nothing — or that took down
discovery of every agent — would erode trust in the automation file. Catching it at
both the reload and the UI, with a naming message, respects Constitution VI. It depends
on the format existing, so it is P3.

**Independent Test**: Hand-write an automation entry naming a non-existent agent and
confirm the reload fails with a message naming that entry; separately, attempt to save
such an entry in the Automation view and confirm the save is refused with an explanatory
message.

**Acceptance Scenarios**:

1. **Given** an `automation/` entry naming an agent that does not exist, **When** the orchestrator reloads, **Then** the reload fails with a message that names the offending entry (the agent name and the file).
2. **Given** the Automation view, **When** the operator tries to save an entry that names a non-existent agent, **Then** the save is refused with a message explaining why.
3. **Given** an entry naming a real agent, **When** the orchestrator reloads, **Then** the entry is accepted and applied.

---

### Edge Cases

- **No entry for an agent**: the agent is on-demand — the default. `on_demand: true` is the explicit spelling of that same state.
- **Empty / manual-only prior schedule**: an agent whose `schedule` was `""` had no automatic trigger; the migration produces no `cron` entry for it (it is simply on-demand), so `migrated.yaml` stays minimal.
- **A `schedule` key survives in an agent file** (hand-edited back in, or a not-yet-migrated file): the on-read migration drops the key and logs a warning that names the file; the file still loads. The dropped value does **not** silently become a trigger — triggering comes only from `automation/`.
- **Both `cron` and `on_demand` on one entry**: rejected — an entry declares exactly one trigger.
- **Neither `cron` nor `on_demand` on an entry**: treated as on-demand (an entry that names an agent but sets no trigger is equivalent to no entry), or rejected as empty — see Assumptions.
- **The same agent named in two automation files (or twice in one)**: a conflict; rejected with a message naming the agent and the files, so the operator resolves it (mirrors 004's duplicate-key handling).
- **Invalid cron in an entry**: rejected with the same five-field / no-macro rules the schedule field used before, and the UI refuses to save it.
- **Disabled agent (`enabled: false`) with an automation entry**: the agent is skipped at startup exactly as today; its entry attaches to nothing and produces no trigger (and is not treated as a dangling-agent error, since the agent file exists).
- **Template files (`_template-*.yaml`) in migration**: their `schedule` key is stripped (FR-018) but they get no `migrated.yaml` entry — otherwise the two templates that share the placeholder name `my-agent` would collide and name a non-real agent (FR-012).
- **A partitioned asset whose cron condition cannot target the right partition**: see Null Action — fall back to a schedule that targets the asset.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent YAML schema MUST NOT include a `schedule` key; an agent definition describes the agent only, not when it runs.
- **FR-002**: The schema version MUST be bumped, and an on-read migration MUST drop a `schedule` key from any older or hand-edited agent file, logging a warning that names the file. The dropped value MUST NOT be turned into a trigger.
- **FR-003**: The set of always-written agent fields MUST no longer include `schedule`; the YAML emitter MUST NOT write a `schedule` key for any agent.
- **FR-004**: A new top-level `automation/` directory MUST hold one or more YAML files whose top level is a map keyed by agent name; each key's value gives that agent exactly one trigger.
- **FR-005**: A trigger MUST be either `cron: "<five-field expression>"` (an automatic trigger) or `on_demand: true` (no automatic trigger).
- **FR-006**: An agent named in no `automation/` entry MUST default to on-demand (no automatic trigger).
- **FR-007**: For a job-mode agent, a `cron` entry MUST produce a schedule for that agent on that cron; an `on_demand` entry (or no entry) MUST produce no schedule.
- **FR-008**: For an asset-mode agent (declares `produces`, feature 004), a `cron` entry MUST produce a cron-based automation condition on the asset — not a `ScheduleDefinition` — and an `on_demand` entry (or no entry) MUST produce no automation condition. (See Null Action for the partitioned-asset fallback.)
- **FR-009**: A `cron` value MUST be validated with the same rules the former schedule field used (exactly five fields; cron macros such as `@daily` unsupported); invalid values MUST be rejected at both the orchestrator reload and the management-UI entry point.
- **FR-010**: An automation entry that names an agent which does not exist MUST fail the reload with a message that names the offending entry (agent name and file), and the management UI MUST refuse to save such an entry.
- **FR-011**: When the same agent is named by more than one automation entry (across files or within one), the conflict MUST be rejected with a message naming the agent and the files involved.
- **FR-012**: `scripts/migrate-schedules.py` MUST read every agent YAML and strip the `schedule` key from every file (including templates, per FR-018), but MUST write `automation/migrated.yaml` entries only for non-template agent files (filename not starting with `_`) that have a non-empty `schedule`, each as a `cron` entry keyed by that agent's name. Template files (`_template-*.yaml`) MUST NOT produce an entry.
- **FR-013**: `scripts/migrate-schedules.py` MUST be idempotent — running it again after a successful run MUST change no file.
- **FR-014**: After migration and reload, every schedule that existed before MUST exist after, on the same cron, and MUST retain its prior on/off (running) state wherever the orchestrator can preserve it.
- **FR-015**: The management UI MUST gain an "Automation" view that lists every agent with its current trigger (a cron expression or "on demand") and lets the operator edit that trigger.
- **FR-016**: Saving in the Automation view MUST write the change into `automation/` and reload the orchestrator.
- **FR-017**: The Schedule card MUST be removed from the agent form; the agent form's Runs column MUST retain Enabled and Limits.
- **FR-018**: The agent-definition templates MUST no longer carry a `schedule` line (Constitution VI — templates track the schema).
- **FR-019**: The README MUST remove `schedule` from the agent key table and MUST gain an "Automation" section documenting the `automation/` file format (`cron` and `on_demand`, the default-on-demand rule, and one entry per agent).
- **FR-020**: Enabling/disabling an automatic trigger from the Automation view MUST NOT delete or disable the agent itself; the agent remains listed and runnable by hand.
- **FR-021**: A brand-new `cron` trigger MUST start paused (not firing) until an operator turns it on, matching today's schedule behavior. A migrated trigger MUST retain its prior on/off state (FR-014). An asset-mode agent's cron automation condition MUST follow the same operator-controlled on/off, so setting a cron on a job-mode and an asset-mode agent behaves consistently.

### Key Entities *(include if feature involves data)*

- **Automation entry**: One key/value pair in a file under `automation/`: the **key** is the agent's name, the **value** gives it exactly one trigger — either `cron` (a valid five-field expression) or `on_demand: true`. Absence of a key for an agent is equivalent to `on_demand: true`.
- **Automation file**: A YAML file under `automation/` whose top level is a map keyed by agent name (one entry per key). `migrated.yaml` is the file the one-off migration writes; more files MAY exist. Each agent MUST appear at most once across all files (a duplicate key across files is the conflict of FR-011).
- **Agent definition**: The existing declarative agent file — now describing the agent only, with no triggering key. Still the single source of truth for the agent (no database).
- **Trigger**: The when-it-runs concern, expressed as `cron` (automatic) or `on_demand` (manual only). For a job-mode agent a cron trigger becomes a schedule; for an asset-mode agent it becomes an asset automation condition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After running `scripts/migrate-schedules.py` on the current repo, 100% of non-template agents that previously set a non-empty schedule have a matching `cron` entry in `automation/migrated.yaml` with the identical expression, zero agent YAML files (templates included) still contain a `schedule` key, and no template contributes an entry.
- **SC-002**: Running the migration a second time changes zero files.
- **SC-003**: After migration and reload, the set of active schedules (agent → cron) is identical to the set before migration, and each schedule's on/off state is preserved wherever the orchestrator can preserve it.
- **SC-004**: An asset-mode agent (declares `produces`) with a cron automation entry shows in the orchestrator as an asset with an automation condition (not a schedule) and, once that condition is turned on (FR-021), materializes at the cron time.
- **SC-005**: Deleting an agent's automation entry and reloading leaves the agent listed and runnable by hand, with no automatic trigger — verified by launching it manually after the delete.
- **SC-006**: An automation entry naming a non-existent agent is rejected at reload with a message naming the entry in 100% of cases, and the same entry is refused by the Automation view before it can be saved.
- **SC-007**: The agent form contains no Schedule card, and the README agent key table contains no `schedule` row, while the README documents the `automation/` format — verified by inspection.
- **SC-008**: An operator can change an agent from on-demand to a cron trigger entirely through the Automation view, with no hand-editing of any file, and see the schedule **appear (paused, per FR-021) on that cron** after the automatic reload — ready to be turned on, exactly as schedules behave today.

## Assumptions

- **Schedule identity is preserved for on/off parity**: the orchestrator stores a schedule's running (on/off) state keyed by the schedule's name; the migration and the automation loader keep each agent's schedule name stable (e.g. `sched_<name>`), so Dagster preserves the prior toggle state "where it can." A rename or a job→asset conversion is the case where prior state cannot be preserved. New triggers default to paused per FR-021.
- **Entry shape** (resolved by clarification): each automation file is a top-level map keyed by the agent's `name`, the value carrying the single trigger; an agent appears at most once across all `automation/` files, and a duplicate key is the conflict of FR-011.
- **UI write target**: the Automation view reads entries from every file under `automation/` but writes edits to a single canonical file (the migration's `automation/migrated.yaml`, or an equivalent UI-managed file); it does not scatter one agent's trigger across files.
- **An entry with neither `cron` nor `on_demand`** is treated as on-demand (equivalent to no entry) rather than an error, so a partially edited file degrades to "not triggered" rather than taking down the reload; the conflicting-both case (FR-005) is the only malformed-trigger rejection.
- **Cron validation rules are inherited** from the former schedule field (five fields, no `@`-macros); this feature moves that validation, it does not redefine it.
- **The existing schema-versioning / migration / YAML-emitting machinery** (the same mechanism used to add `produces` in 004) is how `schedule` is removed from the schema, the version bumped, and old files migrated on read.
- **Feature 004 (`produces`) is present**: asset-mode agents already exist; this feature attaches their trigger via an automation condition. If 004 is absent, only the job-mode paths (Stories 1–3, 5, 6) apply.
- **Reload is the existing UI action**: "reloads Dagster" means the same reload the agent form already performs on save.

## Out of Scope

- Event-driven triggers (feature 008).
- Dagster sensors of any kind.
- Any trigger type other than `cron` and `on_demand` (e.g. intervals, calendars, dependencies between agents).
- Changing what a schedule or a materialization actually does when it fires — this feature moves *when* an agent runs, not *how* it runs.
- Multiple triggers per agent.

## Null Action

If the orchestrator's asset API cannot attach a cron-based automation condition to a
**partitioned** asset in a way that materializes the correct partition (feature 004's
daily partition), the implementer MUST fall back to a `ScheduleDefinition` that targets
the asset (materializing the intended partition) and MUST say so explicitly in the plan,
rather than silently shipping an automation condition that materializes the wrong
partition or none. Unpartitioned assets and job-mode agents are unaffected by this
fallback.
