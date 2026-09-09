# Quickstart: validating Design System Compliance

Runnable checks that prove the feature. Static behavior is covered by `pytest`; visual and interactive fidelity is a manual browser pass against the [component contracts](contracts/components.md).

## Prerequisites

- The project virtualenv at `.venv/` (Python 3.12), as in the root `CLAUDE.local.md`.
- Docker + Compose on the agentbox host to run the UI for the browser checklist.

## 1. Automated tests (no Docker needed)

```bash
cd ui && ../.venv/bin/python -m pytest -q
```

Expected: all tests pass, including the new/extended checks:
- Token discipline holds — no literal color or `font-family` in `app.css` or any template.
- The toggle maps on-track to `--ax-cyan`, on-thumb to `--ax-text-primary`, and off-thumb to `--ax-text-low`.
- `.ax-grid-form` exists with `auto-fill` and `minmax(280px`.
- The rendered create form still contains backing `<select>` controls and loads `dropdown.js`.
- `ARCHON-DESIGN-SYSTEM.md` documents each named grid pattern and a Select/Dropdown component.

## 2. Run the UI

```bash
docker compose up -d --build ui
```

Open `http://<host>:8080`.

## 3. Browser checklist

Tick each item; all map to the spec's user stories and the [component contracts](contracts/components.md).

> Verified 2026-09-09 against a local `uvicorn` instance of `ui/` (scratch copies of `agents/` and `prompts/`), driven headlessly in Chromium over the DevTools protocol: 48 automated checks covering every item below passed, and screenshots of the open dropdown, both toggle states, the wide/narrow grid, the flipped panel, and the edit screen were reviewed by eye. The Docker `ui` service mounts `./ui` read-only, so the running container serves the same files without a rebuild.

**Custom dropdown (US1, FR-001..006)**
- [x] On the create form, every selectable field (template picker, harness, model, effort, permission mode, network, prompt) opens the custom panel, not the browser's native popup.
- [x] The open panel is an elevated card with the current value highlighted in the accent color and other options muted.
- [x] Choosing an option updates the control, closes the panel, and where applicable marks the form unsaved.
- [x] Clicking outside or pressing Escape closes the panel with no change.
- [x] Keyboard only: focus a dropdown, open it, move with arrows, choose with Enter — no pointer needed.
- [x] The harness switch still shows/hides fields; the template picker still pre-fills; the prompt picker's "Create new prompt…" still reveals its inputs.
- [x] A field left invalid still shows its error state while keeping the custom appearance.
- [x] The model and prompt dropdowns (long lists) scroll inside the panel and are not clipped near the bottom of the form.

**Toggle (US2, FR-007..009)**
- [x] Off state: track is the muted/translucent surface, thumb is the muted color at the left.
- [x] On state: track is solid accent (cyan), thumb is white at the right.
- [x] Switching animates the thumb sliding between positions with the colors swapping.
- [x] Compared side by side with the `/design-system` reference toggle, the size and colors match in both states.

**Form grid (US3, FR-010..012)**
- [x] At a wide viewport, the create/edit form fields lay out in multiple auto-filled columns with the reference gap.
- [x] The edit ("detail") screen shows the same multi-column field layout.
- [x] Wide controls (env map, tool lists, append-system-prompt, prompt-create panel) span the full row rather than being squeezed.
- [x] Narrowing the window reduces the columns down to one, with no horizontal page scroll at any width.
- [x] The agents list remains a table (unchanged).

**Design-system guide (US4, FR-013)**
- [x] `ARCHON-DESIGN-SYSTEM.md` now has a Select/Dropdown section describing both the native and custom variants, matching the reference.
- [x] Its grid table lists every named pattern including `ax-grid-cards` and `ax-grid-form` with the correct column rule and gap.

**Regression (FR-015)**
- [x] Create and edit an agent through the updated UI and confirm the written `agents/<name>.yaml` is byte-identical to what the pre-change UI produced, with the same validation and Dagster-reload behavior. (Compare against a file saved before this change, or against `emit_yaml` output.)

## 4. Reference cross-check

Open `/design-system/` and compare the dropdown, toggle, and grid demos directly against the running app's create/edit screens; there should be no discernible difference in the dropdown panel, the toggle states, or the field grid.
