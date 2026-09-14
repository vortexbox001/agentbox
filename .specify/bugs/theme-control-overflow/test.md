# Bug Verification: Theme selector clipped in the sidebar column

- **Slug**: theme-control-overflow
- **Tested**: 2026-09-13
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The reported symptom no longer reproduces. In a real headless-Chromium render of
`/agents`, the theme control fits inside the 240px sidebar (right edge 227px, zero
horizontal overflow) as three visible icon buttons — the native `<select>` that
overflowed and was clipped is gone. Theme switching, persistence, and the collapsed
(68px) layout were also exercised and behave correctly. The full test suite shows no
new regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix), expanded | Headless Chromium (CDP) render of `/agents`, measure `.ax-theme-control` vs `.ax-sidebar` | pass | 3 options, no `<select>`, ctlRight 227 ≤ sideRight 240, `overflowX=0`, all options visible and within the sidebar |
| Reproduction (post-fix), collapsed | Set `localStorage['agentbox.sidebar']='collapsed'`, reload, re-measure | pass | 68px sidebar, `flex-direction: column`, options 30px each, `overflowX=0`, all within column |
| Theme switch behaviour | CDP click each option, read `<html data-theme>` + `localStorage` + `aria-checked` | pass | dark→`data-theme=dark`/pref `dark`; light→no attr/pref `light`; system→pref `system`; each `aria-checked=true`; no reload |
| New markup test | `pytest tests/test_ui_consistency.py::test_theme_control_is_accessible_icon_buttons` | pass | radiogroup, 3 choices, aria-label + title + `ax-btn` on each, no `<select>` |
| Conformance | `pytest tests/test_conformance.py` | pass | no literal colour/px/`font-family`/`--ax-*` in the new markup/CSS |
| Regression suite | `cd ui && ../.venv/bin/python -m pytest -q` | pass* | 20 failed / 302 passed — the 20 are the unchanged pre-existing baseline red set (Archon-referencing `test_design_system_docs.py` + 3 `test_api.py` design-system *serving* tests, owned by spec 009 US3); no new failures |
| Lint / type-check | — | not-run | project has no configured lint/type gate for `ui/` |

## Output Excerpts

```
EXPANDED  {"options":3,"hasSelect":false,"ctlRight":227,"sideRight":240,"sideWidth":240,
           "overflowX":0,"flexDir":"row","optWidths":[64,64,64],"optVisible":true,"allWithinSidebar":true}
CLICK dark   {"dataTheme":"dark","pref":"dark","checked":"true"}
CLICK light  {"dataTheme":null,"pref":"light","checked":"true"}
CLICK system {"dataTheme":null,"pref":"system","checked":"true"}
COLLAPSED {"options":3,"hasSelect":false,"ctlRight":61,"sideRight":68,"sideWidth":68,
           "overflowX":0,"flexDir":"column","optWidths":[30,30,30],"optVisible":true,"allWithinSidebar":true}
```

Screenshot (expanded, light/system): the sidebar foot shows the Dagster status link,
a row of three theme icon buttons (monitor active, sun, moon), and the Collapse
toggle — all within the column, none clipped.

`pytest -q` tail: `20 failed, 302 passed`.

## Residual Risks

- The hover **tooltip text** (`title` attribute) was not visually captured — its
  presence is asserted in markup, but the native tooltip popup itself was not
  screenshotted (browsers render `title` on real pointer hover only).
- Keyboard model is basic: each option is Tab-focusable and Enter/Space activates it;
  the fuller WAI-ARIA radio arrow-key roving pattern is a noted follow-up, not a
  regression.
- Verified against Chromium 152 only; other engines' `title`/focus rendering not
  exercised (the layout math is engine-independent flexbox).

## Recommendation

Close the bug — verified end-to-end: the overflow/clipping is resolved at both sidebar
widths, theme switching persists and re-stamps without a reload, and no regressions
were introduced. The two follow-ups (arrow-key roving, and the `.ax-collapse-toggle`
gaining `ax-btn` when US2/T015 lands) are tracked in `fix.md` and are out of scope for
this bug.
