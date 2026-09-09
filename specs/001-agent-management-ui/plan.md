# Implementation Plan: Agent Management UI

**Branch**: `web-ui` | **Date**: 2026-09-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-agent-management-ui/spec.md`

## Summary

Replace the one-file FastAPI control panel (`ui/main.py`) with an agentbox web app: an app shell (sidebar, top bar, content pane) built on the Archon token/component system, an Agents list, and a schema-driven create/edit form that reads and regenerates the YAML files in `agents/`, manages prompt files in `prompts/`, enforces harness/model compatibility, flags secret-like env values, previews the YAML on demand, deletes agents, and optionally reloads Dagster after every write. The component library ships unchanged and is served at `/design-system`.

Technical approach: keep the existing FastAPI service and add server-rendered Jinja2 pages plus a small JSON API; a single Python schema module (`ui/schema.py`) is the one source of truth for every field's harness applicability, choices, default, and explanation — it drives the form, validation, the YAML emitter (comments included), and the `/api/schema` payload the browser uses. No frontend build step: plain ES-module JavaScript against the token CSS already in the repo.

## Technical Context

**Language/Version**: Python 3.12 (server; `python:3.12-slim` image already in `ui/Dockerfile`); browser-side JavaScript (ES2020 modules, no transpile)

**Primary Dependencies**: FastAPI, uvicorn, Jinja2, python-multipart, httpx, PyYAML (all already installed by `ui/Dockerfile`); add `croniter` (cron validation) and `pytest` (tests). Frontend: `archon-tokens.css` + inline SVG icons; Google Fonts via the token file's `@import`.

**Storage**: Files on the host, bind-mounted into the `ui` container — `agents/*.yaml` (read/write), `prompts/*.md` (read/write, new mount), `litellm/config.yaml` (read-only, new mount, source of LiteLLM aliases). No database.

**Testing**: `pytest` + FastAPI `TestClient` against temp directories for stores, API, YAML emitter, secret heuristic, and harness/model matrix. Browser behaviour verified manually with the quickstart checklist (no browser-automation harness in this repo).

**Target Platform**: Linux container (Docker Compose `ui` service on the agentbox host, which may be a Raspberry Pi); modern desktop browsers. Served on `:8080` inside `agentnet`.

**Project Type**: Web service with server-rendered pages + JSON API (single `ui/` package)

**Performance Goals**: Agents list renders in < 1 s for ≤ 50 agent files (SC-007 allows 3 s); form interactions (harness switch, model filter, secret flag, YAML preview) respond in < 200 ms perceived; Dagster reload round-trip reported within 10 s or surfaced as a timeout error.

**Constraints**: No frontend build toolchain; no new services; the `ui` container must not receive any secret (it never launches agents); files it writes must remain editable by the host user (run the container as the host uid/gid); works offline except for the fonts and the `/design-system` page's React CDN load.

**Scale/Scope**: Single operator, ≤ 50 agents, ≤ 50 prompts; 3 pages (list, new, edit) + 1 static reference page; ~24 YAML keys across 4 harnesses.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Agent Isolation | The UI never launches agents or touches workspaces/outputs; its container mounts only `ui/` (ro), `agents/` (rw), `prompts/` (rw), `litellm/config.yaml` (ro). | PASS |
| II. Configuration over Code | The UI is a front end for the declarative YAML; adding a harness means one entry in the schema matrix, not orchestrator changes. The schema module is the UI's only harness-specific code. | PASS |
| III. Secrets Never in the Open | FR-020: secret-like env values warn inline and require confirmation on save; `${NAME}` passthrough is the promoted path and never flagged. The UI process receives no secrets (`DAGSTER_URL` only). | PASS |
| IV. Uniform Interface, Diverse Runtimes | Common fields are shared across harnesses; harness-specific fields are declared per harness in the matrix; a new harness cannot alter another's field set. | PASS |
| V. Ephemeral Runs, Immutable Outputs | Delete removes only `agents/<name>.yaml`; workspaces and `output_dir` are never read, listed, or removed (FR-019). | PASS |
| VI. Docs Track Reality | Field explanations live in one schema and are emitted as YAML comments and shown in the form, so file, UI, and README stay aligned; README sections "Adding an agent", "Repository layout", and the compose docs must be updated in implementation (tracked as tasks). | PASS (with follow-through) |

No violations; Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-management-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── http-api.md      # Pages + JSON API contract
│   └── agent-yaml.md    # Emitted YAML file contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
ui/
├── main.py                 # FastAPI app: page routes, API routers, static mounts
├── schema.py               # field definitions, harness matrix, choice sources (single source of truth)
├── agents_store.py         # list/read/write/delete agents/*.yaml; YAML emitter with comments
├── prompts_store.py        # list/read/create prompts/*.md
├── secrets.py              # secret-like heuristic for env names/values
├── dagster.py              # reloadWorkspace GraphQL call + outcome mapping
├── templates/
│   ├── base.html           # app shell: sidebar (LHN), top bar (TLN), content pane (MWP)
│   ├── agents/list.html    # Agents page
│   └── agents/form.html    # New/Edit agent page (form skeleton; fields rendered from schema)
├── static/
│   ├── app.css             # component styles built on the token variables
│   ├── shell.js            # nav state, toasts, unsaved-changes guard
│   ├── agent-form.js       # schema-driven fields, harness/model filtering, secret flags, preview
│   └── icons.svg           # inline-able SVG sprite (nav + actions)
├── design-system/          # the Archon reference folder, renamed (git mv), served at /design-system/
│   ├── Archon Design System.dc.html
│   ├── Archon Prototype.dc.html
│   ├── Agent Orchestration.dc.html
│   ├── ARCHON-DESIGN-SYSTEM.md
│   ├── archon-tokens.css
│   └── support.js
├── requirements.txt        # pinned deps; Dockerfile installs from it
├── Dockerfile
└── tests/
    ├── conftest.py         # tmp agents/prompts dirs, litellm fixture, TestClient
    ├── test_schema.py      # matrix, choices, model validation per harness
    ├── test_agents_store.py# round-trip, emitter comments, name/uniqueness rules, delete
    ├── test_prompts_store.py
    ├── test_secrets.py
    └── test_api.py         # every endpoint incl. reload option, secret confirmation, preview

docker-compose.yml          # ui service: add prompts (rw) + litellm/config.yaml (ro) mounts, user: uid:gid
README.md                   # "Adding an agent" → UI flow; layout section; ui service description
```

**Structure Decision**: Single `ui/` package, extended in place. Pages are server-rendered by Jinja2 and enhanced by two ES modules; all data access goes through the JSON API so the form JS and the tests share one contract. The design reference folder is renamed to `ui/design-system/` (contents untouched) so it can be mounted as static files without a space-containing path; `/design-system` redirects to `/design-system/` so the document's relative `./support.js` and `./archon-tokens.css` references resolve inside the mount, and the app links directly to `/design-system/archon-tokens.css` rather than copying the tokens.

**Schema evolution**: no database exists in this feature, so there is nothing for Alembic to manage; the equivalent discipline for the YAML-backed model is a schema version stamp in each file, ordered forward-only migrations in `schema.py` applied on load, and verbatim preservation of keys the UI does not know (research R12). When run history or performance data introduces a database in a later feature, that state will use SQLAlchemy + Alembic under `ui/alembic/`; agent definitions stay in YAML.

## Complexity Tracking

No constitution violations to justify.
