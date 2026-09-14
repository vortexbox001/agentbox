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
enforced by the UI test suite (`cd ui && ../.venv/bin/python -m pytest -q`):

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

## Conventions

- Add or change an agent through its YAML under the config root's `agents/` and its prompt under
  `prompts/` — not orchestrator code (the orchestrator auto-discovers definitions from the config
  root). Prefer the management UI, which writes both there.
- Secrets live in `.env` (gitignored); never commit secret values. See `.env.example`.
- Run the UI tests from the repo root: `cd ui && ../.venv/bin/python -m pytest -q`.
