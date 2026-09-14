# WCAG 2.1 AA contrast audit — US1 (T008 / FR-026 / SC-009)

Ratios computed from the resolved `ui/design-system/tokens/` values (translucent
backgrounds composited over their surface) in both themes. Threshold: **4.5:1** for
normal text (badge label text is 11px, so the 3:1 large-text exemption does not
apply); **3:1** for non-text UI/icons.

## Checked pairs (after fixes) — all ≥ 4.5:1 text / ≥ 3:1 UI

| Pair | Light | Dark |
|------|-------|------|
| body text (`text-default` / `background-default`) | 20.18 | 20.18 |
| muted / help / table-header (`text-light` / `background-default`) | 9.17 | 8.82 |
| link (`link-default` / `background-default`) | 6.71 | 11.55 |
| nav idle (`nav-text` / `nav-background`) | 6.16 | 6.16 |
| nav hover (`nav-text-hover` / `nav-button-hover`) | 5.98 | 5.98 |
| nav active (`nav-text-selected` / `background-blue`↠navy) | 17.95 | 15.22 |
| Dagster label / status (`nav-text*` / `nav-button`) | 5.35 / 7.55 | 5.35 / 7.55 |
| primary button (`accent-reversed` / `accent-primary`) | 12.86 | 12.74 |
| badge enabled (`text-green` / `background-green`) | 4.65 | 12.03 |
| badge error (`text-red` / `background-red`) | 7.85 | 10.13 |
| badge harness (`text-teal` / `background-blue`) | 5.81 | 11.09 |
| badge fallback (`text-yellow` / `background-yellow`) | 4.58 | 12.30 |
| badge disabled / queued (`text-light` / `background-gray`) | 7.92 | 7.83 |
| badge scheduled / template (lime, theme-split) | 6.20 | 13.29 |
| status ok / error text (`text-green`/`text-red` / `popover-background`) | 5.10 / 9.27 | 12.51 / 9.41 |

## Fixes applied (token remappings, `app.css`)

1. **`--color-text-lighter` → `--color-text-light`** for readable secondary text
   (`.ax-muted`, `.ax-help`, `.ax-empty`, `.ax-breadcrumb`, `.ax-new-prompt-label`,
   `.ax-table th`, `.ax-form-section > h2`, `.ax-automation-kind`). `text-lighter`
   (gray500) on the page background is 4.27:1 in dark — below 4.5:1.
2. **Gray badges** (`--disabled`, `--queued`) use `--color-text-light` (were 4.08 /
   3.79:1 with `text-lighter`).
3. **Lime badges** (`--scheduled`, `--template`) are theme-split: `--color-core-lime800`
   in light (the token `text-lime`/lime700 is only 3.80:1 over the pale light tint),
   the token `--color-text-lime` in dark. Both ≥ 6:1.
4. **Nav hover** uses `--color-nav-button-hover` (not the prescribed theme-flipping
   `--color-background-lighter`, which is opaque near-white and fails on the fixed
   navy sidebar in light mode). Active fill stays `--color-background-blue` as specified.

Interactive controls (inputs, buttons, dropdown trigger, toast/status close ×) meet
the 3:1 UI-component minimum and lift further on hover/focus.
