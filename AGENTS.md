# AGENTS.md

Guidance for AI coding agents working in this repository. See `README.md` for the full
architecture and operator documentation.

## Overview

AgentBox is a self-hosted agent-orchestration platform: Dagster orchestrates runs, LiteLLM proxies
LLM calls, and agents run as short-lived containers. Agents are declared in `agents/*.yaml` with
prompts in `prompts/`; the orchestrator (`orchestrator/`) turns each definition into a Dagster job.
A FastAPI management UI lives in `ui/`.

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

- Add or change an agent through its YAML in `agents/` and prompt in `prompts/` — not orchestrator
  code (the orchestrator auto-discovers definitions).
- Secrets live in `.env` (gitignored); never commit secret values. See `.env.example`.
- Run the UI tests from the repo root: `cd ui && ../.venv/bin/python -m pytest -q`.
