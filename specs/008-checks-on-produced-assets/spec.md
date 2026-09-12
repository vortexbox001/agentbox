# Feature Specification: Checks on Produced Assets

**Feature Branch**: `008-checks-on-produced-assets`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "An agent YAML can declare checks that run after the asset is produced, each a command that passes or fails. Results attach to the asset in Dagster. Checks are generic commands — agentbox doesn't know whether they're tests, linters, or a script that counts files."

## Clarifications

### Session 2026-09-12

- Q: When the producing run itself is non-`ok` (failed or timed out per spec 007), do checks still run on whatever output exists, or are they skipped? → A: Checks still run. The output directory and `/report.json` exist even for a failed/timed-out producer, so a partial output can still be inspected; checks run and report their own pass/fail independently of the producing run's status.
- Q: Should a check container get network access, and if so how is it decided? → A: No network by default (checks are isolated observers). A check opts in with an optional `network:` field, using the same network choices as an agent (`agentnet-isolated`, `agentnet`, `bridge`).
- Q: How is a check's `command` interpreted — a shell command line or a literal argument list? → A: A shell string, run via `sh -c "<command>"`, so command substitution, pipes, `&&`, and shell builtins (e.g. `false`) all work.
- Q: When an agent declares multiple checks, do they run sequentially or in parallel? → A: Sequentially, in declared order; each check has its own independent `timeout_seconds`, and every declared check runs and reports (no early stop on a blocking failure).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare a check that gates an asset (Priority: P1)

An operator adds a `checks:` list to an asset agent's `produces:` block. Each entry gives
a check a `name` and a `command`. After the agent's container finishes and the asset is
produced, agentbox runs each check in a fresh container that can see the run's output (read
only) and its run report. A check that exits 0 passes; anything else fails. The result of
every check appears on the asset in Dagster as an asset check — green when it passed, red when
it failed — so the operator can tell at a glance not just that a partition materialized, but
whether what it produced is acceptable.

**Why this priority**: This is the core of the feature. Without it there is no way to attach a
pass/fail verdict about an asset's content to the asset itself. It delivers the central value —
a produced asset that carries its own acceptance verdicts — on its own, with a single check.

**Independent Test**: Add one check to an asset agent — `name: has-output`,
`command: test -n "$(ls /output)"` — trigger a materialization, and confirm the asset shows a
single asset check named `has-output` that is green when the run wrote a file (and would be red
when the output directory is empty), with the check's captured output attached.

**Acceptance Scenarios**:

1. **Given** an asset agent with one check `test -n "$(ls /output)"`, **When** the agent runs and writes a file, **Then** the asset shows an asset check `has-output` that passed, with its command output attached as metadata.
2. **Given** the same agent whose run produced no output file, **When** the check runs, **Then** the asset check `has-output` fails.
3. **Given** any check, **When** it finishes, **Then** its result carries the last 4 KB of the check's combined stdout/stderr as metadata.

---

### User Story 2 - Blocking vs. non-blocking checks (Priority: P1)

An operator marks one check `blocking: false` and leaves another at the default. Both run and
both show their result on the asset. The blocking check, when it fails, marks the asset's health
as failing and prevents downstream automation from firing on that materialization; the
non-blocking check, when it fails, is visible as a red check but does not block anything and does
not stop the asset from counting as materialized.

**Why this priority**: The distinction between "this must pass for the asset to be usable" and
"report this but don't gate on it" is what makes checks safe to add incrementally. Without it,
every check would be all-or-nothing and operators could not add advisory checks.

**Independent Test**: Add two checks to an asset agent — one `command: false` with
`blocking: false`, and one that passes. Materialize the asset and confirm: the asset still counts
as materialized, both checks appear, the non-blocking one shows failed, and the failed
non-blocking check does not block downstream automation.

**Acceptance Scenarios**:

1. **Given** a non-blocking check `command: false`, **When** the agent runs, **Then** the asset still counts as materialized, the check shows failed, and nothing downstream is blocked.
2. **Given** a blocking check that fails, **When** the agent runs, **Then** the asset's check shows failed and downstream automation does not fire on that materialization.
3. **Given** a check with no `blocking` field, **When** it is loaded, **Then** it is treated as blocking (default true).

---

### User Story 3 - A check sees the output but cannot change it (Priority: P2)

An operator wants confidence that a check inspects an asset without altering it. Each check
container mounts the output directory read-only at `/output`, the workspace (when the agent has
one) read-only at `/workspace`, and the run report at `/report.json`. A check that tries to write
into `/output` fails because the mount is read-only, and the produced asset is never modified by
its own checks.

**Why this priority**: Read-only isolation is what lets an operator trust that checks are
observers, not editors. It is essential to the feature's integrity but rides on top of the core
run-and-attach mechanism (US1), so it is P2.

**Independent Test**: Add a check whose command writes to `/output` (e.g.
`touch /output/x`). Materialize the asset and confirm the check fails with a read-only /
permission error in its captured output, and the output directory is unchanged.

**Acceptance Scenarios**:

1. **Given** a check that writes to `/output`, **When** it runs, **Then** it fails and its output shows a read-only/permission error.
2. **Given** any check, **When** it runs, **Then** it can read the produced files at `/output`, the workspace (if any) at `/workspace`, and the run report at `/report.json`.
3. **Given** a check, **When** it runs, **Then** it neither adds, removes, nor modifies any file in the output directory.

---

### User Story 4 - A check that runs too long is failed with a timeout (Priority: P2)

An operator sets `timeout_seconds` on a check. If the check's command runs longer than that, the
check container is killed and the check is reported failed, with its metadata noting the timeout,
so a hung check never blocks the asset indefinitely.

**Why this priority**: Bounds every check so a runaway command can't stall the pipeline; important
for reliability but secondary to checks existing and gating at all.

**Independent Test**: Add a check `command: sleep 60` with `timeout_seconds: 2`. Materialize the
asset and confirm the check is reported failed with `timeout` present in its metadata, and no
check container from that run survives.

**Acceptance Scenarios**:

1. **Given** a check whose command exceeds its `timeout_seconds`, **When** it runs, **Then** the check is reported failed and its metadata records that it timed out.
2. **Given** a timed-out check, **When** the run ends, **Then** no check container from that run remains.

---

### User Story 5 - Checks require an asset (Priority: P2)

An operator can only declare checks on an agent that produces an asset. In the management UI, the
Checks card is hidden for a job-only agent (one with no `produces`), and at load the orchestrator
rejects an agent file that declares `checks` without a `produces` asset, naming the offending
file while other agents still load.

**Why this priority**: A check attaches to an asset, so "checks without an asset" is meaningless.
Rejecting it early (both in the editor and at load) keeps the config honest, but it is a guardrail
around the core, not the core.

**Independent Test**: Open a job-only agent in the UI and confirm no Checks card is shown. Hand
the orchestrator an agent file that names `checks` but no `produces` asset and confirm that file
is rejected with a message naming it, while every valid agent still loads.

**Acceptance Scenarios**:

1. **Given** a job-only agent (no `produces`), **When** an operator edits it in the UI, **Then** no Checks card is shown.
2. **Given** an agent file declaring `checks` without a `produces` asset, **When** the orchestrator loads, **Then** that file is rejected with a message naming it and the remaining agents load normally.

---

### Edge Cases

- **No checks declared**: An asset agent with no `checks` behaves exactly as today — the asset
  materializes with no asset checks attached. Checks are purely additive.
- **Check runs regardless of run outcome**: When the producing run itself fails or times out (a
  red materialization carrying `status: failed`/`timeout` from spec 007), the checks still have an
  output directory and a `/report.json` to inspect, so they still run and report their own pass/fail
  independently of the producing run's status (see Assumptions).
- **Check container image missing/unpullable**: If a check names an `image` that cannot be
  resolved, that check is reported failed with an explanatory message in its metadata, rather than
  failing the whole materialization silently.
- **Agent has no workspace**: `/workspace` is only mounted when the agent defines a workspace; a
  check on a workspaceless agent simply has no `/workspace` mount and must not assume one.
- **Duplicate check names within one agent**: Two checks sharing a `name` are rejected at load
  (asset-check names must be unique on an asset), with a message naming the file.
- **Output larger than 4 KB**: Only the last 4 KB of a check's combined stdout/stderr is retained
  as metadata; the truncation is applied to the tail so the end of the output (usually the failure)
  is what's kept.
- **Partition attach limitation**: If this Dagster version cannot attach an asset-check result to a
  specific partition, the result is attached unpartitioned and the partition key is recorded in the
  check's metadata (see FR-014).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An asset agent's `produces:` block MUST accept an optional `checks:` list. Each entry
  has a required `name` (unique within the agent) and a required `command`; and optional `image`
  (default: the agent's harness image), `blocking` (default true), `timeout_seconds`, and `network`
  (default: no network; see FR-016).
- **FR-002**: After the producing container finishes and the asset is produced, the orchestrator
  MUST run each declared check as a command in a fresh container, and MUST treat exit code 0 as
  pass and any non-zero exit as fail. The `command` MUST be run as a shell command line (via
  `sh -c`), so command substitution, pipes, `&&`, and shell builtins are available.
- **FR-003**: Each check container MUST mount the run's output directory read-only at `/output`,
  the agent's workspace (when it has one) read-only at `/workspace`, and the run report (spec 007)
  at `/report.json`.
- **FR-004**: A check MUST run in the image named by its `image`, defaulting to the producing
  agent's harness image when `image` is omitted.
- **FR-005**: Each declared check MUST surface as a Dagster asset check on the produced asset,
  named by the check's `name`, showing passed or failed.
- **FR-006**: A failed **blocking** check MUST mark the asset's check as failed in a way that
  prevents downstream automation (spec 010) from firing on that materialization; a failed
  **non-blocking** check MUST show as failed but MUST NOT block downstream automation and MUST NOT
  prevent the asset from counting as materialized.
- **FR-007**: The last 4 KB of each check's combined stdout/stderr MUST be attached to that
  check's result as metadata.
- **FR-008**: A check whose command exceeds its `timeout_seconds` MUST be killed and reported
  failed, with its metadata recording that it timed out; no check container from that run may
  survive the run.
- **FR-009**: Because `/output` and `/workspace` are mounted read-only, a check that attempts to
  write to them MUST fail, and a check MUST NOT be able to add, remove, or modify any file in the
  produced output.
- **FR-010**: An agent that does not declare a `produces` asset MUST NOT be allowed to declare
  `checks`: the orchestrator MUST reject such a file at load with a message naming it, while all
  other agents still load.
- **FR-011**: The management UI MUST present a Checks card under the Job/Produces area only for an
  agent that produces an asset, and MUST hide it for a job-only agent.
- **FR-012**: The agent-definition schema, the YAML template comments, and the README MUST be
  updated to document the `checks:` list and each check field.
- **FR-013**: An asset agent with no `checks` MUST behave exactly as before this feature — the
  asset materializes with no asset checks and no change to existing metadata.
- **FR-014**: If this Dagster version cannot attach an asset-check result per partition, the
  result MUST be attached unpartitioned and the partition key recorded in the check's metadata;
  the limitation MUST be noted in the plan.
- **FR-015**: A check that cannot be run because its named `image` cannot be resolved MUST be
  reported failed with an explanatory message in its metadata, rather than being silently skipped
  or aborting the materialization.
- **FR-016**: A check container MUST run with no network by default. A check MAY opt in to a
  network via an optional `network` field that accepts the same choices as an agent
  (`agentnet-isolated`, `agentnet`, `bridge`); a check that omits `network` gets no network access.
- **FR-017**: When an agent declares more than one check, the checks MUST run sequentially in
  declared order, each with its own independent `timeout_seconds`. Every declared check MUST run
  and report its result; a failed blocking check MUST NOT short-circuit the remaining checks.

### Key Entities *(include if feature involves data)*

- **Check**: A named, generic pass/fail command declared inside an agent's `produces.checks` list.
  Fields: `name` (unique per agent), `command`, optional `image`, `blocking` (default true),
  `timeout_seconds`, `network` (default: none). agentbox attaches no meaning to what the command
  does — test, lint, count files — only to its exit code.
- **Check result**: The outcome of running one check: passed/failed, a blocking flag, the last
  4 KB of captured output, a timeout marker when it timed out, and (when needed) the partition key.
  Surfaces as a Dagster asset check on the produced asset.
- **Check container**: The fresh, short-lived container a check runs in, with `/output` and
  `/workspace` read-only and `/report.json` present. Distinct from the producing agent's container.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An asset agent with a check `test -n "$(ls /output)"` shows, on its asset, an asset
  check that is green when the run wrote a file and red when the output directory is empty — 100%
  of the time.
- **SC-002**: An asset agent with a `command: false`, `blocking: false` check materializes
  successfully with that check shown as failed, and the failed non-blocking check does not stop the
  asset from counting as materialized nor block downstream automation.
- **SC-003**: A blocking check that fails prevents downstream automation from firing on that
  materialization, verifiable by observing that no downstream run is triggered.
- **SC-004**: A check with `timeout_seconds` short enough to trip is reported failed with a
  timeout recorded in its metadata, and no check container from that run remains afterward.
- **SC-005**: A check that writes to `/output` fails with a read-only/permission error in its
  captured output, and the output directory is byte-for-byte unchanged by the check.
- **SC-006**: Every check's result carries at most the last 4 KB of its combined stdout/stderr.
- **SC-007**: A job-only agent shows no Checks card in the UI, and an agent file declaring `checks`
  without a `produces` asset is rejected at load with a message naming it while other agents load.

## Assumptions

- **Runs after production, in a separate container**: Checks are a post-production step; they never
  run inside the producing agent's container and never share its write access. Each check is its own
  container launched via the same Docker-outside-of-Docker mechanism used for agent runs, so its
  mounts resolve under `/data` on the host (consistent with existing agentbox mount handling).
- **Default image**: When a check omits `image`, it uses the producing agent's harness image, which
  is guaranteed present on the host because the agent just ran in it — so common checks
  (`test`, `ls`, shell one-liners) run with no extra image to build or pull.
- **Blocking gates automation, not materialization**: A blocking check's failure is expressed as a
  failed asset check that downstream automation (spec 010) consults before firing; the asset is
  still recorded as materialized (its content exists). This mirrors how spec 007 records a failed
  run rather than erasing it.
- **Checks run even when the producing run is non-`ok`**: A failed or timed-out producing run
  (spec 007) still leaves an output directory and a `/report.json`, so checks run against whatever
  output exists and report their own pass/fail; they are not skipped on account of the producer's
  status (see Clarifications, 2026-09-12).
- **Report location**: The run report mounted at `/report.json` is the same structured report
  defined in spec 007; checks read it but do not alter it.
- **Out of scope**: Escalating or alerting on failed checks (spec 016); checks for job-only agents;
  any built-in/known check types (all checks are opaque commands) — agentbox ships no test/lint
  presets as part of this feature.
- **Verification fixtures**: Exercising the pass, non-blocking-fail, timeout, and read-only paths
  requires an asset agent carrying those specific checks; such a fixture agent is provisioned as
  part of this feature's verification (it does not exist as a runnable agent today).
- **Schema version**: This feature extends the agent-definition schema (currently version 4) with
  the `produces.checks` list; the schema version is bumped accordingly and the template/README kept
  in step (FR-012).
