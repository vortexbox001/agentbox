# Implementation Plan: Shell, User Settings Modal, and Tabbed Agents List

**Branch**: `011-shell-settings-agents-list` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-shell-settings-agents-list/spec.md`

## Summary

Bring the served management UI level with the delivered design-system mocks
(`ui/design-system/templates/tabbed-list/`) in three visible places plus one supporting
place, without touching the agent schema:

1. **Revised shell** — the sidebar nav links only to pages that exist (Agents, below the
   retained divider keyline), and the foot replaces the inline three-button theme radiogroup
   with a Dagster status block (in an indigo accent), a keyline, "Hide navigation", and
   "Settings". Collapse still uses `agentbox.sidebar`; the collapsed link's accessible name
   becomes "Show navigation".
2. **User settings modal** — a `role="dialog"` "User settings" panel rendered into the
   existing `#ax-modal-root`, with one Preferences section and a Theme dropdown (Light, Dark,
   Use system setting) that applies and persists (`localStorage["agentbox.theme"]`) with no
   Save. The same square keylined chrome restyles the existing confirm/dirty-form modal.
3. **Tabbed agents list** — the agents page rebuilt with no page header as tabs
   (All/Assets/Jobs/Scheduled/Disabled with server-computed counts), a toolbar
   (Filter, Show-disabled, New agent), and an eight-column full-bleed table. Columns 1–5
   (Name, Harness, Model, Kind, Schedules/Sensors labels) render server-side from the store;
   the Dagster-derived parts (schedule toggle state, Latest run, Checks, Run history) fill
   after first paint from **one bounded aliased GraphQL read** and degrade to em-dashes with a
   "Run data unavailable" warning when Dagster is unreachable. A pill toggle flips the schedule
   via a new write endpoint, degrading to a disabled "Turn on from Dagster" control.
4. **Design-system sync** — bring served `app.css`, `dropdown.js`, and the icon sprite level
   with their design-system copies; add a sync test so the design-system copy cannot silently
   run ahead; extend the shared macros (schedule-pill icon, select per-option icon/note/filter,
   tab count); move all mock inline styles to token classes.

The standalone Automation page, route, store, script, template, and tests are removed;
schedule editing already lives in the agent form's schema-driven Triggers section, so nothing
is lost. Presentation-and-shell work on top of completed 009 (design system) and 010 (file
layout); the only behaviour addition is the live schedule toggle. **Note:** the delivered mock
still lists a "Dagster Indigo" theme option — per the resolved clarification the served build
must **not** carry it; indigo is an accent ramp, not a theme value.

## Technical Context

**Language/Version**: Python 3.12 (project `.venv/`, matching `ui/Dockerfile`); browser-side
vanilla JavaScript ES modules (no build step, no framework).

**Primary Dependencies**: FastAPI + Starlette (`Jinja2Templates`, `StaticFiles`,
`JSONResponse`, `RedirectResponse`); Jinja2 server-rendered templates; `httpx.AsyncClient`
for the Dagster GraphQL client (`ui/dagster.py`). No frontend bundler; the `.jsx` reference
kit under `ui/design-system/` is a contract, not shipped.

**Storage**: No server-side state for this feature. Per-browser `localStorage` only:
`agentbox.theme` ∈ {light, dark, system} (existing key, keep the pre-paint resolver),
`agentbox.sidebar` (existing collapse key), and a new show-disabled flag. Active tab lives in
the URL (`?tab=`); filter text is transient. Dagster owns all run state — the UI never scans
run directories on disk.

**Testing**: `pytest`, run as `cd ui && ../.venv/bin/python -m pytest -q`. Existing suites to
extend/repoint: `test_conformance.py` (no literal colour/px/font-family, no inline style, no
external URL — the negative gate), `test_design_system_docs.py` (manifest⇄macro, docs source
of truth), `test_ui_consistency.py` (DS-class conformance), `test_api.py` (routes). Suites to
remove/repoint with the Automation page: `test_automation_store.py`,
`test_migrate_automation.py`. New: a design-system **sync** test (FR-024).

**Target Platform**: Self-hosted Raspberry Pi (arm64, Debian) that may have **no internet
egress**; served over the LAN, modern evergreen browsers only.

**Project Type**: Single project — a server-rendered web UI (`ui/`) inside the Agentbox
monorepo. No separate frontend/backend split.

**Performance Goals**: No hard budgets. Constraints that matter: (a) theme resolves **before
first paint** (no flash) via the existing inline head script; (b) the agents page renders its
store-backed columns (1–5), tabs, counts, and toolbar within the normal page load **even when
Dagster is unreachable**; (c) run-derived columns for **all** agents fill after first paint
from **one aliased GraphQL query** (never one per agent) with a short timeout.

**Constraints**: Offline-first — no `googleapis`/`unpkg`/`cdn`/`http(s)://` asset URL in any
served CSS/HTML/JS (enforced by `test_no_external_urls`). All styling through design tokens —
no literal colours/pixels/font-families and **no inline `style` attributes or `<style>`
blocks** in served templates (Constitution VII, enforced by `test_conformance.py`). WCAG AA
contrast in both themes, incl. the new indigo accent ramp. The page must never fail to render
because Dagster is down.

**Scale/Scope**: Three served pages (agents list, agent create/edit form, 404) + the app
shell + one new modal; the Automation page is removed. Touched files (approx.):
`ui/templates/base.html` (foot/nav/modal-root), `ui/templates/agents/list.html` (full
rebuild), a new `ui/static/settings.js` + `ui/static/agents-list.js`, `ui/static/shell.js`
(foot links, drop radiogroup), `ui/static/dropdown.js` (sync + listbox reuse),
`ui/static/app.css` (indigo ramp, tabbed-list/toolbar/modal/pill classes, token classes for
mock inline styles), `ui/static/icons.svg` (add filter, settings, check-circle, warn-tri,
x-circle, overview, runs, clock, sensor, search), `ui/templates/components/macros.html`
(schedule_pill/select/tabs), `ui/agents_store.py` (row gains kind/crons/checks), `ui/dagster.py`
(+aliased activity read, +start/stop mutation), `ui/main.py` (list context, activity + toggle
endpoints, remove Automation routes), a shared cron-to-text helper, README sections, and
~3 test modules (sync test new; conformance/consistency extended; automation tests removed).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution (v1.3.0) has seven principles. This is a UI presentation/shell feature plus
one read-only-adjacent write endpoint (start/stop a Dagster schedule); it changes no agent-run,
orchestration, secret, or runtime behaviour.

| Principle | Relevance | Assessment |
|-----------|-----------|------------|
| I. Agent Isolation | None | No change to run sandboxing, network, or filesystem grants. **PASS** |
| II. Configuration over Code | None | No orchestrator or agent-definition changes; agent YAML schema untouched (spec Out of Scope). The list reads existing store fields; schedule editing stays in the schema-driven form. **PASS** |
| III. Secrets Never in the Open | None | No secrets touched. The new Dagster start/stop endpoint carries no secret values; Dagster's GraphQL is on the internal `agentnet` network. **PASS** |
| IV. Uniform Interface, Diverse Runtimes | None | Harness config surface untouched. **PASS** |
| V. Ephemeral Runs, Immutable Outputs | **Indirect** | The activity read is **read-only** and derives current state from Dagster (the run-state owner); the UI never scans run dirs or fabricates data (FR-019, edge cases). The toggle mutates a *schedule's* instigation state in Dagster, not any run's output. **PASS** |
| VI. Docs Track Reality | **Direct** | FR-027 adds README sections (tabbed list, settings modal, foot links, indigo accent); FR-024 adds an **automated** design-system sync test (the principle's preferred verification); removed Automation docs/tests are cleaned up. **PASS — advances this principle.** |
| VII. One Design System | **Direct** | Whole feature rebuilds screens from the delivered design-system mocks and shared macros; FR-023/025 land icon + macro changes in the design system, FR-026 moves every mock inline style to token classes, FR-024 prevents the served/design-system copies from drifting, and `test_conformance.py` keeps enforcing no-literal/no-inline-style. **PASS — advances this principle.** |

**Result: PASS (no violations).** Complexity Tracking table left empty. The new indigo accent
ramp is added as design-system tokens (both Light and Dark themes) and applied via classes — it
is not a literal colour in app CSS and not a selectable theme, so it is consistent with
Principle VII.

## Project Structure

### Documentation (this feature)

```text
specs/011-shell-settings-agents-list/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — resolves the GraphQL/sync/icon unknowns
├── data-model.md        # Phase 1 output — the four render-time/activity entities
├── quickstart.md        # Phase 1 output — per-user-story validation scenarios
├── contracts/           # Phase 1 output
│   ├── agents-list-view.md      # Store-row extension, tabs/toolbar/columns, activity JSON
│   ├── dagster-activity.md      # Aliased activity read + start/stop mutation + degradation
│   ├── shell-and-modal.md       # Sidebar/foot, settings modal, theme dropdown, indigo, focus
│   └── design-system-sync.md    # Sync test, macro extensions, icon set, sprite mechanism
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
ui/
├── design-system/                        # AUTHORITATIVE bundle (009/010) — the sync target
│   ├── templates/tabbed-list/            # Delivered mocks this feature realizes
│   │   ├── TabbedList.dc.html            #   agents page: tabs + toolbar + 8-col table
│   │   └── Sidebar.dc.html               #   revised foot + settings modal + theme dropdown
│   ├── static/app.css                    # design-system copy (944 ln) — AHEAD of served (850);
│   │                                     #   FR-024 sync test target for ui/static/app.css
│   ├── static/dropdown.js                # design-system copy (403 ln) — ahead of served (344)
│   ├── static/icons.svg                  # design-system copy of the sprite — sync target
│   ├── tokens/                           # EDIT: add the indigo accent ramp (light + dark)
│   └── _ds_manifest.json                 # manifest⇄macro test source (unchanged component set)
├── templates/
│   ├── base.html                         # EDIT: nav = Agents only (keep divider); foot =
│   │                                     #   Dagster block + keyline + Hide-nav + Settings;
│   │                                     #   drop the theme radiogroup; keep #ax-modal-root
│   │                                     #   and the pre-paint theme/sidebar script
│   ├── agents/list.html                  # REBUILD: no page header; tabs + toolbar + 8-col
│   │                                     #   full-bleed table; server-side cols 1–5; empty-state
│   │                                     #   card below the toolbar; error/name-mismatch rows
│   ├── agents/form.html                  # KEEP (Triggers section stays); confirm-modal restyle
│   ├── 404.html                          # KEEP (revised shell only)
│   ├── automation/list.html              # REMOVE (FR-022)
│   └── components/macros.html            # EDIT: schedule_pill type-icon; select per-option
│                                         #   icon/note/filter passthrough; tabs count
├── static/
│   ├── app.css                           # EDIT: indigo ramp usage; tabbed-list/toolbar/modal/
│   │                                     #   pill/check-grid/run-history classes; token classes
│   │                                     #   for the mock's inline styles (em-dash, mono link)
│   ├── icons.svg                         # EDIT: add filter,settings,check-circle,warn-tri,
│   │                                     #   x-circle,overview,runs,clock,sensor,search
│   ├── shell.js                          # EDIT: foot links (Hide/Show nav accessible name),
│   │                                     #   drop the radiogroup handler; Dagster status poll kept
│   ├── dropdown.js                       # EDIT: bring level with design-system copy; reuse the
│   │                                     #   listbox for the settings theme dropdown
│   ├── settings.js                       # NEW: open/close modal, focus trap, theme dropdown,
│   │                                     #   apply+persist theme, Escape (panel then modal)
│   ├── agents-list.js                    # NEW: tab/filter/show-disabled client narrowing +
│   │                                     #   URL ?tab= sync; after-paint activity fetch + fill;
│   │                                     #   pill toggle POST
│   └── automation.js                     # REMOVE (FR-022)
├── agents_store.py                       # EDIT: list_agents() row gains kind (asset/job),
│                                         #   crons [{type, expr}], checks[]; reuse dagster_job/
│                                         #   dagster_asset naming helpers (already present)
├── automation_store.py                   # REMOVE (FR-022)
├── dagster.py                            # EDIT: + activity(agents) aliased read (instigation
│                                         #   state, latest run, last-10, asset-check results);
│                                         #   + set_instigation(kind,name,running) start/stop
├── cron_text.py (or a macros helper)     # NEW: one shared cron-to-text helper (box timezone)
├── main.py                               # EDIT: list context (tabs/counts/rows); GET
│                                         #   /api/agents/activity; POST schedule toggle; REMOVE
│                                         #   /automation + /api/automation routes
└── tests/
    ├── test_design_system_sync.py        # NEW (FR-024): served ⇄ design-system copies agree
    ├── test_conformance.py               # EXTEND: still fails on inline style / literal / URL;
    │                                     #   theme-a11y assertion targets the modal dropdown
    ├── test_ui_consistency.py            # EXTEND: new list/table/toolbar carry DS classes;
    │                                     #   move test_theme_control_is_accessible_icon_buttons
    │                                     #   to target the modal dropdown; drop the two
    │                                     #   automation.js assertions (FR-022)
    ├── test_api.py                       # EXTEND: activity + toggle endpoints; Automation gone
    ├── test_automation_store.py          # REMOVE (FR-022)
    └── test_migrate_automation.py        # REMOVE / repoint (FR-022)

README.md                                 # EDIT: tabbed list, settings modal, foot links,
                                          #   indigo Dagster accent sections (FR-027)
```

**Structure Decision**: Single-project, server-rendered UI under `ui/`. The design-system
bundle stays authoritative; the running app consumes it and the new **sync test** pins the
served shared assets (`app.css`, `dropdown.js`, sprite) to their design-system copies within
one documented substitution. Components remain **Jinja2 macros**; this feature extends three
of them rather than adding a manifest component (the Dropdown is a form of Select, FR-025).
The sync test pins each served asset to its `ui/design-system/static/` sibling (the copies
currently ahead: `app.css` 944 vs 850, `dropdown.js` 403 vs 344, plus the sprite).
Store-backed columns render server-side; Dagster-derived columns fill from one aliased
GraphQL read after first paint, keeping the page independent of Dagster availability.

## Complexity Tracking

> No constitution violations — table intentionally empty.
