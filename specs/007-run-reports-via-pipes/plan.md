# Implementation Plan: Structured Run Reports via Dagster Pipes

**Branch**: `run-reports-via-pipes` (spec dir `007-run-reports-via-pipes`) | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-run-reports-via-pipes/spec.md`

## Summary

Every agent run hands the orchestrator one structured **run report** — a fixed JSON shape
(`status`, `tokens_in`, `tokens_out`, `turns`, `cost_usd`, `files_written`, `transcript_path`,
`error`, `notes`) — instead of the orchestrator scraping each harness's stdout to reconstruct a
summary. Each harness **image** owns translating its own native events into that shape (the
per-harness parsing leaves `factory.py`), and reports it back over the **Dagster Pipes protocol on
a mounted messages file**. The orchestrator attaches the report as materialization metadata (asset
agents) or run metadata (job-only agents), records failed asset runs **as** materializations
carrying `status: failed` (instead of throwing them away), and streams each run's logs live into
the Dagster run page.

**Technical approach**: keep the existing `docker run` launch verbatim — every isolation flag is
preserved (FR-011/SC-007) — and layer Dagster Pipes over it via `open_pipes_session` +
`PipesEnvContextInjector` + `PipesFileMessageReader`. The launch switches from
`subprocess.run(capture_output)` to `subprocess.Popen` with line-by-line stdout draining so logs
stream live (FR-003) while the transcript `.jsonl` is written exactly as today (FR-006). This path
is not a fallback of convenience: the Pipes **Docker client** (`dagster_docker.PipesDockerClient`)
is not installed and cannot express the launch's isolation flags, so the spec's stated alternative
— "keep `docker run`, implement the Pipes protocol over a mounted messages file" — is the path
taken.

## Technical Context

**Language/Version**: Python 3.12 (orchestrator + `agent-python` image); Node 20 (claude/codex/pi
images) with a Python 3 report wrapper added.

**Primary Dependencies**: Dagster 1.13.21 (pinned, running) — uses `open_pipes_session`,
`PipesEnvContextInjector`, `PipesFileMessageReader`, `PipesSession.get_reported_results()` /
`get_custom_messages()`, all confirmed present. `dagster-pipes` (pure-Python, zero-dependency)
added to each harness image for the report wrapper. **Not** used: `dagster_docker` /
`PipesDockerClient` (not installed; see Constitution Check + research R1).

**Storage**: Filesystem under `/data` (transcripts at `/data/dagster/agent-logs/...`, outputs at
`/data/outputs`, Dagster state at `/data/dagster`). New: a per-run **Pipes messages file** under a
host temp dir bind-mounted read-write into the container at `/pipes` (distinct from `/output`).

**Testing**: `pytest` — orchestrator suite at `orchestrator/tests/` (in-process `materialize()`
with a stubbed launch), plus new per-harness report-parser unit tests driven by recorded
native-event fixtures. UI suite unaffected.

**Target Platform**: Raspberry Pi arm64, Debian Bookworm; Docker-outside-of-Docker via socket
mount; orchestrator runs as two containers (webserver + daemon).

**Project Type**: Single project — a Dagster code location (`orchestrator/`) that launches agent
container images (`images/`), configured by declarative agent YAML (`agents/`).

**Performance Goals**: N/A (batch agent runs; report emission is once-per-run and negligible).

**Constraints**: No isolation flag may be dropped or weakened (FR-011/SC-007). No new agent-config
keys (`produces`/`job` schema untouched). The transcript `.jsonl` byte stream is unchanged
(FR-006). `notes` must render in the Dagster UI without opening the transcript (FR-010).

**Scale/Scope**: 4 harnesses (api, claude-code, pi, codex); ~15 agent definitions today; one op
(`make_run_op`) shared by asset-mode (`from_op`) and job-mode.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| **I. Agent Isolation** | **PASS.** The `docker run` argv is preserved verbatim; the only additions are two `DAGSTER_PIPES_*` env vars and one read-write `/pipes` mount for the messages file. `PipesDockerClient` is rejected precisely *because* it cannot guarantee the current isolation flags (network attachment, tmpfs-with-uid creds, `--env-file`, passthrough-by-name). A test asserts the launched argv is unchanged except for those additions (SC-007). |
| **II. Configuration over Code** | **PASS.** No new agent-config keys; report fields surface as metadata only. Adding a harness still means an image + parser, not orchestrator branching — and *less* orchestrator code than today (the per-harness parsing is deleted, SC-002). |
| **III. Secrets Never in the Open** | **PASS.** Passthrough-by-name (`-e VAR`) is untouched. The injected Pipes env vars (`DAGSTER_PIPES_CONTEXT`, `DAGSTER_PIPES_MESSAGES`) carry only run/asset/partition context and a file path — no secrets. The messages file carries only report fields. |
| **IV. Uniform Interface, Diverse Runtimes** | **PASS — strengthened.** The whole feature makes every harness present one report shape. A shared report-emit helper keeps the shape identical across images. |
| **V. Ephemeral Runs, Immutable Outputs** | **PASS.** The `/pipes` messages file is per-run scratch on a host temp dir, never `/output`; `/output` stays the immutable finished-artifact location. `files_written` is a count, not a rewrite of output. |
| **VI. Docs Track Reality** | **PASS with required doc updates.** `CLAUDE.local.md`'s "Debugging failed Dagster runs" section describes the orchestrator's stdout summarisation, which this feature removes; README/CLAUDE debugging notes must be updated in the same change (tracked as a task). |

**Result**: No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/007-run-reports-via-pipes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── run-report.schema.json     # the common report JSON shape
│   ├── pipes-transport.md         # orchestrator ↔ image Pipes/env/mount contract
│   └── metadata.md                # the metadata union attached to runs/materializations
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
orchestrator/
├── factory.py                 # CHANGED: make_run_op — Popen + live streaming, open_pipes_session,
│                              #   read reported report, attach metadata, materialize-on-failure,
│                              #   timeout kill + fallback report. DELETE per-harness stdout parsing.
├── definitions.py             # unchanged (asset/job wiring from spec 006 preserved)
└── tests/
    ├── conftest.py            # CHANGED: stub Popen (streaming launch) instead of subprocess.run
    ├── test_factory.py        # CHANGED/ADDED: metadata union, materialize-on-failure, timeout
    └── test_reports.py        # NEW: orchestrator-side report routing + fallback authoring

images/
├── lib/
│   └── agent_report.py        # NEW shared helper: common report schema + Pipes emit
│                              #   (report_asset_materialization vs report_custom_message)
├── agent-python/
│   ├── Dockerfile             # CHANGED: pip install dagster-pipes; copy lib
│   └── runner.py              # CHANGED: build + emit report (tokens/cost from LiteLLM)
├── agent-claude/
│   ├── Dockerfile             # CHANGED: add python3 + dagster-pipes; wrapper entrypoint
│   └── wrapper.py             # NEW: run `claude`, stream stdout, parse stream-json → report
├── agent-codex/
│   ├── Dockerfile             # CHANGED: add python3 + dagster-pipes; wrapper entrypoint
│   └── wrapper.py             # NEW: run `codex`, parse turn.completed/item.completed → report
└── agent-pi/
    ├── Dockerfile             # CHANGED: add python3 + dagster-pipes; wrapper in entrypoint
    └── wrapper.py             # NEW: run `pi`, parse agent_end → report (cost from pi usage)

images/tests/                  # NEW: per-harness parser unit tests over recorded fixtures
└── fixtures/                  # recorded native-event streams per harness

docker-compose.yml             # unchanged (no new orchestrator mounts; /pipes is per-run, created
                               #   by the op under a host tmp dir the daemon already can write)
CLAUDE.local.md / README       # CHANGED: update debugging docs (report replaces stdout scraping)
```

**Structure Decision**: Single-project layout is unchanged. The feature moves per-harness parsing
**out of** `orchestrator/factory.py` and **into** each `images/<harness>/` wrapper, backed by a
shared `images/lib/agent_report.py` so the report shape and Pipes-emit path stay identical across
harnesses (Constitution IV). The 006 asset/job wiring in `definitions.py` and the `from_op` asset
construction in `factory.py` are preserved; only the op **body** (`make_run_op`) changes.

## Complexity Tracking

*No constitution violations — section intentionally empty.*
