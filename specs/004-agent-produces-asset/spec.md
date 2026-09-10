# Feature Specification: Agent Produces Asset

**Feature Branch**: `004-agent-produces-asset`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "An agent YAML can say 'I produce this asset,' and Dagster then shows that asset, its materialization history, and its metadata — instead of only a job. Agents that don't produce anything keep working exactly as today."

## Clarifications

### Session 2026-09-09

- Q: How should a materialization determine the "output file paths written this run" it records in metadata? → A: Snapshot the agent's output location before and after the run; record the files created or modified during the run window (no agent cooperation required).
- Q: For a daily-partitioned asset, what does the partition key do to the run itself? → A: It is a tracking label only — the container launch is identical regardless of which partition is materialized; metadata records which partition it was.
- Q: When two enabled agents declare the same asset key, what should happen at orchestrator load? → A: Reject the conflicting agent file(s) with a message naming them; all other agents still load.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare an agent's output as a tracked asset (Priority: P1)

An operator edits an agent definition to declare that the agent produces a named
asset. After reload, that agent appears in the orchestrator as an asset — with a
name of the operator's choosing, an optional daily partition, its materialization
history, and per-run metadata — rather than as a bare job. Running the agent works
exactly as before; the asset is simply a tracked pointer to the output the agent
already writes.

**Why this priority**: This is the core of the feature. Without it, none of the
other stories have anything to observe or manage. It delivers the central value —
seeing an agent's output as a first-class, historied artifact — on its own.

**Independent Test**: Add a `produces` block naming an asset (with a daily
partition) to an existing agent definition, reload, and confirm the asset appears
with the declared name and partition set. Trigger a materialization and confirm the
same container runs, the output file lands in its usual location, and the
materialization records the expected metadata.

**Acceptance Scenarios**:

1. **Given** an agent definition with `produces: {asset: repo-review/agentbox, partition: daily}`, **When** the orchestrator reloads, **Then** an asset named `repo-review/agentbox` appears with a daily partition set (and no bare job for that agent).
2. **Given** that asset, **When** the operator materializes today's partition, **Then** the same container that the agent launched before is launched, unchanged.
3. **Given** a completed materialization, **When** the operator inspects it, **Then** its metadata lists the output file path(s) written this run, the transcript path, the run stamp, the session id, the harness, and the model.
4. **Given** a completed materialization, **When** the operator looks for the output file, **Then** it is found in the agent's usual output location and naming (e.g. `/data/outputs/repo-librarian/agentbox/`), with no duplicate copy created by the asset.
5. **Given** the agent produced the asset once before, **When** the operator views the asset, **Then** a materialization history is available.

---

### User Story 2 - Reverting to job-mode leaves nothing else changed (Priority: P1)

An operator removes the `produces` block from an agent definition. After reload,
the agent is back to being an ordinary job under its original job name, and no other
behavior has changed.

**Why this priority**: The promise that "agents that don't produce anything keep
working exactly as today" must be verifiable and reversible. If declaring an asset
were a one-way door, operators could not safely experiment. This must ship with P1.

**Independent Test**: Take an agent currently in asset-mode, remove `produces`,
reload, and confirm the agent is a job named `agent_<name>` again with all other
behavior identical to before the asset was ever declared.

**Acceptance Scenarios**:

1. **Given** an asset-mode agent, **When** its `produces` block is removed and the orchestrator reloads, **Then** the agent appears as a job named `agent_<name>` (e.g. `agent_repo_librarian_agentbox`) and no longer as an asset.
2. **Given** an agent definition that has never contained a `produces` block, **When** the orchestrator loads it, **Then** it loads with no warnings and produces no migration noise.
3. **Given** the reverted agent, **When** it runs, **Then** its behavior (container launch, output location, schedule) is identical to before the asset was declared.

---

### User Story 3 - Create an asset-producing agent from the management UI (Priority: P2)

An operator creating or editing an agent in the management UI fills in the
"Produces" fields (asset key and partition). Saving writes the `produces` block
into the correct place in the YAML with a comment per field. Reopening the agent in
the form shows the same values back.

**Why this priority**: The declarative-config promise (Constitution II) means asset
declaration should be doable without hand-editing YAML. It depends on the format
existing (Stories 1–2), so it follows them, but it is what makes the feature usable
by operators who work through the UI.

**Independent Test**: Create a new agent in the management UI with the Produces
fields filled in, inspect the written YAML for the commented block in the right
section, and reopen the agent to confirm the values round-trip.

**Acceptance Scenarios**:

1. **Given** the agent form, **When** the operator fills in the Produces asset key and partition and saves, **Then** the written YAML contains a `produces` block in the Runs section with an explanatory comment per field.
2. **Given** a saved asset-producing agent, **When** the operator reopens it in the form, **Then** the Produces fields show the same asset key and partition that were saved.
3. **Given** the agent form for an agent with no asset, **When** the operator leaves the Produces fields empty and saves, **Then** no `produces` block is written and the agent remains a job.

---

### User Story 4 - Invalid asset keys are rejected with a helpful message (Priority: P2)

When an operator supplies an asset key that is not a valid asset key, both the
management UI and the orchestrator reject it, and the rejection message names the
file at fault so the operator can find and fix it.

**Why this priority**: A malformed asset key that slips through would fail at
orchestrator load and could take down discovery of other agents. Catching it at
both entry points, with a file-naming message, protects the whole set of agents and
respects Constitution VI (docs/behavior track reality). It depends on the format
existing, so it is P2.

**Independent Test**: Enter an invalid asset key in the UI and confirm it is
rejected before save; separately, hand-write an invalid asset key into a YAML file
and confirm the orchestrator rejects it with a message that names that file.

**Acceptance Scenarios**:

1. **Given** the agent form, **When** the operator enters an asset key that is not a valid asset key and tries to save, **Then** the save is rejected with a message explaining why.
2. **Given** a YAML file whose `produces.asset` is not a valid asset key, **When** the orchestrator loads it, **Then** it is rejected with a message that names the offending file.

---

### Edge Cases

- **Partition omitted**: `produces` is present but `partition` is absent → treated as `none` (unpartitioned asset).
- **`partition: none`**: the asset is emitted without a partition set; materialization is a single unpartitioned run.
- **Materializing a non-current daily partition** (e.g. a past date): permitted; because the partition is a tracking label only (FR-008b), the run launches identically to a current-partition run and the metadata records which partition was chosen.
- **Empty `produces` block**: `produces:` present with no `asset` → rejected as invalid (an asset declaration must name an asset).
- **Asset key with a path prefix** (e.g. `code-map/agentbox`): the slash-separated segments form the asset's key path; the asset is grouped/displayed under that prefix.
- **Disabled agent with `produces`**: an agent with `enabled: false` is skipped at startup exactly as today, whether or not it declares an asset.
- **Two enabled agents declaring the same asset key**: the conflicting agent file(s) are rejected with a message naming them; all other agents still load (FR-019).
- **A run that writes no output file**: the materialization still records its other metadata; the output-file list is empty rather than an error.
- **Existing outputs before first materialization**: the asset points to output files by convention; if no materialization has run yet, the asset shows an empty history rather than an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An agent definition MUST support an optional top-level `produces` block containing an `asset` key and an optional `partition`.
- **FR-002**: `produces.partition` MUST accept the values `none` and `daily`, defaulting to `none` when omitted.
- **FR-003**: When `produces` is present, the orchestrator MUST represent the agent as an asset (partitioned when `partition: daily` is declared) instead of as a job.
- **FR-004**: When `produces` is absent, the orchestrator MUST represent the agent exactly as it does today — a job named `agent_<name>` — with no change in behavior.
- **FR-005**: The asset's materialization MUST launch the same container the agent launches today, via the existing launch path — not a forked or duplicated launch path (see Null Action).
- **FR-006**: A partitioned asset MUST expose a daily partition set that an operator can materialize per-partition from the UI.
- **FR-007**: Output files MUST keep their current host location and naming; the asset MUST be a pointer to those files, not a new copy of them.
- **FR-008**: Every materialization MUST record metadata including: the output file path(s) written this run, the transcript path, the run stamp, the session id, the harness, and the model.
- **FR-008a**: The "output file path(s) written this run" MUST be determined by snapshotting the agent's output location before and after the run and recording the files created or modified during the run window; the agent is not required to report its own paths.
- **FR-008b**: A partition key MUST act as a tracking label only: the container launch MUST be identical regardless of which partition is materialized, and the materialization metadata MUST record which partition was materialized. The partition key MUST NOT be injected into the container or alter output location or naming.
- **FR-009**: The materialization metadata MUST leave room for token/cost fields to be added later (feature 005) without a further schema change to the `produces` block.
- **FR-010**: An asset-mode agent's compute step MUST remain recognizably named `run_<name>`, matching the op naming used for job-mode agents.
- **FR-011**: An asset key MUST be validated against the rules for a valid asset key at both the management-UI entry point and orchestrator load; invalid keys MUST be rejected.
- **FR-012**: An orchestrator-side rejection of an invalid asset key MUST name the offending file in its message.
- **FR-013**: The management UI schema MUST gain the `produces` fields, surfaced as a new "Produces" card under the Runs column.
- **FR-014**: The schema version MUST be bumped and the migrations list updated so that existing agent files without `produces` load without warnings or migration noise.
- **FR-015**: The agent-YAML field comments and the README key table MUST be updated to describe the new `produces` fields (Constitution VI).
- **FR-016**: The agent definition templates MUST gain a commented-out `produces` block so authors can uncomment it to opt in.
- **FR-017**: When the management UI writes a `produces` block, it MUST place the block in the Runs section with an explanatory comment per field, and the block MUST round-trip (reopening the form shows the same values).
- **FR-018**: Agent definitions that predate this feature and contain no `produces` block MUST continue to load and run unchanged.
- **FR-019**: When two or more enabled agents declare the same asset key, the orchestrator MUST reject the conflicting agent file(s) with a message that names them, while continuing to load all other agents.

### Key Entities *(include if data involves data)*

- **Produces declaration**: The optional block in an agent definition stating that the agent produces a tracked asset. Attributes: `asset` (a valid asset key, optionally path-prefixed such as `code-map/agentbox`) and `partition` (`none` or `daily`, default `none`).
- **Asset**: The orchestrator-side representation of an agent's declared output. Identified by its asset key; carries a partition set when declared; owns a materialization history and per-materialization metadata; points to existing output files rather than copying them.
- **Materialization record**: The record produced each time the asset is materialized. Carries metadata: output file path(s), transcript path, run stamp, session id, harness, model — with room reserved for later token/cost fields.
- **Agent definition**: The existing declarative agent file, now optionally carrying a `produces` block, still the single source of truth for the agent (no database).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding a `produces` block to an existing agent and reloading makes its asset (with the declared partition) visible in the orchestrator, with no edits to any code outside the agent file required by the operator.
- **SC-002**: 100% of an asset-mode materialization's required metadata fields (output file path(s), transcript path, run stamp, session id, harness, model) are present and correct on inspection.
- **SC-003**: A materialization produces exactly one output artifact in the agent's usual location — zero duplicate copies attributable to the asset.
- **SC-004**: Removing `produces` and reloading returns the agent to a job named `agent_<name>` with no other observable change (diff of behavior is limited to job-vs-asset representation).
- **SC-005**: Loading the full existing set of agent definitions (none of which declare `produces`) produces zero warnings and zero migration-noise messages.
- **SC-006**: An invalid asset key is rejected at both the UI and the orchestrator, and the orchestrator's rejection message names the offending file in 100% of cases.
- **SC-007**: A `produces` block created through the management UI round-trips: reopening the agent shows the identical asset key and partition that were saved.

## Assumptions

- **Run stamp and session id** already exist as per-run values the launch path emits (`AGENTBOX_RUN_STAMP`, `AGENTBOX_SESSION_ID`) and are available to record in materialization metadata.
- **The transcript path convention** (`/data/dagster/agent-logs/<agent>/<date>/<run-id>.jsonl`) and **output convention** are unchanged by this feature; the asset records these paths, it does not relocate them.
- **A valid asset key** follows the orchestrator's asset-key rules (identifier-like segments, optionally joined by `/` into a key path); the exact character rules are inherited from the orchestrator rather than newly invented here.
- **One asset per agent**: exactly zero or one `produces` block per agent; multiple assets per agent, dependencies between assets, and dynamic partitions are out of scope.
- **Two enabled agents declaring the same asset key** is an operator error resolved by FR-019: the conflicting files are rejected by name and every other agent still loads.
- **Only `daily` partitioning** is offered in this feature; other cadences (and scheduling changes generally) are deferred to feature 005. A daily partition is a tracking/backfill label only in this feature (FR-008b); making the partition date actually drive the run belongs to feature 005.
- **The management UI's existing schema-versioning, migration, and YAML-emitting machinery** is the mechanism for adding the fields, bumping the version, and preserving unknown keys.

## Out of Scope

- Scheduling changes (deferred to feature 005).
- Token/cost metadata fields (hooks are left; the fields themselves come in feature 005).
- Pipes / structured run reports (feature 006).
- Multiple assets per agent.
- Dependencies between assets.
- Dynamic partitions.

## Null Action

If the orchestrator's asset API cannot wrap the existing launch step without
changing how the container is launched, the implementer MUST stop and report,
rather than fork the launch code into two divergent paths (one for jobs, one for
assets). A single launch path shared by both modes is a hard requirement of this
feature.
