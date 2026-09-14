# AgentBox Design System

AgentBox is a self-hosted "runner" that launches AI agents on a schedule. Each agent is a short-lived container that wakes up, does a job, writes its output, and vanishes. AgentBox is a plugin/addon for [Dagster](https://dagster.io) — it lives in the same ecosystem and should feel like a natural sibling app. When a user navigates between Dagster and AgentBox, the experience should feel seamless: same layout, same font, same component behavior, different brand.

## Sources

This design system was built from the following references:

- **Dagster UI codebase:** [github.com/dagster-io/dagster](https://github.com/dagster-io/dagster) — `js_modules/ui-components/` (color palettes, component CSS, theme tokens) and `js_modules/ui-core/` (app shell, navigation layout)
- **An earlier in-house design system:** a local dark-theme token set for agent-orchestration UIs, since retired in favour of this Dagster-sibling system
- **AgentBox logo:** `assets/logo.svg` (standalone mark, used on the collapsed 68px sidebar rail), plus the theme-aware horizontal lockups `assets/logo-light.svg` (for light grounds) and `assets/logo-dark.svg` (for dark grounds) — mark + wordmark in one SVG, shown at `--brand-lockup-width` (130px) on the expanded sidebar and toggled by the resolved theme. (`assets/wordmark.svg` / `assets/wordmark-navy.svg` remain the standalone wordmarks.) Fish school mark in navy, teal, and lime

## Brand Identity

AgentBox uses a school-of-fish motif. Where Dagster has an octopus, AgentBox has fish swimming in formation — a metaphor for agents coordinating as a swarm. The brand colors are derived directly from the logo:

| Color | Hex | Role |
|-------|-----|------|
| Navy | `#183040` | Dark brand, text, nav backgrounds |
| Teal | `#308888` | Primary accent, links, active states |
| Lime | `#c8d850` | Secondary accent, highlights, agent status |

---

## Content Fundamentals

### Voice and Tone
AgentBox copy is **technical and direct**, mirroring Dagster's style. It addresses the user as an engineer who knows what they're doing — no hand-holding, no marketing language in the UI.

- **Sentence case** for all UI text: "Create new agent", not "Create New Agent"
- **No emoji** in the product UI
- **Second person** where needed: "Your agents", "Configure your schedule"
- **Terse labels:** prefer single words ("Runs", "Agents", "Schedules") over phrases
- **Status text is lowercase:** "running", "success", "error", "queued"
- **Technical terms are unabbreviated:** "container", "schedule", "template", not jargon shortcuts

### Copy Patterns
- Page titles: noun, 1-2 words ("Agents", "Run Detail", "Deployment")
- Empty states: one sentence explaining what will appear ("No agents have been created yet.")
- Error messages: state what happened, then what to do ("Container failed to start. Check the agent logs.")
- Timestamps: relative when recent ("2m ago"), absolute otherwise ("Sep 12, 2026 14:30")
- Counts: always numeric, monospace font ("12 runs", "3 agents")

---

## Visual Foundations

### Color System
AgentBox uses a layered color architecture matching Dagster's structure: core color scales → semantic theme tokens → component usage. The semantic layer supports light and dark themes via CSS custom properties.

**Primary accent (teal):** Used for links, active nav items, focus rings, checkboxes, and interactive highlights. Replaces Dagster's blurple as the brand accent.

**Status colors:** Identical to Dagster's red/yellow/green for error/warning/success. This ensures users moving between apps read status the same way.

**Surfaces:** Same gray scale as Dagster (gray-990 through gray-10) for backgrounds, borders, and text levels. This is the key to the "same ocean" feel.

### Typography
AgentBox uses the same font stack as Dagster:
- **Sans-serif:** Inter (substitute for Geist Sans — see Font Substitution below)
- **Monospace:** Source Code Pro (substitute for Geist Mono)

**Font substitution note:** Dagster uses Geist Sans and Geist Mono as primary fonts. This design system uses Inter and Source Code Pro as close substitutes available via Google Fonts. To match Dagster exactly, replace with Geist font files and update `tokens/typography.css`.

**Type scale:**
- Display: 32/24/20/16px, weight 600 — page headings, stats
- Body: 16/14/12/11px, weight 400 — content, descriptions
- Label: 12/11px, weight 500, uppercase tracked — field labels, table headers
- Mono: 14/12/11/10px — IDs, code, technical values, timestamps

### Spacing
A 2px-based scale from 0 to 48px, matching Dagster's density:
- 4px: badge gaps
- 8px: tight UI gaps, nav group separators
- 12px: nav item padding, inline gaps
- 16px: card grid gaps, section internal spacing
- 20px: detail layout gaps
- 24px: card padding, section spacing
- 32px: page section breaks

### Borders and Radii
- **Radii:** 4px (badges) → 6px (buttons, inputs) → 8px (nav items, cards) → 10px (panels) → 12px (modals)
- **Borders:** keyline at `rgba(gray, 0.20)`, default at gray-200 (light) / gray-800 (dark). No decorative borders.
- **Dividers:** 1px solid keyline, full width

### Shadows
Shadows are minimal, matching Dagster's approach:
- Cards and in-flow surfaces: **no shadow** — elevation is indicated by background shift and border
- Popovers and dropdowns: `--shadow-lg` (the only floating-layer shadow)
- Hover buttons: `--shadow-md` on hover only

### Backgrounds
- **No gradients** on surfaces (flat fills only)
- **No textures or patterns**
- **Brand gradient** (`--color-brand-gradient`: teal→lime at 135°) is reserved for the logo ring and marketing — never on UI surfaces

### Animation
- **Transitions:** 100ms for hover states, 150ms for border/background changes, 300ms for page transitions
- **Easing:** `ease` for all transitions (matching Dagster)
- **Entrance:** `ab-fadeIn` (opacity + 4px translateY) for content loads
- **No bounces, no springs** — transitions are functional, not decorative

### Hover and Press States
- **Hover:** background shifts one level lighter (e.g., `background-default` → `background-default-hover`). No opacity changes.
- **Press/active:** `filter: brightness(0.95)` on buttons
- **Disabled:** `opacity: 0.5`, `cursor: default`

### Cards
- Background: `--color-background-default` (white in light mode)
- Border: `1px solid var(--color-border-default)`
- Radius: `--radius-lg` (8px)
- Padding: 16-24px
- No shadow (elevation via border)
- Hover: border shifts to `--color-border-hover`

### Imagery
- No decorative imagery in the product UI
- Logo uses the fish school mark
- Status indicators use colored dots, not icons
- Illustration style: if needed, flat line art in brand teal/navy/lime (not used in current product)

---

## Iconography

AgentBox uses **Lucide** icons (outline stroke style), matching the icon aesthetic of modern data tools. This was chosen for compatibility with Dagster's outline icon style (stroke-width 1.5-2, no fill).

- **Size:** 16×16 for navigation and inline, 20×20 for page actions, 24×24 for empty states
- **Style:** Outline stroke, `stroke: currentColor`, `stroke-width: 2`, `fill: none`
- **Color:** Always `currentColor` — inherits from parent text color
- **Format:** Inline SVG preferred; Lucide CDN as fallback
- **CDN:** `https://unpkg.com/lucide-static@latest/icons/`

No emoji in the product UI. No custom icon font. Unicode characters are not used as icons.

---

## Layout

### App Shell (matches Dagster)
```
┌─────────┬────────────────────────────┐
│ Sidebar │ Content Area               │
│ (240px) │ (flex: 1)                  │
│         │                            │
│         │                            │
│         │                            │
└─────────┴────────────────────────────┘
```

- **Sidebar:** 240px wide (68px collapsed), same surface as the content area (`--color-background-default`) so the two panes share one ground in both themes, vertical flex column
- **Sidebar border:** `inset -1px 0 0 var(--color-keyline-default)` (right edge shadow, not a CSS border) — the only separator now that the rail shares the content ground
- **Brand lockup:** `--brand-lockup-width` (130px) — width of the expanded-sidebar horizontal lockup (`logo-light.svg` / `logo-dark.svg`); the collapsed rail shows `logo.svg` instead
- **Content area:** `flex: 1`, full height, `overflow-y: auto`
- **Content padding:** determined by the page, typically 24px
- **No top bar** — Dagster's current layout uses the left sidebar for all navigation

### Navigation
- Nav items: 32px height, 8px border-radius, flex row with icon + label
- Active item: `--color-background-blue` fill, `--color-text-default` text (white in dark, near-black in light)
- Hover: `--color-background-lighter` fill
- Font: 14px, weight 400 (500 when active)
- Icons: 16×16, stroke currentColor
- Groups separated by 8px gap
- Collapse toggle at bottom

### Content Pages
- Full height, overflow-y auto
- 64px bottom padding (scroll clearance)
- No fixed top bar in current layout

---

## File Structure

```
├── assets/              Logo and visual assets
│   ├── logo.svg         Standalone mark (collapsed sidebar rail)
│   ├── logo-light.svg   Horizontal lockup for light grounds (130px, expanded sidebar)
│   ├── logo-dark.svg    Horizontal lockup for dark grounds (130px, expanded sidebar)
│   ├── wordmark.svg
│   └── wordmark-navy.svg
├── components/          Reusable React UI primitives
│   ├── buttons/         Button, IconButton
│   ├── forms/           TextInput, Select, Checkbox, Toggle
│   ├── feedback/        Badge, StatusDot, Alert, Spinner
│   ├── navigation/      Tabs, Breadcrumbs
│   ├── layout/          Card, Dialog
│   └── data/            Table
├── guidelines/          Foundation specimen cards
├── tokens/              CSS custom property files
│   ├── colors.css       Core color scales
│   ├── theme.css        Semantic theme mappings
│   ├── typography.css   Font families and type scale
│   ├── spacing.css      Spacing, radii, z-index, sizing
│   ├── shadows.css      Shadows and transitions
│   ├── animations.css   Keyframe animations
│   └── base.css         Reset and global styles
├── ui_kits/             Full-screen product recreations
│   └── agentbox-app/    Main AgentBox application
├── styles.css           Root stylesheet (imports only)
├── index.html           Served specimen gallery (renders every card from _ds_manifest.json)
├── readme.md            This file
├── github.md            Source repo association
├── SKILL.md             Agent skill manifest
└── thumbnail.html       Design system tile
```

## Components

| Component | Directory | Description |
|-----------|-----------|-------------|
| Button | `components/buttons/` | Primary, outlined, ghost, danger variants. 8px radius, inset box-shadow border. |
| TextInput | `components/forms/` | Text field with label support. Matches Dagster's input styling. |
| Select | `components/forms/` | Native select with custom chevron. |
| Checkbox | `components/forms/` | Teal-checked checkbox. |
| Toggle | `components/forms/` | On/off switch with teal active state. |
| Badge | `components/feedback/` | Status badges (running, success, error, etc.) |
| StatusDot | `components/feedback/` | Colored status indicator dot. |
| Alert | `components/feedback/` | Info/warning/error alert banners. |
| Spinner | `components/feedback/` | Loading spinner. |
| Tabs | `components/navigation/` | Bottom-border tab indicator, matches Dagster. |
| Card | `components/layout/` | Content container with border, no shadow. |
| Dialog | `components/layout/` | Modal dialog with backdrop blur. |
| Table | `components/data/` | Grid-based data table with header + rows. |

## UI Kits

- **AgentBox App** (`ui_kits/agentbox-app/`): Full interactive recreation of the AgentBox application — sidebar navigation, agent list, agent detail, run viewer.
