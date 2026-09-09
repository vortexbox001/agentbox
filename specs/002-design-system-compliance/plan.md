# Implementation Plan: Design System Compliance

**Branch**: `002-design-system-compliance` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-design-system-compliance/spec.md`

## Summary

Bring the agent management UI back into visual and behavioral compliance with the updated Archon design reference. Four changes, all inside the existing `ui/` package: (1) replace the native `<select>` controls with the reference's custom dropdown component, built as a progressive enhancement over the existing selects so all current form wiring keeps working; (2) correct the enabled/reload toggle so its on and off states match the reference in color, size, and thumb travel; (3) apply the `ax-grid-form` responsive layout to the create, edit, and detail form fields; and (4) update `ARCHON-DESIGN-SYSTEM.md` so it documents the newly added dropdown styles and the grid patterns. No server, API, YAML, validation, or secret behavior changes.

## Technical Context

**Language/Version**: Browser-side JavaScript (ES2020 modules, no transpile); Python 3.12 for the test suite only. Same toolchain as feature 001.

**Primary Dependencies**: No new runtime dependencies. Frontend uses `archon-tokens.css` design tokens and inline SVG icons already present. Tests use `pytest` + FastAPI `TestClient` (already installed).

**Storage**: N/A for this feature — presentation and interaction only. No change to how `agents/*.yaml` or `prompts/*.md` are read or written.

**Testing**: `pytest` for everything statically checkable — token discipline (no literal colors/fonts), the corrected toggle token mapping and grid CSS present in `app.css`, the design-guide documenting each grid pattern and a dropdown component, and the rendered pages still carrying their backing `<select>` controls. Interactive and visual fidelity (dropdown open/select/keyboard/dismiss, toggle appearance, grid reflow) is verified with the quickstart browser checklist; there is no browser-automation harness in this repo, matching feature 001.

**Target Platform**: The Docker Compose `ui` service on `:8080`; modern desktop and mobile browsers.

**Project Type**: Web service with server-rendered pages plus a JSON API (single `ui/` package).

**Performance Goals**: Dropdown open/select and toggle switch respond in under 100 ms perceived. Grid reflow is native CSS, so it costs nothing at runtime. No regression to the sub-second list render or sub-200 ms form interactions from feature 001.

**Constraints**: No frontend build toolchain. Token discipline (FR-014/FR-015 of feature 001): every color and font in site styles comes from an `--ax-*` token — no literals, including in the new dropdown and the corrected toggle. The custom dropdown must not drop the accessibility a native `<select>` provides: it must be keyboard-operable and expose its selection to assistive technology. Works offline except for fonts.

**Scale/Scope**: 3 UI screens (list, create, edit/detail) plus the design-system guide. ~8 selectable fields per form become custom dropdowns; 2 toggles corrected; 1 grid layout applied; 1 markdown guide updated. Roughly one new small JS module, one CSS block, targeted edits to `agent-form.js`, and doc edits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Not applicable. This feature touches only the management UI, which never launches agents.
- **II. Configuration over Code** — Not applicable. No agent-definition surface changes.
- **III. Secrets Never in the Open** — Respected. The env-var editor and its secret-confirmation flow are unchanged (FR-015). The custom dropdown carries no field values into logs, and nothing new is logged.
- **IV. Uniform Interface, Diverse Runtimes** — Not applicable. No harness or schema change.
- **V. Ephemeral Runs, Immutable Outputs** — Not applicable.
- **VI. Docs Track Reality** — Directly served. User Story 4 / FR-013 update `ARCHON-DESIGN-SYSTEM.md` to match the reference files, and the plan adds an automated `pytest` check asserting the guide documents each named grid pattern and a dropdown component, so the doc's accuracy is machine-verified rather than review-only.

**Result**: PASS. No violations; the Complexity Tracking section is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-design-system-compliance/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (component state/attribute model)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/
│   └── components.md     # Phase 1 output (dropdown / toggle / grid UI contracts)
├── checklists/
│   └── requirements.md   # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
ui/
├── static/
│   ├── dropdown.js       # NEW: enhanceSelect(select) — builds the custom dropdown over a native <select>
│   ├── agent-form.js     # EDIT: enhance every select after each render; wrap section fields in the form grid
│   ├── app.css           # EDIT: .ax-dropdown component styles; corrected .ax-toggle; .ax-grid-form; .ax-field--wide
│   └── shell.js          # (no change expected)
├── templates/
│   └── agents/
│       ├── form.html     # EDIT (minimal): mark wide fields / grid container hooks if needed; template select gets enhanced by JS
│       └── list.html     # (no change — stays a table per the reference's "tables stay grid-based" rule)
├── design-system/
│   └── ARCHON-DESIGN-SYSTEM.md   # EDIT: add Select/Custom Dropdown component section; verify Toggle + Grid entries
└── tests/
    ├── test_api.py       # EDIT: extend static checks (toggle tokens, grid CSS, backing selects, doc accuracy)
    └── test_design_system_docs.py   # NEW (optional): dedicated doc-accuracy test for ARCHON-DESIGN-SYSTEM.md
```

**Structure Decision**: Single existing `ui/` package (feature 001's layout). The only new source file is `ui/static/dropdown.js`; everything else is a targeted edit. The agents list stays a table — no card-grid surface exists in the app, so this feature introduces `ax-grid-form` (forms) but not `ax-grid-cards` (see research for this correction to the spec's FR-012a).

## Complexity Tracking

No constitution violations; this section is intentionally empty.
