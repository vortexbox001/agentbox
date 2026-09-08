<!--
Sync Impact Report
  Version change: 1.0.0 → 1.1.0 (generalised all principles — removed implementation specifics)
  Modified principles:
    - I. Container Isolation → I. Agent Isolation (broader; no longer names specific networks)
    - II. Declarative Agent Definitions → II. Configuration over Code (broader)
    - III. Credential Hygiene → III. Secrets Never in the Open (broader)
    - IV. Harness Abstraction → IV. Uniform Interface, Diverse Runtimes (broader)
    - V. Ephemeral Runs, Persistent Outputs → V. Ephemeral Runs, Immutable Outputs (broader)
    - VI. Documentation Accuracy → VI. Docs Track Reality (broader)
  Removed sections:
    - Operational Constraints (implementation-specific details)
    - Development Workflow (derivable from repo)
  Added sections: none
  Deferred TODOs: none
-->

# Agentbox Constitution

## Core Principles

### I. Agent Isolation

Each agent run MUST be sandboxed so that it cannot affect other runs, the orchestrator,
or the host beyond its explicitly granted interfaces. Isolation covers compute resources,
network reach, and filesystem access. Grant the minimum of each that the agent needs.

**Rationale:** Autonomous AI agents with tool access carry inherent risk. Isolation bounds
the blast radius of any single run.

### II. Configuration over Code

Adding or modifying an agent SHOULD require only a change to declarative configuration —
not orchestrator code. The orchestrator discovers and interprets agent definitions
automatically.

**Rationale:** The barrier to creating a new agent should be low, and every agent's
definition should be auditable in one place without reading Python.

### III. Secrets Never in the Open

Secrets MUST NOT appear in configuration files checked into version control, in process
command lines, or in logs. They MUST be injected at runtime through environment-variable
passthrough or mounted credential files, and prefer long-lived tokens over short-lived
copies that go stale.

**Rationale:** Agent launches produce command lines and log entries visible across the
system. Passthrough-by-name keeps secret values out of all of them.

### IV. Uniform Interface, Diverse Runtimes

Different agent runtimes (harnesses) may have fundamentally different execution models,
but they MUST present a common configuration surface to agent authors. Adding a new
runtime MUST NOT break or change the schema for existing ones.

**Rationale:** Agent authors think in prompts, schedules, and resource limits — not
runtime internals. The orchestrator absorbs that complexity.

### V. Ephemeral Runs, Immutable Outputs

Every run MUST produce uniquely identifiable output. Agents MUST write finished artefacts
to the designated output location and MUST NOT read or modify prior runs' output.
Workspaces are scratch space and MAY be wiped between runs.

**Rationale:** Immutable, identifiable outputs keep every run auditable and prevent agents
from being influenced by — or corrupting — earlier results.

### VI. Docs Track Reality

Documentation MUST reflect the current state of the codebase. Claims that diverge from
the source code are bugs, not tech debt. Automated verification of documentation accuracy
is preferred over manual review alone.

**Rationale:** The system runs headless and unattended. When docs are wrong, operators
misconfigure agents and failures surface hours later.

## Governance

This constitution captures the guiding principles for Agentbox's architecture and
operation. Implementation details — specific file paths, tool names, network names,
platform targets — live in the README and code, not here.

- **Amendments** require updating this document with a version bump, rationale, and date.
- **Versioning** follows semantic versioning: MAJOR for principle removals or
  redefinitions, MINOR for new principles or material expansions, PATCH for wording fixes.
- **Compliance** is verified through automated documentation review and human review on
  pull requests.

**Version**: 1.1.0 | **Ratified**: 2026-09-08 | **Last Amended**: 2026-09-08
