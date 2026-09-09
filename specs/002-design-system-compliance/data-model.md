# Data Model: Design System Compliance

This feature adds no persistent data. The "entities" are UI components and their states/attributes. This model defines each component's parts, states, and the fields it applies to, so the contract and tasks are unambiguous.

## Custom dropdown

Enhances a native `<select>`; the select remains the source of truth.

**Parts**
- **Backing select**: the original `<select class="ax-select">`, visually hidden but present in the DOM and focusable-by-proxy. Holds the value; emits `change`.
- **Trigger**: a button-like element showing the current option's label and a chevron.
- **Panel**: an elevated list of options shown when open.
- **Option**: one row per `<option>`, carrying its value and label.

**States**
- `closed` (default) / `open`.
- `selected option`: mirrors `select.value`.
- `active option`: the keyboard-highlighted row while open (may differ from selected until chosen).
- `disabled`: when the backing select is disabled (e.g., read-only screens) — not rendered as interactive.
- `error`: when the backing select has `aria-invalid="true"`, the trigger shows the error border.

**Transitions**
- open → choose option → set `select.value`, dispatch `change`, close, move focus to trigger.
- open → Escape / outside click / blur → close, value unchanged.
- backing `select.value` changed programmatically (harness switch, template pre-fill) → trigger label re-syncs.

**Applies to** (every `<select class="ax-select">` the forms render):
- `harness` (harness picker, with description + image meta)
- `effort`, `permission_mode`, `network`, and any other enum field
- `model` (the alias/custom select portion)
- `prompt_file` (prompt picker, including the trailing "Create new prompt…" entry)
- the create form's `Start from template` select

## Toggle

A pill switch bound to a checkbox `<input type="checkbox">` inside a `.ax-toggle` label.

**Parts**: hidden checkbox (value), `.ax-toggle-track` (pill), `::after` thumb, text label.

**States**
- `off`: track `--ax-border-strong`, thumb `--ax-text-low` at left inset.
- `on`: track `--ax-cyan`, thumb `--ax-text-primary` at right (translated by one thumb width).
- transition on the thumb position and colors uses `--ax-transition-fast`.

**Geometry** (token-only): track 36×20 (`calc(space-9 + space-8)` × `space-9`), thumb 16 (`space-8`), inset 2 (`space-1`), travel 16 (`translateX(space-8)`).

**Applies to**: the `enabled` field toggle and the "Reload Dagster after saving" toggle.

## Form grid (`ax-grid-form`)

A responsive grid wrapping the fields inside each form section card.

**Attributes**: `display: grid`; `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`; `gap: var(--ax-space-10)` (24px).

**Cell**: one `.ax-field` (label + control + help + error). A `.ax-field--wide` cell spans the full row (`grid-column: 1 / -1`) for intrinsically wide controls: `env` (map), `allowed_tools`/`disallowed_tools` (list), `append_system_prompt` (textarea), and the prompt picker's create panel.

**Responsive**: columns collapse 1→N intrinsically by container width; single column at the narrowest widths; the page never scrolls horizontally.

**Applies to**: the field container in each section of `form.html` on the create, edit, and detail screens (shared `renderForm`).

## Card grid (`ax-grid-cards`) — reference only, not applied

Defined in the reference (auto-fill, `minmax(240px, 1fr)`, 16px gap) for grids of cards. No screen in the built UI is a card grid (the agents list is a table; the template picker is a dropdown), so this feature does not apply it. Documented here to record the deliberate non-use (see research R6).

## Design-system guide (`ARCHON-DESIGN-SYSTEM.md`)

Human-readable description of the reference. Must gain a Select/Dropdown component section (both native and custom variants) and keep its Toggle and Grid sections accurate against the reference files.
