# Bug Fix: Theme selector clipped in the sidebar column

- **Slug**: theme-control-overflow
- **Fixed**: 2026-09-13
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Replaced the native `<select>` theme control — which overflowed the 240px sidebar
column and was clipped by `.ax-sidebar { overflow:hidden }` — with a compact
segmented control of three icon-only buttons (System / Light / Dark). Each button's
name shows on hover (`title`) and to assistive tech (`aria-label`); the group is a
`radiogroup` and the active choice is reflected with `aria-checked`. The buttons share
the row width (`flex:1`), so the control always fits.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `ui/templates/base.html` | modified | Swapped the `.ax-theme-control` `<label>` + `<select>` for a `role="radiogroup"` of three `<button class="ax-btn ax-theme-option" role="radio">` with icon + `title` + `aria-label` + `data-theme-choice`. |
| `ui/static/icons.svg` | added | New glyphs `theme-light` (sun), `theme-dark` (moon), `theme-system` (monitor). |
| `ui/static/app.css` | modified | Rewrote `.ax-theme-control` as a compact segmented control (`flex:1` options, token-only styling); active = `--color-background-blue`, hover = `--color-nav-button-hover`. Dropped the dead `.ax-theme-label`/`.ax-theme-select` rules; collapsed sidebar now stacks the options vertically so they fit 68px. |
| `ui/static/shell.js` | modified | `initTheme()` now binds clicks on the three buttons (was a `<select>` `change` listener), reflecting `aria-checked` and keeping persist + no-reload re-stamp + `system` live-follow. |
| `ui/tests/test_ui_consistency.py` | added test | `test_theme_control_is_accessible_icon_buttons`. |

## Diff Highlights

`base.html` (one of three options):

```html
<div class="ax-theme-control" role="radiogroup" aria-label="Theme">
  <button class="ax-btn ax-theme-option" type="button" role="radio" aria-checked="false"
          data-theme-choice="light" title="Light" aria-label="Light theme">
    <svg class="ax-icon" width="16" height="16" aria-hidden="true"><use href="/static/icons.svg#theme-light"></use></svg>
  </button>
  …
</div>
```

`app.css`:

```css
.ax-theme-control { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-4); }
.ax-theme-control .ax-theme-option { flex: 1; min-width: 0; justify-content: center; padding: var(--space-3);
  background: none; border-color: transparent; color: var(--color-nav-text); }
.ax-theme-control .ax-theme-option[aria-checked="true"] { background: var(--color-background-blue); color: var(--color-nav-text-selected); }
html[data-sidebar="collapsed"] .ax-theme-control { flex-direction: column; gap: var(--space-1); }
```

`shell.js`:

```js
const buttons = Array.from(group.querySelectorAll("[data-theme-choice]"));
b.addEventListener("click", () => {
  const next = b.dataset.themeChoice;
  try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
  stampTheme(next); reflect();
});
```

## Tests Added or Updated

- `ui/tests/test_ui_consistency.py::test_theme_control_is_accessible_icon_buttons` —
  pins that the control is a `radiogroup` with all three `data-theme-choice`s, uses no
  native `<select>`, and that every option `<button>` carries `aria-label`, `title`,
  and the `ax-btn` design-system class.

## Local Verification

- `../.venv/bin/python -m pytest -q` → **20 failed, 302 passed**. The 20 failures are
  the pre-existing baseline red set (Archon-referencing `test_design_system_docs.py` +
  the 3 `test_api.py` design-system *serving* tests), unchanged by this fix and owned
  by spec 009 US3 (T018/T021). Passing count rose by one (the new test).
- `../.venv/bin/python -m pytest tests/test_conformance.py -q` → green: the new markup
  and CSS carry no literal colour/px/`font-family`/`--ax-*`.
- Render smoke via the app: `/agents` emits `role="radiogroup"`, exactly three
  `data-theme-choice` buttons, no `ax-theme-select`, and no `var(--ax-…)`.
- Not verified in a real browser (no headless browser in this environment): the actual
  hover tooltip, the click-to-switch/no-flash behaviour, and the collapsed-sidebar
  vertical stack — covered by `/speckit-bug-test` / the quickstart browser checklist.

## Deviations from Assessment

None material. The dark-theme glyph is a new `theme-dark` moon rather than reusing the
existing `#theme` contrast circle, for a clearer icon-only set; the now-unused `#theme`
symbol was left in `icons.svg` (harmless, may be removed later).

## Follow-ups

- Consider roving-tabindex + arrow-key navigation within the radiogroup for a fuller
  WAI-ARIA radio pattern (currently each button is Tab-focusable and Enter/Space
  activates it — operable, but not the full arrow-key model).
- Manual browser pass for the collapsed (68px) stacked layout and the hover tooltips.
- When US2/T015 lands the "every `<button>` carries `ax-btn`" assertion, the sidebar
  `.ax-collapse-toggle` (still a bare `<button>`) will also need the class — out of
  scope for this bug.
