# Phase 0 Research: Checks on Produced Assets

All Technical-Context unknowns are resolved below — each a decision, its rationale, and the
alternatives rejected. Facts marked *(verified)* were checked against the running orchestrator's
Dagster 1.13.21 (`.venv`), by API-signature probes and in-process `materialize()` runs reading the
instance event log.

---

## R1 — Asset construction for a check-bearing asset: `@multi_asset`, not `from_op`

**Decision**: When an asset agent declares `produces.checks`, build the asset with
`@multi_asset(specs=[AssetSpec(key, partitions_def, automation_condition)],
check_specs=[AssetCheckSpec(name, asset, blocking) …])`. When it declares no checks, keep the
existing `AssetsDefinition.from_op(make_run_op(cfg), …)` path **unchanged** (FR-013).

**Rationale**:
- `AssetsDefinition.from_op` has **no `check_specs` parameter** *(verified — full signature has
  `keys_by_output_name`, `partitions_def`, `automation_conditions_by_output_name`, … but nothing
  for checks)*. An asset built with `from_op` therefore cannot carry asset checks at all.
- `multi_asset` **does** accept `check_specs` *(verified: `'check_specs' in signature(multi_asset)`
  is `True`)*, and its body may emit both the materialization and the check results.
- `AssetSpec` carries `partitions_def` and `automation_condition` *(verified)*, so the daily
  partition (spec 004/006) and the `on_cron` auto-condition (spec 006) reattach with no loss —
  `build_asset_automation_sensor` and `build_materializing_job` operate on the produced
  `AssetsDefinition` unchanged.

**Alternatives considered**:
- *Standalone `@asset_check` / `@multi_asset_check` op targeting the `from_op` asset* — **rejected**.
  Both exist *(verified)* and would keep the producing op untouched, but a check op is a **downstream
  step** of the producing op; when the producer step fails, Dagster **skips** it — violating the
  clarified requirement that checks still run when the producer is non-`ok` (see R4). It also cannot
  guarantee sequential-in-declared-order execution or share the producer's report in-process.
- *Convert **all** asset agents to `multi_asset`* — **rejected**. It would change the compute step
  shape/naming of existing checkless assets and risk their materialization history and per-asset
  sensor on/off state; FR-013 requires checkless behavior be exactly as before. Only agents that
  add checks (net-new) take the new path.

## R2 — One generator op runs producer **and** checks (checks always run)

**Decision**: The `multi_asset` body is a **generator op** that: (1) launches the producing
container through the shared launch+report core, (2) writes the report to `/report.json`, (3) runs
each declared check container sequentially, then (4) emits results. Because the checks run **inside
the same op** after the producer, they are never a skippable downstream step.

**Rationale**: This is the only structure that simultaneously satisfies: checks are declared on the
asset (R1); checks always run regardless of producer outcome (R4); results and the materialization
are emitted together in one step; and the launch stays defined once (the core is shared with the
checkless `make_run_op`). Sequential in-body iteration gives FR-017 (declared order, per-check
timeout, every check runs, no short-circuit) for free.

## R3 — Emission on producer **success**: `MaterializeResult(check_results=…)`; blocking semantics

**Decision**: On producer success (`status == "ok"`, exit 0, not timed out) the op yields a single
`MaterializeResult(asset_key, metadata=<the spec-007 metadata union>, check_results=[<one per
check>])`. A **blocking** check maps to `AssetCheckSpec(blocking=True)` + result
`severity=AssetCheckSeverity.ERROR`; a **non-blocking** check to `AssetCheckSpec(blocking=False)` +
`severity=AssetCheckSeverity.WARN`.

**Verified behavior** *(in-process `materialize()`, three checks: a pass, a failing blocking, a
failing non-blocking)*:
- The `ASSET_MATERIALIZATION` **is recorded** and all three `ASSET_CHECK_EVALUATION`s are recorded.
- A failing **blocking** check raises `DagsterAssetCheckFailedError` at end of step → the **run
  fails**, *but the materialization is already recorded* (asset still counts as materialized). This
  is exactly "asset materialized, downstream automation gated" (FR-006, SC-002/SC-003).
- A failing **non-blocking** check alone does **not** raise → run succeeds, asset materialized, check
  shows red (SC-002).

**Rationale**: `blocking=True` is Dagster's native gate consulted by downstream automation (the
spec-010 consumer), so setting it puts the machinery in place now. `WARN` severity keeps a failed
non-blocking check from marking the asset's health as failing (US2), while `passed=False` still
renders it red.

## R4 — Emission on producer **failure/timeout**: yield checks + observation, then raise

**Decision**: On producer failure/timeout the op **yields** one `AssetCheckResult` per check
(these persist), emits the failed-run report as an `AssetObservation` (as spec 007 does today —
keeping the partition red, **no** materialization), and then **raises** to mark the run failed.

**Verified behavior** *(in-process, generator op that yields an `AssetCheckResult`, logs an
`AssetObservation`, then raises; read from the instance event log for the run)*:
- `ASSET_CHECK_EVALUATION: 1` — **a yielded check result survives the later raise**.
- `ASSET_OBSERVATION: 1` — the observation persists through the raise (this is the same mechanism
  spec 007 relies on; also re-verified for the current `from_op` + `log_event(AssetObservation)` +
  `raise` pattern — `ASSET_OBSERVATION: 1`).
- **No** `ASSET_MATERIALIZATION` — the partition stays red (Constitution / spec-007 fix
  "failed asset run stays red, not materialized").

**Gotcha resolved**: `context.log_event(...)` items emitted *before* a raise do **not** appear in
`ExecuteInProcessResult.all_events` — but they **are** written to the instance event log. Tests
MUST assert against `instance.event_log_storage.get_logs_for_run(run_id)` (or an
`EventRecordsFilter`), **not** `result.all_events`, or they will wrongly conclude the observation /
check was dropped. *Yielded* check results are the robust channel and are what the design uses.

**Rationale**: This is the only way to keep spec 007's "failed producer ⇒ red, not materialized"
while still recording every check's verdict — satisfying the clarification "checks run even when
the producing run is non-`ok`" and its edge case.

## R5 — The `/report.json` mount and `/output` `/workspace` read-only mounts

**Decision**: Before running checks, the op writes the spec-007 report dict as JSON to a per-run
file under `PIPES_ROOT` (e.g. `<pipes_dir>/report.json`) and bind-mounts it read-only at
`/report.json` in each check container. `/output` (`cfg["output_dir"]`) is mounted `:ro`, and
`/workspace` (`cfg["workspace"]`, only for `WORKSPACE_HARNESSES` agents that have one) is mounted
`:ro`.

**Rationale**:
- Docker-outside-of-Docker means the host daemon resolves `-v` sources against the **host**
  filesystem; the report file must live under a host==container shared path — `PIPES_ROOT`
  (`/data/dagster/pipes`) already satisfies this (the pinned lesson: "Pipes dir must be under
  /data"). `cfg["output_dir"]` and `cfg["workspace"]` are already host paths.
- Read-only `/output` makes a write attempt fail with a permission error (US3/SC-005) and makes it
  impossible for a check to alter a produced file (Constitution V).
- The report file is written per run and removed in the op's `finally` **after** the checks have
  run (they run in-process before `finally`), so nothing leaks and `/report.json` is always present
  for checks — including for a failed/timed-out producer (the report is authored either way, R4 /
  spec 007's `_authored_report`).

**Alternatives considered**: writing `report.json` **into `/output`** — **rejected**: it would
pollute the immutable output and appear in the output-file diff; `/output` is read-only to checks
anyway. A dedicated per-run temp file under `PIPES_ROOT` keeps output clean.

## R6 — Default check image = the producing agent's harness image

**Decision**: A check with no `image` runs in the producing agent's harness image, resolved through
a small `HARNESS_IMAGE = {"api": "agentbox/agent-python:latest", "claude-code":
"agentbox/agent-claude:latest", "codex": "agentbox/agent-codex:latest", "pi":
"agentbox/agent-pi:latest"}` map in `factory.py`.

**Rationale**: That image is guaranteed present on the host (the agent just ran in it), so common
checks (`test`, `ls`, shell one-liners via `sh -c`) need nothing built or pulled (spec Assumptions).
The image names are already embedded literally in `_build_agent_cmd`; a named constant is a small,
acknowledged duplication in the same spirit as the existing `ASSET_KEY_RE` / `is_valid_cron` twins.

## R7 — Command is a shell string; exit code is the verdict; 4 KB tail

**Decision**: Each check container runs `sh -c "<command>"` (image entrypoint overridden as needed),
so pipes, `&&`, command substitution, and shell builtins (`false`) all work (clarification). Exit
`0` = pass, any non-zero = fail. stdout and stderr are captured **combined**; only the **last
4 KB** is retained and attached to the `AssetCheckResult` metadata (FR-007/SC-006) — truncated at
the tail so the end (usually the failure) is kept.

## R8 — Timeout and missing-image handling

**Decision**: Each check container is launched with the deterministic name
`check-<agent>-<check>-<runid[:8]>` and `--rm`; the orchestrator waits up to the check's own
`timeout_seconds` and, on expiry, `docker kill`s it and reports the check **failed** with a
`timeout` marker in metadata (SC-004) — mirroring the agent-launch timeout kill. Before launching,
the orchestrator resolves the image; a check whose `image` cannot be resolved (`docker image
inspect` fails and it is not the guaranteed harness image, or `docker run` returns the daemon's
image error) is reported **failed** with the resolution error in its metadata (FR-015), never
silently skipped and never aborting the materialization.

**Rationale**: `--rm` + kill-by-name is the same pattern `make_run_op` already uses for the agent
container, so no check container survives the run (SC-004). Distinguishing "image missing" from
"command failed" gives the operator a clear FR-015 message.

## R9 — No network by default

**Decision**: Check containers launch with `--network none` unless the check sets `network:`, which
accepts the same choices as an agent (`agentnet-isolated`, `agentnet`, `bridge`) and maps to the
same `--network <value>` flag (FR-016). Checks are isolated observers by default.

## R10 — Partitions: association via the run, partition key in metadata (FR-014)

**Decision**: Because the check runs **inside the producer's run**, its `AssetCheckResult` is
recorded in that (partitioned) run and Dagster links the check evaluation to that run's
materialization via `AssetCheckEvaluationTargetMaterializationData` *(verified: on a partitioned
`materialize(partition_key=…)`, the evaluation's `target_materialization_data` points at the
partition's materialization; the evaluation's own `partition` attribute is `None`)*. The design
additionally records the partition key in each check's metadata so the association is explicit and
legible (FR-014).

**Rationale**: The single-op design sidesteps the harder "attach a check to a partition
independently of a run" problem the spec hedged against — the check simply shares the producing
run's partition context. No separate fallback path (à la spec 007's `AGENTBOX_PARTITION_FALLBACK`)
is needed; recording the partition key in metadata is the lightweight FR-014 guarantee.

## R11 — Load-time validation: checks require an asset; unique names

**Decision**: A new `validate_checks(cfg, file)` (called from `definitions.discover`'s per-file
try/except, beside `validate_asset_key`) raises `RejectAgent(file, …)` when: `checks` is declared
but the agent has no valid `produces.asset` (FR-010); a check is missing `name` or `command`; or two
checks share a `name` (asset-check names must be unique on an asset — edge case). One bad file is
logged by name and skipped; every other agent still loads. The UI enforces the same rules in
`schema.validate` so a bad checks list cannot be saved.

## R12 — UI: a Checks card inside the asset nature card; a new list-of-objects field

**Decision**: `produces.checks` is a new schema field of a **new list-of-objects type** (today's
types are scalar/list/map only). The UI renders a **Checks card** — a repeatable-object-rows control
modeled on the existing `renderMap` add/remove scaffolding — **inside** the asset nature card in
`agent-form.js`, so it is present only when the agent is an asset and hidden for a job-only agent
(FR-011). The YAML emitter gains a new branch in `_produces_block_lines` to write a commented,
nested `checks:` sequence-of-mappings (the emitter has no list-of-mappings path today); `read_agent`
lifts `produces.checks` into the flat form model. Schema version bumps 4 → 5 with an identity
`migrate_4_to_5` (checks are additive; older files simply have none).

**Rationale**: Keeps the single-source-of-truth schema model (spec 001/003) intact and the file the
canonical store; checks ride the existing `block: "produces"` mechanism used by `asset`/`partition`.
