# Implementation Plan: Shared Agent Base Image

**Branch**: `014-base-image-refactor` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-base-image-refactor/spec.md`

## Summary

Extract one `agentbox/agent-base` image that carries everything the shell-based harnesses share —
the OS, the uid-1000 `node` user, the `/workspace` working directory, the common command-line tools
(`git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, `gh`, `unzip`, and the standard build
essentials), the Python 3 runtime, and the pinned `dagster-pipes==1.13.21` the wrappers run on — and
rebuild `agent-claude`, `agent-pi`, and `agent-codex` as thin layers (`FROM agentbox/agent-base`)
that add only their harness install, entrypoint, and harness-specific env (`CODEX_HOME`). The common
tool list then lives in exactly one Dockerfile, so adding a tool for every shell-based agent is a
one-line change in one place, and the three harness images stop repeating the same OS/tool/user work
so their deduplicated on-disk footprint shrinks. `agent-python` stays on `python:3.12-slim` — it
needs the Python runtime rather than the Node-bearing base and no shell tools — with that reason
recorded in its image (spec FR-010 / US4 null action). No agent YAML changes; no orchestrator or UI
code changes; no schema change. Behavioral parity is functional/format equivalence: the
wrapper/runner and report code are untouched and the `images/tests` suite passes unchanged.

**Decisions taken unattended** (no human was available to clarify; recorded in
[research.md](research.md)):

- **R1 — Base OS/runtime**: `agent-base` is `FROM node:20-slim`. Three of four harnesses need Node,
  `node:20-slim` already ships the uid-1000 `node` user the harnesses assume, and it is the same base
  the three harness images use today — so the move is behavior-preserving.
- **R2 — `gh` install**: the GitHub CLI is not in Debian's default repos, so the base adds the
  official GitHub CLI apt repository (keyring + source list) and installs `gh` from it; that repo
  publishes arm64, matching the Pi target.
- **R3 — Python runtime location**: the base installs `python3` + `python3-pip` and
  `dagster-pipes==1.13.21` (via `pip3 install --break-system-packages`, exactly as the harnesses do
  today), so no shell-based harness re-declares them (FR-013).
- **R4 — Build context**: the base builds from the `images/` directory (context `images/`) so it can
  be tagged and cached before the harnesses; the harness images keep building from `images/` so the
  shared `images/lib/` stays in context. The existing README build commands (which pass
  `images/agent-*` as the context) contradict the Dockerfiles' own `COPY lib/` and are corrected as
  part of FR-012 (see [research.md](research.md) R4 and the Constitution Check).
- **R5 — Footprint measurement**: "smaller combined footprint" is verified with `docker system df -v`
  (deduplicated unique on-disk size counting the shared base once), not the sum of per-image
  `docker images` sizes (FR-011 / SC-005).

## Technical Context

The stable stack facts (Python 3.12; Node 20 harness images on `node:20-slim`; `agent-python` on
`python:3.12-slim`; Dagster/`dagster-pipes` **1.13.21**; files-only storage; five pytest suites;
Docker Compose on a Raspberry Pi arm64/Bookworm; multi-package product tree) are recorded in
AGENTS.md → **Stack and tests** and are unchanged by this feature. This section states only what the
feature adds or changes.

**Language/Version**: No application-language change. The change is entirely in the image build layer
— Dockerfiles under `images/` and the two build entry points (README build steps and
`scripts/bootstrap.sh`). Base OS/runtime for the shared base: `node:20-slim` (Debian
bookworm-slim, arm64), providing the Node 20 runtime and the built-in uid-1000 `node` user.

**Primary Dependencies**: New shared base `agentbox/agent-base`. Its apt tool set: `git`, `curl`,
`ca-certificates`, `ripgrep`, `jq`, `unzip`, `build-essential`, `python3`, `python3-pip`, plus `gh`
from the official GitHub CLI apt repo. Its pip pin: `dagster-pipes==1.13.21` (identical to the
current harness images). No new orchestrator/UI dependency; Dagster stays **1.13.21**.

**Storage**: N/A — no data-root or config-root change, no database, no `settings.yaml` change. The
only artifacts are Docker images in the local image store.

**Testing**: `images/tests` (per-harness report/event parsers) stays **unchanged** and must pass
unchanged — it is the behavioral-parity evidence (FR-008/SC-002); it is hermetic and does not build
images. The other four suites (`ui`, `orchestrator`, `litellm`, `scripts`) are untouched. Build-time
verification (base builds, harnesses build on it, `git`/`rg`/`jq`/`gh`/`python3` resolve, no agent
YAML changed, deduplicated footprint shrinks) is scripted in [quickstart.md](quickstart.md), the
same live-verification posture used by prior specs.

**Target Platform**: Docker images built and run on the Raspberry Pi host (arm64, Debian Bookworm)
under Docker Compose. Agents run as sibling containers; Compose does not build the agent images
(README step 4), so the build-order change lives in the README steps and `scripts/bootstrap.sh`, not
`docker-compose.yml`.

**Project Type**: Multi-package product tree; this feature touches only the `images/` package (a new
`images/agent-base/`, three edited harness Dockerfiles, one commented-reason edit to
`images/agent-python/Dockerfile`) plus two build entry points (`README.md`, `scripts/bootstrap.sh`).

**Performance Goals**: A faster/cheaper rebuild on the Pi — the common OS+tool+runtime install runs
once in the base and is cached, instead of three times across the shell-based harnesses. No run-time
performance change (containers run the same wrapper/runner as before).

**Constraints**:
- **Single source of truth** (FR-002/FR-003/SC-001): the common tool list and the shared
  Python/`dagster-pipes` runtime exist in exactly one Dockerfile (`images/agent-base/Dockerfile`);
  no shell-based harness re-declares them.
- **Thin harness images** (FR-004/FR-005/SC-003): `agent-claude`/`agent-pi`/`agent-codex` carry no
  OS-package install, no user creation, no `WORKDIR`, and no Python/`dagster-pipes` line — only
  `FROM agentbox/agent-base`, the harness install, `COPY lib/` + the wrapper, the entrypoint, and
  harness-specific env.
- **One-line pointer** (FR-006): each rebuilt harness image carries a one-line comment naming the
  shared base as the source of its common tooling.
- **Tools runnable** (FR-007/SC-004): `git`, `rg`, `jq`, `gh` (and the rest of the common set)
  resolve to executables in every shell-based harness.
- **Behavioral parity** (FR-008/SC-002): wrapper/runner/report code and `images/tests` are unchanged;
  parity is functional/format equivalence, not a byte-identical live rerun.
- **No YAML changes** (FR-009/SC-006): no file under any `agents/` tree changes.
- **Null action** (FR-010): `agent-python` stays on `python:3.12-slim` with the reason documented in
  the image; it is not forced onto the Node base.
- **Smaller footprint** (FR-011/SC-005): deduplicated on-disk usage (shared base counted once) is
  smaller than the pre-refactor shell-based harness total.
- **Build order** (FR-012): README build steps and `scripts/bootstrap.sh` build `agent-base` first,
  then the harness images; Compose notes updated only if they reference image builds (they do not).

**Scale/Scope**: One new Dockerfile; four harness Dockerfiles edited (three thinned, one gains a
comment); two build entry points updated. No Python/JS/YAML/schema changes. Files touched:
`images/agent-base/Dockerfile` (new), `images/agent-claude/Dockerfile`,
`images/agent-pi/Dockerfile`, `images/agent-codex/Dockerfile`, `images/agent-python/Dockerfile`,
`scripts/bootstrap.sh`, `README.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Respected. The refactor changes only how images are built, not what a
  running agent may reach: the same non-root uid-1000 `node` user, the same `/workspace`, the same
  entrypoints, no new network reach or credential, no new mount. Consolidating the tool install adds
  no capability an agent didn't already have — the shell-based harnesses already carried `git`/`curl`
  and a Python runtime; `ripgrep`/`jq`/`gh`/`unzip`/build-essential are ordinary read/transform CLI
  tools inside the same sandbox, granted uniformly rather than ad hoc.
- **II. Configuration over Code** — Respected. No orchestrator code changes; agents are still
  discovered from their YAML, and no agent YAML changes (FR-009). The "add a tool once" win is itself
  a configuration-over-duplication improvement at the image layer.
- **III. Secrets Never in the Open** — Respected. No secret is added to any Dockerfile, build arg, or
  log. `gh` is installed from a public apt repo with its published signing key; no token is baked in.
  `CODEX_HOME` (a path, not a secret) stays in `agent-codex` as before.
- **IV. Uniform Interface, Diverse Runtimes** — Reinforced. The harnesses keep their distinct
  runtimes and entrypoints but now share one base surface; the agent-author-facing schema is
  untouched (no schema change), so existing agents are unaffected and adding a runtime still doesn't
  change the schema.
- **V. Ephemeral Runs, Immutable Outputs** — Unaffected. No change to run/output handling; workspaces
  and outputs behave exactly as before.
- **VI. Docs Track Reality** — Served, and improved. The README build steps and
  `scripts/bootstrap.sh` are updated to build the base first (FR-012); each harness image gains a
  one-line pointer to the base (FR-006); `agent-python`'s standalone reason is documented in its
  image (FR-010). This feature also **corrects a pre-existing doc/reality gap**: the README build
  commands pass `images/agent-*` as the build context while every harness Dockerfile `COPY lib/`
  requires the `images/` context — the corrected steps build from `images/` with `-f`
  (research.md R4).
- **VII. One Design System** — Not applicable. No user-facing UI (`ui/templates`, `ui/static`)
  change; this feature is entirely in the image build layer.

**Result**: PASS — no violations. The one intentional, pre-existing duplication that survives is the
`dagster-pipes==1.13.21` pin appearing in two places: the shared base (for the shell-based harnesses)
and `agent-python`'s own Dockerfile (which stays on the Python base). See Complexity Tracking.

*Post-design re-check (after Phase 1)*: still PASS. The design introduces no new code path, no
per-harness logic, no secret, and no new agent capability beyond making the already-present tool set
uniform; it only relocates duplicated build instructions into one base image and fixes the build
order and the README build-context bug.

## Project Structure

### Documentation (this feature)

```text
specs/014-base-image-refactor/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0: decisions R1–R5 (base OS, gh install, runtime, build context, footprint)
├── data-model.md        # Phase 1: the images as entities — base contract, thin harness, standalone harness
├── quickstart.md        # Phase 1: build-order + parity + footprint verification script
├── contracts/
│   └── agent-base-image.md   # Phase 1: the contract agent-base exposes to harness images
├── checklists/
│   └── requirements.md       # From /speckit-specify (already present)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
images/
├── agent-base/
│   └── Dockerfile        # NEW: FROM node:20-slim; the SINGLE place for the common tool set +
│                         #   Python runtime + pinned dagster-pipes; adds the GitHub CLI apt repo
│                         #   and installs gh; inherits node:20-slim's uid-1000 `node` user; sets
│                         #   WORKDIR /workspace. Tagged agentbox/agent-base.
├── agent-claude/
│   └── Dockerfile        # EDIT: FROM agentbox/agent-base; drop apt/user/WORKDIR/python/dagster-pipes;
│                         #   keep `npm install -g @anthropic-ai/claude-code`, COPY lib/ + wrapper.py,
│                         #   ENTRYPOINT; add the one-line "common tooling from agent-base" pointer.
├── agent-pi/
│   └── Dockerfile        # EDIT: FROM agentbox/agent-base; drop the shared lines; keep the pi npm
│                         #   install (--ignore-scripts), COPY lib/ + wrapper.py + entrypoint.sh
│                         #   (+ chmod), ENTRYPOINT; add the one-line pointer.
├── agent-codex/
│   └── Dockerfile        # EDIT: FROM agentbox/agent-base; drop the shared lines; keep the codex npm
│                         #   install, ENV CODEX_HOME=/creds, COPY lib/ + wrapper.py, ENTRYPOINT;
│                         #   add the one-line pointer.
├── agent-python/
│   └── Dockerfile        # EDIT (comment only): stays FROM python:3.12-slim; add a one-line comment
│                         #   stating why it is NOT on agent-base (needs Python, not Node; no shell
│                         #   tools) per FR-010; keeps its own dagster-pipes pin.
├── lib/                  # UNCHANGED: shared report/event library, still COPY'd by each harness.
└── tests/                # UNCHANGED: hermetic parser tests; must pass unchanged (parity evidence).

scripts/
└── bootstrap.sh          # EDIT: build agentbox/agent-base first, then the four harness images
                          #   (build-order half of FR-012). Today it does host setup only and does
                          #   not build images; the base-first build step is added here.

README.md                 # EDIT: the "Build the agent images" step builds agent-base first, then the
                          #   harnesses; build commands corrected to use `-f images/agent-*/Dockerfile`
                          #   with the `images/` context so COPY lib/ resolves (research.md R4).
```

**Structure Decision**: Keep the existing `images/` package layout — one directory per image, each
with its Dockerfile, built from the `images/` context so the shared `images/lib/` stays available.
The only structural addition is `images/agent-base/`, which becomes the single home for the common
OS+tool+runtime install; the three shell-based harness Dockerfiles shrink to `FROM
agentbox/agent-base` + their harness-specific lines, and `agent-python` is left standalone with a
documented reason. Build order (base → harnesses) is expressed in the two human/scripted build entry
points (README, `scripts/bootstrap.sh`); Docker's own `FROM` resolution enforces it at build time.
No `docker-compose.yml` change — Compose does not build the agent images.

## Complexity Tracking

No constitution violations. One intentional duplication remains, unavoidable given `agent-python`'s
standalone base, and stated explicitly:

| Duplication | Why Needed | Simpler Alternative Rejected Because |
|-------------|------------|--------------------------------------|
| `dagster-pipes==1.13.21` pin in `images/agent-base/Dockerfile` (for the shell-based harnesses) and `images/agent-python/Dockerfile` (which stays on `python:3.12-slim`) | `agent-python` deliberately does not build on the Node-bearing base (FR-010), so it cannot inherit the base's pip install; both must pin the exact version the orchestrator's Dagster expects | Forcing `agent-python` onto the shared base only to dedupe one pip line would drag Node and the whole shell toolchain into a runner that needs none of it — exactly the lowest-common-denominator bloat FR-010 forbids. The pin is one line; the two copies stay in lockstep with the orchestrator's `1.13.21` (AGENTS.md → Stack and tests) and are visible in `docker build`. |
