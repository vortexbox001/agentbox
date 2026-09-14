# Feature Specification: File Layout Overhaul — Three Roots

**Feature Branch**: `010-file-layout-overhaul`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: separate the three kinds of files agentbox has today — the
product (same on every box), the instance configuration (this box's agents, prompts,
projects — versioned in git, edited by the UI), and instance state (run records, outputs,
workspaces, Dagster storage — on disk, backed up).

## Overview

Today agentbox mixes three kinds of files. Product code and this box's instance
configuration both live in the product repository (`agents/`, `prompts/`,
`orchestrator/settings.yaml`, `litellm/config.yaml`), and instance state is scattered
across seven top-level directories under `/data` (`/data/dagster`, `/data/outputs`,
`/data/workspaces`, `/data/credentials`, and more). An operator cannot tell what is safe
to redeploy, what to back up, or what to check into their own git repository.

This feature draws a hard line between the three kinds and gives each a single root:

- **Product** — the checkout of the agentbox repository, identical on every box, mounted
  read-only.
- **Instance configuration** — one directory (`config/`) holding this box's agents,
  prompts, projects, external-asset registrations, settings, and LiteLLM overlay;
  gitignored in the product repo and intended to become its own git repository.
- **Instance state** — one directory (`$AGENTBOX_DATA`) holding run records, outputs,
  workspaces, repo mirrors, provenance, credentials, and box keys; backed up as a unit.

Dagster's own storage keeps a separate sibling root (`$DAGSTER_HOME`) because Dagster may
serve non-agentbox workloads on the same box.

## Clarifications

### Session 2026-09-14

- Q: Where should the Dagster Pipes messages directory (agent→Dagster run-report transport)
  live after this change? → A: It stays under `$DAGSTER_HOME` (`PIPES_ROOT` derives from the
  Dagster-storage root, not the state root). It is the Dagster Pipes transport Dagster reads
  and is wiped per run — transient scratch, not backed-up state — so the "Dagster's own
  storage" definition explicitly includes it and the migration leaves it untouched.
- Q: Where should the generated LiteLLM config that LiteLLM loads live? → A: Under the
  instance-configuration root (a generated file such as `litellm.rendered.yaml`), gitignored
  within the configuration repository, and mounted into the LiteLLM container from there.
- Q: How should the migration treat the box's `/data/logs` directory (currently empty, not in
  the brief's migration list)? → A: Leave it untouched and record in the printed plan that it
  was left in place; no root depends on it.

After this change a fresh install is: clone agentbox, copy `examples/config/` to
`config/`, point `AGENTBOX_DATA` at a disk, run bootstrap, `docker compose up`. Every
future feature places its files under one of the two instance roots.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Migrate the existing box without losing anything (Priority: P1)

The operator of the running Raspberry Pi box upgrades to this layout. They run a
migration tool that relocates their configuration and state into the new roots, restart
the stack, and find every agent, prompt, schedule, past run, and output exactly where the
UI and Dagster expect it — with no manual file shuffling and no lost history.

**Why this priority**: There is a live box with real agents, schedules, and run history.
A layout change that loses or misplaces any of it is unacceptable. Migration is the one
path that must work before anything else ships.

**Independent Test**: On a copy of the existing box, run the migration in dry-run and
confirm the printed plan matches the real contents; run it with apply; restart the stack;
open the UI and Dagster and confirm all agents, prompts, schedules, past runs, and outputs
are present and functional. Confirm the product repository's git status shows only the
expected deletions and the new gitignore entry.

**Acceptance Scenarios**:

1. **Given** a box on the old layout, **When** the operator runs the migration tool
   without the apply flag, **Then** it prints the full plan of every move it would make
   and changes nothing on disk.
2. **Given** the printed plan, **When** the operator runs the migration with apply,
   **Then** `agents/` and `prompts/` and `orchestrator/settings.yaml` move into `config/`,
   each state directory under the old data root moves under `$AGENTBOX_DATA`, and the
   agent-logs directory moves into `$AGENTBOX_DATA/runs`.
3. **Given** agent YAML whose `output_dir`, `workspace`, or `env_file` values begin with
   an old root, **When** the migration applies, **Then** those values are rewritten to the
   corresponding new root.
4. **Given** a destination directory that already has content, **When** the operator runs
   the migration, **Then** it refuses to run rather than overwrite or merge.
5. **Given** a completed migration and a restarted stack, **When** the operator opens the
   UI and Dagster, **Then** every agent, prompt, schedule, past run, and output is present
   and the product repository's git status shows only the deletions of `agents/` and
   `prompts/` and the new gitignore entry.

---

### User Story 2 - Fresh install from examples (Priority: P1)

A new operator stands up a box from scratch. They clone the product repository, copy the
examples into `config/`, point the two instance roots at empty directories, run bootstrap,
and bring the stack up. The UI lists the example agents, one materializes successfully,
and every file the system writes lands under one of the two instance roots — nothing
outside them.

**Why this priority**: The headline promise of this feature is a clean, documented fresh
install. If a new box cannot be stood up from examples with everything landing under the
two roots, the separation has not actually been achieved.

**Independent Test**: In a clean directory, clone, copy `examples/config/` to `config/`,
set both instance roots to empty directories, run bootstrap, bring the stack up. Confirm
the UI lists the example agents, one materializes, its run directory appears under the
data root's `runs/`, and a filesystem watch shows nothing written outside the two roots.
Confirm the Dagster home contains no agentbox run directories.

**Acceptance Scenarios**:

1. **Given** a clean clone with `examples/config/` copied to `config/` and empty instance
   roots, **When** the operator runs bootstrap and brings the stack up, **Then** the UI
   lists the example agents.
2. **Given** the running stack, **When** an example agent materializes, **Then** its run
   directory appears under the data root's `runs/` directory.
3. **Given** a filesystem watch over the whole disk during a materialization, **When** the
   run completes, **Then** every path written falls under either the config root or the
   data root, and the Dagster home contains no agentbox run directories.

---

### User Story 3 - Relocate the roots to any disk (Priority: P2)

An operator points the two instance roots at non-default paths (a mounted data disk, a
different partition for Dagster). Every service follows the configured paths, and nothing
is written back to the default locations.

**Why this priority**: The reason to separate state into one root is so it can live on
backed-up storage. That is only real if the root is genuinely relocatable end to end,
with no component silently falling back to a hard-coded default.

**Independent Test**: Set both instance roots to non-default empty directories, run the
stack, exercise an agent, and confirm all reads and writes go to the configured paths with
no residual writes to the defaults.

**Acceptance Scenarios**:

1. **Given** both instance roots set to non-default paths, **When** the stack runs and an
   agent materializes, **Then** all state is read from and written to the configured
   paths.
2. **Given** the same run, **When** the operator inspects the default locations, **Then**
   nothing was written there.

---

### User Story 4 - Configuration edits stay out of the product repo (Priority: P2)

The operator checks out their own configuration repository at the config path. They edit
agents and prompts through the UI. Those edits land in the configuration directory, and
the product repository's git status stays clean.

**Why this priority**: The point of a separate config root is that an operator's own
changes never touch the product repo, so product upgrades stay conflict-free. This must
hold with the config directory as an independent git repository.

**Independent Test**: Check out a separate git repository at the config path. Make edits
through the UI. Confirm the edits appear in the config directory and the product
repository's git status is clean.

**Acceptance Scenarios**:

1. **Given** a separate git repository checked out at the config path, **When** the
   operator edits an agent or prompt through the UI, **Then** the change lands in the
   config directory.
2. **Given** that edit, **When** the operator checks the product repository's git status,
   **Then** it is clean.

---

### User Story 5 - Config paths are validated against the roots (Priority: P2)

An operator (or the UI) submits an agent definition whose output, workspace, or env-file
path points into the product tree or otherwise outside the data root. The system rejects
it with a message that names the offending field and states the rule.

**Why this priority**: The separation is only enforceable if configuration cannot point
state at the wrong place. A clear, field-named rejection prevents an agent from writing
into the read-only product tree or scattering state outside the backed-up root.

**Independent Test**: Submit an agent YAML with an output path under the product tree.
Confirm it is rejected with a message naming the field and the rule.

**Acceptance Scenarios**:

1. **Given** an agent definition whose output path is under the product tree, **When** it
   is validated, **Then** it is rejected with a message naming the field and stating that
   the path must fall under the data root.
2. **Given** an agent definition whose output, workspace, and env-file paths fall under
   the data root or are the documented defaults, **When** it is validated, **Then** it is
   accepted.

---

### User Story 6 - LiteLLM config is generated from template plus overlay (Priority: P2)

The product ships an alias-tier template (cheap→Haiku, smart→Sonnet, and so on). The
instance supplies providers, key names, and alias→model bindings in its own overlay. A
generator merges the two into the file LiteLLM loads. A missing provider key is reported
when the config is generated, not on the first live request.

**Why this priority**: Model routing has a product-owned part (the tier names features
depend on) and an instance-owned part (which providers and keys this box uses). Splitting
them keeps the product upgradeable while letting each box bind its own providers, and
failing at render time turns a silent runtime outage into an obvious setup error.

**Independent Test**: Provide a template and an overlay; run the generator; confirm the
output binds the product's alias tiers to the instance's providers. Remove a referenced
provider key from the environment; run the generator; confirm it reports the missing key
by name.

**Acceptance Scenarios**:

1. **Given** the product's alias-tier template and an instance overlay naming providers
   and bindings, **When** the generator runs, **Then** it produces a config in which the
   product's alias tiers are bound to the instance's providers.
2. **Given** an overlay that references a provider key name that is not present in the
   environment, **When** the generator runs, **Then** it reports the missing provider key
   by name and does not produce a config that would fail only at first request.

---

### Edge Cases

- **Partial prior migration**: a destination root already holds some content. The
  migration refuses to run rather than merge or overwrite, and says which destination
  blocked it.
- **Broken metadata link after moving run logs**: if moving the agent-logs directory out
  of the Dagster home breaks a materialization-metadata link for existing runs, a
  compatibility symlink from the old location to the new one is left for the migrated
  history only, recorded in the migration plan; new runs never write under the Dagster
  home.
- **Ownership on fresh directories**: bootstrap creates the data tree with correct
  ownership so the UI and agent containers can write — workspaces and outputs owned by the
  runtime user, credentials restricted to owner-only access.
- **Documented-default paths**: an agent that omits an output or workspace path uses the
  documented default under the data root and passes validation without naming a path.
- **Env vars unset**: with no instance-root env vars set, all three roots resolve to their
  documented defaults and the stack still starts.
- **Config directory is not a git repository**: UI edits still land in the config
  directory; the git-cleanliness guarantee simply does not apply because there is no repo
  there to keep clean.
- **Unlisted directory under the old data root**: a directory under the old data root that
  the migration does not recognize (for example an empty `logs/` directory) is left in
  place, not moved or deleted, and the printed plan records that it was left untouched. No
  new root depends on it.

## Requirements *(mandatory)*

### Functional Requirements

#### Roots and resolution

- **FR-001**: The system MUST define exactly three roots, each from a single environment
  variable with a documented default: an instance-configuration root (default: a `config`
  directory resolved against the product checkout), an instance-state root (default:
  `/data/agentbox`), and a Dagster-storage root kept as a sibling (default:
  `/data/dagster`).
- **FR-002**: The three roots MUST be resolved once in the orchestrator and once in the
  UI, and MUST NOT be hard-coded anywhere else. Every other path in the system MUST derive
  from one of the three roots.
- **FR-003**: With no instance-root environment variables set, all three roots MUST
  resolve to their documented defaults and the stack MUST start normally.
- **FR-004**: When the instance roots are set to non-default paths, every service MUST read
  from and write to those paths, with no residual reads or writes to the defaults.

#### Instance configuration tree

- **FR-005**: The instance-configuration root MUST contain the agent definitions, prompt
  files, projects, external-asset registrations, an instance settings file, and an
  instance LiteLLM overlay, each in a defined subpath.
- **FR-006**: The instance-configuration root MUST be gitignored in the product repository
  so that a configuration repository can be checked out at that path without appearing in
  the product repository's git status.
- **FR-007**: The UI MUST read and write instance configuration (agents, prompts) under
  the configuration root, and those writes MUST NOT modify any file in the product tree.
- **FR-008**: The agent-definition templates MUST be removed from the instance
  configuration tree; the UI's template picker MUST read templates from the examples tree,
  not from the instance's agents directory.

#### Instance state tree

- **FR-009**: The instance-state root MUST contain, each in a defined subpath: per-run
  records, outputs, workspaces, repo mirrors, provenance, credentials, and box keys.
- **FR-010**: Per-run records (the agent run logs that today live under the Dagster home)
  MUST live under the state root's `runs/` subpath; new runs MUST NOT write run records
  under the Dagster home. The Dagster Pipes messages directory (the per-run agent→Dagster
  transport, wiped after each run) is the one exception: it stays under the Dagster-storage
  root and its path derives from that root.
- **FR-011**: The credentials subpath MUST be created with owner-only access; workspaces
  and outputs MUST be created owned by the runtime user so the UI and agent containers can
  write to them.
- **FR-012**: The Dagster-storage root MUST contain only Dagster's own storage, compute
  logs, and the transient Dagster Pipes messages directory (the agent→Dagster run-report
  transport); Dagster's configuration MUST derive its paths from the Dagster-storage root,
  and everything else agentbox-owned (run records, outputs, workspaces, repo mirrors,
  provenance, credentials, keys) MUST derive from the state root.

#### Product-owned catalogs

- **FR-013**: The product tree MUST retain the product-owned catalogs (container image
  definitions, the invariants library, the schema, the design system) and MUST be mounted
  read-only wherever a service consumes it.
- **FR-014**: The product's LiteLLM configuration MUST become an alias-tier template; the
  file LiteLLM actually loads MUST be generated by merging that template with the instance
  overlay. The generated file MUST live under the instance-configuration root (a generated
  artifact such as `litellm.rendered.yaml`, gitignored within the configuration repository)
  and MUST be the file the LiteLLM container mounts and loads.

#### Examples

- **FR-015**: The product MUST ship an examples tree containing the agent-definition
  templates, a sample prompt, a sample project, and minimal settings and LiteLLM-overlay
  files, sufficient to stand up a working box by copying it to the configuration root.

#### LiteLLM generation

- **FR-016**: A generator MUST merge the product alias-tier template with the instance
  LiteLLM overlay into the file LiteLLM loads (written under the instance-configuration
  root, per FR-014), and MUST run both on demand and at stack start.
- **FR-017**: When the overlay references a provider key name that is not present in the
  environment, the generator MUST report the missing key by name at generation time and
  MUST NOT emit a config whose only failure would be at first request.

#### Migration

- **FR-018**: A migration tool MUST relocate the old layout to the new one: agent
  definitions and prompts into the configuration root, the old orchestrator settings file
  into the configuration root, each state directory under the old data root into the
  corresponding state-root subpath, and the agent-logs directory into the state root's
  `runs/` subpath, leaving the rest of the Dagster home untouched (including the Dagster
  Pipes messages directory, which stays under the Dagster-storage root). Any directory
  under the old data root that the tool does not recognize MUST be left in place and
  recorded in the plan as left untouched.
- **FR-019**: The migration tool MUST rewrite `output_dir`, `workspace`, and `env_file`
  values in agent definitions when those values begin with an old root, mapping them to
  the corresponding new root.
- **FR-020**: The migration tool MUST print its full plan and change nothing unless an
  explicit apply flag is given, and MUST refuse to run if any destination already has
  content.
- **FR-021**: If relocating the agent-logs directory would break a materialization-metadata
  link for existing runs, the migration MUST leave a compatibility symlink from the old
  agent-logs location to the new runs location for the migrated history only, and MUST
  record that symlink in its printed plan.
- **FR-022**: The bootstrap tool MUST create the data tree with correct ownership (runtime
  user for workspaces and outputs, owner-only for credentials).

#### Compose and mounts

- **FR-023**: The agentbox services (orchestrator, daemon, UI) MUST mount exactly these
  host paths: the product tree read-only, the configuration root (writable for the UI), the
  state root, the Dagster-storage root (for the orchestrator and daemon only), and the
  Docker socket. The LiteLLM service mounts only its generated config file, which is a path
  under the configuration root (per FR-014); no service mounts any host path outside the
  three roots, the product tree, or the Docker socket.
- **FR-024**: Agent containers MUST keep their existing internal mount contract (the
  workspace, output, and prompt mount points unchanged); only the host side of each bind
  changes.

#### Validation and schema

- **FR-025**: The agent-definition schema validation MUST reject an agent whose
  `output_dir`, `workspace`, or `env_file` falls outside the data root (unless it is a
  documented default), MUST reject paths under the product tree, and MUST name the
  offending field and state the rule in the rejection message.
- **FR-026**: The schema version MUST increment, and the schema's migrations list MUST
  record the root change.

#### Documentation

- **FR-027**: The README MUST gain a "Layout" section describing the three-kinds model and
  both instance trees, and the repository's file-tree listing MUST be rewritten to match.
- **FR-028**: The contributor guide MUST state where each new kind of file goes: product
  code in the product, instance configuration under the configuration root, state under
  the state root, samples under the examples tree.
- **FR-029**: The environment-variable example file MUST document all three root variables.

### Key Entities *(include if feature involves data)*

- **Product tree**: the agentbox repository checkout; identical on every box; mounted
  read-only; holds code and product-owned catalogs (images, invariants, schema, design
  system, LiteLLM alias-tier template, examples).
- **Instance-configuration root**: one directory holding this box's agents, prompts,
  projects, external-asset registrations, settings, and LiteLLM overlay; gitignored in the
  product repo; intended to be its own git repository.
- **Instance-state root**: one directory holding runs, outputs, workspaces, repo mirrors,
  provenance, credentials, and box keys; backed up as a unit.
- **Dagster-storage root**: a sibling directory holding only Dagster's own storage and
  compute logs; may serve non-agentbox workloads.
- **Examples tree**: product-owned sample configuration (agent templates, a sample prompt,
  a sample project, minimal settings and LiteLLM overlay) copied to seed a new instance.
- **LiteLLM alias-tier template**: product-owned mapping of alias tiers that features
  depend on; merged with the instance overlay to produce the loaded config.
- **Instance LiteLLM overlay**: instance-owned providers, key names, and alias→model
  bindings.
- **Migration plan**: the printed set of moves and rewrites (including any compatibility
  symlink) the migration tool would apply.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After migrating the existing box and restarting the stack, 100% of agents,
  prompts, schedules, past runs, and outputs are present and functional in the UI and
  Dagster.
- **SC-002**: After migration, the product repository's git status shows only the deletions
  of the moved configuration directories and the new gitignore entry — no other changes.
- **SC-003**: A fresh install can be stood up from a clean directory in the documented
  steps (clone, copy examples to config, point the data root at a disk, bootstrap, bring
  the stack up) with no manual file editing beyond the environment file.
- **SC-004**: During a fresh-install materialization, a filesystem watch records zero
  writes outside the two instance roots, and the Dagster-storage root contains zero
  agentbox run directories.
- **SC-005**: With the instance roots set to non-default paths, zero writes land in the
  default locations across a full agent run.
- **SC-006**: An agent definition with an output path under the product tree is rejected
  100% of the time with a message that names the field and states the rule.
- **SC-007**: Editing an agent or prompt through the UI with a separate configuration
  repository checked out leaves the product repository's git status clean 100% of the time.
- **SC-008**: A LiteLLM overlay that references an absent provider key is reported at
  generation time in 100% of cases, before any live request is attempted.
- **SC-009**: Every path used by any service resolves from exactly one of the three root
  variables; no state or configuration path is hard-coded outside the two resolution
  points.

## Assumptions

- The existing box is the single Raspberry Pi described in the project instructions; there
  is exactly one instance per box (multi-instance is explicitly out of scope).
- The runtime user for workspaces and outputs is the configured host user (uid 1000 by
  default), matching the current ownership model.
- The Dagster-storage root remains at its current default location so that Dagster's own
  storage, compute logs, and run database are undisturbed by the migration; only the
  agent-logs subtree moves out of it.
- The configuration directory may or may not be an independent git repository; the
  git-cleanliness guarantee for the product repo holds regardless, and the guarantee for
  the config repo applies only when one is checked out there.
- Feature areas referenced by the target trees but owned by other briefs (projects,
  external assets, repo mirrors, provenance, box keys) are represented only as reserved
  subpaths here; their contents and behavior are defined by those briefs.
- The migration operates on a box that is on the immediately preceding layout; migrating
  from older, pre-existing layouts is not in scope.

## Out of Scope

- Multiple configuration directories or running multiple instances on one box.
- Sharing the Dagster-storage root with a non-agentbox Dagster code location (the sibling
  layout supports it, but it is not configured here).
- Moving the design system or the container image definitions out of the product tree.
- Git-committing configuration edits from the UI (a later brief); this feature only
  guarantees edits land in the config directory and leave the product repo clean.
- Backup tooling beyond documenting that the two instance roots are the single things to
  back up.
