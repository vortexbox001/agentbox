# Contract: Orchestrator ↔ image Pipes transport

Defines the boundary between `make_run_op` (orchestrator) and each harness image's report wrapper.
Both sides must agree on it; it is exercised by `orchestrator/tests/test_reports.py` and the
per-harness parser tests.

## 1. What the orchestrator provides to the container

On the existing `docker run` argv (all prior isolation flags preserved verbatim — FR-011/SC-007),
the orchestrator additionally passes:

| Addition | Value |
|----------|-------|
| `-v <host-pipes-dir>:/pipes` | a per-run host temp dir (read-write), for the Pipes messages file. **Not** `/output`. |
| `-e DAGSTER_PIPES_CONTEXT=<blob>` | from `PipesEnvContextInjector` via `session.get_bootstrap_env_vars()`, passed as-is. |
| `-e DAGSTER_PIPES_MESSAGES=<blob>` | from `get_bootstrap_env_vars()`, with its `path` **rewritten** from the host path to `/pipes/messages` (the container mount). |

Nothing else about the launch changes. No secret is added to either env var.

## 2. What the container (wrapper) must do

1. Call `dagster_pipes.open_dagster_pipes()` (reads `DAGSTER_PIPES_CONTEXT` /
   `DAGSTER_PIPES_MESSAGES` from the env, writes messages to `/pipes/messages`).
2. Run the underlying harness CLI, **teeing its native JSON events to the container's stdout**
   unchanged, so the orchestrator's stdout drain both streams them live (FR-003) and writes the
   `.jsonl` transcript (FR-006).
3. Parse those native events into a report conforming to `run-report.schema.json`, leaving
   `transcript_path = null` (the orchestrator fills it).
4. Emit the report:
   - **Asset step** — the injected context carries an asset key ⇒
     `pipes.report_asset_materialization(metadata=<report fields, one metadata entry each>)`.
   - **Job step** — no asset key ⇒ `pipes.report_custom_message({"report": <report object>})`.
5. Exit non-zero iff the run failed, matching `status` (so job-only exit semantics are unchanged,
   FR-008). A successful asset run exits zero even if `status` will be surfaced as `ok`.

The wrapper never writes to `/output` except the agent's own output files, and never reads other
runs' outputs (Constitution V).

## 3. What the orchestrator does after the container exits

1. Read back: `session.get_reported_results()` (asset) and `session.get_custom_messages()` (job).
2. If a report is present, use it. If none is present:
   - container was killed by timeout ⇒ author `status: "timeout"` (numeric fields null, `error`
     naming the timeout);
   - normal exit but no readable/well-formed report ⇒ author `status: "failed"` with an `error`
     saying the report was missing or malformed.
3. Set the report's `transcript_path` to the host `.jsonl` path.
4. Build the **metadata union** (see `metadata.md`) and attach it:
   - **asset, `status == ok`** ⇒ `context.add_output_metadata(metadata)`; return normally (the
     `from_op` binding records the materialization). The wrapper's `report_asset_materialization`
     (§2.4) is read via `get_reported_results()` **only to recover the report fields** — the
     orchestrator does NOT re-emit it, so exactly one materialization is recorded on the happy path
     (asserted in `test_reports.py`, T014).
   - **asset, `status != ok`** ⇒ `context.log_event(AssetObservation(asset_key, partition,
     metadata=metadata))`, then `raise` — the partition shows red **with** the report (FR-007). It
     must be an observation, not a materialization: a materialization event greens the partition,
     so emitting one on failure rendered a failed partition MATERIALIZED (bug
     `failed-asset-shows-materialized`). An observation attaches the report without materializing,
     so the failed run leaves the partition red.
   - **job-only** ⇒ `context.add_output_metadata(metadata)`; `raise` on non-zero container exit
     (FR-008).

## 4. Isolation invariant (SC-007)

A test compares the launched `docker run` argv against the pre-feature argv and asserts they are
identical except for the three additions in §1. No prior flag (`--network`, `--memory`, `--cpus`,
`--tmpfs`, credential mounts, `--env-file`, passthrough-by-name `-e VAR`, `-v .../output`,
`--name`, `--rm`) is removed, reordered away, or altered.
