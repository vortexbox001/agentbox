---
name: agentbox-design
description: Use this skill to generate well-branded interfaces and assets for AgentBox, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

The AgentBox design system lives in the repo at `ui/design-system/`, and it is the
single source of truth for how the management UI looks and behaves.

1. **Read `ui/design-system/readme.md` first** — it documents the brand, colour system,
   typography, spacing, layout (240px sidebar sharing the content ground, no top bar),
   and the component set. Then explore the rest of the bundle: `ui/design-system/tokens/*.css`
   (the machine-readable tokens), `ui/design-system/guidelines/` (specimen cards), and
   `ui/design-system/_ds_manifest.json` (the component manifest).

2. **In the running management UI, style through the shared layer, never with literals.**
   - Every colour, spacing, type, radius, shadow, and transition resolves from a
     `var(--…)` token defined under `ui/design-system/tokens/*.css`. No literal hex/rgb/hsl
     colours, no literal `px`, no `font-family`, and no `--ax-*` custom properties in
     `ui/templates/**`, `ui/static/**`, or the served bundle CSS.
   - Every control is rendered from the shared Jinja2 macros in
     `ui/templates/components/macros.html` — `button`, `text_input`, `select`, `checkbox`,
     `toggle`, `badge`, `status_dot`, `alert`, `spinner`, `tabs`, `card`, `dialog`, `table`.
     Do not hand-roll button/card/table markup or bespoke control styling. For example, to
     add a card, `{% from "components/macros.html" import card %}` and call the `card` macro
     rather than writing a `<div class="...">` by hand.
   - New components land in the design system (`ui/design-system/`) first and the shared
     macro set (`ui/templates/components/macros.html`) second.

3. **For throwaway visual artifacts** (slides, mocks, prototypes), copy assets out of
   `ui/design-system/assets/` and the token stylesheets and build static HTML files for the
   user to view. For production code, follow the token + macro rules above.

If the user invokes this skill without further guidance, ask them what they want to build or
design, ask a few clarifying questions, and act as an expert designer who outputs HTML
artifacts _or_ production code, depending on the need.
