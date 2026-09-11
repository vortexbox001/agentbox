# Bug Assessment: Automation page schedule controls no longer right-aligned

- **Slug**: automation-form-alignment
- **Created**: 2026-09-11
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

> the form fields on the automation page should be right-aligned, like they were before, while still group as is happening now

## Symptom

On the Automation page, the trigger-mode dropdown and cron input in each schedule row now sit
immediately after the "Asset/Job schedule" label, hugging the left side of the card and sizing to
content. Before the spec 006 rework they occupied dedicated table columns that stretched to the
card's right edge, so the controls formed vertically aligned columns anchored on the right. The
new per-agent grouping (one group per agent, one row per kind) should be kept; only the field
alignment regressed.

## Reproduction

1. Open http://10.0.0.100:3000 is Dagster; the UI in question is the agentbox UI (`ui/` app) — open its Automation page.
2. Observe each agent group: the mode dropdown and cron input are left-packed next to the kind label rather than aligned to the card's right edge.
3. Compare with the pre-006 build (commit `8da9a18`), where the same controls filled the last two columns of a full-width `.ax-table`.

## Suspected Code Paths

- `ui/static/app.css` — `.ax-automation-schedule` (added in the working-tree spec 006 change, ~line 560): `display: flex` with `align-items: flex-start; flex-wrap: wrap; gap` and **no growing element**, so the label (min-width 8rem), the dropdown, and `.ax-automation-cron-wrap` all shrink to content and pack left. Nothing pushes the controls toward the right edge.
- `ui/static/app.css` — `.ax-automation-cron-wrap { display:flex; flex-direction:column; min-width:0 }`: no width/flex-grow, so the cron input collapses to its intrinsic size instead of filling a column.
- `ui/static/automation.js` — `scheduleRow()`: builds the row as `[kind label][select][cron-wrap][optional "partition fallback" badge]`. The badge is a sibling appended after the cron wrap, which matters for any column-based fix (an extra trailing item on asset rows would misalign them against job rows).
- Old behavior for reference: `git show HEAD:ui/templates/automation/list.html` — a `width:100%` `.ax-table` whose last two columns held the select and input (both `width:100%` via `.ax-input, .ax-select`), producing the right-anchored, cross-row-aligned columns the user remembers.

## Root Cause Hypothesis

Confidence: high. Spec 006 replaced the four-column full-width table with per-agent groups of
content-sized flex rows. The table previously supplied the alignment for free (fixed columns
spanning to the card's right edge, `width:100%` controls filling their cells). The new
`.ax-automation-schedule` flex rule has no `flex: 1` / `margin-left: auto` / grid track to absorb
the leftover width, so all fields pack left and no longer align into right-anchored columns.

## Proposed Remediation

**Preferred**: Make `.ax-automation-schedule` a grid whose first (label) track absorbs the free
width so the control tracks are pushed to and aligned at the right edge, e.g.:

```css
.ax-automation-schedule {
  display: grid;
  grid-template-columns: minmax(8rem, 1fr) max-content minmax(min(16rem, 100%), 18rem);
  align-items: flex-start;
  gap: var(--ax-space-5) var(--ax-space-6);
  padding: var(--ax-space-3) 0 var(--ax-space-3) var(--ax-space-8);
}
```

(track widths indicative — pick values that match the old table's proportions). Drop the
`min-width: 8rem` on `.ax-automation-kind` in favor of the track, and let `.ax-automation-cron-wrap`
fill its track (`min-width: 0`). Because the mode select is enhanced into `.ax-dropdown`
(`position: relative`, trigger `width: 100%`), the grid item is the `.ax-dropdown` wrapper and will
size to its track correctly.

One JS adjustment in `scheduleRow()` (`ui/static/automation.js`): move the "partition fallback"
badge out of the trailing position — append it inside the kind-label cell (or the agent head)
instead of after the cron wrap. Otherwise asset rows carry a fourth grid item that either wraps
oddly or forces a fourth column that job rows lack, breaking the cross-row alignment being restored.

Add a narrow-viewport fallback (the spec 006 work targets ~400 px, SC-006): inside the existing
`@media (max-width: 640px)` block, collapse the row to a single column (`grid-template-columns: 1fr`)
so fixed tracks cannot cause horizontal overflow.

**Alternatives**:
- Keep flex and add `margin-left: auto` on the select (dropdown) plus a fixed width on the cron
  wrap. Simpler, but cross-row column alignment then depends on the enhanced dropdown always
  rendering the same width ("on demand" vs "cron" labels differ), so it is less robust than grid
  tracks.
- Reintroduce a table per agent group. Heaviest option; loses the flexibility the 006 rows added
  (reserved warning line, fallback badge) for no extra benefit.

**Files likely to change**:
- `ui/static/app.css` (`.ax-automation-schedule`, `.ax-automation-kind`, `.ax-automation-cron-wrap`, the 640px media block)
- `ui/static/automation.js` (badge placement in `scheduleRow()`)

**Tests to add or update**:
- No pytest coverage is practical for CSS alignment; the ui test suite (`cd ui && ../.venv/bin/python -m pytest -q`) should still pass untouched.
- If `scheduleRow()` badge placement changes, no server-side test asserts that DOM shape today; verify visually.
- Verify with the headless chromium + node DevTools driver against a scratch uvicorn (per the
  established host verification workflow): screenshot the Automation page at desktop width
  (controls right-aligned and vertically aligned across asset/job rows and across agent groups)
  and at ~400 px (no horizontal overflow, rows stack).

## Risks & Considerations

- The dropdown enhancement replaces the `<select>`; any width rules must target `.ax-dropdown`
  (the grid/flex item), not the hidden native select.
- The reserved-warning-line behavior (SC-007: `.ax-field-error` `min-height` keeps the row from
  shifting) must survive the layout change — keep the error div inside the cron column.
- Asset rows with the "partition fallback" badge must stay aligned with job rows after the fix.
- Spec 006 is uncommitted work in progress on branch `006-explicit-asset-job`; the fix should land
  as part of that branch's UI polish rather than against `main`.

## Open Questions

- [NEEDS CLARIFICATION: exact intended widths for the mode and cron columns — match the old
  table's visual proportions by eye, or should the cron input stretch to the card edge?]
