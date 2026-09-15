# Implementation Plan: File Layout Overhaul — Three Roots

**Branch**: `010-file-layout-overhaul` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-file-layout-overhaul/spec.md`

## Summary

Draw a hard line between agentbox's three kinds of files and give each a single root:
the **product** (the read-only repo checkout), **instance configuration** (`config/` —
agents, prompts, projects, settings, LiteLLM overlay; gitignored, becomes its own git
repo), and **instance state** (`$AGENTBOX_DATA` — runs, outputs, workspaces, mirrors,
provenance, credentials, keys; backed up as a unit). Dagster keeps a separate sibling
storage root (`$DAGSTER_HOME`).

Technically this means: (1) collapse the scattered hard-coded paths into **one resolution
module per process** — a new `orchestrator/paths.py` and the existing `ui/config.py` — that
derive every path from three env vars with documented defaults; (2) move agent-logs out of
the Dagster home into `$AGENTBOX_DATA/runs`; (3) split `litellm/config.yaml` into a product
alias-tier **template** plus an instance **overlay** merged by a **generator** into
`config/litellm.rendered.yaml`; (4) add a **migration tool** that relocates the live box's
files (dry-run by default, refuses to clobber, rewrites in-YAML paths, leaves a
compatibility symlink for old run history); (5) ship an **`examples/config/`** tree and move
the `_template-*.yaml` starters there; (6) add **path validation** to the schema (bump to
version 6) that rejects `output_dir`/`workspace`/`env_file` under the product tree or outside
the data root; (7) rewire `docker-compose.yml` and `bootstrap.sh` to the three roots; and
(8) rewrite the README/AGENTS.md/`.env.example` documentation to match.

## Technical Context

**Language/Version**: Python 3.12 (orchestrator + UI, matching the container images); Bash
(bootstrap). Migration tool and LiteLLM generator: Python 3.12 (stdlib + `pyyaml`, already a
dependency).

**Primary Dependencies**: Dagster 1.13.21, `dagster-pipes`, FastAPI + Jinja2 (UI), `pyyaml`,
`croniter` (UI only), Docker Engine (Docker-outside-of-Docker via socket), LiteLLM proxy image.

**Storage**: Filesystem only. Three host roots resolved from env vars:
`AGENTBOX_CONFIG` (default `<product>/config`), `AGENTBOX_DATA` (default `/data/agentbox`),
`DAGSTER_HOME` (default `/data/dagster`, unchanged). Dagster run DB / storage / compute logs
under `$DAGSTER_HOME`; everything agentbox-owned under `$AGENTBOX_DATA`.

**Testing**: `pytest`. Orchestrator suite `cd orchestrator && ../.venv/bin/python -m pytest -q`;
UI suite `cd ui && ../.venv/bin/python -m pytest -q`; image lib suite under `images/tests`.
New unit tests for path resolution (both processes), the LiteLLM generator, the schema path
validator, and the migration planner. Migration + fresh-install are validated by the
quickstart on a copy of the box (no live-box CI).

**Target Platform**: Raspberry Pi (arm64, Debian) running Docker Compose; single instance per box.

**Project Type**: Self-hosted multi-service platform (orchestrator + daemon + UI + LiteLLM),
containers composed by `docker-compose.yml`, agent containers launched via the host Docker socket.

**Performance Goals**: N/A (setup/refactor feature; no runtime hot path changed). The generator
and migration run at setup/stack-start, not per request.

**Constraints**: Docker-outside-of-Docker — `-v` sources on agent-container launches are resolved
by the **host** daemon, so any path handed to `docker run -v` must be a real host path (drives
the `AGENTBOX_HOST_REPO`/host-path split; see [[pipes-dir-must-be-under-data]]). PIPES messages
dir must stay under a host==container bind mount, so it remains under `$DAGSTER_HOME`.
PEP 668 host: use the existing `.venv` (Python 3.12); do not `pip install` outside it.

**Scale/Scope**: One box, ~30 agent YAMLs, ~15 prompts. Refactor touches: `orchestrator/`
(new `paths.py`, `factory.py`, `definitions.py`), `ui/` (`config.py`, `schema.py`, template
picker, stores), `litellm/` (template split + new generator + overlay example),
`scripts/` (`bootstrap.sh` + new `migrate-layout.py`), `docker-compose.yml`, `.env.example`,
`.gitignore`, new `examples/config/`, README + AGENTS.md.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — PASS. The product tree becomes read-only everywhere a service
  consumes it (FR-013/FR-023); agent containers keep their existing internal mount contract
  (FR-024), only host sources change. Path validation (FR-025) prevents an agent from writing
  into the product tree. Net increase in isolation.
- **II. Configuration over Code** — PASS. Adding/editing agents still requires only YAML +
  prompt edits, now landing under the config root instead of the product repo (FR-007). The
  orchestrator still auto-discovers. No new orchestrator code is needed per agent.
- **III. Secrets Never in the Open** — PASS. Credentials subpath stays owner-only (FR-011);
  env-passthrough-by-name is unchanged. The LiteLLM generator resolves provider **key names**
  and checks their env presence at render time (FR-017) without ever writing key *values* into
  the generated config (`os.environ/<KEY>` references are preserved, not expanded).
- **IV. Uniform Interface, Diverse Runtimes** — PASS. The agent schema surface is unchanged
  except the new path-validation rule and optional-with-default `output_dir`; no per-harness
  divergence is introduced. Schema version bumps to 6 (FR-026).
- **V. Ephemeral Runs, Immutable Outputs** — PASS. Outputs/workspaces/runs simply relocate
  under the state root; immutability and identifiability are unchanged.
- **VI. Docs Track Reality** — PASS (with required work). FR-027/028/029 mandate README
  "Layout" section, file-tree rewrite, AGENTS.md contributor guidance, and `.env.example` for
  all three roots. Preferred automated verification: a doc test asserting the three root vars
  are documented and the layout tree lists the real subpaths.
- **VII. One Design System** — PASS. The only UI-visible change is the template picker now
  sourcing from `examples/` and the field-named path-validation rejection message; both reuse
  existing macros/tokens and add no new component or literal styling.

**Result**: No violations. Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/010-file-layout-overhaul/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output — roots, trees, entities
├── quickstart.md        # Phase 1 output — migration + fresh-install validation
├── contracts/           # Phase 1 output
│   ├── path-resolution.md      # the three-root env-var contract (both processes)
│   ├── migration-cli.md        # migrate-layout.py behaviour + plan format
│   ├── litellm-generator.md    # template+overlay merge + missing-key report
│   └── path-validation.md      # schema rejection rule + message shape
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

Target layout after this feature. `config/` and `$AGENTBOX_DATA` are runtime roots (the
former gitignored in the product repo, the latter off-repo entirely); everything else is
product code.

```text
# PRODUCT TREE (repo checkout — mounted read-only into services)
agents/                     # REMOVED from product after migration (moves to config/agents/)
prompts/                    # REMOVED from product after migration (moves to config/prompts/)
images/                     # product-owned container image defs + images/lib + images/tests
orchestrator/
├── paths.py                # NEW — single root-resolution point for the orchestrator/daemon
├── factory.py              # paths now derive from paths.py (no literal /data or /opt/agentbox)
├── definitions.py          # agents glob derives from the config root
├── dagster.yaml            # derives its paths from $DAGSTER_HOME
└── workspace.yaml
ui/
├── config.py               # single root-resolution point for the UI (extended for 3 roots)
├── schema.py               # +path validation (FR-025), version bump 5→6, output_dir default
├── main.py                 # template picker reads examples/, not the agents dir
├── agents_store.py / prompts_store.py   # read/write under the config root
└── ...
litellm/
├── config.template.yaml    # product-owned alias-tier TEMPLATE (was config.yaml)
└── generate.py             # NEW — merges template + overlay → config/litellm.rendered.yaml
examples/                   # NEW — product-owned samples copied to seed a fresh config/
└── config/
    ├── agents/             # the _template-*.yaml starters (moved out of the product agents/)
    ├── prompts/            # a sample prompt
    ├── projects/           # a sample project (reserved subpath; other brief owns contents)
    ├── settings.yaml       # minimal instance settings
    └── litellm.overlay.yaml# minimal instance overlay (providers, key names, alias bindings)
scripts/
├── bootstrap.sh            # creates the $AGENTBOX_DATA tree with correct ownership
└── migrate-layout.py       # NEW — dry-run-by-default relocation tool
docker-compose.yml          # mounts: product RO, config RW(UI), data, dagster home, socket
.env.example                # documents AGENTBOX_CONFIG, AGENTBOX_DATA, DAGSTER_HOME
.gitignore                  # + /config/
README.md / AGENTS.md       # Layout section + contributor guidance

# INSTANCE CONFIG ROOT ($AGENTBOX_CONFIG, default <product>/config, gitignored)
config/
├── agents/  prompts/  projects/  external-assets/   # instance config
├── settings.yaml            # instance settings (moved from orchestrator/settings.yaml if present)
├── litellm.overlay.yaml     # instance LiteLLM overlay
└── litellm.rendered.yaml    # GENERATED (gitignored within the config repo); LiteLLM loads this

# INSTANCE STATE ROOT ($AGENTBOX_DATA, default /data/agentbox, backed up)
$AGENTBOX_DATA/
├── runs/       # per-run records incl. the agent-logs the Dagster home used to hold
├── outputs/  workspaces/  repo-mirrors/  provenance/  credentials/  keys/

# DAGSTER STORAGE ROOT ($DAGSTER_HOME, default /data/dagster — sibling)
$DAGSTER_HOME/
├── storage/  history/  compute_logs/   # Dagster's own
└── pipes/                              # transient PIPES messages (stays here, per FR-010)
```

**Structure Decision**: Keep the existing single-repo, multi-service structure. The
overhaul is about *where files land at runtime*, not about restructuring the source tree.
The one architectural addition is the explicit single-resolution-point pattern:
`orchestrator/paths.py` and `ui/config.py` are the only two places that read the root env
vars; every other path derives from them (FR-002, SC-009). Templates leave the product
`agents/` directory for `examples/config/agents/`; the LiteLLM config file splits into a
product template plus an instance overlay merged by `litellm/generate.py`.

## Complexity Tracking

No constitution violations — table intentionally empty.
