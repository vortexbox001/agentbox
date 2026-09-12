# Contract: check execution — container launch & Dagster asset-check mapping

Governs the orchestrator runtime. The declarative model is in
[check-model.md](./check-model.md). All Dagster behaviors below are **verified** on 1.13.21
(see research.md).

## §1 Asset construction

- **Checkless** asset agent ⇒ built with `AssetsDefinition.from_op(make_run_op(cfg), …)` exactly as
  today (FR-013). No change.
- **Check-bearing** asset agent ⇒ built with:
  ```python
  @multi_asset(
      specs=[AssetSpec(key=<asset key>, partitions_def=<daily|None>,
                       automation_condition=<on_cron|None>)],
      check_specs=[AssetCheckSpec(name=c.name, asset=<asset key>, blocking=c.blocking)
                   for c in checks],
      name=f"run_{name}",
  )
  ```
  The body is a **generator op** (below). `build_asset_automation_sensor`,
  `build_materializing_job` (`define_asset_job(selection=AssetSelection.assets(asset_def))`, which
  includes the asset's checks by default), schedules, and the daily partition all operate on the
  produced `AssetsDefinition` unchanged.

## §2 Op body (generator)

1. **Launch the producer** through the shared launch+report core (extracted from `make_run_op`):
   Popen the existing `docker run` argv, stream stdout live, drain stderr, enforce the agent
   `timeout_seconds`, extract the spec-007 report over Pipes (data channel only, not re-emitted),
   author a fallback report on timeout/missing report, and build the metadata union
   (`build_metadata`). No isolation flag on this launch changes.
2. **Write `/report.json`**: serialize the report dict to `<pipes_dir>/report.json` (under
   `PIPES_ROOT`, host==container shared).
3. **Run checks** (`run_checks`), sequentially in declared order → a list of `AssetCheckResult`
   (§3).
4. **Emit** (§4).
5. **`finally`**: `rmtree` the per-run pipes dir (removes `report.json`) — after the checks ran.

## §3 `run_checks` — one check container per check

For each check, in declared order:

- **Resolve image**: `check.image` or `HARNESS_IMAGE[cfg["harness"]]`. If it cannot be resolved
  (not present and unpullable) ⇒ `AssetCheckResult(passed=False, …)` with the resolution error in
  `metadata` (FR-015); continue to the next check (never abort the materialization).
- **argv**:
  ```
  docker run --rm --name check-<agent>-<check>-<runid[:8]>
    --network <check.network or "none">
    -v <output_dir>:/output:ro
    [-v <workspace>:/workspace:ro]           # only if the agent has a workspace
    -v <pipes_dir>/report.json:/report.json:ro
    --entrypoint sh <image> -c "<check.command>"
  ```
- **Run**: capture combined stdout+stderr; enforce `check.timeout_seconds` — on expiry
  `docker kill <name>` and mark `timed_out` (FR-008). No check container survives the run (`--rm`
  + kill-by-name).
- **Result**: `AssetCheckResult(check_name=check.name, passed=(exit==0),
  severity=ERROR if check.blocking else WARN, metadata={output: <last 4 KB, tail>, exit_code,
  timed_out, blocking, image, partition: <key if partitioned>})` (FR-002/005/007, R7/R8/R10).

Every declared check runs and produces a result; a failing blocking check does **not**
short-circuit the remaining checks (FR-017).

## §4 Emission — by producer outcome

**Producer OK** (`status == "ok"`, exit 0, not timed out):

```python
yield MaterializeResult(asset_key=<key>, metadata=<metadata union>, check_results=<all results>)
```
- A failing **blocking** check ⇒ Dagster raises `DagsterAssetCheckFailedError` after the step: the
  **run fails** but the **materialization is recorded** (asset counts as materialized; downstream
  automation gated — FR-006/SC-003).
- Only failing **non-blocking** checks ⇒ run **succeeds**, asset materialized, checks red (SC-002).

**Producer FAILED / TIMEOUT**:

```python
for r in <all results>:
    yield r                                            # persists through the raise (verified)
context.log_event(AssetObservation(asset_key=<key>,
                  partition=<key or None>, metadata=<metadata union>))   # red, no materialization
if stderr: context.log.error(stderr[-4000:])
raise Exception(f"{name}: run failed (status=…, exit=…)")
```
- Result: partition **red** (no `ASSET_MATERIALIZATION`), the report attached via `ASSET_OBSERVATION`
  (spec 007), and **every check's verdict recorded** as `ASSET_CHECK_EVALUATION` (checks run even
  when the producer is non-`ok` — clarification / edge case).

> **Test lens**: events emitted right before a raise (the observation, and check results in the
> failed path) do **not** appear in `ExecuteInProcessResult.all_events`; assert against
> `instance.event_log_storage.get_logs_for_run(run_id)` / an `EventRecordsFilter`.

## §5 Isolation invariants (Constitution I & V)

- `/output` and `/workspace` are **read-only** in every check container; a write attempt fails with
  a permission error (SC-005) and no produced file is ever added/removed/modified (US3/FR-009).
- No network by default (`--network none`); a network only when the check opts in (FR-016).
- No `env`, no `env_file`, no credential mounts reach a check container.
- The `/report.json` file is per-run scratch under `PIPES_ROOT`, never `/output`.

## §6 Load-time rejection (FR-010, edge case)

`validate_checks(cfg, file)`, called in `definitions.discover`'s per-file try/except beside
`validate_asset_key`, raises `RejectAgent(file, msg)` when checks are present without a valid
`produces.asset`, when a check lacks `name`/`command`, or when two checks share a `name`. One bad
file is logged by name and skipped; all other agents load.

## §7 Backward compatibility (FR-013)

An asset agent with no `checks` builds via the unchanged `from_op` path and records exactly one
materialization with exactly today's metadata and no asset checks. A job-only agent is untouched.
