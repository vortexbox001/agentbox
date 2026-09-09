# Research: Design System Compliance

Decisions that resolve the open technical questions before design. Each records what was chosen, why, and what was rejected.

## R1. Custom dropdown: enhance the native `<select>` rather than replace it

**Decision**: Build the custom dropdown as a progressive enhancement. Keep every existing `<select class="ax-select">` in the DOM as the value store and event source, hide it visually, and layer a scripted trigger + listbox panel over it. A new module `ui/static/dropdown.js` exports `enhanceSelect(select)`; it reads the select's options to build the panel, and on choice sets `select.value` and dispatches a native `change` event.

**Rationale**: `agent-form.js` already wires all form behavior to select `change` events — the harness switch that shows/hides fields, the network mismatch warning, the template pre-fill, the prompt picker's "Create new prompt…" reveal, and value collection for save. Driving a hidden native select keeps all of that working untouched (FR-003, FR-005), preserves the browser's form semantics and validation hooks (`aria-invalid` already set on the select for FR-006), and leaves a working control if scripting fails. It also keeps the change surface small: the render functions keep producing selects; only a post-render enhancement pass is added.

**Alternatives considered**:
- *Fully custom widget replacing selects*: rejected — it would require rewriting every render/collect/validate path in `agent-form.js` and re-implementing form-value semantics, for no visible benefit over enhancement.
- *CSS-only restyle of the native select's popup*: rejected — browsers do not allow styling the native option list, so it cannot match the reference's panel (elevated card, accent-highlighted selection). The reference explicitly ships a scripted "Custom Dropdown (open)" component for this reason.

## R2. Accessibility pattern for the custom dropdown

**Decision**: Implement the WAI-ARIA collapsible listbox pattern on the trigger: `role="combobox"` (or a button) with `aria-haspopup="listbox"`, `aria-expanded`, and a panel of `role="option"` items with `aria-selected`, tracked by `aria-activedescendant`. Keyboard: Enter/Space/ArrowDown opens; ArrowUp/ArrowDown move the active option; Home/End jump; Enter/Space chooses; Escape closes without change; Tab closes and moves on; printable keys do type-ahead. The trigger carries the field's label association so screen readers announce it.

**Rationale**: Replacing a native select removes the keyboard and assistive-technology support the browser gave for free; FR-004 requires restoring it. The listbox pattern is the standard, and the hidden native select remains as a semantic backstop.

**Alternatives considered**: mouse-only custom dropdown (rejected — fails FR-004 and regresses accessibility); relying solely on the hidden select for keyboard (rejected — focus is on the visible trigger, so keys must be handled there).

## R3. Dropdown panel placement and clipping

**Decision**: Position the panel absolutely relative to a wrapping element around the trigger, opening downward by default and flipping upward when there is not enough space below the trigger within the viewport. Ensure the form section cards do not clip it (they use default visible overflow). Constrain the panel to a max height with internal scroll for long lists (model, prompt).

**Rationale**: Handles the edge cases in the spec — long option lists, and a dropdown near the bottom of a scrolling form must not be clipped. Keeping the panel inside a positioned wrapper (rather than portaling to `document.body`) avoids reposition-on-scroll bookkeeping while the cards' visible overflow prevents clipping.

**Alternatives considered**: portal to `body` with fixed positioning (rejected — needs scroll/resize reposition logic for little gain at this scale); no flip (rejected — clips near the viewport bottom).

## R4. Toggle correction — colors and sizes both, mapped to tokens

**Decision**: Correct `.ax-toggle` in `app.css` so both states match the reference, using only tokens:

| Part | State | Reference value | Token to use |
|---|---|---|---|
| Track bg | on | solid cyan | `--ax-cyan` |
| Track bg | off | `rgba(255,255,255,.15)` | `--ax-border-strong` (`rgba(255,255,255,.1)`, nearest existing token) |
| Thumb bg | on | white | `--ax-text-primary` |
| Thumb bg | off | `rgba(255,255,255,.5)` | `--ax-text-low` (exact match) |
| Track size | — | 36 × 20 | width `calc(var(--ax-space-9) + var(--ax-space-8))` = 36; height `var(--ax-space-9)` = 20 |
| Thumb size | — | 16 × 16 | `var(--ax-space-8)` = 16 |
| Thumb inset | — | 2px | `var(--ax-space-1)` = 2 |
| Thumb travel | on | left 2 → 18 (16px) | `translateX(var(--ax-space-8))` = 16 |
| Transition | — | `transition-fast` | `var(--ax-transition-fast)` |

**Rationale**: The current implementation is wrong on more than color: its on-track uses translucent `--ax-cyan-bg-strong` instead of solid cyan, its thumb is cyan instead of white, its off-thumb is `--ax-text-mid` (.7) not `--ax-text-low` (.5), its track width is `--ax-space-13` (40px) not 36px, and its thumb is `--ax-space-7` (14px) not 16px. Fixing all of it is what "render as spec'ed" means (FR-007, FR-008, FR-009). Token math (`calc`) reaches the reference's 36px and 16px without literals, honoring token discipline (FR-014).

**Off-track token choice**: no token equals `rgba(255,255,255,.15)`; the candidates are `--ax-border-strong` (.1) and `--ax-text-ghost` (.2). `--ax-border-strong` is chosen — it is already the neutral surface/border token and reads as a subtle pill. The ~0.05 alpha difference is below the threshold of a visible defect, and introducing a new literal or editing the user-owned token file is out of scope. Recorded as the one place the reference uses a value with no exact token.

**Alternatives considered**: editing `archon-tokens.css` to add a `.15` token (rejected — the token file is design-system source the requester maintains; not modified by this feature); keeping literals for the off state (rejected — violates token discipline).

## R5. `ax-grid-form` application and wide fields

**Decision**: Add `.ax-grid-form { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--ax-space-10); }` (space-10 = 24px). In `agent-form.js`, wrap each section's fields in an `.ax-grid-form` container inside the section card. Fields whose control is intrinsically wide — the env map editor, list/chip editors, the append-system-prompt textarea, and the prompt picker's "create" panel — get a `.ax-field--wide { grid-column: 1 / -1; }` modifier so they span the full row rather than being squeezed into one column.

**Rationale**: Matches the reference's `ax-grid-form` (280px min, 24px gap) that its own guide assigns to agent-config forms. The wide-field span keeps multi-line and repeating controls readable, following the reference's "stack, don't squeeze" grid rule. This applies to create, edit, and detail because they share `form.html` and `renderForm`.

**Alternatives considered**: forcing every field into the grid uniformly (rejected — a map/list/textarea in a 280px column is cramped); a separate media-query layout (rejected — the reference uses intrinsic `auto-fill`, no breakpoints).

## R6. Correction to spec FR-012a — no card-grid surface exists

**Decision**: This feature applies `ax-grid-form` to the forms and does **not** introduce `ax-grid-cards`. The agents list is a `<table>` (`ax-table`) and stays one; the template picker is a `<select>` that becomes a custom dropdown under User Story 1. No screen in the built UI is a card grid.

**Rationale**: FR-012a assumed the agents list and template picker use `ax-grid-cards`. In the actual code they are a table and a select, and `ax-grid-cards` appears nowhere. The reference's own grid rules say "tables stay grid-based," so the table is already compliant. Forcing the list into a card grid was not requested and would be scope creep. `/speckit-tasks` should treat FR-012a as satisfied by leaving the table as-is and converting the template picker via US1, not by adding a card grid.

**Alternatives considered**: converting the agents list to an `ax-grid-cards` card grid (rejected — not requested, larger change, and a table is the reference-endorsed form for tabular data).

## R7. Testing approach for a JS-heavy, visual feature

**Decision**: Keep feature 001's split. Automated `pytest` covers everything statically checkable:
- Token discipline unchanged (existing `test_no_literal_colours_or_fonts`, which also scans `app.css`).
- The corrected toggle: assert `app.css` maps the on-track to `--ax-cyan`, the on-thumb to `--ax-text-primary`, and the off-thumb to `--ax-text-low`.
- The grid: assert `.ax-grid-form` exists with `auto-fill` and `minmax(280px`.
- Backing selects: assert the rendered create form still contains `<select` controls (the enhancement is additive) and that `dropdown.js` is loaded.
- Doc accuracy (Constitution VI): assert `ARCHON-DESIGN-SYSTEM.md` documents each named grid pattern and a dropdown/select component.

Interactive and visual fidelity — dropdown open/select/keyboard/dismiss, panel placement, toggle appearance, grid reflow — is verified with the quickstart browser checklist. There is no browser-automation harness in this repo and adding one (node/jsdom/Playwright) is out of scope.

**Rationale**: Matches the existing repo capability and constitution preference for automated verification where feasible, without importing a new toolchain for one feature.

**Alternatives considered**: adding Playwright/jsdom (rejected — new toolchain and CI surface for a small feature); asserting nothing and relying only on manual checks (rejected — the constitution prefers automated verification, and the toggle/grid/doc claims are statically checkable).

## R8. `ARCHON-DESIGN-SYSTEM.md` gap

**Decision**: Add a "Select / Dropdown" component section documenting both variants the reference now ships — the native select styling (appearance-none plus custom chevron, `bg-input`) and the custom dropdown component (elevated `bg-card` panel, `border-strong`, `shadow-lg`, accent-highlighted selected option, `radius-sm` items). Verify the existing Toggle and Layout/Grid sections already match the reference (they do: the guide's toggle spec is the correct on=cyan/white, off=.15/.5 target, and the grid table already lists `ax-grid-cards`/`ax-grid-form`), and leave them unless a mismatch is found.

**Rationale**: The guide currently has no dropdown/select section at all, while the reference canvas defines two dropdown variants — that is the concrete "out of date" gap (FR-013). The toggle and grid entries are already accurate, so US4 is mostly the missing dropdown documentation.

**Alternatives considered**: rewriting the whole guide (rejected — unnecessary; only the dropdown section is missing).
