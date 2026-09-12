# Feature Specification: Structured Run Reports via Dagster Pipes

**Feature Branch**: `run-reports-via-pipes`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Stop scraping the container's stdout to guess what happened. Each run hands Dagster a structured report, recorded as materialization metadata (or run metadata for job-only agents). Failed runs of asset agents are recorded, not thrown away."

## Clarifications

### Session 2026-09-11

- Q: In the run report, what should the `files_written` field contain? → A: An integer count. The full path list stays in the existing output-file snapshot metadata; the report field is a quick scannable count.
- Q: Where does the `notes` field come from? → A: The run's final assistant message (the last text the model emitted), extracted from the harness's native events. No new prompt convention is introduced.
- Q: On a timeout/failed run where usage couldn't be measured, what do `tokens_in`, `tokens_out`, and `turns` hold? → A: `null` when unknown. These numeric fields are nullable, so "unmeasured" stays distinct from a genuine zero (matching how `cost_usd` uses null).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every run reports itself in a single structured shape (Priority: P1)

An operator opens a completed run (or its materialization) in the Dagster UI and sees a
structured report attached: the run's status, tokens in and out, cost, turn count, files
written, transcript path, any error, and the agent's free-text end-of-run note. The report
looks the same for every harness (api, claude-code, pi, codex) — the operator no longer has
to know which harness ran, nor read raw stdout, to understand what happened.

**Why this priority**: This is the core value. Today the orchestrator parses each harness's
native stdout events after the container exits to reconstruct a summary, with a separate code
path per harness. A single, uniform, self-describing report is the thing every downstream
consumer (a human reading the UI, a future check, a future cost rollup) needs first.

**Independent Test**: Run one agent of each harness. Confirm every run's materialization (or
run metadata) shows all report fields populated with real numbers, in the same shape, with
`cost_usd` present for api/pi and null for claude-code/codex.

**Acceptance Scenarios**:

1. **Given** an api agent, **When** it runs to completion, **Then** its materialization shows `status = ok` with real `tokens_in`, `tokens_out`, `cost_usd`, `turns`, `files_written`, `transcript_path`, `error = null`, and `notes`.
2. **Given** a claude-code agent, **When** it runs to completion, **Then** the same report fields are present and `cost_usd` is null (subscription).
3. **Given** a pi agent, **When** it runs to completion, **Then** the report shows a non-null `cost_usd`.
4. **Given** a codex agent, **When** it runs to completion, **Then** the report is present and `cost_usd` is null (subscription).
5. **Given** any completed run, **When** the operator views it, **Then** the `notes` field is legible in the Dagster UI without opening the transcript file.

---

### User Story 2 - Failed asset runs are recorded, not thrown away (Priority: P1)

An operator looks at a partitioned asset in the Dagster UI. A partition whose run failed shows
red **with the report attached** — status, error, and transcript path all present — instead of
showing no materialization at all. The operator can see what a failed partition attempted and
why it failed, directly from the asset view.

**Why this priority**: Today a non-successful asset run raises and produces no materialization,
so the partition looks unattempted and the diagnostic context is lost to stdout. Recording the
failure as a materialization with `status: failed` is the difference between an auditable
history and a silent gap.

**Independent Test**: Force a claude-code asset agent to fail (e.g. cap it so it cannot finish).
Confirm the partition materializes with `status: failed`, an `error` that explains, a present
`transcript_path`, and that the run itself is marked failed.

**Acceptance Scenarios**:

1. **Given** an asset agent whose run cannot complete successfully, **When** the run ends, **Then** the partition shows a materialization carrying `status: failed` and the full report, and the run is marked failed.
2. **Given** the same failed partition, **When** the operator inspects it, **Then** `error` explains the failure and `transcript_path` points to the saved transcript.
3. **Given** a job-only agent (no asset), **When** its container exits non-zero, **Then** the run is marked failed (behavior unchanged) and the report is attached to the run as run metadata.

---

### User Story 3 - Logs stream live while the run is in flight (Priority: P2)

An operator watching a claude-code run in the Dagster run page sees the agent's tool calls and
output appear **as they happen**, not in one dump after the container exits. Long runs become
observable in real time.

**Why this priority**: Valuable for monitoring and debugging in-flight runs, but the structured
report (P1) is what most consumers depend on. Live streaming improves the experience of watching
a run without changing what a finished run records.

**Independent Test**: Start a claude-code run and watch the Dagster run page; confirm tool-call
events appear during execution rather than only at the end.

**Acceptance Scenarios**:

1. **Given** a claude-code run in progress, **When** the operator watches the Dagster run page, **Then** tool calls and output appear in the run log while the container is still running.

---

### Edge Cases

- **Timeout**: `timeout_seconds` still kills the container. If the container is killed before it
  can write its own report, the orchestrator writes a report on its behalf with `status: timeout`
  and `null` for any numeric field it could not measure (`tokens_in`, `tokens_out`, `turns`,
  `cost_usd`); after the run ends the container is gone. The report is attached the same way as any
  other.
- **Missing or unreadable report on a normal exit**: If a container exits without a readable,
  well-formed report, the run is treated as failed with an `error` explaining the report was
  missing or malformed, so the absence is itself recorded rather than silently ignored.
- **Cost unknown**: For subscription harnesses (claude-code, codex) `cost_usd` is null; a null
  cost is a valid report, not an error.
- **Job-only agents**: Retain today's semantics — a non-zero container exit raises and fails the
  run; the report rides along as run metadata rather than as a materialization.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every harness image MUST write a run report before its container exits, produced
  from that harness's own native events (the per-harness parsing that lives in the orchestrator
  today moves into each image).
- **FR-002**: The report MUST use one JSON shape across all harnesses, with fields: `status`
  (one of `ok`, `failed`, `timeout`), `tokens_in`, `tokens_out`, `turns` (each an integer, or
  `null` when the run could not measure it — e.g. a timeout), `cost_usd` (null if unknown),
  `files_written` (an integer count of files the run wrote), `transcript_path`,
  `error` (string or null), and `notes` (free text — the agent's end-of-run note to its future
  self, taken from the run's final assistant message; no new prompt convention is added). The full
  list of output file paths is not part of the report; it stays in the existing output-file
  snapshot metadata (FR-005).
- **FR-003**: The orchestrator MUST receive each run's logs live and stream them into the Dagster
  run log while the container is running, rather than only after it exits.
- **FR-004**: The orchestrator MUST read the report from the run and attach every report field as
  metadata — as materialization metadata for asset agents, as run metadata for job-only agents.
- **FR-005**: The attached metadata MUST include, alongside the report fields, the existing
  metadata a run records today: output files, transcript path, run stamp, session id, harness,
  model, and (when partitioned) partition.
- **FR-006**: The per-run transcript `.jsonl` MUST continue to be written exactly as it is today.
- **FR-007**: For an asset agent, a report `status` other than `ok` MUST still produce a
  materialization — carrying `status: failed` and the full report — and MUST mark the run failed,
  so the partition shows red with the report attached rather than showing no materialization.
- **FR-008**: For a job-only agent, behavior MUST be unchanged: a non-zero container exit raises
  and fails the run, with the report attached to the run as run metadata.
- **FR-009**: When `timeout_seconds` elapses, the orchestrator MUST kill the container and ensure
  a report with `status: timeout` is recorded — written by the orchestrator if the container could
  not write its own — and the container MUST be gone after the run ends.
- **FR-010**: The `notes` field MUST be visible in the Dagster UI without opening the transcript.
- **FR-011**: All agent-run isolation currently applied MUST be preserved unchanged — network
  attachment, credential mounts, and environment passthrough-by-name. No isolation guarantee may
  be dropped or weakened in order to adopt the new launch mechanism.

### Key Entities *(include if data involves data)*

- **Run report**: The single structured record a run hands back. One JSON object with a fixed set
  of fields (`status`, `tokens_in`, `tokens_out`, `cost_usd`, `turns`, `files_written` [integer
  count], `transcript_path`, `error`, `notes`). Produced by the harness image, or by the orchestrator when
  the container cannot produce it (timeout, crash before writing). It is the canonical answer to
  "what happened in this run."
- **Run metadata / materialization metadata**: The set of fields Dagster displays for a run or a
  materialized partition. After this feature it is the union of the report fields and the existing
  run-context fields (output files, transcript, stamp, session id, harness, model, partition).
- **Harness image**: A container image for one runtime (api, claude-code, pi, codex). Each now owns
  translating its native run events into the common report shape.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every harness (api, claude-code, pi, codex), a completed run's report shows all
  fields populated with real values; `cost_usd` is null only for claude-code and codex.
- **SC-002**: The orchestrator contains zero per-harness stdout-parsing code paths for producing
  the run summary — reconstructing what happened no longer depends on scraping container stdout.
- **SC-003**: A forced-failure asset run (an agent capped so it cannot finish) produces a visible
  materialization on its partition with `status: failed`, an explanatory `error`, a present
  `transcript_path`, and a run marked failed — 100% of the time, versus no materialization today.
- **SC-004**: A run with `timeout_seconds` set short enough to trip records `status: timeout`, and
  no container from that run remains after the run ends.
- **SC-005**: While a claude-code run is in flight, an operator can see its tool calls in the
  Dagster run page before the container exits.
- **SC-006**: An operator can read the agent's end-of-run `notes` for any run directly in the
  Dagster UI without opening the transcript file.
- **SC-007**: Every isolation flag applied to agent launches before this feature is still applied
  after it (verifiable by comparing the launched-container configuration).

## Assumptions

- **Launch mechanism**: The intended mechanism is Dagster Pipes over a Docker launch, which is
  what delivers live log streaming. If the Pipes Docker client cannot express the isolation flags
  the current launch relies on (network attachment, tmpfs/credential mounts, environment
  passthrough by name), the existing `docker run` launch is kept and the Pipes protocol is
  implemented over a mounted messages file. No isolation flag is dropped to make Pipes fit
  (FR-011). This is a constraint on how the feature is built, not a user-visible behavior.
- **Report ownership**: Each harness image's entrypoint/runner is the normal author of the report;
  the orchestrator authors it only as a fallback when the container cannot (timeout, early crash).
- **`files_written` in the report** is the harness's own account of files it wrote; the existing
  output-file snapshot metadata (diffing the output directory) is retained alongside it, not
  replaced.
- **Existing schema untouched**: The `produces`/`job` agent-definition schema is unchanged; report
  fields surface as metadata only and require no new agent-config keys.
- **Out of scope**: Acting on the report (health checks, escalation, alerting), cost aggregation
  across runs, and output-file naming conventions are explicitly not part of this feature.
- **Verification agents**: Exercising all four report producers end-to-end requires one agent per
  harness (api, claude-code, pi, codex), plus a capped agent and a short-`timeout_seconds` agent to
  force the failure and timeout paths. Existing enabled agents already cover claude-code, pi, and
  codex; the api-harness agent and the failure/timeout fixtures are provisioned as part of this
  feature (they do not otherwise exist as runnable agents today).
