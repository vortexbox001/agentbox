# Contract: Agent form layout (DOM and CSS)

The interface this feature exposes is the page structure and the named layout. All colours, fonts, spaces, and radii are `--ax-*` tokens; the only literals are the two width thresholds and the column ratio (research R2, R3).

## 1. Page structure (both create and edit)

```
main.ax-content                      (container-type: inline-size; container-name: ax-content)
  form#ax-agent-form.ax-form
    div.ax-form-actionbar             (first child; right-aligned "Reload Dagster after saving" toggle)
    div#ax-form-lead.ax-form-lead.ax-grid-form
      label.ax-field  #ax-template-select   (create mode only: "Start from template")
      div#ax-form-lead-fields           (mount: fields of sections with group null → today, name)
    div#ax-form-sections.ax-grid-agent[data-sections]
      section.ax-form-group[data-group="runs"]
        h2.ax-form-section-heading  "Runs"
        section.ax-card.ax-form-section   (one per applicable card, in SECTIONS order)
          h2                              (card label, existing uppercase style)
          div.ax-grid-form > div.ax-field[data-field=…] …
      section.ax-form-group[data-group="job"]  …
      section.ax-form-group[data-group="box"]  …
```

Guarantees:
- The actionbar precedes the lead strip, which precedes the group grid, in document order.
- The lead strip is not a card (no `ax-card` class); it is a form grid so its cells sit side by side and wrap.
- All three group containers exist for every harness, in the order runs, job, box.
- A card exists only if at least one of its fields applies to the current harness (existing rule, now per card).
- Every field keeps `div.ax-field[data-field="<id>"]` as its wrapper wherever it is mounted, so validation error mapping and `lockName` keep working by id.
- The loading placeholder `#ax-form-loading` sits inside `#ax-form-sections` until the first render, as today.

## 2. Layout CSS

```css
.ax-content { container-type: inline-size; container-name: ax-content; }

.ax-grid-agent {
  display: grid;
  gap: var(--ax-space-9);
  align-items: start;
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: "runs" "job" "box";
}
.ax-form-group[data-group="runs"] { grid-area: runs; }
.ax-form-group[data-group="job"]  { grid-area: job; }
.ax-form-group[data-group="box"]  { grid-area: box; }
.ax-form-group { display: flex; flex-direction: column; gap: var(--ax-space-9); min-width: 0; }
.ax-form-group > .ax-form-section { margin-bottom: 0; }

@container ax-content (min-width: 720px) {
  .ax-grid-agent {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas: "runs job" "box job";
  }
}
@container ax-content (min-width: 1320px) {
  .ax-grid-agent {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) minmax(0, 1fr);
    grid-template-areas: "runs job box";
  }
}
```

Guarantees:
- Exactly one arrangement applies at any width; the two thresholds are the only literals and the guide states the same two numbers (checked by test).
- `align-items: start` plus flex-column groups keep every card at its natural height (spec FR-012).
- `minmax(0, …)` tracks and `min-width: 0` on groups prevent long values from forcing horizontal scroll (spec FR-014).
- Inside cards nothing changes: `.ax-grid-form` and `.ax-field--wide` from spec 002 still apply.

## 3. Heading and lead-strip styling

- Group heading: `h2.ax-form-section-heading` (existing: `--ax-type-display-sm`, `--ax-text-high`), margin-bottom `--ax-space-6`.
- Lead strip: `.ax-form-lead` keeps `margin-bottom: var(--ax-space-9)`; its `.ax-field` max-width rule is dropped so the grid governs cell width.
- Read-only name in edit mode: unchanged `.ax-input--readonly` treatment.

## 4. Reference widths (spec FR-008 to FR-010)

| Viewport | Pane inline size (220px sidebar, 28px padding a side) | Expected |
|---|---|---|
| 1800px | 1524px | three columns, Job widest |
| 1440px | 1164px | two columns, Runs over Box on the left, Job right |
| 900px | 624px | one column: Runs, Job, Box |
