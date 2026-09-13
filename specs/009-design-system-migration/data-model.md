# Phase 1 Data Model: Design System Migration

This feature ships no persisted database entities. The "entities" are the design-system
constructs the migration operates on: design tokens, component macros, the theme, and the
in-repo bundle. Client-side state (theme choice, sidebar collapse) lives only in browser
`localStorage`.

## Design token

A named design value that all styling references instead of a literal.

- **Fields**: `name` (CSS custom property, e.g. `--color-accent-teal`, `--space-4`,
  `--type-body-md`, `--radius-md`, `--shadow-md`, `--nav-width`, `--icon-size`); `category`
  (colour | type | space | radius | shadow | transition | nav-width | icon); `value` (a core
  value, another token, or — only in the token/font files — a literal).
- **Source**: `ui/design-system/tokens/*.css` — `colors.css` (core scales), `theme.css`
  (semantic Light/Dark mappings), `typography.css`, `spacing.css`, `shadows.css`,
  `animations.css`, `base.css`.
- **Rules**:
  - Every colour, font-family, and pixel-like value used in app CSS/templates MUST be a token
    reference, not a literal (FR-008, FR-022). Literals are permitted **only** inside the token
    files and the font-face file.
  - No `--ax-*` token may resolve anywhere in served CSS, templates, or JS (FR-008).
  - Semantic tokens resolve differently per resolved theme (see **Theme**).

## Component macro

A shared, reusable Jinja2 macro whose parameters mirror a design-system component contract;
the single definition every page composes.

- **Fields**: `name`; `parameters` (mirroring the bundle `.d.ts`); `design-system class`
  (the class the macro emits so conformance checks can see it); `source contract` (the
  `.jsx`/`.d.ts` in `ui/design-system/components/`).
- **The set (13, from `_ds_manifest.json` / readme Components table)**: `button`, `text_input`,
  `select`, `checkbox`, `toggle`, `badge`, `status_dot`, `alert`, `spinner`, `tabs`, `card`,
  `dialog`, `table`. (The manifest also lists `Tab` as a sub-part of `Tabs`; it is covered by
  the `tabs` macro.)
- **Rules**:
  - One macro per manifest component (FR-004); parameters mirror the component contract
    (FR-005) — full parameter table in [contracts/component-macros.md](./contracts/component-macros.md).
  - Pages compose these macros; no page defines its own button or card styling (FR-006).
  - `select`, `button`, and `table` occurrences in rendered pages MUST carry the design-system
    class (FR-024); `select` stays on the spec-002 shared-dropdown path (`ax-select` +
    `enhanceSelect`), behaviour frozen (FR-025).
  - The agent-form responsive form-grid is preserved, re-expressed on the new spacing scale
    (FR-007).

## Theme

One of Light, Dark, or System; the resolved theme decides which semantic token values apply.

- **Fields**: `preference` ∈ {light, dark, system} (persisted per viewer in `localStorage`);
  `resolved` ∈ {light, dark} (preference, or the OS value when preference = system);
  `applied via` = presence/absence of `data-theme="dark"` on `<html>`.
- **State transitions**:
  - *initial load*: read stored `preference`; if none → `system`. Resolve and stamp
    `data-theme` **before first paint** (FR-009, Edge Cases) — no wrong-theme flash.
  - *toggle in sidebar foot*: user picks Light/Dark/System → update `localStorage`, re-resolve,
    re-stamp — no full reload (FR-009).
  - *OS theme changes while preference = system*: `matchMedia` listener re-resolves and
    re-stamps live — no reload flash (Edge Cases).
- **Rules**: base template MUST NOT hard-code `data-theme="dark"` (FR-009); default is the OS
  preference; contrast meets WCAG 2.1 AA in both themes (FR-026). Contract:
  [contracts/theme-and-shell.md](./contracts/theme-and-shell.md).

## Sidebar collapse state

Per-viewer UI state, persisted in `localStorage` (not a server setting).

- **Fields**: `collapsed` ∈ {true, false}; expanded width = `--nav-width` (240px), collapsed
  width = the defined collapsed width (68px per readme).
- **State transitions**: toggle at sidebar foot flips `collapsed`; value persists across
  navigation and reloads (Edge Cases, FR-010).

## Design-system bundle

The in-repo authoritative set humans and agents consult.

- **Fields**: `readme.md` (single human source of truth, FR-002); `tokens/*` (machine-readable
  source, FR-002); `_ds_manifest.json` (component manifest, FR-004/023); `components/`,
  `guidelines/`, `ui_kits/`, `assets/` (references); `SKILL.md` (skill body); `fonts/`
  (self-hosted faces, FR-015).
- **Rules**:
  - The retired Archon artefacts (Archon doc, its token file, the three specimen files, its
    support script) MUST be removed (FR-001) and no test may reference them (FR-023 replacement).
  - The bundle is served in-app; `/design-system` opens the developer reference app (FR-003).
  - Served bundle CSS MUST contain no external font/CDN/asset URL (FR-017) — this includes
    removing the `@import` in `typography.css` (research Decision 2).

## Client persistence summary

| Key (localStorage) | Values | Set by | Read by |
|--------------------|--------|--------|---------|
| theme preference | `light` \| `dark` \| `system` | sidebar theme control | pre-paint head script, `matchMedia` listener |
| sidebar collapsed | `true` \| `false` | sidebar collapse toggle | shell on load |

No server-side persistence, no schema changes, no new API endpoints.
