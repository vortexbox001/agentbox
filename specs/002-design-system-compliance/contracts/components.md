# UI Component Contracts: Design System Compliance

The interfaces this feature exposes are UI components, not HTTP endpoints. Each contract fixes the structure, tokens, states, and behavior an implementation must satisfy, and is what the quickstart checks against. All colors, fonts, spaces, and radii are `--ax-*` tokens; no literals (FR-014).

## 1. Custom dropdown (`enhanceSelect`)

**Module**: `ui/static/dropdown.js`, exporting `enhanceSelect(selectEl)`. Called by `agent-form.js` for every `<select class="ax-select">` after each render, and for the static template select on load. Idempotent: enhancing an already-enhanced select is a no-op.

**Structure produced** (around the untouched backing `<select>`, which becomes visually hidden):

```
.ax-dropdown                      (wrapper, position: relative)
  button.ax-dropdown-trigger      (aria-haspopup="listbox", aria-expanded, labelled by the field label)
    span.ax-dropdown-value        (current option label)
    svg chevron                   (aria-hidden)
  ul.ax-dropdown-panel[role=listbox]   (hidden unless open)
    li.ax-dropdown-option[role=option][aria-selected]  (one per <option>)
  <select ...>                    (hidden; value store; still dispatches change)
```

**Styling contract** (from the reference "Custom Dropdown (open)"):
- Trigger: `bg-input`, `border-input`, `radius-md`, body text; open state border `--ax-cyan-border`; error state (backing `aria-invalid="true"`) border `--ax-error`.
- Panel: `bg-card`, `border-strong`, `radius-lg`, `shadow-lg`, `z-index: var(--ax-z-dropdown)`, small inner padding; max-height with `overflow-y:auto` for long lists.
- Option: `radius-sm`, body text; selected option `--ax-cyan-bg` background with `--ax-cyan` text; unselected `--ax-text-mid`; hover/active `--ax-bg-card-hover`.

**Behavioral contract**:
- Opening shows the panel with the selected option marked; closing hides it.
- Choosing an option sets `select.value`, dispatches a bubbling `change`, closes, and returns focus to the trigger.
- Escape, outside click, and blur close without changing the value.
- Keyboard: Enter/Space/ArrowDown open; ArrowUp/ArrowDown/Home/End move the active option; Enter/Space choose; Escape closes; printable keys type-ahead; Tab closes and moves on.
- Programmatic `select.value` changes (harness switch, template pre-fill, "Create new prompt…" reveal) re-sync the trigger label; a re-render re-enhances the fresh selects.
- A disabled backing select renders a non-interactive trigger (no panel).

**Preservation contract**: the harness switch, network mismatch warning, template pre-fill, prompt-create reveal, validation error display, and save collection all behave exactly as before, because they still act on the backing select and its `change` event (FR-003, FR-005, FR-006).

## 2. Toggle (`.ax-toggle`)

**Structure** (unchanged from today): `label.ax-toggle > input[type=checkbox] + span.ax-toggle-track + span(text)`; the thumb is the track's `::after`.

**Rendering contract** (tokens only):

| Property | Off | On |
|---|---|---|
| Track background | `--ax-border-strong` | `--ax-cyan` |
| Thumb background | `--ax-text-low` | `--ax-text-primary` |
| Thumb position | left inset `--ax-space-1` | translated `translateX(var(--ax-space-8))` |

Geometry: track width `calc(var(--ax-space-9) + var(--ax-space-8))` (36px), height `var(--ax-space-9)` (20px), `radius-pill`; thumb `var(--ax-space-8)` square, `radius-round`, margin `var(--ax-space-1)`; thumb transition `left`/`transform` and background over `var(--ax-transition-fast)`.

**Behavioral contract**: toggling animates the thumb between positions and swaps track+thumb colors to the target state.

## 3. Form grid (`.ax-grid-form`)

**Contract**:
```
.ax-grid-form { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--ax-space-10); }
.ax-field--wide { grid-column: 1 / -1; }
```
Applied to the field container within each section card on the create, edit, and detail screens. Wide controls (`env` map, `allowed_tools`/`disallowed_tools` lists, `append_system_prompt` textarea, prompt-create panel) carry `.ax-field--wide`. Columns reflow intrinsically; single column at narrow widths; no horizontal page scroll.

## 4. Untouched surfaces

- The agents list stays a `<table class="ax-table">` ("tables stay grid-based").
- No `ax-grid-cards` surface is introduced (research R6).
- No change to any HTTP route, request/response shape, YAML output, validation, or secret handling (FR-015).

## 5. Design-guide contract (`ARCHON-DESIGN-SYSTEM.md`)

Must document, matching the reference files: a Select/Dropdown component (native styled select and the custom dropdown component) with its tokens and states; the Toggle on/off spec; and every named grid pattern (`ax-grid-stats`, `ax-grid-cards`, `ax-grid-cards-lg`, `ax-grid-detail`, `ax-grid-split`, `ax-grid-form`) with its column rule and gap. No claim may contradict the reference.
