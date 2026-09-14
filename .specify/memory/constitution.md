<!--
Sync Impact Report
  Version change: 1.1.0 → 1.2.0 (added Principle VII. One Design System — spec 009)
  Modified principles: none
  Removed sections: none
  Added sections:
    - VII. One Design System (design-system tokens + shared component macros; no literal
      colours/fonts/pixel values in app styling; new components land in the design system first)
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

### VII. One Design System

Every user-facing screen MUST be built from the shared design system: styling MUST resolve
from design-system tokens, and controls MUST be composed from the shared component macros.
Literal colours, typefaces, and pixel values MUST NOT appear in application styling or
templates. A new component MUST land in the design system first and the shared component set
second, so a single change to a token or a component updates the whole interface.

**Rationale:** AgentBox is meant to feel like a sibling of the tools it lives beside. One
authoritative design system keeps every screen consistent, makes visual change a single edit,
and lets both humans and agents build correct UI by reusing the same parts.

## Governance

This constitution captures the guiding principles for Agentbox's architecture and
operation. Implementation details — specific file paths, tool names, network names,
platform targets — live in the README and code, not here.

- **Amendments** require updating this document with a version bump, rationale, and date.
- **Versioning** follows semantic versioning: MAJOR for principle removals or
  redefinitions, MINOR for new principles or material expansions, PATCH for wording fixes.
- **Compliance** is verified through automated documentation review and human review on
  pull requests.

**Version**: 1.2.0 | **Ratified**: 2026-09-08 | **Last Amended**: 2026-09-13
