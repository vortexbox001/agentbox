# Feature Specification: Shared Agent Base Image

**Feature Branch**: `014-base-image-refactor`

**Created**: 2026-09-16

**Status**: Clarified

**Input**: User description: "Extract a single `agent-base` image with the OS, non-root user, git, and the common command-line tools every agent tends to need, and rebuild each harness image as a thin layer on top. Adding a tool for all agents becomes a one-line change in one place; Pi builds get smaller and faster. No agent YAML changes. New `images/agent-base/` (Debian slim + Node 20, since three harnesses need Node): installs `git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, the GitHub CLI (`gh`), `unzip`, and standard build essentials; creates the uid-1000 `node` user the harness images already assume; sets `WORKDIR /workspace`. Tagged `agentbox/agent-base`. `agent-claude`, `agent-pi`, `agent-codex` change to `FROM agentbox/agent-base` and drop their duplicated `apt-get`/user/workdir lines, keeping only the harness install, entrypoint, and harness-specific env (`CODEX_HOME`). `agent-python` stays on `python:3.12-slim` unless the plan finds it benefits. README build steps and `scripts/bootstrap.sh` build `agent-base` first, then the harness images. The common tool list lives in exactly one Dockerfile; each harness image carries a one-line comment pointing at the base. Out of scope: per-agent images, runtime tool installation (022), changing which harness images exist, language toolchains beyond the common set. Null action: if a harness genuinely can't use the shared base, leave that one on its own base and document why."

## Clarifications

### Session 2026-09-16

- Q: The three shell-based harness wrappers are launched with `python3` and depend on a pinned `dagster-pipes`; if the harnesses drop their own `apt-get`/`pip` lines, where does that Python runtime come from? → A: The shared base also provides the Python 3 runtime (`python3` + `pip`) and the pinned `dagster-pipes` the wrappers require, so no shell-based harness re-declares them.
- Q: What does "identical report, same output" (behavioral parity) mean for acceptance, given every live run differs by timestamp/run id and model nondeterminism? → A: Functional/format equivalence — the report format and agent output semantics are unchanged (same wrapper/runner and report code, image test suites pass unchanged), not a byte-identical comparison of two live runs.
- Q: How is the "combined on-disk footprint is smaller" outcome measured, given `docker images` reports each image's full size including the now-shared base? → A: Deduplicated actual on-disk usage that counts the shared base layer once (e.g. the image store's unique size), not the sum of per-image reported sizes.
- Q: Is `agent-python` decided to stay on its own base now, or is that deferred to the plan? → A: Decided now — `agent-python` stays on `python:3.12-slim` (it needs the Python runtime, not Node, and no shell tools), with the reason documented in its image.

### Session 2026-09-16 (analysis remediation)

These decisions were taken unattended while acting on the `/speckit-analyze` findings; no human was
available to clarify. They are recorded here so the reasoning is reviewable.

- Q: FR-011/SC-005 asserted the combined harness footprint MUST be *smaller* after the refactor, yet
  the shared base **adds** tools the harnesses do not carry today (`ripgrep`, `jq`, `gh`, `unzip`,
  `build-essential` — the last alone is ~150–200 MB), while the five already-shared packages
  (`git`, `curl`, `ca-certificates`, `python3`, `python3-pip`) plus the `dagster-pipes` pin are
  byte-identical across the three harnesses today. Is "combined footprint is smaller" the right
  success gate? (analysis finding H1) → A: No. Re-scope FR-011/SC-005/US3 to the structurally
  guaranteed claim — the common OS + tool + runtime install is **stored once**, as a single shared
  base layer all three shell-based harnesses share, instead of built and stored three times. The raw
  combined total is *not* asserted to be numerically smaller than before, because the base
  standardizes net-new tools; the durable win is single-storage of the shared install (and the common
  work being built once and cached), not a net size reduction. This keeps T016/SC-005 a real
  pass/fail gate rather than one that could legitimately fail once `build-essential`/`gh` are added.
- Q: Principle I grants each agent the *minimum* tooling it needs, yet the shared base installs a full
  compiler toolchain (`build-essential`) and `gh` into every shell-based agent uniformly — is that
  acceptable? (analysis finding C1) → A: Yes, keep the uniform common set. FR-002 fixes
  `build-essential` and `gh` as part of the standard common tool set, and granting them uniformly in
  one auditable place is preferable to per-agent ad-hoc installs that drift. The trade-off (uniform
  common tooling vs. strict per-agent minimum) is now recorded explicitly in the plan's Constitution
  Check §I so the decision is auditable; there is no isolation-boundary, network-reach, or mount
  change, so this is not a Principle I violation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rebuild every harness on one shared base with identical behavior (Priority: P1)

An image maintainer wants the common tooling every agent relies on — the OS, the non-root
`node` user, the `/workspace` working directory, `git`, and the standard command-line utilities —
defined once in a shared `agent-base` image, with each shell-based harness image (`agent-claude`,
`agent-pi`, `agent-codex`) rebuilt as a thin layer on top that adds only its harness. After the
refactor, every existing agent runs end to end exactly as before — same report, same output — and
no agent YAML changes.

**Why this priority**: The shared base is the foundation the rest of the feature stands on. Until
the common tooling is factored into one image and the harnesses are rebuilt on it without changing
what any agent produces, there is no single place to add a tool and no shared layer to shrink the
footprint. It is the MVP and delivers a maintainable base plus verified behavioral parity on its
own.

**Independent Test**: Build `agent-base`, then the four harness images. Run one existing agent of
each harness end to end and confirm its report and output are identical to a pre-refactor run.
Confirm no agent YAML file changed.

**Acceptance Scenarios**:

1. **Given** the shared base and the rebuilt harness images, **When** an existing agent of each
   harness is run end to end, **Then** its report and output are identical to the pre-refactor run.
2. **Given** the rebuilt `agent-claude`, `agent-pi`, and `agent-codex` images, **When** their image
   definitions are inspected, **Then** none carries its own OS-package installation, working-directory
   line, or Python-runtime install, and each inherits the base image's uid-1000 `node` user (no
   user-creation line of its own — none existed before either) — all of these come from the shared
   base.
3. **Given** the refactor is complete, **When** the agent YAML files are compared to before,
   **Then** no agent YAML changed.

---

### User Story 2 - Add a tool for all agents by changing one place (Priority: P1)

A maintainer needs a new command-line tool available to every shell-based agent. They add it in the
one place the common tool list lives, rebuild the base and the harness images, and the tool is
present in every shell-based harness — with no edit to any harness image definition.

**Why this priority**: This is the headline value of the feature — turning "edit every harness
image" into a one-place change. It is the reason the shared base is worth extracting, and it is
independently demonstrable once the base exists.

**Independent Test**: Add `yq` to the shared common tool list, rebuild the base and one harness
image, and confirm `yq` is present in that harness with no change to the harness image definition.

**Acceptance Scenarios**:

1. **Given** the shared common tool list, **When** a maintainer adds one tool there and rebuilds the
   base and the harness images, **Then** the tool is available in every shell-based harness image.
2. **Given** that same addition, **When** the harness image definitions are inspected, **Then** none
   of them was edited to gain the new tool.
3. **Given** the shared common tool list, **When** it is searched for the common tools, **Then** the
   common tool set — `git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, `gh`, `unzip`, and the
   standard build essentials — is defined in exactly one place, and no shell-based harness image
   re-declares those OS-package installs.

---

### User Story 3 - Common work built and stored once, faster rebuilds (Priority: P2)

An operator building images on a Raspberry Pi wants the shared work built once and stored once, and
rebuilds to be faster. Today the three shell-based harnesses each install the same five packages
(`git`, `curl`, `ca-certificates`, `python3`, `python3-pip`) plus the same pinned `dagster-pipes`;
after the refactor those — together with the newly standardized common tools (`ripgrep`, `jq`, `gh`,
`unzip`, `build-essential`) and the `/workspace` workdir — live in one shared base layer. That common
OS+tool+runtime work is built once and cached, and stored once (deduplicated) instead of three times.
(The refactor consolidates the five already-shared packages and *newly standardizes* the additional
tools; because those additions are net-new, the raw combined total is not asserted to shrink — see
Clarifications 2026-09-16 (analysis remediation).)

**Why this priority**: Building and storing the common work once is a concrete benefit for the
constrained Pi target, but it follows from the shared base rather than standing alone, so it ships
after the base and the one-place tool change.

**Independent Test**: Inspect deduplicated on-disk usage and confirm the three shell-based harnesses
share a single `agent-base` layer — the common install stored once, not three times — rather than
confirming a raw net size reduction.

**Acceptance Scenarios**:

1. **Given** the rebuilt shell-based harness images, **When** deduplicated on-disk usage is inspected,
   **Then** the common OS+tool+runtime install is stored once as the shared `agent-base` layer, not
   copied into each of the three harnesses.
2. **Given** the shared base is already built, **When** the harness images are rebuilt, **Then** the
   common OS and tool installation is not repeated per harness — it is inherited from the base.

---

### User Story 4 - Keep a harness on its own base when it can't share (Priority: P3)

A maintainer inspecting a harness that genuinely cannot use the shared base — for example a runner
that needs no shell tools — leaves that harness on its own base rather than forcing it onto a
lowest-common-denominator base that would bloat the others, and records why in the harness image.

**Why this priority**: This is the null-action safeguard: the refactor must not degrade a harness
that legitimately doesn't fit the shared base. It matters for correctness but applies only to the
exceptional case, so it is the lowest priority.

**Independent Test**: Confirm that any harness left off the shared base (e.g. `agent-python`)
carries a stated reason for staying on its own base, and that keeping it off the base did not add
the common tooling it does not need.

**Acceptance Scenarios**:

1. **Given** a harness that does not benefit from the shared base, **When** the refactor is applied,
   **Then** that harness stays on its own base and the reason is documented in its image.
2. **Given** the `agent-python` runner, which needs no shell tools, **When** the refactor is
   applied, **Then** it is not forced onto the shared base solely to share a layer.

---

### Edge Cases

- **A harness cannot use the shared base**: It stays on its own base with a documented reason rather
  than forcing every harness onto a lowest-common-denominator base (null action / US4).
- **Build ordering**: The shared base must be built before any harness image that depends on it;
  build documentation and the bootstrap script build the base first.
- **A harness needs a tool no other agent needs**: That tool stays in the individual harness image,
  not the shared common tool list, which holds only the tools common to all shell-based agents.
- **Runtime (per-agent) tool installation**: Out of scope here (deferred to spec 022); this feature
  only changes how images are built, not how a running agent adds tools.

## Requirements *(mandatory)*

### Functional Requirements

**Shared base**

- **FR-001**: There MUST be a single shared base image (`agentbox/agent-base`) that carries the
  common operating system, the non-root uid-1000 user the harness images already assume, the
  `/workspace` working directory, and the common command-line tools.
- **FR-002**: The shared base's common tool set MUST include `git`, `curl`, `ca-certificates`,
  `ripgrep`, `jq`, the GitHub CLI (`gh`), `unzip`, and the standard build essentials (the
  `build-essential` apt package).
- **FR-003**: The common tool list MUST be defined in exactly one place; adding or removing a tool
  shared by all shell-based agents MUST require editing only that one place.
- **FR-013**: The shared base MUST additionally provide the Python 3 runtime (`python3` and its
  package installer) and the pinned `dagster-pipes` (Dagster 1.13.21) that every shell-based harness
  wrapper is launched with and reports through, so that no shell-based harness re-declares them. This
  runtime is defined in the same single place as the common tool set.

**Harness images on the base**

- **FR-004**: The shell-based harness images (`agent-claude`, `agent-pi`, `agent-codex`) MUST build
  on the shared base and MUST NOT re-declare the OS-package installation, the non-root-user
  creation, the working directory, or the Python runtime / pinned `dagster-pipes` that the base
  provides.
- **FR-005**: Each of those harness images MUST retain only its harness-specific setup — its harness
  installation, its entrypoint, and its harness-specific environment (for example `CODEX_HOME`).
- **FR-006**: Each harness image built on the shared base MUST indicate, in the image itself, that
  its common tooling comes from the shared base (a one-line pointer to the base).
- **FR-007**: The common tools MUST be present and runnable in every shell-based harness image built
  on the base (e.g. `git`, `rg`, `jq`, and `gh` resolve to executables).

**Behavioral parity & scope**

- **FR-008**: Every existing agent MUST behave identically after the refactor across all four
  harnesses. Parity means functional/format equivalence — the report format and agent output
  semantics are unchanged because the wrapper/runner and report code are unchanged and the image
  test suites pass unchanged — not a byte-identical comparison of two live runs (which always differ
  by timestamp, run id, and model nondeterminism).
- **FR-009**: The refactor MUST require no changes to any agent YAML file.
- **FR-010**: A harness that genuinely cannot use the shared base MUST be left on its own base with
  a documented reason, rather than forcing a lowest-common-denominator base onto the others.
  `agent-python` is decided to stay on `python:3.12-slim` — it needs the Python runtime rather than
  the Node-bearing base and needs no shell tools — with that reason documented in its image.

**Footprint & build process**

- **FR-011**: The common OS + tool + runtime install MUST be stored once — as a single shared base
  layer that all three shell-based harness images share — rather than built and stored separately in
  each harness. Verified via deduplicated on-disk usage (the image store's unique size, which counts
  the shared base layer once, not the sum of each image's individually reported size). Because the
  shared base standardizes tools the harnesses did not carry before (`ripgrep`, `jq`, `gh`, `unzip`,
  `build-essential`), the raw combined total is NOT required to be numerically smaller than before
  the refactor; the guaranteed win is single-storage of the shared install (see Clarifications
  2026-09-16 (analysis remediation)).
- **FR-012**: The build documentation (README build steps) and the bootstrap script
  (`scripts/bootstrap.sh`) MUST build the shared base first and then the harness images; compose
  notes MUST be updated if they reference image builds.

### Key Entities *(include if feature involves data)*

- **Shared base image (`agentbox/agent-base`)**: The single image carrying the common OS, the
  non-root uid-1000 user, the `/workspace` working directory, the common command-line tools, and the
  Python 3 runtime plus pinned `dagster-pipes` the shell-based wrappers run on; the sole place the
  common tool list and that shared runtime are defined.
- **Common tool set**: The command-line tools shared by every shell-based agent — `git`, `curl`,
  `ca-certificates`, `ripgrep`, `jq`, `gh`, `unzip`, and the standard build essentials — installed
  once in the shared base.
- **Shell-based harness image**: A harness image (`agent-claude`, `agent-pi`, `agent-codex`) that
  builds on the shared base and adds only its harness install, entrypoint, and harness-specific
  environment.
- **Standalone harness image**: A harness image that stays on its own base because it cannot benefit
  from the shared base (e.g. `agent-python`, which needs no shell tools), with a documented reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can make a new command-line tool available to every shell-based agent by
  editing exactly one place and rebuilding, with zero edits to any harness image definition.
- **SC-002**: Every existing agent, across all four harnesses, produces a report of the same format
  and output of the same semantics before and after the refactor (functional/format equivalence, per
  FR-008; verified by the unchanged wrapper/runner and report code and the image test suites passing
  unchanged), rather than a byte-identical rerun.
- **SC-003**: No shell-based harness image contains its own OS-package installation, working-directory
  declaration, or Python-runtime install, and each inherits the base's uid-1000 `node` user rather
  than creating one (no harness ever carried a user-creation line) — the common install is defined in
  exactly one place.
- **SC-004**: The common tools (`git`, `rg`, `jq`, `gh`, and the rest of the common set) resolve to
  executables in each shell-based harness image.
- **SC-005**: The common OS + tool + runtime install is stored once, not three times — verified by
  inspecting deduplicated on-disk usage (the image store's unique size) and confirming the three
  shell-based harnesses share a single `agent-base` layer rather than each carrying its own copy. The
  raw combined total is not asserted to be smaller than before, since the base standardizes tools the
  harnesses did not previously carry (see Clarifications 2026-09-16 (analysis remediation)).
- **SC-006**: The refactor changes no agent YAML file.

## Assumptions

- The four harness images that exist today — `agent-claude`, `agent-codex`, `agent-pi`, and
  `agent-python` — are the complete set; this feature changes how they are built, not which
  harnesses exist.
- The harness images already assume a non-root uid-1000 `node` user and a `/workspace` working
  directory; the shared base provides exactly those so the harnesses need not redeclare them.
- Three of the four harnesses require Node, so a Node-bearing shared base is the reasonable common
  denominator; `agent-python` needs the Python runtime rather than Node and no shell tools, so it
  stays on its own base (`python:3.12-slim`) — decided, not deferred (see FR-010).
- The three shell-based harness wrappers are launched with `python3` and report through a pinned
  `dagster-pipes`; the shared base therefore carries the Python runtime and that pinned
  `dagster-pipes` alongside the common CLI tools (see FR-013), so the harnesses need not redeclare
  them. `agent-python` keeps installing its own `dagster-pipes` because it stays on the Python base.
- The specific base OS/runtime image and the exact build-instruction details are plan-level
  decisions; this specification fixes the common tool set, the single-source-of-truth requirement,
  and the behavioral-parity requirement, not the Dockerfile mechanics.
- "Standard build essentials" means the common compiler/build toolchain packages that shell-based
  agents rely on, defined once in the shared base.
- **Null action / fallback**: If a harness cannot be moved onto the shared base without harm, it
  stays on its own base with the reason recorded, rather than bloating the shared base for the rest.

## Out of Scope

- Per-agent images (one image per agent).
- Runtime tool installation for a running agent (deferred to spec 022).
- Changing which harness images exist.
- Language toolchains beyond the common set.
