# Feature Specification: Event-Driven Triggers — Asset Dependency Graph

**Feature Branch**: `013-event-driven-triggers`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "An agent can declare that its asset depends on other assets and be triggered when they change. Upstream outputs are handed to the container. This replaces 'watch a folder' with an explicit graph. `produces.depends_on:` list of asset keys; `triggers:` gains `on_upstream: true` and `on_missing: true` behind the same `autocond_<name>` sensor; partitioned upstream/downstream map one-to-one (daily → daily); at launch the container receives `AGENTBOX_UPSTREAM_<KEY>` pointing at a read-only JSON file listing the upstream's latest materialization for the matching partition; governors in `config/settings.yaml` cap `max_runs_per_hour` (default 12) and `max_chain_depth` (default 5) for automated runs, both editable on the Settings page; `depends_on` cycles are rejected at load naming the assets."

## Clarifications

### Session 2026-09-16

- Q: For a daily-partitioned asset with `on_missing: true`, which never-produced partitions does it materialize? → A: Only the current/latest expected partition (today for daily; the single partition when unpartitioned) — it does not backfill older historical partitions.
- Q: Is `max_runs_per_hour` enforced over a rolling 60-minute window or a fixed clock hour? → A: A rolling 60-minute window (count of automated launches in the trailing 60 minutes).
- Q: When a downstream fires but one of its declared upstreams has no materialization for the matching partition, what does that upstream's `AGENTBOX_UPSTREAM_<KEY>` provide? → A: The variable is still present and points at a handoff file whose fields are null/empty, marking "no materialization" for that partition.
- Q: What `chain_depth` does a root automated run (schedule- or `on_missing`-initiated, or fired by a manual upstream) carry? → A: Root automated run is `chain_depth` 1; each downstream run carries parent's depth + 1.
- Q: Does an automated run refused by a governor consume a `max_runs_per_hour` slot? → A: No — only runs that actually launch count toward the per-hour cap; refused runs are skipped without consuming a slot.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fire a downstream asset when its upstream materializes (Priority: P1)

An operator declares that one asset agent depends on another and asks it to run whenever its
upstream produces fresh output. Agent A produces `notes/daily`; agent B declares
`depends_on: [notes/daily]` and `on_upstream: true`. When A's partition for today materializes
and passes its blocking checks, B materializes on its own — no one clicks anything. The dependency
is an explicit, declared graph edge, replacing any "watch a folder for changes" arrangement.

**Why this priority**: This is the core promise of the feature — turning an implicit,
change-watching arrangement into an explicit dependency graph where an upstream materialization
directly drives a downstream one. Without it none of the rest (handoff, backfill, governors) has a
reason to exist. It is the MVP and delivers value on its own.

**Independent Test**: Configure A → B with B's `on_upstream: true`, turn on B's automation, then
materialize A's today partition. Confirm B materializes for the matching partition without any
manual action against B.

**Acceptance Scenarios**:

1. **Given** A produces `notes/daily` and B has `depends_on: [notes/daily]` with
   `on_upstream: true` and its automation turned on, **When** A's today partition materializes and
   its blocking checks pass, **Then** B materializes for the matching partition with no manual
   action.
2. **Given** the same setup where A has a **blocking** check that fails on this materialization,
   **When** A materializes, **Then** B does **not** fire.
3. **Given** that failing blocking check is then fixed, **When** A materializes again with the check
   passing, **Then** B fires.
4. **Given** B's `on_upstream` trigger has never been turned on, **When** A materializes, **Then** B
   does not fire until an operator enables B's automation (new triggers start paused).

---

### User Story 2 - Hand upstream outputs to the downstream container (Priority: P1)

When a downstream asset fires because of an upstream, its container is told what the upstream
produced so its prompt can use it. At launch, for each declared upstream the container receives an
environment variable `AGENTBOX_UPSTREAM_<KEY>` (the asset key upper-snaked) whose value is the path
to a small read-only JSON file. That file lists the upstream's latest materialization for the
matching partition: the upstream's output file paths, its report metadata, and its materialization
time. The prompt can be instructed to read the file.

**Why this priority**: Triggering a downstream run is only half of a dependency — the downstream
agent has to be able to act on what changed upstream. The handoff is what makes the graph useful
rather than merely a firing mechanism, so it ships alongside the trigger as part of the MVP.

**Independent Test**: With A → B and B fired by A's materialization, inspect B's container
environment and confirm `AGENTBOX_UPSTREAM_NOTES_DAILY` is set to a readable JSON file that lists
A's output paths, report metadata, and materialization time for the matching partition.

**Acceptance Scenarios**:

1. **Given** B depends on `notes/daily` and fires from A's materialization, **When** B's container
   launches, **Then** `AGENTBOX_UPSTREAM_NOTES_DAILY` is present and points at a JSON file listing
   A's latest matching-partition output paths, report metadata, and materialization time.
2. **Given** the handoff file, **When** B's container reads it, **Then** the file is read-only to
   the container and cannot be modified.
3. **Given** B declares more than one upstream, **When** B launches, **Then** one
   `AGENTBOX_UPSTREAM_<KEY>` variable is present per declared upstream, each pointing at its own
   handoff file.

---

### User Story 3 - Materialize a partition that has never been produced (Priority: P2)

An operator wants an asset to fill in a partition it has never produced, without wiring it to an
upstream event. Setting `on_missing: true` makes the asset materialize when its current/latest expected partition
(today for a daily asset; the single partition for an unpartitioned asset) has never been produced;
it does not backfill older historical partitions. Like `on_upstream`, this is an automation
condition on the asset controlled by the same paused `autocond_<name>` sensor.

**Why this priority**: Backfilling never-produced partitions is a distinct, valuable trigger, but
it is secondary to reacting to upstream changes and is independently testable, so it follows the
core upstream flow.

**Independent Test**: Give an asset `on_missing: true`, turn on its automation for a partition that
has never materialized, and confirm the asset materializes that partition on its own; confirm it
does not re-fire once the partition exists.

**Acceptance Scenarios**:

1. **Given** an asset with `on_missing: true` and its automation on, **When** a partition has never
   been produced, **Then** the asset materializes that partition without manual action.
2. **Given** the same asset after that partition exists, **When** the sensor next evaluates, **Then**
   `on_missing` does not fire again for that partition.
3. **Given** an asset with both `on_upstream: true` and `on_missing: true`, **When** either
   condition holds, **Then** the asset materializes, both conditions living behind the one
   `autocond_<name>` sensor.

---

### User Story 4 - Reject dependency cycles at load (Priority: P2)

An operator who accidentally wires a loop into the dependency graph is told immediately. If an
asset ends up depending on itself directly or transitively (e.g. B depends on C which depends on
B), reloading fails and the error names the assets in the cycle, so the mistake is fixed before any
automation runs.

**Why this priority**: A cycle would let automated runs trigger each other endlessly; catching it
at load — with a message that names the offending assets — is essential for safety but builds on
the dependency declaration, so it follows the core trigger and handoff.

**Independent Test**: Declare B → C → B (B depends on C, C depends on B), reload, and confirm the
reload fails with an error that names the assets forming the cycle.

**Acceptance Scenarios**:

1. **Given** `depends_on` edges that form a cycle (direct or transitive), **When** the
   configuration is loaded, **Then** the load fails and the error names the assets in the cycle.
2. **Given** an acyclic dependency graph, **When** the configuration is loaded, **Then** it loads
   successfully.
3. **Given** a `depends_on` entry naming an asset key that does not exist, **When** the
   configuration is loaded, **Then** the load fails naming the missing asset key.

---

### User Story 5 - Cap automated run rate and chain depth (Priority: P3)

An operator bounds how much automated chaining can happen so a busy graph cannot run away. In
`config/settings.yaml`, `max_runs_per_hour` (default 12) caps automated runs per hour, and
`max_chain_depth` (default 5) caps how deep an automated chain of triggers may go; every automated
run carries a `chain_depth` tag. A run that would exceed either limit is refused, logged, and
skipped — visibly in the daemon log. Manual runs bypass both limits. Both governors are editable on
the Settings page.

**Why this priority**: The governors are a safety valve rather than core functionality — the graph
works without them — but they protect a constrained host from runaway chains, so they ship after
the trigger, handoff, and cycle-safety slices.

**Independent Test**: Set `max_runs_per_hour: 2`, trigger three automated materializations within an
hour, and confirm the third is refused and logged. Separately, chain A → B → C → D → E → F with
`max_chain_depth: 5` and confirm F is refused for exceeding the depth.

**Acceptance Scenarios**:

1. **Given** `max_runs_per_hour: 2`, **When** three automated materializations are triggered within
   one rolling 60-minute window, **Then** the third is refused, skipped, and the refusal is visible
   in the daemon log.
2. **Given** `max_chain_depth: 5` and an automated chain A → B → C → D → E → F, **When** the chain
   reaches F (depth 6), **Then** F's automated run is refused and logged.
3. **Given** an automated run is refused by either governor, **When** an operator triggers the same
   agent **manually**, **Then** the manual run proceeds — manual runs bypass both governors.
4. **Given** the Settings page, **When** an operator edits `max_runs_per_hour` or
   `max_chain_depth`, **Then** the new values persist to `config/settings.yaml` and take effect on
   reload.

---

### Edge Cases

- **Upstream materializes but its blocking check fails**: The downstream does not fire; a blocking
  failure gates downstream automation while the upstream still counts as materialized.
- **Partitioned upstream/downstream mapping**: Upstream and downstream partitions map one-to-one by
  the same partition kind (daily → daily); a today upstream drives the today downstream. Non-identity
  mappings are out of scope.
- **Partitioned `on_upstream` misbehaving**: If the daily one-to-one mapping cannot be made to work
  reliably for partitioned assets in this release, `on_upstream` is restricted to unpartitioned
  assets and that restriction is stated (see Assumptions).
- **Missing or unknown upstream asset key**: A `depends_on` entry naming a non-existent asset is
  rejected at load naming the missing key.
- **Self- or transitive dependency cycle**: Rejected at load with the offending assets named.
- **Governor refusal**: A refused automated run is logged and skipped, not queued or retried
  silently; the operator can see it in the daemon log. A refused run does not consume a
  `max_runs_per_hour` slot — only runs that actually launch count against the rolling window.
- **Upstream with no matching-partition materialization**: When a downstream fires from one upstream
  but another declared upstream has no materialization for the matching partition, that upstream's
  `AGENTBOX_UPSTREAM_<KEY>` is still set and points at a handoff file marked as "no materialization"
  (null/empty fields).
- **Upstream has multiple materializations**: The handoff file reflects the upstream's *latest*
  materialization for the matching partition.

## Requirements *(mandatory)*

### Functional Requirements

**Dependency declaration & graph**

- **FR-001**: An asset agent MUST be able to declare `produces.depends_on` as a list of asset keys
  it depends on (other agents' produced assets, or external assets introduced later).
- **FR-002**: The system MUST reject at load any `depends_on` entry that names an asset key which
  does not exist, and the error MUST name the missing key.
- **FR-003**: The system MUST reject at load any `depends_on` graph that contains a cycle (direct or
  transitive), and the error MUST name the assets forming the cycle.

**Upstream trigger (`on_upstream`)**

- **FR-004**: `triggers:` MUST accept `on_upstream: true` as an asset-kind trigger that materializes
  the asset when any declared upstream materializes and passes its blocking checks.
- **FR-005**: `on_upstream` MUST be expressed as an automation condition on the asset, controlled by
  the same paused `autocond_<name>` sensor used for existing asset automation, and MUST start paused
  until an operator turns it on.
- **FR-006**: A downstream MUST NOT fire on an upstream materialization whose **blocking** check
  failed; it MUST fire once that materialization's blocking checks pass.
- **FR-007**: For partitioned assets, upstream and downstream partitions MUST map one-to-one by the
  same partition kind (daily → daily) by default; an upstream partition drives the matching
  downstream partition.

**Missing-partition trigger (`on_missing`)**

- **FR-008**: `triggers:` MUST accept `on_missing: true` as an asset-kind trigger that materializes
  the asset for its current/latest expected partition (today for a daily asset; the single partition
  for an unpartitioned asset) when that partition has never been produced. `on_missing` MUST NOT
  backfill older historical partitions.
- **FR-009**: `on_missing` MUST be expressed as an automation condition on the asset behind the same
  `autocond_<name>` sensor, MUST start paused, and MUST NOT re-fire for a partition once it exists.
- **FR-010**: When an asset declares both `on_upstream` and `on_missing`, materialization MUST occur
  when either condition holds, both living behind the one `autocond_<name>` sensor.

**Upstream handoff**

- **FR-011**: At launch, for each declared upstream the downstream container MUST receive an
  environment variable named `AGENTBOX_UPSTREAM_<KEY>`, where `<KEY>` is the upstream asset key
  upper-snaked.
- **FR-012**: Each `AGENTBOX_UPSTREAM_<KEY>` MUST point at a read-only JSON file listing the
  upstream's latest materialization for the matching partition: its output file paths, its report
  metadata, and its materialization time.
- **FR-012a**: When a declared upstream has no materialization for the matching partition (for
  example, the downstream fired from a different upstream), its `AGENTBOX_UPSTREAM_<KEY>` variable
  MUST still be present and MUST point at a handoff file whose materialization fields are null/empty,
  explicitly marking "no materialization" for that partition.
- **FR-013**: The handoff file MUST be read-only to the container (a container cannot modify it),
  consistent with agents never reading or modifying prior runs' output except through this
  explicit handoff.

**Governors**

- **FR-014**: `config/settings.yaml` MUST support `max_runs_per_hour` (default 12), enforced before
  launching any automated run against a **rolling 60-minute window** (the count of automated runs
  launched in the trailing 60 minutes); a run that would exceed it MUST be refused, logged, and
  skipped. Only runs that actually launch count toward the window; a refused run does not consume a
  slot.
- **FR-015**: Every automated run MUST carry a `chain_depth` tag recording how deep in a trigger
  chain it is. A root automated run (one initiated by a schedule or `on_missing`, or fired by a
  manual upstream) MUST carry `chain_depth` 1; a run fired by an upstream automated run MUST carry
  that upstream run's `chain_depth` + 1.
- **FR-016**: `config/settings.yaml` MUST support `max_chain_depth` (default 5); an automated run
  whose `chain_depth` would exceed it MUST be refused and logged.
- **FR-017**: Manual runs MUST bypass both `max_runs_per_hour` and `max_chain_depth`.
- **FR-018**: `max_runs_per_hour` and `max_chain_depth` MUST be editable on the Settings page and
  MUST persist to `config/settings.yaml`.

**Schema, UI & docs**

- **FR-019**: The create/edit agent form MUST present a "Depends-on" card for declaring
  `produces.depends_on`.
- **FR-020**: The Automation view MUST present the two new asset trigger kinds (`on_upstream`,
  `on_missing`) alongside the existing `asset_schedule`.
- **FR-021**: The README MUST document `depends_on`, the two new trigger kinds, the upstream handoff
  env var and file, and the two governors.

### Key Entities *(include if feature involves data)*

- **Dependency edge (`depends_on`)**: A declared directed edge from a downstream asset to an
  upstream asset key it depends on. The set of edges forms the dependency graph, which must be
  acyclic and reference only existing assets.
- **Asset trigger kind**: The kind of automation condition on an asset — `asset_schedule` (existing),
  `on_upstream`, or `on_missing` — all controlled by the asset's paused `autocond_<name>` sensor.
- **Upstream handoff record**: The read-only JSON file, referenced by `AGENTBOX_UPSTREAM_<KEY>`,
  describing an upstream's latest materialization for the matching partition — output file paths,
  report metadata, and materialization time.
- **Run governor**: An instance-level limit in `config/settings.yaml` — `max_runs_per_hour` and
  `max_chain_depth` — applied to automated runs and bypassed by manual runs.
- **Chain depth**: A tag on each automated run recording how deep in a trigger chain the run sits,
  compared against `max_chain_depth`. A root automated run is depth 1; each downstream run is the
  triggering upstream run's depth + 1.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can make a downstream asset materialize automatically on an upstream's
  materialization purely by declaring `depends_on` and `on_upstream` and turning the trigger on —
  with zero manual action against the downstream.
- **SC-002**: A downstream fired by an upstream can, in its prompt, read exactly what the upstream
  produced (output paths, report metadata, materialization time) via the handoff file, without
  scanning the filesystem for changes.
- **SC-003**: An upstream materialization whose blocking check fails triggers no downstream run;
  fixing the check and re-materializing does trigger the downstream.
- **SC-004**: A dependency cycle or a reference to a non-existent asset is caught at load 100% of the
  time, with the offending assets named, before any automation runs.
- **SC-005**: With `max_runs_per_hour: 2`, the third automated run within any rolling 60-minute
  window is refused and observable in the daemon log; with `max_chain_depth: 5`, the sixth link in an
  automated chain is refused.
- **SC-006**: A manual run always proceeds even when a governor has just refused the equivalent
  automated run.

## Assumptions

- The `produces:` block and asset nature (spec 004), asset checks and blocking/non-blocking
  semantics (spec 008), the `triggers:` block with `asset_schedule` and the paused `autocond_<name>`
  sensor (spec 006), and the `config/settings.yaml` instance-settings file and Settings page (spec
  012) all already exist; this feature extends them rather than redefining them.
- Partition kinds are limited to `none` (unpartitioned) and `daily` as today; the one-to-one
  partition mapping is daily → daily.
- **Null action / fallback**: If `on_upstream` cannot be made to behave reliably on partitioned
  assets under the daily one-to-one mapping in this release, `on_upstream` is restricted to
  unpartitioned assets and the README states that restriction explicitly.
- External assets (from spec 017) are a valid `depends_on` target conceptually, but sensors on
  external systems are out of scope here; only assets produced within Agentbox are exercised.
- "Automated run" means any run initiated by an automation condition/sensor or schedule; "manual
  run" means an operator materializing or launching by hand from the UI or Dagster.
- Crons and automation conditions continue to run in the box timezone as established previously.

## Out of Scope

- Fan-in of many upstream partitions to one downstream partition.
- Non-identity partition mappings (e.g. daily → weekly).
- Sensors on external systems (deferred to spec 017).
