# AGENTS.md

Guidance for AI coding agents working in this repository. See `README.md` for the full
architecture and operator documentation.

## Overview

AgentBox is a self-hosted agent-orchestration platform: Dagster orchestrates runs, LiteLLM proxies
LLM calls, and agents run as short-lived containers. Agents are declared in agent YAML files with
prompts alongside them (both under the config root — see below); the orchestrator (`orchestrator/`)
turns each definition into a Dagster job. A FastAPI management UI lives in `ui/`.

## Where each kind of file goes

Files fall into three kinds, and each has one home. Put new work in the right one; the README's
**Layout** section has the full picture and the resolution rule (every path derives from one of
three roots, read only in `orchestrator/paths.py` and `ui/config.py`).

- **Product code and product-owned catalogs → the product tree (this repo).** Orchestrator and UI
  code, agent images (`images/`), the schema (`ui/schema.py`), the design system
  (`ui/design-system/`), the LiteLLM alias-tier template (`litellm/config.template.yaml`), and the
  seed samples (`examples/`). Mounted read-only in every service. If it is identical on every box,
  it belongs here.
- **Instance configuration → the config root (`$AGENTBOX_CONFIG`, default `<repo>/config`).** This
  box's `agents/`, `prompts/`, `projects/`, `external-assets/`, `settings.yaml`, and the LiteLLM
  overlay/rendered config. Gitignored in this repo (via `/config/`) so it can be its own git repo;
  the UI writes here and never into the product tree. **Do not** add agent or prompt files at the
  repo top level — that path no longer exists as instance config.
- **Instance state → the data root (`$AGENTBOX_DATA`, default `/data/agentbox`).** Runs, outputs,
  workspaces, repo mirrors, provenance, credentials, and box keys — anything a run reads or writes.
  Never hard-code a `/data/...` state path; derive it from `DATA_ROOT`.
- **Seed samples → the examples tree (`examples/config/`).** Agent templates (`_template-*.yaml`),
  a sample prompt/project, a minimal `settings.yaml`, and a minimal LiteLLM overlay. A fresh install
  is stood up by copying `examples/config/` to the config root.

## Design system (management UI)

The **AgentBox design system** lives in the repo at `ui/design-system/` and is the single source of
truth for how the management UI looks and behaves. `ui/design-system/readme.md` is the authoritative
guide; the token stylesheets under `ui/design-system/tokens/` are the machine-readable source. It is
served read-only at `/design-system/` (the developer reference app) and the `agentbox-design` skill
points at it.

The design system makes AgentBox a **sibling of Dagster** — same layout, fonts, and surfaces, only
the brand differs. When changing the UI (`ui/templates/`, `ui/static/`), follow three rules, all
enforced by the UI test suite (see **Stack and tests**):

- **Style through tokens.** Every colour, spacing, type, radius, shadow, and transition resolves
  from a design-system `var(--…)` token. No literal colours (hex/rgb/hsl/named), no literal pixel
  values, no `font-family`, and no `--ax-*` custom properties in app styling or templates.
- **Keep CSS in stylesheets.** App CSS lives in `ui/static/app.css` and the token stylesheets —
  never as an inline `style="…"` attribute or an embedded `<style>` block in a template. The only
  exception is the self-contained design-system reference pages under `ui/design-system/`, which
  must render offline as standalone documents.
- **Compose from macros.** Every control is rendered from the shared Jinja2 macros in
  `ui/templates/components/macros.html` (`button`, `text_input`, `select`, `checkbox`, `toggle`,
  `badge`, `status_dot`, `alert`, `spinner`, `tabs`, `card`, `dialog`, `table`). Do not hand-roll
  button/card/table markup or bespoke control styling. New components land in the design system
  first and the shared macro set second.

## Stack and tests

Recorded once here so planning does not re-derive it: a feature plan's Technical Context copies
these facts and states only what the feature adds or changes.

- **Language**: Python 3.12 everywhere (`python:3.12-slim` for the orchestrator, UI, and `api`
  harness image; `node:20-slim` for the `claude-code`, `codex`, and `pi` harness images).
  Browser code is plain ES-module JavaScript in `ui/static/` — no bundler, no `package.json`.
- **Orchestrator** (`orchestrator/`): Dagster **1.13.21** plus `dagster-pipes` for run reports,
  pinned in `orchestrator/Dockerfile`; the agent images pin `dagster-pipes` to the same version.
  Bump all of them together.
- **Management UI** (`ui/`): FastAPI + Jinja2 + httpx + PyYAML + croniter, pinned in
  `ui/requirements.txt`; tested through FastAPI's `TestClient`.
- **Storage**: files only, no database. Agent YAML under the config root is the source of truth,
  runs and outputs live under the data root, and Dagster keeps its own run storage under
  `$DAGSTER_HOME`.
- **Platform**: Docker Compose on a Raspberry Pi (arm64, Debian Bookworm). Services: `litellm`,
  `dagster-webserver`, `dagster-daemon`, `ui`, and the one-shot `litellm-generate`. Agents run as
  sibling containers through the host's Docker socket.
- **Project type**: multi-package product tree — orchestrator, UI, four agent images, LiteLLM
  generator, host scripts (see the README's **Repository layout**).

**Dev environment** — a repo-root venv (gitignored):

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r ui/requirements.txt dagster==1.13.21 dagster-pipes==1.13.21
```

**Tests** — five pytest suites, one per package, run from the repo root:

```bash
.venv/bin/python -m pytest -q ui/tests            # schema, stores, routes, docs, design-system conformance
.venv/bin/python -m pytest -q orchestrator/tests  # factory, definitions, governors, paths, redaction, reports
.venv/bin/python -m pytest -q images/tests        # per-harness report and event parsers
.venv/bin/python -m pytest -q litellm/tests       # config generator
.venv/bin/python -m pytest -q scripts/tests       # layout migration
```

All suites pass on the box. Off the box, two orchestrator tests assume a writable `/data` and an
unset `DAGSTER_HOME`; everything else is hermetic.

## Conventions

- Add or change an agent through its YAML under the config root's `agents/` and its prompt under
  `prompts/` — not orchestrator code (the orchestrator auto-discovers definitions from the config
  root). Prefer the management UI, which writes both there.
- Secrets live in `.env` (gitignored); never commit secret values. See `.env.example`.
- Run the tests after a change — commands under **Stack and tests** above.
- A schema change bumps `SCHEMA_VERSION` in `ui/schema.py`, adds its `migrate_N_to_M` entry to
  `MIGRATIONS`, regenerates `ui/tests/golden/*.yaml` from the emitter, and updates the README's
  **Agent YAML reference** and the `examples/config/agents/_template-*.yaml` samples.

## Spec-driven development

Features are built with [spec-kit](https://github.github.io/spec-kit/): each lives in
`specs/NNN-name/` (spec, plan, research, data-model, contracts, quickstart, tasks), the backlog of
briefs that feed `/speckit-specify` is `specs/000-briefs*.md`, and the principles every command
checks against are in `.specify/memory/constitution.md`. The constitution deliberately holds
principles only; the stack facts a plan needs are in **Stack and tests** above.

Product vocabulary is not implementation detail. Agent YAML keys (`harness`, `produces`,
`triggers`, `depends_on`, …), `settings.yaml` keys, harness names, and Dagster object names
(`agent_<name>`, `sched_<name>`, `autocond_<name>`) are the declarative surface operators work
with, so specs and quality checklists may use them freely.
