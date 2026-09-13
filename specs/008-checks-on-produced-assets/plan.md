# Implementation Plan: Checks on Produced Assets

**Branch**: `008-checks-on-produced-assets` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-checks-on-produced-assets/spec.md`

## Summary

An asset agent's `produces:` block gains an optional `checks:` list. Each check is a named,
generic shell command that runs — in a fresh, isolated container — after the producing container
finishes, sees the run's `/output` and `/workspace` (read-only) and its spec-007 report at
`/report.json`, and passes on exit 0 / fails on anything else. Every check surfaces as a Dagster
**asset check** on the produced asset (green/red) with the last 4 KB of its output attached; a
failed **blocking** check gates downstream automation while a **non-blocking** one is advisory.
agentbox attaches no meaning to what a check's command does — only to its exit code.

**Technical approach**: A check-bearing asset is built from a plain generator `@op` wired into an
`AssetsDefinition` via `AssetsDefinition.dagster_internal_init(check_specs_by_output_name=…)`
instead of `AssetsDefinition.from_op` — because `from_op` **cannot declare check specs** (verified)
and a standalone `@asset_check` op is **skipped when the producer step fails** (Dagster
downstream-skip), which would break "checks run even when the producer is non-`ok`". (The
`@multi_asset` decorator was the original plan but **cannot build with kebab check names** on
Dagster 1.13.21 — it derives the op output name from the check name and Dagster rejects the hyphen;
the manual construction maps each check to a valid `check_<i>` output while its `AssetCheckSpec`
keeps the kebab name, so the Dagster label matches the YAML — see research R1 / Complexity Tracking.)
The op body is a **generator** that reuses the existing container-launch + report core (extracted
from `make_run_op`), then runs each check container sequentially and emits one `AssetCheckResult`
per check. On producer success it yields
`MaterializeResult(metadata=…, check_results=[…])`; on producer failure/timeout it *yields* the
check results (which persist through the subsequent raise — verified) plus an `AssetObservation`
carrying the report (keeping the partition red, per spec 007), then raises. **Checkless** asset
agents keep the `from_op` path untouched (FR-013).

## Technical Context

**Language/Version**: Python 3.12 (orchestrator + `agent-python` image); the check runner is pure
orchestrator Python (`docker run` a check container) — no new language surface in the agent images.

**Primary Dependencies**: Dagster 1.13.21 (pinned, running). New symbols used, all **verified
present**: `AssetsDefinition.dagster_internal_init` (`check_specs_by_output_name=`, `specs=`),
`AssetSpec` (`partitions_def`, `automation_condition`), `AssetCheckSpec` (`blocking`; kebab
`name` kept while the op output name is a separate valid `check_<i>` — see research R1),
`AssetCheckResult` (`passed`, `check_name`, `severity`, `metadata`), `AssetCheckSeverity`
(`ERROR`/`WARN`), `MaterializeResult` (`check_results=`), `Out`/`Nothing` for the op's check
outputs. (`@multi_asset` was verified to accept `check_specs` but is not used — it cannot build
with kebab check names on this version; research R1.) Docker
CLI (already available Docker-outside-of-Docker) launches check containers exactly as it launches
agent containers.

**Storage**: Filesystem under `/data`. New: a per-run **report file** the producing op writes so
it can be bind-mounted read-only into each check container at `/report.json`. It lives under
`PIPES_ROOT` (`/data/dagster/pipes/…`, already host==container shared) alongside the per-run Pipes
messages dir, and is removed in the op's `finally` after the checks have run.

**Testing**: `pytest` — orchestrator suite (`orchestrator/tests/`) with in-process `materialize()`
and a stubbed launch, extended to cover: check-container argv (mounts/network/`sh -c`/timeout),
pass/fail/timeout/missing-image outcomes, blocking vs non-blocking severity, the failed-producer
path (checks + observation both recorded, no materialization), and load-time rejection. UI suite
(`ui/`) extended for the schema field, validation, and the YAML round-trip of `produces.checks`.

**Target Platform**: Raspberry Pi arm64, Debian Bookworm; Docker-outside-of-Docker via socket
mount; orchestrator runs as two containers (webserver + daemon).

**Project Type**: Single project — a Dagster code location (`orchestrator/`) launching agent
container images (`images/`), configured by declarative agent YAML (`agents/`), edited through a
FastAPI UI (`ui/`).

**Performance Goals**: N/A (batch). Checks are sequential and each bounded by its own
`timeout_seconds`; total added wall-clock is the sum of check runtimes.

**Constraints**: `/output` and `/workspace` MUST be read-only to checks (Constitution V, US3). Check
containers get **no network by default** (Constitution I, FR-016). Checkless asset agents and
job-only agents MUST be byte-for-byte unchanged in behavior (FR-013). No isolation flag on the
producing launch changes. Schema version bumps 4 → 5; template/README/help kept in step (FR-012).

**Scale/Scope**: 4 harnesses; ~15 agents today, none with checks (checks are net-new/additive). One
new verification fixture agent carrying pass/non-blocking-fail/timeout/read-only checks.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| **I. Agent Isolation** | **PASS — strengthened.** Each check runs in a *fresh, short-lived* container with **no network by default** (`--network none`), `/output` and `/workspace` mounted **read-only**, its own `timeout_seconds`, and is killed + `--rm`'d on timeout. A check opts into a network only via an explicit `network:` field using the same choices as an agent (FR-016). |
| **II. Configuration over Code** | **PASS.** Checks are pure declarative YAML; the orchestrator runs them generically by exit code with **zero** per-check-type logic (no test/lint presets). One new *construction* path (a manual `AssetsDefinition` for check-bearing assets) is added, but no per-agent branching — see Complexity Tracking. |
| **III. Secrets Never in the Open** | **PASS.** Check containers receive no `env`, no `env_file`, and no credentials mounts — only the three read-only inspection mounts. With no network by default, a check cannot exfiltrate even if a command tried. |
| **IV. Uniform Interface, Diverse Runtimes** | **PASS.** Checks present one surface regardless of harness; the default check image is the producing agent's harness image (already on the host). Adding a harness does not change the check schema or runner. |
| **V. Ephemeral Runs, Immutable Outputs** | **PASS — strengthened.** Read-only `/output` makes it *impossible* for a check to add/remove/modify a produced file (US3/FR-009). The `/report.json` file is per-run scratch under `PIPES_ROOT`, never `/output`. |
| **VI. Docs Track Reality** | **PASS with required doc updates.** README agent-YAML reference, the `produces:` narrative, the YAML template comments, and `schema.py` help strings must document `produces.checks` in the same change (FR-012), tracked as tasks. |

**Result**: No violations. One justified complexity item (below).

## Project Structure

### Documentation (this feature)

```text
specs/008-checks-on-produced-assets/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions + verified Dagster behaviors
├── data-model.md        # Phase 1 output — Check / Check result / Check container entities
├── quickstart.md        # Phase 1 output — end-to-end verification incl. all 5 user stories
├── contracts/           # Phase 1 output
│   ├── check-model.md            # agent YAML `produces.checks` schema, UI, validation, load rules
│   └── check-execution.md        # orchestrator runtime: container launch + Dagster asset-check mapping
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
orchestrator/
├── factory.py                 # CHANGED:
│                              #  - extract a shared launch+report core from make_run_op
│                              #    (Popen/stream/timeout/report-extract/build_metadata) reused by both paths
│                              #  - build_asset: when produces.checks present, construct a manual
│                              #    AssetsDefinition (op + AssetCheckSpec per check, kebab name kept) instead of from_op; else unchanged
│                              #  - run_checks(): sequential check-container launcher → [AssetCheckResult]
│                              #  - HARNESS_IMAGE map (default check image = harness image)
│                              #  - validate_checks(): reject checks-without-asset + duplicate names (RejectAgent)
├── definitions.py             # CHANGED (small): call validate_checks in the load try/except so a bad
│                              #   checks block costs only its own file (FR-010); register asset_checks
│                              #   via Definitions if any standalone checks are produced (none expected — inline)
└── tests/
    ├── conftest.py            # CHANGED: stub check-container docker runs alongside the agent launch stub
    ├── test_factory.py        # CHANGED: check argv (mounts ro, --network none, sh -c, per-check timeout)
    └── test_checks.py         # NEW: pass/fail/timeout/missing-image, blocking vs non-blocking severity,
                               #      failed-producer path (checks+observation recorded, no materialization),
                               #      partition key recorded in check metadata (FR-014)

ui/
├── schema.py                  # CHANGED: SCHEMA_VERSION 4→5; migrate_4_to_5 (identity); new produces.checks
│                              #   field (list-of-objects) + per-item validation; help text constant
├── agents_store.py            # CHANGED: read_agent lifts produces.checks; _produces_block_lines emits a
│                              #   nested sequence-of-mappings with comments (new emitter branch)
├── main.py                    # unchanged wiring (validate + emit already flow through schema/agents_store)
└── static/agent-form.js       # CHANGED: new repeatable-object-rows control (Checks card) inside the asset
                               #   nature card; shown only when the agent is an asset (FR-011)

agents/
└── verify-checks.yaml         # NEW: verification fixture — an asset agent carrying the pass / non-blocking-
                               #   fail / timeout / read-only checks the quickstart exercises (spec Assumptions)

README.md                      # CHANGED: agent-YAML reference rows + produces narrative document checks (FR-012)
agents/_template-*.yaml        # CHANGED: produces block template comments mention the optional checks list
```

**Structure Decision**: Single-project layout unchanged. The producing container launch and report
handling stay defined **once** — extracted into a shared core so both the unchanged `from_op`
(checkless) path and the new manual-`AssetsDefinition` (check-bearing) path reuse it. Checks are
interpreted generically by exit code; no check-type logic enters the orchestrator (Constitution II).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| A **second asset-construction path**: check-bearing assets use a manual `AssetsDefinition.dagster_internal_init` (a plain generator op + `check_specs_by_output_name`) instead of the established `AssetsDefinition.from_op`. | `from_op` **cannot declare `check_specs`** (verified — no such parameter), so an asset built with it can carry no asset checks at all. A manual `AssetsDefinition` lets one op declare checks *and* emit both the materialization and the check results, **and** keeps the operator's kebab check name as the Dagster asset-check label. | (a) **`@multi_asset(check_specs=…)`** — the original plan, rejected at implementation: on Dagster 1.13.21 it derives the op **output name** from the check via `get_python_identifier()` (`verify__checks_has-output`) and Dagster rejects the hyphen (`^[A-Za-z0-9_]+$`), so a **kebab** check name (required by check-model §2.1) raises `DagsterInvalidDefinitionError` at build. `dagster_internal_init` decouples the valid `check_<i>` op output from the kebab `AssetCheckSpec.name` (verified in-process). (b) **Standalone `@asset_check` op** — rejected: a check op downstream of the producing op is **skipped when the producer step fails** (Dagster's default downstream-skip), directly violating the clarified requirement that checks run even when the producer is non-`ok`; it also cannot guarantee sequential order or share the producer's report in-process. (c) **Yield `AssetCheckResult` from the existing `from_op` op** — impossible: an op may only emit check results for checks the asset *declares*, and `from_op` cannot declare them. Divergence is mitigated by extracting the launch+report core so it is written once; checkless assets keep `from_op` verbatim (FR-013). |
