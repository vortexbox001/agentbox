# Implementation Plan: Design System Migration

**Branch**: `009-design-system-migration` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-design-system-migration/spec.md`

## Summary

Replace the Archon design language in the management UI (dark-only, cyan/magenta,
Playfair serif, `--ax-*` tokens, top bar) with the in-repo AgentBox design system
(Dagster-derived: light+dark themes, navy/teal/lime, Inter + Source Code Pro, a 240px
collapsible left sidebar with no top bar, Lucide icons). The design-system **bundle** —
tokens, guidelines, React reference kit, README, manifest, skill — already landed in
`ui/design-system/` (commit 62ccefe). This feature completes the migration: it rewires the
**running app** (`ui/templates/`, `ui/static/`) onto the new tokens, re-expresses every
manifest component as a shared **Jinja macro** that pages compose, resolves theme before
first paint with a persisted Light/Dark/System control in the sidebar foot, self-hosts the
fonts and vendors a local Lucide sprite so nothing leaves the box, wires the design skill
into `.claude/skills/`, adds a "Design" constitution principle, updates README/AGENTS.md,
and replaces the stale Archon design tests with automated conformance checks. Visual and
structural migration only — no feature behaviour changes (spec 002 dropdown keyboard model
and form validation states are preserved). Lands before spec 011.

## Technical Context

**Language/Version**: Python 3.12 (project `.venv/`, matching `ui/Dockerfile`); browser-side
vanilla JavaScript ES modules (no build step, no framework).

**Primary Dependencies**: FastAPI + Starlette (`StaticFiles`, `RedirectResponse`), Jinja2
(`fastapi.templating.Jinja2Templates`) for server-rendered templates. No frontend bundler.
The `ui/design-system/` React reference kit (`.jsx`) is a documentation/contract artefact,
not shipped to the browser.

**Storage**: N/A for this feature. Theme choice and sidebar collapse state persist in browser
`localStorage` only (no server-side setting — that arrives with spec 011).

**Testing**: `pytest`, run as `cd ui && ../.venv/bin/python -m pytest -q`. Existing suites:
`test_ui_consistency.py` (static greps over templates/static), `test_design_system_docs.py`
(currently red — points at deleted Archon files), `test_secrets.py`/`secret_scan.py` (the
existing static-grep-as-test pattern to mirror for conformance checks).

**Target Platform**: Self-hosted Raspberry Pi (arm64, Debian) that may have **no internet
egress**. Served over the LAN at `http://10.0.0.100:3000`-adjacent UI port; modern evergreen
browsers only.

**Project Type**: Single project — a server-rendered web UI (`ui/`) inside the Agentbox
monorepo. No separate frontend/backend split.

**Performance Goals**: No hard budgets. Constraint that matters: theme must resolve **before
first paint** (no wrong-theme flash) via a tiny inline head script; page weight stays small
(self-hosted fonts + one SVG sprite, no CDN, no framework runtime).

**Constraints**: Offline-first — no `googleapis`/`unpkg`/`cdn` URL in any served CSS/HTML/JS;
fonts self-hosted (or system-font fallback under the licence null-action, §research); icons
from a local Lucide sprite. WCAG 2.1 AA contrast in both themes. All styling through design
tokens — no literal colours/pixels/font-families in app CSS or templates (enforced by an
automated check, outside the token and font files).

**Scale/Scope**: Four existing pages (agents list, agent create/edit form, automation list,
404) + the app shell. Thirteen manifest components → thirteen shared macros. One design-system
bundle already in-repo. Roughly: `ui/templates/base.html` + 4 page templates, a new macros
set, `ui/static/app.css` (~669 lines to rewrite onto new tokens), `shell.js`/`dropdown.js`/
`agent-form.js`/`automation.js` (restyle hooks only, behaviour frozen), self-hosted fonts,
Lucide sprite, `.claude/skills/` skill, constitution + docs, ~3 conformance test modules.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution (v1.1.0) has six principles. This is a UI-only, visual/structural migration
with no changes to agent runs, orchestration, secrets, or runtimes.

| Principle | Relevance | Assessment |
|-----------|-----------|------------|
| I. Agent Isolation | None | No change to run sandboxing, network, or filesystem grants. **PASS** |
| II. Configuration over Code | None | No orchestrator or agent-definition changes. **PASS** |
| III. Secrets Never in the Open | None | No secrets touched; no new command lines or logs. **PASS** |
| IV. Uniform Interface, Diverse Runtimes | None | Harness config surface untouched. **PASS** |
| V. Ephemeral Runs, Immutable Outputs | None | No run/output semantics touched. **PASS** |
| VI. Docs Track Reality | **Direct** | FR-020/021 update README, AGENTS.md, and the constitution to the new design-system location and rule; FR-022–024 add **automated** conformance checks (the principle's preferred verification) and this feature **replaces** the stale `test_design_system_docs.py` that now points at deleted Archon files. **PASS — actively advances this principle.** |

**New governance work is additive, not a violation**: FR-021 *adds* a seventh "Design"
principle to the constitution (every screen uses design tokens + component macros; no literal
colours/fonts/pixels in app styling; new components go into the design system first, the
shared macro set second). Adding a principle is a MINOR constitution amendment under the
existing governance rules, not a breach of an existing gate.

**Result: PASS (no violations).** Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-design-system-migration/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── component-macros.md      # Macro ⇄ manifest-component parameter contracts
│   ├── theme-and-shell.md       # Theme resolution, sidebar, page-header shell contract
│   └── conformance-checks.md    # The automated checks (FR-022/023/024) as a contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
ui/
├── design-system/                 # AUTHORITATIVE bundle — already in repo (62ccefe)
│   ├── readme.md                  # single human source of truth (FR-002)
│   ├── SKILL.md                   # design skill body (wired into .claude/skills — FR-019)
│   ├── _ds_manifest.json          # machine-readable component manifest (FR-004/023)
│   ├── tokens/                    # colors, typography, spacing, shadows, theme, base, animations
│   │   └── typography.css         # EDIT: replace Google-Fonts @import with local @font-face (FR-015)
│   ├── fonts/                     # NEW: self-hosted Inter + Source Code Pro (or null-action note)
│   ├── guidelines/ ui_kits/ components/ assets/   # references (unchanged)
├── templates/
│   ├── base.html                  # REWRITE: no top bar; 240px collapsible sidebar; page header
│   │                              #   in content area; theme control in sidebar foot; pre-paint
│   │                              #   theme script; link new tokens (drop archon-tokens.css)
│   ├── components/                # NEW: shared Jinja macros, one per manifest component
│   │   └── macros.html            #   button, text_input, select, checkbox, toggle, badge,
│   │                              #   status_dot, alert, spinner, tabs, card, dialog, table
│   ├── agents/list.html, agents/form.html, automation/list.html, 404.html   # recompose on macros
├── static/
│   ├── app.css                    # REWRITE onto new --color-*/space/type tokens; drop --ax-* + top bar
│   ├── icons.svg                  # REPLACE/EXTEND: local Lucide sprite (FR-016)
│   ├── shell.js                   # theme toggle + sidebar collapse persistence; Dagster status (restyle)
│   ├── dropdown.js                # spec 002 dropdown — behaviour frozen, restyled hooks only (FR-025)
│   ├── agent-form.js, automation.js   # restyle hooks only; validation states preserved
│   └── fonts/  (or design-system/fonts served)   # self-hosted font files, no external URL
├── main.py / config.py            # serving unchanged except any macro/template wiring; /design-system mount
└── tests/
    ├── test_design_system_docs.py # REPLACE stale Archon-file checks → manifest⇄macro + README ref (FR-023)
    ├── test_ui_consistency.py     # EXTEND: every select/button/table carries the DS class (FR-024)
    └── test_conformance.py        # NEW: no literal colour/px/--ax-*/external-URL/stray font-family (FR-022)

.claude/skills/
└── agentbox-design/               # NEW: skill wiring pointing at ui/design-system/readme.md (FR-019)

README.md, AGENTS.md               # EDIT: new design-system location + "sibling of Dagster" rule (FR-020)
.specify/memory/constitution.md    # EDIT: add "Design" principle, MINOR version bump (FR-021)
```

**Structure Decision**: Single-project, server-rendered UI under `ui/`. The design-system
*bundle* stays the authoritative source in `ui/design-system/` and is served read-only at
`/design-system/`; the *running app* consumes it. Components are re-expressed as **Jinja2
macros** in `ui/templates/components/macros.html` (the bundle's `.jsx` files are the contract,
not runtime code — see Assumptions in spec). Conformance is enforced by pytest static-grep
modules, mirroring the existing `test_secrets.py` / `secret_scan.py` pattern.

## Complexity Tracking

> No constitution violations — table intentionally empty.
