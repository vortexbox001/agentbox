# Research: Agent Produces Asset

Phase 0 decisions. Each resolves a technical unknown implied by the spec and the
Constitution Check. No open NEEDS CLARIFICATION remain.

---

## R1 — Single launch path: wrap the op, don't fork it

**Decision**: Keep `make_run_op(cfg)` as the one place a container is launched. In
asset-mode, wrap that *same op object* with `dagster.AssetsDefinition.from_op(the_op, ...)`.
In job-mode, keep the existing `@job` wrapper. The op is built once per agent and used by
exactly one of the two wrappers.

**Rationale**: `from_op` adapts an existing op into an asset without re-implementing its
body, so the `docker run` command construction, credential mounts, timeout, transcript
writing, and result parsing are literally the same code in both modes. This is what the
spec's **Null Action** demands ("a single launch path shared by both modes is a hard
requirement"). It also keeps the compute step named `run_<name>` for free (see R2), because
`from_op` reuses the op's own name.

**Alternatives considered**:
- `@asset` with the launch logic in the asset function body — rejected: it would duplicate
  (or force a re-extraction of) the launch code and would name the underlying op after the
  asset key, violating FR-010.
- `@graph_asset` — unnecessary indirection for a single-op agent.
- A shared free function `launch(context, cfg)` called by both a job op and an asset — viable,
  but `from_op` reuses the *op itself*, which is a stronger guarantee of "one path" and less
  code. If `from_op` proves unable to wrap the op cleanly, this is the documented fallback
  (still one shared function, not two copies) — and per the Null Action, anything beyond that
  means STOP and report.

## R2 — Preserving the `run_<name>` step name (FR-010)

**Decision**: Build the op with its current name `run_{name}` and let `from_op` carry that
name through to the asset's compute step. Do not rename per mode.

**Rationale**: `AssetsDefinition.from_op` keeps the wrapped op's name as the materialization's
compute step, so an operator sees `run_repo_librarian_agentbox` whether the agent is a job or
an asset. Consistent naming across modes is the requirement.

**Alternatives**: `@asset(name=...)` derives the op name from the asset key — rejected for the
naming mismatch it would create.

## R3 — Giving the op an output so it can carry metadata

**Decision**: The run op gains one nominal output (value `None`) and attaches metadata with
`context.add_output_metadata({...})` just before returning. In job-mode the output is unused
and harmless; in asset-mode `from_op` maps that output to the asset and the metadata becomes
the materialization's metadata.

**Rationale**: `from_op` needs an op output to bind to the asset key, and
`add_output_metadata` is the supported way to attach per-run metadata that Dagster records on
the materialization. Reserving an open metadata dict also satisfies FR-009 (token/cost fields
can be added later with no change to the `produces` block schema).

**Alternatives**: Emitting a raw `AssetMaterialization` from inside the op — rejected: it
side-steps the asset framework, produces materializations detached from the asset's partition
lineage, and is redundant when `from_op` already yields one.

## R4 — Determining "files written this run" (FR-008a)

**Decision**: Snapshot the agent's `output_dir` immediately before launch and again after the
container exits; record files whose mtime is within the run window or that are newly present.
Store the resulting list as a metadata field (`output_files`). No agent cooperation.

**Rationale**: The spec fixes this method in a clarification. A before/after diff on
`os.scandir(output_dir)` (path → mtime, size) is simple, robust to the output-naming
convention, and requires nothing from the agent. A run that writes nothing yields an empty
list, not an error (edge case honored). The output convention already guarantees each file is
written once in a single write, so a mtime-window diff is reliable.

**Consequence**: The orchestrator process must be able to read `output_dir` — see R7.

## R5 — Partition as a tracking label only (FR-008b)

**Decision**: Use `DailyPartitionsDefinition` for `partition: daily`; unpartitioned for
`none`/omitted. The partition key is **not** passed into the container and does **not** change
`output_dir` or file naming. The op records `context.partition_key` (when partitioned) in
metadata as `partition`.

**Rationale**: The spec is explicit: the launch is identical regardless of partition;
the partition is a backfill/label affordance this feature only tracks. Feature 005 will make
the date drive the run. Materializing a past date therefore launches exactly like today's.

**Start date for the daily partition set**: a fixed, sensible epoch (e.g. the feature's ship
date) configured in the factory, so the partition set is bounded and identical across reloads.
Contract specifies the exact value.

## R6 — Asset-key validation, at two entry points, across a container boundary (FR-011/FR-012)

**Decision**: A valid asset key is one or more kebab segments joined by `/`:
`^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$` (e.g. `repo-review/agentbox`,
`code-map/agentbox`). Slash-separated segments become the `AssetKey` path. Validate at the UI
(before save, per-field error) and at orchestrator load (reject the file, naming it). The
regex is stated once in `ui/schema.py` and once in the orchestrator, deliberately duplicated.

**Rationale**: The two validators live in separate containers with no shared import, so a
shared module would mean a new shared package for two lines of regex — more machinery than the
duplication it removes. The rule is compatible with Dagster's `AssetKey` (which accepts these
segments) and mirrors the existing agent-`name` kebab rule, so it reads as house style. A test
pins both copies against the same accept/reject fixtures so they cannot drift silently
(Constitution VI).

**Alternatives**: Extract a shared package — rejected as over-engineering for a regex.
Rely on Dagster's own key validation only — rejected: it is broader than we want and its error
would not name the offending file.

## R7 — The orchestrator must see `/data/outputs`

**Decision**: Mount the outputs root into both `dagster-webserver` and `dagster-daemon`
(read is all the snapshot needs; mount read-only). Today neither service mounts it.

**Rationale**: The launch uses docker-outside-of-docker, so `-v {output_dir}:/output` is
resolved by the *host* dockerd, not the orchestrator — which is why outputs work today without
the orchestrator seeing them. But R4's before/after snapshot runs *in the orchestrator
process*, which therefore needs read access to the same host path. `output_dir` values live
under `/data/outputs/...`, so mounting that root covers every agent. Read-only keeps the
orchestrator unable to mutate outputs (Constitution V).

**Alternatives**: Have the container report its own paths — rejected by the spec's
clarification (no agent cooperation). Snapshot from inside the agent container — rejected: same
reason, and it would fork the launch.

## R8 — Job ⇄ asset is fully reversible with no other change (Story 2 / SC-004)

**Decision**: The decision is purely `"produces" in cfg`. With `produces` present →
`build_asset`; absent → `build_job_and_schedule` exactly as today. Removing the block returns
the agent to `agent_<name>` with identical launch behavior.

**Rationale**: The op is the same in both branches (R1), so the only observable difference is
job-vs-asset representation — which is precisely SC-004's allowed diff. No migration of state,
no rename of the op, no change to output location.

**Schedules in asset-mode**: this feature defers scheduling changes (Out of Scope; feature
005). For asset-mode agents a schedule, if present, is not wired to an automatic materialization
in this feature; job-mode scheduling is unchanged. The contract states this explicitly so it is
a known, documented limitation rather than a silent gap.

## R9 — Duplicate and invalid declarations at load (FR-019/FR-012)

**Decision**: `definitions.py` builds per file inside a try/except that, on any rejection
(invalid asset key, malformed `produces`), logs a message **naming the file** and skips just
that file — all others still load. Before assembling `Definitions`, collect asset keys from
enabled, valid agents; if two or more share a key, reject *all* the files that declare that key,
naming them, and load everything else.

**Rationale**: Dagster refuses a `Definitions` with two assets under one key, so the conflict
must be caught first and turned into a file-naming operator message rather than a hard load
failure that takes down discovery of unrelated agents (the spec's stated goal). Per-file
isolation makes one bad file cost only itself.

**Alternatives**: Let the last writer win — rejected: silent and non-deterministic. Fail the
whole code location — rejected: violates "all other agents still load."

## R10 — Nested `produces` block in a flat-field schema (Story 3 / FR-017)

**Decision**: Model `produces` in `ui/schema.py` as a new section (`id: produces`, group
`runs`) containing two fields, `asset` and `partition`, marked as belonging to a `produces`
block. The emitter special-cases block fields: it writes a `produces:` header then the
indented `asset:`/`partition:` lines, each with its help text as a comment. The store maps the
nested YAML block to/from the flat fields on read/write so the block is *managed* (round-trips,
not dumped into "Unmanaged"). Bump `SCHEMA_VERSION` 1→2 with an identity migration.

**Rationale**: The schema is the single source of truth for the form, the emitter, the comments,
and the README (Constitution II/VI). Keeping `produces` in that model — rather than hand-writing
it into the emitter only — means the form, validation, comments, and README all derive from one
place, and the block round-trips by construction. A nested block is the smallest extension that
fits the two-key shape the spec dictates ("a `produces` block in the Runs section with an
explanatory comment per field"). The identity migration makes existing schema-1 files (no
`produces`) load with zero noise (SC-005): nothing to transform, just re-stamped on next save.

**Alternatives**:
- Two flat top-level keys `produces_asset`/`produces_partition` — rejected: the file format the
  spec and orchestrator want is a nested `produces:` mapping, not two flat keys.
- Emit the block only in the emitter, treat `produces` as unmanaged on read — rejected: it would
  not round-trip through the form and would drift from the schema.
