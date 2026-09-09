# Implementation Plan: Agent Form Layout

**Branch**: `003-agent-form-layout` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-agent-form-layout/spec.md`

## Summary

Regroup the agent create/edit form from eight YAML-shaped cards into three column groups (Runs, Job, Box) of eight smaller cards, with the agent name in a lead strip above them, and lay the groups out as three, two, or one columns depending on the width of the content pane. The grouping lives in the schema so the YAML emitter writes files in the same order. All of it is inside the existing `ui/` package: a schema reshuffle in `schema.py`, a rendering change in `agent-form.js`, a named layout in `app.css`, a small template change, regenerated golden files, test updates, and a design-guide entry. No validation, API, or orchestrator behaviour changes.

## Technical Context

**Language/Version**: Python 3.12 (schema, emitter, tests); browser-side JavaScript ES2020 modules with no build step; CSS with container queries. Same toolchain as features 001 and 002.

**Primary Dependencies**: No new dependencies. FastAPI + Jinja templates already serve the page; `pytest` + `TestClient` already test it. `archon-tokens.css` provides every colour, space, and type token used.

**Storage**: `agents/*.yaml` files. Their key order and section comment headers change on next save (spec FR-015); values do not.

**Testing**: `pytest` in `ui/tests/` for everything statically checkable: schema group/section integrity, emitter section order via regenerated golden files, page markup (lead strip, reload toggle position, group mounts), the layout CSS present with its three arrangements, and the design guide documenting the layout with thresholds that match the stylesheet. Column behaviour at 1800/1440/900 px is verified in a browser per the quickstart; the repo has no browser-automation harness (same as 001 and 002).

**Target Platform**: The Docker Compose `ui` service on `:8080`; evergreen desktop browsers. Container queries require Chrome/Edge 105+, Safari 16+, Firefox 110+; older browsers fall back to the single-column arrangement, which is still correct.

**Project Type**: Web service with server-rendered pages plus a JSON API (single `ui/` package).

**Performance Goals**: No runtime cost beyond today: the arrangement is pure CSS, and `renderForm` still builds the same number of fields once per harness change.

**Constraints**: No frontend build toolchain. Token discipline from 001/002 (no literal colours or fonts in site CSS). Two explicit width thresholds are required and are a documented exception to the design system's "no fixed breakpoints" rule (research R2). Every existing form behaviour (harness switch, template pre-fill, prompt create panel, secret warnings, validation error mapping, dirty guard, YAML preview) must keep working unchanged (spec FR-016).

**Scale/Scope**: 2 screens (create, edit) sharing one renderer; 24 schema fields re-homed across 9 sections in 3 groups; 4 golden files regenerated; 1 CSS layout block; 1 guide section; ~6 test additions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Not applicable. The management UI never launches agents; the orchestrator is untouched.
- **II. Configuration over Code** — Respected. Grouping is data in the schema (`GROUPS`, `SECTIONS`, each field's `section`), consumed by both the form and the emitter. No per-card code paths are added.
- **III. Secrets Never in the Open** — Respected. The env-var editor, its secret heuristic, and the confirmation flow are moved, not changed. Nothing new is logged.
- **IV. Uniform Interface, Diverse Runtimes** — Respected. Field-to-harness applicability is unchanged; a card simply disappears when none of its fields apply. Adding a harness later still only touches `harnesses` in the field definitions.
- **V. Ephemeral Runs, Immutable Outputs** — Not applicable.
- **VI. Docs Track Reality** — Served. The design guide gains an "Agent form layout" section, and a new test asserts the thresholds it states are the ones in `app.css`. The YAML contract from 001 is amended to the new section order, and the golden files that pin the emitter are regenerated so the contract, the code, and the fixtures agree.

**Result**: PASS. No violations; Complexity Tracking is intentionally empty.

*Post-design re-check (after Phase 1)*: still PASS. The design adds no new runtime code paths per harness, keeps secrets handling untouched, and pairs every documentation change with an automated check.

## Project Structure

### Documentation (this feature)

```text
specs/003-agent-form-layout/
├── plan.md                    # This file
├── research.md                # Phase 0: decisions R1–R8
├── data-model.md              # Phase 1: groups, sections, field re-homing, YAML order
├── quickstart.md              # Phase 1: validation guide
├── contracts/
│   ├── schema-and-yaml.md     # /api/schema additions and the amended YAML section order
│   └── layout.md              # DOM and CSS contract for the lead strip, groups, and arrangements
├── checklists/
│   └── requirements.md        # From /speckit-specify
└── tasks.md                   # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
ui/
├── schema.py                  # EDIT: add GROUPS; replace SECTIONS; re-home and reorder FIELDS; expose groups in public_schema
├── agents_store.py            # (no change: emitter already iterates SECTIONS and FIELDS)
├── static/
│   ├── agent-form.js          # EDIT: renderForm builds lead-strip fields + three group containers; lockName looks in the lead mount
│   ├── app.css                # EDIT: .ax-content container; .ax-grid-agent arrangements; .ax-form-group; lead strip as a non-card grid
│   ├── dropdown.js            # (no change)
│   └── shell.js               # (no change)
├── templates/agents/
│   └── form.html              # EDIT: lead strip container (template picker + name mount), sections mount becomes the group grid
├── design-system/
│   └── ARCHON-DESIGN-SYSTEM.md  # EDIT: "Agent form layout" subsection under Layout; note the breakpoint exception
└── tests/
    ├── golden/*.yaml          # REGENERATE: new section order and headers (values unchanged)
    ├── test_schema.py         # EDIT: group/section integrity, field order, public schema shape
    ├── test_agents_store.py   # EDIT: assert emitted section headers follow SECTIONS order
    ├── test_api.py            # EDIT: page markup checks (lead strip, toggle before sections, group grid); CSS presence checks
    └── test_design_system_docs.py  # EDIT: guide's agent-form-layout thresholds match app.css

specs/001-agent-management-ui/
├── contracts/agent-yaml.md    # EDIT: §2 section list replaced by a pointer to 003 contracts/schema-and-yaml.md
└── data-model.md              # EDIT: applicability matrix row labels use the new card names
```

**Structure Decision**: No new source files. The schema remains the single source of truth for grouping and order, so the form and the emitter cannot drift (research R1). The layout is one CSS block on the existing sections mount plus three group containers built by `renderForm`, keeping the change inside the module that already owns form assembly.

## Complexity Tracking

No constitution violations; this section is intentionally empty. The one design-system deviation (explicit width thresholds) is justified in research R2 and documented in the guide, not a constitution matter.
