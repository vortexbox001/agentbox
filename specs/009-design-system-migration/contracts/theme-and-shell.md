# Contract: Theme Resolution & App Shell

Covers FR-009 (theme), FR-010/011/012 (shell), FR-013 (typography), FR-015/016/017 (no-egress).

## Theme resolution (FR-009)

**Storage**: `localStorage` key holding the preference ∈ {`light`, `dark`, `system`}. Absent →
treated as `system`. No server-side setting (that arrives with spec 011).

**Pre-paint contract** — an **inline** `<script>` in `<head>`, before any visible paint:
1. read the stored preference; missing → `system`.
2. `resolved = preference === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : preference`.
3. stamp `document.documentElement` — set `data-theme="dark"` when `resolved === 'dark'`,
   otherwise remove the attribute (bare `:root` = light, per `theme.css`).
- The base template MUST NOT hard-code `data-theme="dark"` (it does today — must change).
- No wrong-theme flash on first load even with no stored preference (Acceptance 1, Edge Cases).

**Runtime contract** (in `shell.js`):
- The sidebar-foot control offers Light / Dark / System; selecting one writes `localStorage`,
  re-resolves, re-stamps `<html>` — no full reload (Acceptance 2).
- A `matchMedia('(prefers-color-scheme: dark)')` `change` listener: while preference =
  `system`, re-resolve + re-stamp live (Acceptance 3, Edge Cases) — no reload flash.
- Choice persists across visits (Acceptance 2).

**Verification hook**: no `--ax-*` token resolves and no serif font loads on any page
(Acceptance 4, SC-001) — covered by the conformance check + manual inspection.

## App shell (FR-010, FR-011, FR-012)

**No top bar.** The current `<header class="ax-topbar">` in `base.html` is removed; page title,
breadcrumb, and page actions move into a **page header** at the top of the content area
(FR-011).

**Sidebar** (240px, `--nav-width`; collapsed width 68px per readme):
- Dark background (`--color-nav-background`), vertical flex column, right-edge keyline via
  `inset -1px 0 0 var(--color-keyline-default)` (not a CSS border).
- Contains: brand block (logo/wordmark from `assets/`), primary nav (Agents, Automation) with
  16×16 Lucide icons + labels, and the sidebar foot holding **both** the Dagster status link
  **and** the theme control (FR-010).
- Collapse toggle at the foot; collapsed/expanded state persists in `localStorage` across
  navigation and reloads (FR-010, Edge Cases).
- Nav item: 32px height, 8px radius; active = `--color-background-blue` fill + selected text;
  hover = `--color-background-lighter`.

**Preserved shell regions, restyled** (FR-012): the Dagster status link + `#ax-dagster-*`
status behaviour, the status region (`#ax-status-region`), toast region (`#ax-toast-region`),
and modal root (`#ax-modal-root`) keep their IDs and behaviour, restyled on the new tokens.

**Content area**: `flex: 1`, full height, `overflow-y: auto`, ~24px padding, 64px bottom
scroll clearance (readme Layout).

## Typography (FR-013)

- All serif (Playfair) typography is removed, including the former italic-serif "thinking"
  treatment — replaced by the body/mono split (`--font-default` Inter, `--font-mono` Source
  Code Pro) from `typography.css`.
- No `font-family` is declared outside the font file (enforced by the conformance check).

## No-egress rendering (FR-015, FR-016, FR-017)

- **Fonts**: `typography.css` loads Inter + Source Code Pro via local `@font-face` → self-hosted
  `.woff2` under the bundle; the Google-Fonts `@import` is removed. Null-action fallback
  (licence-blocked) = system-font stack, no external import ever restored (research Decision 2).
- **Icons**: resolve from the local `ui/static/icons.svg` Lucide sprite via `<use>`; no
  `unpkg`/CDN reference anywhere, including bundle docs (research Decision 3).
- **Invariant**: no served CSS or HTML references a `googleapis`, `unpkg`, or `cdn` host, or
  any external font/icon/asset URL (FR-017, SC-003) — enforced by the conformance check;
  "block egress and reload" stays a manual pre-release check (spec Out of Scope).
