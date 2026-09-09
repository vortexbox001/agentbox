# Archon Design System — Agent Instructions

> **Version:** 1.0.0  
> **Files:** `archon-tokens.css` (tokens), `Archon Design System.dc.html` (specimen/component library), `Archon Prototype.dc.html` (reference implementation)

## Overview

Archon is a dark-theme design system for agent orchestration UIs. It was designed for an application that defines, schedules, and monitors AI agents operating on code repositories via Dagster pipelines. The system balances technical precision with humanistic warmth — machine operations rendered in monospace and sans-serif, agent reasoning rendered in italic serif.

---

## Quick Start

```html
<link rel="stylesheet" href="archon-tokens.css">
```

This imports Google Fonts (Playfair Display, Inter, Source Code Pro) and defines all CSS custom properties on `:root`. It also includes a minimal base reset (`box-sizing`, `body` styles, `a` colors) and keyframe animations.

---

## Design Principles

1. **Dark foundation, signal accents.** The background is near-black (`#101216`). Content surfaces are dark grey (`#1a1e26`). Color is reserved for accents that carry meaning — status, identity, interaction.

2. **Three typefaces, three roles.**
   - **Playfair Display** (serif): headings, stat numbers, page titles, and — in italic — agent thinking/reasoning blocks. This is the humanistic counterpoint.
   - **Inter** (sans-serif): body text, labels, UI chrome, navigation, descriptions.
   - **Source Code Pro** (monospace): technical values, IDs, model names, token counts, code blocks, timestamps.

3. **Four signal colors.** Cyan (`#00e5ff`), magenta (`#e040fb`), yellow (`#ffd740`), green (`#69f0ae`). Each has a semantic role:
   - **Cyan** — primary accent, running status, interactive highlights, CTAs
   - **Magenta** — agent thinking/reasoning, queued status, template identity
   - **Yellow** — warnings, scheduled status, draft stage, caution states
   - **Green** — success, production stage, positive deltas, health

4. **Thinking is different.** When the UI shows what an agent is thinking, reasoning, or deliberating, switch to italic Playfair Display with magenta-tinted containers and a left border accent. This makes machine reasoning feel like inner monologue rather than data output.

5. **Information hierarchy through opacity.** Text uses white at varying opacities rather than distinct grey hex values. This keeps everything harmonious on dark backgrounds:
   - Primary: `#ffffff` — headings, large stat numbers
   - High: `rgba(255,255,255,.9)` — important content, names
   - Mid: `rgba(255,255,255,.7)` — body text, secondary content
   - Low: `rgba(255,255,255,.5)` — descriptions, less important data
   - Muted: `rgba(255,255,255,.4)` — labels, field names
   - Faint: `rgba(255,255,255,.3)` — metadata, timestamps
   - Ghost: `rgba(255,255,255,.2)` — disabled, decorative

---

## Token Reference

### Surfaces

| Token | Value | Use |
|-------|-------|-----|
| `--ax-bg-root` | `#101216` | Page/app background |
| `--ax-bg-sidebar` | `#0c0d10` | Sidebar panel background |
| `--ax-bg-card` | `#1a1e26` | Card/panel backgrounds |
| `--ax-bg-card-hover` | `#1e2230` | Card hover state |
| `--ax-bg-input` | `rgba(255,255,255,.04)` | Form inputs, badges, subtle fills |
| `--ax-bg-elevated` | `rgba(255,255,255,.03)` | Nested content blocks |
| `--ax-bg-overlay` | `rgba(0,0,0,.6)` | Modal backdrop |

### Borders

| Token | Value | Use |
|-------|-------|-----|
| `--ax-border-subtle` | `rgba(255,255,255,.06)` | Card borders, dividers |
| `--ax-border-default` | `rgba(255,255,255,.08)` | Stronger dividers, field borders |
| `--ax-border-strong` | `rgba(255,255,255,.1)` | Modal borders, focus rings |
| `--ax-border-input` | `rgba(255,255,255,.1)` | Input field borders |

### Accent Colors

Each accent has a full range: `{color}`, `{color}-bg` (8% opacity fill), `{color}-bg-strong` (15%), `{color}-border` (20%), `{color}-muted` (70%), and where applicable `-light`, `-dark`, `-glow`.

| Accent | Token prefix | Hex |
|--------|-------------|-----|
| Cyan | `--ax-cyan` | `#00e5ff` |
| Magenta | `--ax-magenta` | `#e040fb` |
| Yellow | `--ax-yellow` | `#ffd740` |
| Green | `--ax-green` | `#69f0ae` |
| Error (Red) | `--ax-error` | `#ff5252` |
| Dagster | `--ax-dagster` | `#4f43ef` |

### Typography

Font families:
- `--ax-font-display` → `'Playfair Display', Georgia, serif`
- `--ax-font-body` → `'Inter', system-ui, sans-serif`
- `--ax-font-mono` → `'Source Code Pro', monospace`

Type presets (use with `font:` shorthand):

| Token | Weight/Size | Use |
|-------|------------|-----|
| `--ax-type-display-xl` | 600 32px | Large stat numbers, hero headings |
| `--ax-type-display-lg` | 600 24px | Page titles |
| `--ax-type-display-md` | 600 20px | Section titles |
| `--ax-type-display-sm` | 500 18px | Card section headings |
| `--ax-type-display-xs` | 500 14px | Card titles, subsection headings |
| `--ax-type-thinking-lg` | italic 500 14px/1.7 | Agent reasoning panels |
| `--ax-type-thinking-md` | italic 400 13px/1.7 | Agent thinking inline |
| `--ax-type-thinking-sm` | italic 400 12px/1.6 | Small thinking contexts |
| `--ax-type-body-lg` | 400 14px | Primary body text |
| `--ax-type-body-md` | 400 13px | Default body text |
| `--ax-type-body-sm` | 400 12px | Secondary text, descriptions |
| `--ax-type-body-xs` | 400 11px | Metadata, small descriptions |
| `--ax-type-label` | 500 11px | Uppercase field labels |
| `--ax-type-label-sm` | 500 10px | Table headers, small labels |
| `--ax-type-mono-lg` | 400 13px | Model names, large tech values |
| `--ax-type-mono-md` | 400 12px | Code blocks, run IDs |
| `--ax-type-mono-sm` | 400 11px | Badges, small tech values |
| `--ax-type-mono-xs` | 400 10px | Timestamps, version numbers |

**Labels** should always include `text-transform: uppercase` and `letter-spacing: var(--ax-tracking-label)` (0.06em).

### Spacing

Scale from `--ax-space-0` (0) to `--ax-space-14` (48px). Key stops:

| Token | Value | Common use |
|-------|-------|-----------|
| `--ax-space-4` | 8px | Tight gaps (between badges) |
| `--ax-space-6` | 12px | Nav item padding, small gaps |
| `--ax-space-8` | 16px | Card internal sections, grid gaps |
| `--ax-space-9` | 20px | Card padding (compact) |
| `--ax-space-10` | 24px | Card padding (standard), section gaps |
| `--ax-space-11` | 28px | Page content padding |

### Radii

| Token | Value | Use |
|-------|-------|-----|
| `--ax-radius-sm` | 4px | Badges, small tags |
| `--ax-radius-md` | 6px | Buttons, inputs, nav items |
| `--ax-radius-lg` | 8px | Avatars, icon containers, nested blocks |
| `--ax-radius-xl` | 10px | Cards |
| `--ax-radius-2xl` | 12px | Modals |
| `--ax-radius-pill` | 9999px | Thinking context pills, toggles |
| `--ax-radius-round` | 50% | Status dots, round avatars |

---

## Component Patterns

### Card

The base content container. Always on `--ax-bg-card` with `--ax-border-subtle` and `--ax-radius-xl`.

```css
background: var(--ax-bg-card);
border: 1px solid var(--ax-border-subtle);
border-radius: var(--ax-radius-xl);
padding: var(--ax-space-10); /* 24px */
```

For interactive cards, add hover border transition:
```css
cursor: pointer;
transition: border-color var(--ax-transition-normal);
/* on hover: border-color: rgba(0,229,255,.2) or accent-specific */
```

### Stat Card

Large serif number with delta indicator inside a standard card.

Structure:
1. Uppercase label (`--ax-type-label`, `--ax-text-muted`)
2. 12px gap
3. Large number (`--ax-type-display-xl`, `--ax-text-primary`) + delta badge (mono 11px, accent color)

### Status Badge

Small mono pill for run/agent status.

```css
padding: 4px 10px;
border-radius: var(--ax-radius-sm);
font: 500 10px var(--ax-font-mono);
/* bg and color from status map */
```

Status color map:
| Status | Background | Text |
|--------|-----------|------|
| running | `--ax-cyan-bg` | `--ax-cyan` |
| success | `--ax-green-bg` | `--ax-green` |
| error | `--ax-error-bg` | `--ax-error` |
| scheduled | `--ax-yellow-bg` | `--ax-yellow` |
| queued | `--ax-magenta-bg` | `--ax-magenta` |
| idle | `--ax-bg-input` | `--ax-text-muted` |

### Lifecycle Stage Badge

Same structure as status badge. Stage map:
| Stage | Background | Text |
|-------|-----------|------|
| draft | `--ax-yellow-bg` | `--ax-yellow` |
| testing | `--ax-magenta-bg` | `--ax-magenta` |
| staging | `--ax-cyan-bg` | `--ax-cyan` |
| production | `--ax-green-bg` | `--ax-green` |

### Status Dot

Small colored circle, optionally with glow for active states.

```css
width: 8px; height: 8px;
border-radius: var(--ax-radius-round);
background: var(--ax-status-running);
/* for running state, add: */
box-shadow: var(--ax-shadow-glow-cyan);
```

### Thinking Block

The humanistic treatment for agent reasoning.

**Inline:** Italic Playfair with left border accent.
```css
font: var(--ax-type-thinking-md);
color: var(--ax-text-low);
border-left: 2px solid var(--ax-magenta-border);
padding-left: 14px;
```

**Panel:** Gradient background card with spectrum top bar.
```css
background: var(--ax-gradient-thinking);
border: 1px solid var(--ax-magenta-border);
border-radius: var(--ax-radius-xl);
/* spectrum bar: absolute top, height 2px, gradient-spectrum at 60% opacity */
```

Always wrap thinking content in quotes. Use thinking context pills (see Tags) to annotate what the agent is processing.

### Buttons

**Primary CTA:**
```css
padding: 8px 16px;
border-radius: var(--ax-radius-md);
background: var(--ax-gradient-cta);
font: 500 12px var(--ax-font-body);
color: #0a0b0e;
```

**Secondary:**
```css
background: var(--ax-bg-input);
color: var(--ax-text-low);
```

**Ghost:**
```css
background: transparent;
border: 1px solid var(--ax-border-default);
color: var(--ax-text-low);
```

**Small accent:**
```css
padding: 4px 10px;
background: var(--ax-cyan-bg); /* or accent-bg */
color: var(--ax-cyan);
font: 500 10px var(--ax-font-body);
```

### Filter/Tab Buttons

Active state uses accent-bg + accent-border + accent text.
Inactive uses `--ax-bg-input` + transparent border + `--ax-text-muted`.

### Navigation Item

Sidebar navigation uses icon + label in a flex row.

```css
padding: 8px 12px;
border-radius: var(--ax-radius-md);
display: flex; align-items: center; gap: 10px;
font: 400 13px var(--ax-font-body);
/* active: bg cyan-bg, color cyan, font-weight 500 */
/* inactive: bg transparent, color text-muted */
```

Icons are 16×16 SVG, `stroke: currentColor`, `stroke-width: 1.4`, `fill: none`.

### Table

Grid-based layout inside a card. Header row with uppercase labels, data rows with hover highlight.

```css
/* Header */
font: var(--ax-type-label-sm);
color: var(--ax-text-faint);
text-transform: uppercase;
letter-spacing: var(--ax-tracking-label);
padding: 8px 0;
border-bottom: 1px solid var(--ax-border-subtle);

/* Row */
padding: 14px 0;
border-bottom: 1px solid rgba(255,255,255,.03);
cursor: pointer;
transition: background var(--ax-transition-fast);
/* hover: background rgba(255,255,255,.02) */
```

### Tags

**Flat tags** (categories): `padding: 2px 7px`, `border-radius: 3px`, `--ax-bg-input`, `--ax-type-mono-xs`, `--ax-text-faint`.

**Context pills** (thinking): `padding: 4px 10px`, `border-radius: pill`, accent-bg + accent-border, `--ax-type-mono-xs`, accent-muted text.

**Workflow chips**: `padding: 5px 10px`, `border-radius: 5px`, accent-bg + accent-bg-strong border, `--ax-type-body-xs`, accent-muted text.

### Input

```css
padding: 10px 14px;
border-radius: var(--ax-radius-md);
background: var(--ax-bg-input);
border: 1px solid var(--ax-border-input);
font: var(--ax-type-body-md);
color: var(--ax-text-primary);
outline: none;
```

Read-only display fields use the same structure but with `--ax-border-default` and `--ax-text-mid` color.

### Code/Prompt Block

```css
padding: 16px;
border-radius: var(--ax-radius-lg);
background: var(--ax-bg-elevated);
border: 1px solid var(--ax-border-subtle);
font: var(--ax-type-mono-md);
color: var(--ax-text-low);
white-space: pre-wrap;
```

### Modal

```css
/* Backdrop */
position: fixed; inset: 0;
background: var(--ax-bg-overlay);
backdrop-filter: blur(8px);
z-index: var(--ax-z-modal);

/* Container */
width: 600–960px; /* vary by content */
background: var(--ax-bg-card);
border: 1px solid var(--ax-border-strong);
border-radius: var(--ax-radius-2xl);
```

Header: display-sm title + body-sm subtitle + close button (28px square, bg-input, × glyph).
Content area: scrollable, `max-height: calc(85vh - header)`.

### Toggle

```css
/* Track */
width: 36px; height: 20px;
border-radius: var(--ax-radius-pill);
/* on: background cyan; off: rgba(255,255,255,.15) */

/* Thumb */
width: 16px; height: 16px;
border-radius: var(--ax-radius-round);
/* on: white, left 18px; off: rgba(255,255,255,.5), left 2px */
transition: left var(--ax-transition-fast);
```

### Turn Timeline (Run Detail)

Each turn type has a distinct color and container style:

| Type | Dot/Label Color | Background | Border |
|------|----------------|-----------|--------|
| system | `--ax-text-faint` | `rgba(255,255,255,.04)` | `--ax-border-default` |
| input | `--ax-cyan` | `--ax-cyan-bg` | `rgba(0,229,255,.12)` |
| thinking | `--ax-magenta` | `rgba(224,64,251,.04)` | `--ax-magenta-border` |
| tool_call | `--ax-yellow` | `rgba(255,215,64,.04)` | `rgba(255,215,64,.1)` |
| output | `--ax-green` | `rgba(105,240,174,.05)` | `--ax-green-border` |
| action | `--ax-cyan` | `--ax-cyan-bg` | `rgba(0,229,255,.12)` |
| error | `--ax-error` | `--ax-error-bg` | `--ax-error-border` |

Thinking turns use `--ax-type-thinking-md` (italic serif). All others use `--ax-type-mono-md`.

### Activity Feed

Vertical list with colored left bar:
```css
/* Bar */
width: 4px; min-height: 36px;
border-radius: 2px;
background: /* accent color matching event type */;

/* Text: body-sm, text-low */
/* Timestamp: mono-xs, text-ghost */
```

---

## Layout Patterns

### App Shell

```
┌─────────┬────────────────────────────┐
│ Sidebar │ Top Bar (56px)             │
│ (220px) ├────────────────────────────┤
│         │ Scrollable Content         │
│         │ (padding: 28px)            │
│         │                            │
└─────────┴────────────────────────────┘
```

- Sidebar: `--ax-bg-sidebar`, fixed width 220px, flex column
- Top bar: 56px height, border-bottom, page title (display-xs) + breadcrumb
- Content: flex-1, overflow-y auto, 28px padding

### Page Content

- Grid layouts: `grid-template-columns: repeat(auto-fill, minmax(Xpx, 1fr))` with 16px gap for card grids
- Two-column detail: `grid-template-columns: 1fr minmax(0, 340px)` with 20-24px gap
- Section spacing: 20-24px between cards

### Dashboard

- Filter row at top (flex, space-between)
- 4-column stat cards row
- Two-column: main content + sidebar (thinking panel + activity feed)

---

## Animations

Three standard animations defined in the tokens:

| Name | Use | Duration |
|------|-----|----------|
| `ax-fadeIn` | Page transitions, new content | 0.3s |
| `ax-slideIn` | Detail pages (slides from right) | 0.3s |
| `ax-pulse` | Idle status dots | 2s infinite |

Transitions for interactive elements use `--ax-transition-fast` (0.1s) for hover states and `--ax-transition-normal` (0.15s) for border/background changes.

---

## Gradients

| Token | Value | Use |
|-------|-------|-----|
| `--ax-gradient-brand` | `135deg, #00e5ff → #e040fb` | Logo, avatar rings |
| `--ax-gradient-cta` | `135deg, #00e5ff → #00b8d4` | Primary action buttons |
| `--ax-gradient-thinking` | `135deg, #1a1e26 → #1e1a24` | Thinking panel background |
| `--ax-gradient-spectrum` | `90deg, #e040fb → #00e5ff → #ffd740` | Thinking panel top bar accent |

---

## Icon Guidelines

- Size: 16×16 for nav/inline, 18×18 for top bar
- Style: outline stroke, `stroke-width: 1.4`, `fill: none`
- Color: `currentColor` (inherits from parent text color)
- Format: inline SVG preferred for color inheritance

---

## Do / Don't

**Do:**
- Use serif (Playfair) only for headings, stats, and thinking blocks
- Use monospace for anything technical: IDs, models, tokens, costs, code
- Put thinking text in quotes to suggest inner monologue
- Use opacity-based text colors, not distinct greys
- Keep card borders subtle; use accent borders only for special states
- Use the spectrum gradient bar only on thinking/reasoning panels

**Don't:**
- Use serif for body text, labels, or navigation
- Use color for decoration — every accent color should signal something
- Use more than 2 accent colors in a single component
- Put sharp corners on cards (always radius-xl minimum)
- Use solid white backgrounds — everything is dark
- Use shadows for elevation — use border opacity and background shifts instead
- Mix thinking italic style with non-thinking content
