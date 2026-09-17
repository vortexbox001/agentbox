# Phase 0 Research: Shared Agent Base Image

All decisions below were taken **unattended** — no human was available to clarify. Each records the
decision, the rationale, and the alternatives rejected, per the plan workflow. There are no remaining
`NEEDS CLARIFICATION` markers: the spec's four clarifications (base runtime carries Python +
`dagster-pipes`; parity = functional/format equivalence; footprint = deduplicated on-disk usage;
`agent-python` stays standalone) are already resolved, and the items below settle the Dockerfile
mechanics the spec deliberately deferred to the plan.

## R1 — Base OS / runtime for `agent-base`

- **Decision**: `agent-base` is `FROM node:20-slim`.
- **Rationale**:
  - Three of the four harnesses (`agent-claude`, `agent-pi`, `agent-codex`) install their harness
    with `npm` and therefore need Node 20 — the spec itself states a Node-bearing base is the
    reasonable common denominator (Assumptions).
  - The three shell-based harness images already use `FROM node:20-slim` today, so basing the shared
    image on the same tag is behavior-preserving — no OS or Node version shift, satisfying the
    functional-parity requirement (FR-008).
  - `node:20-slim` (Debian bookworm-slim) **already ships a uid-1000 `node` user**; the current
    harness Dockerfiles never run `useradd`/`adduser` and simply `USER node`. So "the base creates
    the uid-1000 `node` user" (FR-001) is satisfied by inheriting it from `node:20-slim` rather than
    re-creating it — the base only needs to declare `WORKDIR /workspace` and (optionally) `USER node`
    where appropriate.
  - It is a `-slim` Debian variant, so `apt-get` is available for the common tool set and the arm64
    variant exists for the Pi target.
- **Alternatives considered**:
  - `debian:bookworm-slim` + install Node manually — rejected: re-implements what `node:20-slim`
    already provides (Node + the `node` user) and risks a different Node version than the harnesses
    ship today, threatening parity.
  - A distro-less / Alpine base — rejected: Alpine's musl and different package names would change
    the runtime under every harness (parity risk) and complicate `build-essential`/`gh`; the spec
    fixes the tool set, not a size-at-all-costs base.

## R2 — Installing the GitHub CLI (`gh`)

- **Decision**: add the **official GitHub CLI apt repository** (its signing key to a keyring + a
  `/etc/apt/sources.list.d` entry) and install `gh` from it in the same `apt-get` layer as the rest
  of the common tools.
- **Rationale**: `gh` is not in Debian bookworm's default repositories, so it cannot be installed by
  simply naming it alongside `git`/`curl`. GitHub publishes an apt repo that includes an **arm64**
  build, matching the Pi target (arm64/Bookworm). This keeps `gh` a normal apt package — installed,
  cached, and upgradable in one place — consistent with the single-source-of-truth requirement
  (FR-003).
- **Alternatives considered**:
  - Download a pinned `gh` release tarball/`.deb` and `dpkg -i` it — rejected: pins a version by hand
    and adds bespoke download/verify logic; the apt repo tracks upstream and reuses apt's signature
    verification.
  - `npm install -g` a `gh` wrapper — rejected: `gh` is a Go binary, not an npm package.

## R3 — Where the Python runtime and `dagster-pipes` live

- **Decision**: the base installs `python3` + `python3-pip` via apt and
  `dagster-pipes==1.13.21` via `pip3 install --no-cache-dir --break-system-packages
  dagster-pipes==1.13.21` — byte-for-byte the lines the three shell-based harness images run today —
  and the harnesses stop declaring them (FR-004/FR-013).
- **Rationale**: the shell-based wrappers are launched with `python3` and report over a
  `dagster-pipes` pinned to the orchestrator's Dagster (**1.13.21**, AGENTS.md → Stack and tests).
  Moving the exact same install into the base preserves behavior (same interpreter, same pinned
  wire-format library → functional parity, FR-008) and makes the runtime part of the one shared place
  the spec requires (FR-013). `--break-system-packages` is retained because it is what the current
  Debian-Python + pip3 combination already uses; changing it would be an unrelated behavioral change.
- **Alternatives considered**:
  - A virtualenv in the base — rejected: none of the current images use one; introducing it would
    change how the wrappers are launched (parity risk) for no benefit at this scale (one
    zero-dependency, pure-Python package).
  - Leave Python in each harness — rejected: directly violates FR-013 (no shell-based harness may
    re-declare the runtime) and defeats the single-source-of-truth goal.

## R4 — Build context and build order (and a pre-existing doc bug)

- **Decision**:
  - Build `agent-base` first, tagged `agentbox/agent-base`, from the `images/` directory as context:
    `docker build -f agent-base/Dockerfile -t agentbox/agent-base images/` (or `cd images && docker
    build -f agent-base/Dockerfile -t agentbox/agent-base .`).
  - Then build each harness the same way (context `images/`, `-f images/agent-*/Dockerfile`), so the
    shared `images/lib/` remains in the build context for their `COPY lib/`.
  - `FROM agentbox/agent-base` in the harness Dockerfiles makes Docker enforce the base-first order
    at build time; the README steps and `scripts/bootstrap.sh` state it explicitly for the human/one
    -shot build path (FR-012).
- **Rationale / finding**: every current harness Dockerfile carries the comment *"Build from the
  images/ directory so the shared lib (images/lib) is in the build context"* and does `COPY lib/
  /app/lib/`, yet the **README build commands pass `images/agent-*` as the context**
  (`docker build -t agentbox/agent-python images/agent-python`). With that context, `images/lib/` is
  not present and `COPY lib/` cannot resolve — the documented commands contradict the Dockerfiles.
  Because FR-012 already requires rewriting the build steps to build the base first, the corrected
  steps also fix the context (Constitution VI, Docs Track Reality). This is called out here so the
  implementation phase treats it as an in-scope correction, not scope creep.
- **Alternatives considered**:
  - Copy `lib/` into each image directory so the per-image context works — rejected: duplicates the
    shared library into four places, the opposite of this feature's consolidation goal.
  - Use BuildKit `--build-context`/bake — rejected: adds tooling the project doesn't use elsewhere;
    the plain `-f … images/` form matches the Dockerfiles' own documented invocation.

## R5 — Measuring the smaller combined footprint

- **Decision**: verify FR-011/SC-005 with **`docker system df -v`** (or the image store's unique
  size), reading the deduplicated on-disk usage that counts the shared base layer **once**, and
  compare the shell-based harness total before vs. after the refactor.
- **Rationale**: `docker images` reports each image's *full* size including shared layers, so summing
  those columns after the refactor would count the base layer three times and could look *larger* —
  exactly the trap the spec's clarification warns about. The deduplicated store size is the metric the
  spec fixed (FR-011). The saving comes from the common OS+tool+runtime install existing as one shared
  layer instead of three near-identical copies.
- **Alternatives considered**:
  - Sum of `docker images` SIZE column — rejected: double/triple-counts shared layers; not the
    clarified metric.
  - `docker history` per image — rejected: useful for spotting the shared layers but doesn't give the
    single deduplicated total the success criterion asks for.

## Non-decisions (fixed by the spec, restated for the implementer)

- **Common tool set** is fixed by FR-002: `git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, `gh`,
  `unzip`, and the standard build essentials (`build-essential`). Nothing beyond this common set is
  added to the base (Out of Scope: language toolchains beyond the common set).
- **`agent-python` stays standalone** (FR-010, decided in the spec, not deferred): `FROM
  python:3.12-slim`, keeps its own `dagster-pipes` pin, gains only a one-line comment stating why it
  is off the shared base.
- **No agent YAML, orchestrator, UI, or schema changes** (FR-009) — this feature is confined to the
  image build layer and the two build entry points.
