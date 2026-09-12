# Phase 0 Research: Structured Run Reports via Dagster Pipes

All Technical-Context unknowns are resolved below. Each item is a decision, its rationale, and the
alternatives rejected. Nothing is left as NEEDS CLARIFICATION. Facts marked *(verified)* were
checked against the running orchestrator (Dagster 1.13.21).

---

## R1 — Launch mechanism: `docker run` kept; Pipes over a mounted messages file

**Decision**: Keep the existing `docker run` invocation in `make_run_op` **verbatim** and layer
Dagster Pipes on top with the file-based primitives:

```python
with open_pipes_session(
    context,
    context_injector=PipesEnvContextInjector(),
    message_reader=PipesFileMessageReader(path=<host messages file>),
) as session:
    env = dict(session.get_bootstrap_env_vars())      # DAGSTER_PIPES_CONTEXT, DAGSTER_PIPES_MESSAGES
    env["DAGSTER_PIPES_MESSAGES"] = <messages env, path rewritten to the container path /pipes/messages>
    # existing docker run argv + `-e DAGSTER_PIPES_CONTEXT=... -e DAGSTER_PIPES_MESSAGES=...`
    # + `-v <host pipes dir>:/pipes`
    proc = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
    ... stream stdout ...
```

**Rationale**:
- `dagster_docker` / `PipesDockerClient` is **not installed** *(verified: `import dagster_docker`
  → ModuleNotFoundError)*. Adding it would still not satisfy FR-011: it launches via docker-py
  `containers.run(**container_kwargs)` and does not cleanly express the current launch's
  `--env-file`, passthrough-by-name (`-e VAR` with no value), `--tmpfs /creds:uid=1000,...`, and
  the exact `--network`/mount set the isolation guarantees depend on. The spec's own assumption
  authorises this path: "the existing `docker run` launch is kept and the Pipes protocol is
  implemented over a mounted messages file."
- `open_pipes_session` accepts any op/asset context and any injector/reader *(verified signature)*;
  the launcher is ours, so every isolation flag is preserved unchanged (SC-007).
- `PipesEnvContextInjector` passes context inline in an env var (no extra mount for context);
  `PipesFileMessageReader` needs only one shared file, satisfied by a single `/pipes` bind mount.

**Path rewrite detail**: `get_bootstrap_env_vars()` yields a `DAGSTER_PIPES_MESSAGES` whose `path`
is the **host** path. The container sees the file at `/pipes/messages`, so the op rewrites that env
var's `path` to the container path before adding it to the `-e` list. `DAGSTER_PIPES_CONTEXT` is a
path-independent inline blob and is passed as-is.

**Alternatives considered**:
- *`PipesDockerClient`* — rejected: not installed, and cannot guarantee FR-011's flags.
- *`PipesTempFileContextInjector`* (context via a file) — rejected: needs a second mounted path for
  no benefit over the inline env injector.
- *Abandon Pipes, read a plain report file only* — rejected: loses live log forwarding (FR-003)
  and the `get_reported_results()` / `get_custom_messages()` channel that cleanly separates the
  report from the transcript stdout.

## R2 — Report transport: Pipes messages, routed by step kind

**Decision**: The wrapper in each image uses `dagster_pipes.open_dagster_pipes()` and reports the
common report through the messages file:
- **Asset step** (an asset key is present in the injected Pipes context) →
  `pipes.report_asset_materialization(metadata=<report fields as metadata>)`.
- **Job step** (no asset key) → `pipes.report_custom_message({"report": <report>})`.

The orchestrator, after the container exits, reads back:
- `session.get_reported_results()` for the asset case *(verified present on `PipesSession`)*, and
- `session.get_custom_messages()` for the job case *(verified present)*.

**Rationale**: `report_asset_materialization` is the native Pipes way to attach metadata to an
asset and is the obvious carrier for an asset agent. A **job-only** op has no asset key, so
`report_asset_materialization` cannot be used there — `report_custom_message` carries the identical
report shape for jobs. Reading both back as **data** (not `yield from get_results()`) lets us keep
spec 006's `AssetsDefinition.from_op` wiring untouched (R3) and lets the orchestrator decide the
success/failure materialization behaviour itself (R4).

**Alternatives considered**:
- *Always `report_asset_materialization`* — rejected: errors in a job-only op with no asset key.
- *Always `report_custom_message` (even for assets)* — rejected: throws away the native asset
  metadata channel and would force the orchestrator to hand-build the materialization on the
  success path too, duplicating what `from_op` already does.
- *A plain (non-Pipes) `report.json` mount* — rejected as the primary transport: it is not "via
  Dagster Pipes" and forfeits live log forwarding; retained only conceptually — the Pipes messages
  file *is* the mounted file the spec's fallback describes.

## R3 — Preserve the spec-006 asset/job wiring; change only the op body

**Decision**: `definitions.py` and `factory.py`'s `build_asset` (`AssetsDefinition.from_op`),
`build_job`, `build_materializing_job`, schedules, and sensors are **unchanged**. Only
`make_run_op`'s **body** changes.

**Rationale**: The nature/trigger model (spec 006) is well-tested and orthogonal to how a run
reports itself. Rebuilding assets as Pipes-`yield`-ing `@asset`s would churn tested wiring for no
requirement. The op stays named `run_<name>` (FR still holds; existing tests keep passing).

**Alternatives considered**: *Convert assets to `@asset` that `yield from session.get_results()`*
— rejected: large, risky refactor of 006's `from_op` construction with no functional gain, since
`get_reported_results()` exposes the same data without yielding.

## R4 — Recording failed asset runs as materializations (US2 / FR-007)

**Decision**: In `make_run_op`, after building the metadata union (R6):
- **Success (`status == ok`)**: `context.add_output_metadata(metadata)` and return normally — the
  `from_op` binding records the materialization exactly as today, now carrying the report fields.
- **Failure (`status != ok`)** for an **asset** agent: emit an explicit materialization event
  *before* raising —
  `context.log_event(AssetMaterialization(asset_key=<key>, partition=<key or None>, metadata=metadata))`
  — then `raise` so the run is marked failed. The explicit event is recorded even though the op
  raises, so the partition shows red **with** the report attached (SC-003), instead of no
  materialization.
- **Failure** for a **job-only** agent: attach the report via the run/output path and `raise`
  (behaviour unchanged, FR-008); the report is visible as the logged custom message + transcript.

The op closes over its own kind and asset key: `make_run_op(cfg)` already receives `cfg`, so it
knows `cfg.get("produces")` and can build the `AssetKey` and read `context.has_partition_key`.

**Rationale**: `add_output_metadata` does not survive a raise (no output is produced), so the
success and failure paths must differ. `context.log_event(AssetMaterialization(...))` is the
documented way to record a materialization independent of the op's output — exactly what "red with
the report attached" needs.

**Alternatives considered**:
- *Return normally on failure so `from_op` materializes, then fail the run some other way* —
  rejected: a normally-returning op is a **successful** step; the run would not be marked failed
  (violates FR-007's "mark the run failed").
- *`yield from session.get_results()`* — rejected with R3 (would require abandoning `from_op`).

## R5 — Live log streaming (US3 / FR-003)

**Decision**: Replace `subprocess.run(capture_output=True)` with `subprocess.Popen(stdout=PIPE,
stderr=PIPE, text=True)` and drain stdout **line by line** in the op: each line is (a) written to
the transcript file handle and (b) forwarded to `context.log.info` as it arrives. Applies to every
harness uniformly, so US3's claude-code case is one instance of a general behaviour. The wrapper's
own Pipes **log messages** (written to the messages file) are additionally surfaced live by
`PipesFileMessageReader`.

**Rationale**: `capture_output` buffers until exit — the current cause of the "one dump at the end"
behaviour. Line-draining Popen gives real-time visibility while still capturing the full stream for
the `.jsonl` transcript, unchanged (FR-006). stderr is drained on a second thread (or via
`select`) to avoid pipe-buffer deadlock on chatty runs.

**Alternatives considered**:
- *Rely solely on Pipes log messages* — rejected: only the wrapper's explicit log calls would
  appear; the harness CLI's native stdout (the transcript content operators watch) would not stream.
- *`docker logs -f` in a side process* — rejected: redundant with draining the Popen pipe we
  already own, and complicates ordering with the transcript write.

## R6 — The common report shape and the metadata union (FR-002 / FR-004 / FR-005)

**Decision**: The report is one JSON object with exactly these fields (contract
`run-report.schema.json`):

| field | type | notes |
|-------|------|-------|
| `status` | `"ok" \| "failed" \| "timeout"` | required |
| `tokens_in` | int \| null | null when unmeasured (e.g. timeout) |
| `tokens_out` | int \| null | " |
| `turns` | int \| null | " |
| `cost_usd` | number \| null | null for subscription harnesses (claude-code, codex) |
| `files_written` | int | count of files the run wrote to `/output` |
| `transcript_path` | string \| null | filled by the **orchestrator** (owns the host path) |
| `error` | string \| null | explanation when not ok |
| `notes` | string \| null | final assistant message text (no new prompt convention) |

The **metadata** attached to a run/materialization is the **union** of the report fields and the
existing context fields already recorded today: `output_files`, `transcript`, `run_stamp`,
`session_id`, `harness`, `model`, and (when partitioned) `partition` (FR-005). `transcript_path`
in the report is set by the orchestrator to the same host path as the `transcript` metadata (the
container cannot know the host path). `files_written` (a count, from the harness) and
`output_files` (the path list, from the orchestrator's before/after `/output` diff) coexist —
neither replaces the other (FR-005 / spec Assumptions).

**Rationale**: A single fixed shape across harnesses is the feature's core (SC-001). Nullable
numeric fields keep "unmeasured" distinct from a real zero, per the spec clarifications. Letting
the orchestrator own `transcript_path` avoids leaking host paths into the container.

## R7 — Per-harness parsing moves into the images; a shared emit helper

**Decision**: Add `images/lib/agent_report.py`, a small pure-Python module **copied into every
image**, providing: the report dataclass/serialiser, `files_written` counting (before/after
`/output` snapshot), and `emit(report, cfg_is_asset)` which calls the right
`report_asset_materialization` / `report_custom_message` via `open_dagster_pipes()`. Each image
supplies a **harness-specific parser** that turns its native events into a report:
- **api** (`runner.py`): tokens from the LiteLLM response `usage`; `cost_usd` from LiteLLM's
  `x-litellm-response-cost` response header (non-null, SC-001); `turns = 1`; `notes` = the model's
  message text; `files_written = 1`.
- **claude-code** (`wrapper.py`): parse `stream-json` — the final `result` event gives
  `num_turns`, usage, `is_error`, and final text (`notes`); `cost_usd = null` (subscription).
- **codex** (`wrapper.py`): aggregate `turn.completed` usage, take the last `item.completed`
  `agent_message` text as `notes`, collect `error` events; `cost_usd = null`.
- **pi** (`wrapper.py`): parse the `agent_end` event — sum assistant `usage.cost.total` for
  `cost_usd` (non-null, SC-001), count assistant messages for `turns`, last assistant text for
  `notes`, `stopReason == "error"` for `error`.

This is exactly the parsing that lives in `factory.py` today (the codex `turn.completed`
aggregation, the pi `agent_end` summariser, the claude `result` extraction) — **deleted** from the
orchestrator (SC-002) and relocated next to the harness that produces the events.

**Rationale**: FR-001/SC-002 require the parsing to live in the image and the orchestrator to hold
zero per-harness stdout parsing. A shared emit helper keeps the report shape and Pipes path
identical across harnesses (Constitution IV) while each parser stays small and independently
unit-testable against recorded fixtures.

**Node images and Python**: claude/codex/pi are `node:20-slim` with no Python. Add
`python3-minimal` + `dagster-pipes` (pure-Python, zero-dependency) so the wrapper is Python in
every image and shares `agent_report.py`. The wrapper spawns the underlying CLI (`claude`/`codex`/
`pi`) as a subprocess, tees its stdout to the container's stdout (so the orchestrator's Popen
drain still streams and captures the transcript) while parsing it, then emits the report.

**Alternatives considered**:
- *Emit Pipes messages from Node/bash by hand* — rejected: re-implements the Pipes wire format in
  three images; `dagster-pipes` is tiny and official.
- *Keep parsing in the orchestrator but read the transcript file* — rejected: violates
  FR-001/SC-002 (parsing must be in the image).

## R8 — Timeout and missing/malformed report (FR-009 / edge cases / SC-004)

**Decision**: The op enforces `timeout_seconds` on the `Popen` (via `proc.wait(timeout=...)`); on
`TimeoutExpired` it `docker kill`s the named container (`agent-<name>-<run_id[:8]>`, already set by
`--name`), drains remaining output, and — since the container was killed before it could report —
the orchestrator **authors** a report with `status: "timeout"`, `error` explaining the timeout, and
`null` for every numeric field it could not measure. `--rm` guarantees no container survives
(SC-004). On a **normal** exit where no report was reported and none can be read (missing/malformed
messages), the orchestrator authors `status: "failed"` with an `error` saying the report was
missing or malformed (edge case), so the absence is itself recorded rather than silently ignored.

**Rationale**: The spec makes the orchestrator the fallback author when the container cannot report
(timeout, early crash). Killing by the deterministic container name is reliable and needs no
`docker ps` lookup.

**Alternatives considered**:
- *Let `--rm` + process death imply timeout without writing a report* — rejected: the partition/run
  would carry no report, contradicting FR-009 and the "absence is recorded" edge case.

## R9 — Tests: stub the streaming launch; fixture-driven parsers

**Decision**:
- `orchestrator/tests/conftest.py`: replace the `subprocess.run` stub with a `Popen` stub that
  yields canned stdout lines and a returncode, and additionally lets a test drop a canned report
  into the Pipes messages file / reported-results so the op's routing can be exercised in-process
  via `materialize()` — no `docker run`, no Pipes network. The `docker-run-argv` assertions
  (SC-007) are preserved.
- New `orchestrator/tests/test_reports.py`: metadata union (FR-004/FR-005), materialize-on-failure
  for assets (FR-007/SC-003), job-only routing (FR-008), and fallback authoring for
  timeout/missing report (FR-009).
- New `images/tests/`: each harness parser is unit-tested against a small recorded native-event
  fixture, asserting the produced report matches the schema and expected field values (SC-001,
  including `cost_usd` null for claude-code/codex and non-null for api/pi).

**Rationale**: Mirrors the existing in-process, launch-stubbed test style (`stub_launch`) and adds
coverage exactly where the risk moved — the per-harness parsers and the report routing.
