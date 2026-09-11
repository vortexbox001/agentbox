# Bug Fix: Automation page schedule controls no longer right-aligned

- **Slug**: automation-form-alignment
- **Fixed**: 2026-09-11
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Converted `.ax-automation-schedule` from a content-sized flex row to a fixed-track grid so the
mode dropdown and cron input keep constant widths and line up vertically across rows and agent
groups. The final layout (after two rounds of user feedback on the first grid) is: the
"Asset/Job schedule" label on its own grid row directly above the dropdown (matching the stacked
mobile layout), and the whole control block left-anchored at the row indent — fields do not
stretch to the card edge.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `ui/static/app.css` | modified | `.ax-automation-schedule` → `display: grid; grid-template-columns: 10rem minmax(min(16rem, 100%), 18rem); justify-content: start` with explicit placements: `.ax-automation-kind` on row 1 spanning both control tracks, dropdown (`.ax-dropdown` / pre-enhancement `.ax-automation-mode`) and `.ax-automation-cron-wrap` on row 2; label made inline-flex so the fallback badge sits beside it; 640px media block stacks to one column and resets the placements with matching-specificity selectors |
| `ui/static/automation.js` | modified | `scheduleRow()` appends the "partition fallback" badge into the kind-label cell instead of as a trailing row sibling, so asset rows keep the same column shape as job rows |

## Diff Highlights (optional)

```css
.ax-automation-schedule {
  display: grid;
  grid-template-columns: 10rem minmax(min(16rem, 100%), 18rem);
  justify-content: start;
  ...
}
.ax-automation-kind { grid-column: 1 / -1; grid-row: 1; ... }
.ax-automation-schedule > .ax-automation-mode,
.ax-automation-schedule > .ax-dropdown { grid-column: 1; grid-row: 2; }
.ax-automation-cron-wrap { grid-column: 2; grid-row: 2; ... }
```

The mode track is a fixed `10rem` rather than `max-content` on purpose: the enhanced dropdown's
intrinsic width follows the selected value ("on demand" vs "cron"), which would misalign rows.
Gotcha encountered: the 640px reset must use `> .ax-dropdown`-style selectors, not `> *` — the
desktop placement selectors are specificity 0-2-0 and a 0-1-0 reset loses, leaving the dropdown
pinned to an implicit second column on phones.

## Tests Added or Updated

- None in pytest — the regression is pure CSS layout, which the server-side suite cannot see
  (matches the assessment). Verified live in a browser instead (below).

## Local Verification

- Commands run: `cd ui && ../.venv/bin/python -m pytest -q` → **293 passed** (re-run after each
  layout revision).
- Browser check (per the established host workflow): scratch uvicorn on :8089 with copies of the
  real `agents/`/`prompts/` (13 agents, 14 schedule rows), driven by headless chromium over the
  DevTools protocol (`/tmp/bugfix-align/verify.mjs`):
  - Desktop 1280×900: all 14 dropdowns share a single left/right edge (289/449) at the row
    indent inside the card (card content starts ~273); all cron wraps share one right edge
    (749), well short of the card edge (1237) — left-anchored, constant-width, cross-row
    aligned; every kind label sits above and left-aligned with its dropdown. Screenshot
    confirmed by eye: grouping intact, two clean control columns.
  - Phone 400×800: rows stack single-column, horizontal overflow 0 px (SC-006 holds).
  - The reserved warning line (`.ax-field-error` min-height, SC-007) is untouched — the error div
    stayed inside the cron column.

## Deviations from Assessment

- The assessment (following the original report's wording) proposed right-anchoring the controls
  at the card edge, and the first grid did exactly that. On seeing it, the user revised the goal
  twice: the kind label should sit above the dropdown (like mobile), and the control block should
  be left-aligned with fields at their fixed widths, not pushed right. The final layout follows
  that direction; what survives from the assessment is the fixed-track grid, the cross-row
  column alignment, and the badge relocation.
- The assessment suggested `max-content` as one option for the mode track; a fixed `10rem` track
  was used instead so row alignment cannot depend on the selected value's text width.
- The badge moved into the kind-label span (made inline-flex with a gap) rather than the agent
  head, keeping the per-row semantics.

## Follow-ups

- No fixture agent produces `fallback: true`, so the badge-in-label placement was verified only
  structurally (it renders inside `.ax-automation-kind`, which wraps via inline-flex), not
  visually with real data. Worth an eyeball if/when a partition-fallback agent exists.
- The open question about exact column widths was answered with 10rem (mode) / 16–18rem (cron);
  tweak the two track literals in `.ax-automation-schedule` if different proportions are wanted.
