# Implementation Plan: Agent Produces Asset

**Branch**: `004-agent-produces-asset` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-agent-produces-asset/spec.md`

## Summary

Let an agent definition carry an optional `produces` block (`asset` key + `partition`)
that makes the orchestrator register the agent as a Dagster **asset** — with a
materialization history and per-run metadata — instead of a bare job. Agents without
`produces` are untouched: they stay jobs named `agent_<name>`.

The hard requirement (Null Action, FR-005) is a **single launch path**: the container
`docker run` logic is not duplicated. We achieve this by keeping `make_run_op` as the one
place that launches the container, and — in asset-mode only — wrapping that *same op* with
`dagster.AssetsDefinition.from_op`. `from_op` reuses the identical op object, so the compute
step stays named `run_<name>` (FR-010) and the launch is provably shared. The op gains a
nominal output plus a before/after snapshot of the output directory so it can attach
materialization metadata (output paths, transcript, run stamp, session id, harness, model)
via `context.add_output_metadata` — harmless in job-mode, surfaced as materialization
metadata in asset-mode.

Two entry points validate the asset key (orchestrator load and the management UI). The UI
gains a "Produces" card under the Runs column that reads/writes the nested `produces` block
and round-trips it. The schema version is bumped with an identity migration so the existing
`produces`-free files load with zero migration noise.

## Technical Context

**Language/Version**: Python 3.12 (orchestrator `factory.py`/`definitions.py`; UI `schema.py`/`agents_store.py`/tests). Browser-side ES2020 modules (no build step) for the form. Same toolchain as features 001–003.

**Primary Dependencies**: Dagster (`AssetsDefinition.from_op`, `DailyPartitionsDefinition`, `AssetKey`, `MaterializeResult`/`Output` metadata, `Definitions(assets=...)`) — already installed in `orchestrator/Dockerfile`, no new pin. FastAPI + Jinja + `pytest`/`TestClient` for the UI, unchanged. `pyyaml` for both.

**Storage**: `agents/*.yaml` (single source of truth; no database). New optional top-level key `produces: {asset, partition}`. Dagster run/materialization state under `/data/dagster`. Agent outputs under `/data/outputs/...` (unchanged location; the asset points at them, FR-007).

**Testing**: `pytest` in `ui/tests/` for everything statically checkable (schema block integrity, validation of asset keys, emitter round-trip of the nested block via regenerated golden files, `/api/schema` payload, form markup for the Produces card). Orchestrator logic (job-vs-asset selection, op naming, conflict/invalid-key rejection, snapshot diff, partition-as-label) covered by unit tests over `factory`/`definitions` with a stubbed launch. End-to-end materialization is verified by the quickstart against the live Dagster UI (the repo has no orchestrator-integration harness — same posture as 001–003).

**Target Platform**: Docker Compose on the Raspberry Pi host (arm64, Debian). Orchestrator runs as `dagster-webserver` + `dagster-daemon`; UI as the `ui` service. Dagster UI at `http://10.0.0.100:3000`.

**Project Type**: Web service (management UI) + orchestrator (Dagster code location). Two packages: `orchestrator/` and `ui/`.

**Performance Goals**: No new per-run cost of note. The added work per run is two directory scans of the agent's `output_dir` (before/after) — O(files in one agent's output dir), negligible next to a container launch.

**Constraints**:
- **Single launch path** (Null Action): asset-mode MUST wrap the existing op, not fork `docker run`. If `AssetsDefinition.from_op` cannot wrap the op without changing how the container launches, STOP and report rather than duplicate the launch code.
- **Partition is a label only** (FR-008b): the partition key MUST NOT enter the container or change output location/naming; it is recorded in metadata only.
- **No copies** (FR-007, SC-003): the asset points at existing output files; the run must not create a duplicate.
- The orchestrator process currently cannot see `/data/outputs` (not mounted) — the before/after snapshot (FR-008a) requires adding that mount (see research R7).
- Backward compatibility: loading the current agent set (none declare `produces`) MUST produce zero warnings and zero migration noise (SC-005).

**Scale/Scope**: ~10 agent files today, none producing assets. Feature touches: `orchestrator/factory.py`, `orchestrator/definitions.py`, `docker-compose.yml` (outputs mount), `ui/schema.py`, `ui/agents_store.py`, the four golden files, the agent templates, README key table, and tests. One asset per agent; `none`/`daily` partitions only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Respected. The container launch (network, memory, cpus, mounts, credential handling) is byte-for-byte the same op in both modes; asset-mode adds only host-side bookkeeping (a directory scan and metadata) outside the container. No new interface is granted to the agent. The partition key never enters the container (FR-008b).
- **II. Configuration over Code** — Central to the feature. Declaring an asset is a config edit (`produces:` in the agent YAML); the orchestrator discovers it and switches representation automatically (SC-001). No orchestrator code change is needed to add an asset-producing agent.
- **III. Secrets Never in the Open** — Respected. No secrets are added to metadata (metadata is paths/ids/model/harness only). The credential mounts and passthrough-by-name in the launch op are untouched.
- **IV. Uniform Interface, Diverse Runtimes** — Respected. `produces` is harness-agnostic and additive; adding it does not change the schema or behavior for any existing harness (FR-018). The asset wrapping is applied uniformly regardless of harness because it wraps the shared op.
- **V. Ephemeral Runs, Immutable Outputs** — Reinforced. The asset is a *pointer* to the immutable outputs the run already writes (FR-007); no copy is made (SC-003). Metadata records what a run produced without relocating or mutating it. The before/after snapshot only reads the directory.
- **VI. Docs Track Reality** — Served. FR-015/FR-016 pair every format change with docs: schema help text (the source the README key table and YAML comments derive from) gains the new fields, templates gain a commented `produces` block, and the golden files are regenerated so contract, code, and fixtures agree. Invalid/conflicting declarations are rejected with file-naming messages (FR-012/FR-019) so operators learn of drift at load, not hours later.

**Result**: PASS. No violations; Complexity Tracking is intentionally empty.

*Post-design re-check (after Phase 1)*: still PASS. The design introduces no per-harness code path (the op is shared and wrapped once), adds no secret to any log or metadata field, and keeps outputs in place with a read-only snapshot. The one new mount (`/data/outputs`) is read-only for the orchestrator's purposes and does not widen any agent's isolation.

## Project Structure

### Documentation (this feature)

```text
specs/004-agent-produces-asset/
├── plan.md                     # This file
├── research.md                 # Phase 0: decisions R1–R10
├── data-model.md               # Phase 1: produces block, asset/materialization entities, YAML placement
├── quickstart.md               # Phase 1: end-to-end validation guide
├── contracts/
│   ├── orchestrator-asset.md   # How produces maps to a Dagster asset: op wrapping, partitions, metadata, conflict/invalid-key handling
│   └── schema-and-yaml.md      # /api/schema additions, the produces block's YAML placement + comments, validation rules
├── checklists/
│   └── requirements.md         # From /speckit-specify
└── tasks.md                    # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
orchestrator/
├── factory.py          # EDIT: give run op a nominal output + before/after output-dir snapshot + add_output_metadata;
│                        #       add build_asset(cfg) that wraps the SAME op via AssetsDefinition.from_op
│                        #       (DailyPartitionsDefinition when partition: daily); keep build_job_and_schedule for job-mode;
│                        #       add asset-key parsing + validation (shared regex)
└── definitions.py      # EDIT: per-file try/except naming the offending file (FR-012); route produces→asset, else→job;
                         #       detect duplicate asset keys among enabled agents and reject the conflicting files by name
                         #       (FR-019); assemble Definitions(jobs=, schedules=, assets=)

docker-compose.yml      # EDIT: mount the outputs root read-only into dagster-webserver AND dagster-daemon so the op can snapshot (R7)

agents/
├── _template-claude-code.yaml  # EDIT: add commented-out produces block (FR-016)
├── _template-pi.yaml           # EDIT: same
├── _template-codex.yaml        # EDIT: same
├── _template-api.yaml          # EDIT: same
└── _template-repo-librarian.yaml # EDIT: same

ui/
├── schema.py           # EDIT: add "produces" SECTION (group runs); add asset/partition fields as a nested block;
│                        #       bump SCHEMA_VERSION 1→2 with an identity MIGRATION; asset-key validation; block in to_public()
├── agents_store.py     # EDIT: emitter writes the produces block (nested, one comment per field); read side maps
│                        #       the nested block to/from the flat fields so it round-trips and is "managed", not "unmanaged"
└── tests/
    ├── golden/*.yaml   # REGENERATE: schema-2 header + commented produces block (+ real block where the fixture sets one)
    ├── test_schema.py  # EDIT: produces section/fields present; asset-key validation accept/reject; migration identity; public shape
    ├── test_agents_store.py # EDIT: produces block round-trips (emit→load→emit stable); placed in Runs section; comments present
    └── test_api.py     # EDIT: /api/schema carries produces; form renders a Produces card under Runs

README.md               # EDIT: key table gains produces.asset / produces.partition rows (FR-015; schema is authoritative)
```

**Structure Decision**: Keep the two packages separate and let each own its half. The orchestrator owns the job-vs-asset decision and the launch; the UI owns authoring and validation. The asset-key validation rule is stated once per package (a small shared regex duplicated deliberately across the container boundary — see research R6) because the two run in different containers with no shared import. The schema stays the single source of truth for the UI (form, emitter, comments, README) so authoring and file format cannot drift.

## Complexity Tracking

No constitution violations; this section is intentionally empty. The one cross-boundary duplication (the asset-key regex in both `orchestrator/` and `ui/schema.py`) is a deliberate, documented choice justified in research R6 — the packages ship as separate containers with no shared module, and a two-line regex is cheaper and clearer than introducing a shared package for it. It is guarded by a test that asserts both copies accept/reject the same fixtures.
