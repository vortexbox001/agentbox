# Bug Assessment: Theme selector clipped in the sidebar column

- **Slug**: theme-control-overflow
- **Created**: 2026-09-13
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

> the theme dropdown selector at the bottom of the left hand nav doesn't show all
> the way because its too wide for the column; solution, make the theme selections
> clickable ui elements with no text, showing the text on hover over

## Symptom

In the left sidebar foot, the Light/Dark/System theme control is a single horizontal
row — an icon, a **"Theme"** text label, and a native `<select>` — and the `<select>`
is clipped on its trailing edge because the row is wider than the 240px sidebar
column. Expected: the theme control fits the column at both the expanded (240px) and
collapsed (68px) widths and every option is fully reachable.

## Reproduction

1. Start the UI (`docker compose up -d`, or run `ui/` locally) and open any page,
   e.g. `/agents`.
2. Look at the sidebar foot below the Dagster status link.
3. Observe the theme `<select>` is cut off on the right — its native chevron and/or
   the widest option label ("System") are clipped by the sidebar edge.
   [NEEDS CLARIFICATION: exact browser/OS — native `<select>` intrinsic width and
   chevron rendering vary; reported on the deployed Pi UI.]

## Suspected Code Paths

- `ui/templates/base.html:60-68` — the `.ax-theme-control` `<label>` row: icon +
  `<span class="ax-theme-label">Theme</span>` + `<select class="ax-select
  ax-theme-select">` (System/Light/Dark) laid out in one row.
- `ui/static/app.css:112-132` — `.ax-theme-control { display:flex }` with
  `.ax-theme-label { flex:1 }` and `.ax-theme-select { width:auto }`. The label
  claims the free space and the select keeps its intrinsic width (longest option +
  native chevron); their sum overflows the column.
- `ui/static/app.css:31-40` — `.ax-sidebar { overflow:hidden; padding: … var(--space-6) }`.
  The hidden overflow is what visually clips the too-wide row rather than scrolling it.
- `ui/static/app.css:254-266` — the generic `.ax-select` control styling the theme
  select inherits (full input padding), which inflates its width further.
- `ui/static/shell.js:44-60` (`initTheme`) — reads `#ax-theme-select` `.value` and
  listens for its `change` event; any markup change to the control must keep this
  behaviour (preference write + live re-stamp) intact.

## Root Cause Hypothesis

The theme control was authored (spec 009 US1, T004/T005) as a one-line row of
icon + text label + native `<select>`. In the narrow 240px column the label (`flex:1`)
plus the select's intrinsic `width:auto` (widest option "System" + the OS chevron)
exceed the available inner width (~216px after padding), and `.ax-sidebar { overflow:
hidden }` clips the trailing edge instead of scrolling. Confidence: **high** — the
overflow follows directly from the flex row + intrinsic-width select in a fixed narrow
column.

## Proposed Remediation

**Preferred** (the user's proposal): replace the native `<select>` with a compact
**segmented control of three icon-only buttons** — System / Light / Dark — that fits
the column with room to spare, and surface each option's text on hover (and to
assistive tech) rather than inline.

- `base.html`: swap the `.ax-theme-control` label + `<select>` for a
  `role="radiogroup"` (aria-label "Theme") holding three `<button type="button">`
  controls, each with an icon (`<use href="/static/icons.svg#…">`), a `title` (hover
  tooltip) and an `aria-label` for its name, and a `data-theme-choice="system|light|dark"`
  hook. Keep the section labelled for the collapsed state. Give each button the
  design-system button class so it stays consistent with FR-024/T015 (`ax-btn`, or a
  dedicated `ax-theme-option` that carries `ax-btn`), and reflect the active choice
  with `aria-checked`/`aria-pressed` + an active token fill (`--color-background-blue`,
  matching the nav active state).
- `app.css`: add `.ax-theme-control` as a tight row/segmented group of fixed-size
  icon buttons (sizes from the spacing/`--icon-*` scale, no literals — the
  conformance check forbids px/hex/`font-family`); drop the `flex:1` text label; hide
  the labels when the sidebar is collapsed as today. Hover text is the native `title`
  tooltip (no custom colour/px needed).
- `shell.js`: rework `initTheme()` to bind click handlers on the three buttons
  instead of a `change` listener — on click, write the `agentbox.theme` preference,
  re-resolve + re-stamp `<html>` (no reload), and move the active/`aria-checked`
  state; keep the `matchMedia('(prefers-color-scheme: dark)')` live-follow while the
  preference is `system`. Preference key and pre-paint script in `base.html` are
  unchanged.
- `icons.svg`: add the two missing glyphs (e.g. a sun for light and a monitor for
  system); a moon/`#theme` contrast glyph already exists for dark. Icon-only controls
  need clear, distinct glyphs.

**Alternatives** (smaller, if the segmented control is deferred):
- Drop the inline **"Theme"** text label (keep only the icon + select) and let the
  `<select>` take the row width (`.ax-theme-select { width:100% }`), so the whole
  control fits. Lowest-effort, keeps the native select and its a11y for free, but
  keeps a native `<select>` look in the sidebar.
- Stack the control vertically (label above a full-width select) — fits width but
  adds height to the foot.

## Files likely to change

- `ui/templates/base.html`
- `ui/static/app.css`
- `ui/static/shell.js`
- `ui/static/icons.svg` (new sun/monitor glyphs for the icon-only buttons)
- `ui/tests/test_ui_consistency.py` — the existing `test_every_template_select_is_ax_select`
  guard is satisfied by removing the `<select>`; if the new controls are `<button>`s,
  ensure they carry the button design-system class (aligns with the FR-024/T015
  button-class assertion landing in US2).

## Tests to add or update

- A static/markup test that the sidebar theme control offers the three choices
  (system/light/dark) and that each icon-only control has an accessible name
  (`aria-label`) and a hover `title`.
- Keep `test_conformance.py` green (no literal colour/px/`font-family`/`--ax-*` in the
  new markup and CSS).
- Confirm `test_ui_consistency.py` stays green after the `<select>` is removed (no
  `ax-select` regression) and that any new `<button>` carries the design-system class.
- Behaviour check: selecting each option persists `agentbox.theme` in `localStorage`,
  re-stamps `<html>` with no reload, and `system` continues to live-follow the OS.

## Risks & Considerations

- **Accessibility**: an icon-only control must not rely on the hover `title` alone for
  its name — each button needs an `aria-label`, and the group should expose the
  selected state (`radiogroup` + `aria-checked`, or toggle buttons + `aria-pressed`).
  Keyboard operability (Tab/Enter/Space, ideally arrow-key roving within the group)
  must be preserved.
- **Behaviour preservation (FR-025 spirit)**: the theme resolution contract
  (pre-paint stamp, no-reload re-stamp, `system` live-follow) must be unchanged; only
  the control surface changes from `<select>` to buttons.
- **Conformance gate (FR-022)**: the new CSS must stay pixel-/colour-/font-literal-
  free and use only design-system tokens; `test_conformance.py` will fail otherwise.
- **Collapsed sidebar (68px)**: the icon-only control should read well collapsed;
  ensure the labels/tooltips don't force overflow there either.
- This touches spec 009 US1 files (base.html/app.css/shell.js) that are freshly landed
  and not yet committed — coordinate with the ongoing 009 migration branch.

## Open Questions

- [NEEDS CLARIFICATION: browser/OS where the clipping was observed — native `<select>`
  intrinsic width differs across platforms.]
- [NEEDS CLARIFICATION: should the collapsed sidebar show the full three-way control,
  a single cycle button, or hide it until expanded?]
