# Contract: Shared Component Macros

Every design-system component in `ui/design-system/_ds_manifest.json` has one shared Jinja2
macro in `ui/templates/components/macros.html`. Each macro's parameters mirror the bundle's
component contract (`.d.ts`), re-expressed for server-rendered markup (event props like
`onClick`/`onChange` are dropped; the macro emits the markup + design-system class, and
existing JS wires behaviour). Pages compose these macros only (FR-006).

## Manifest ⇄ macro coverage (FR-004, FR-023)

Thirteen macros, one per manifest component (`Tab` is part of `Tabs`):

| Manifest component | Macro | Emitted design-system class (root) | Source contract |
|--------------------|-------|-----------------------------------|-----------------|
| Button | `button` | `ax-btn` (+ intent/outlined modifiers) | `components/buttons/Button.d.ts` |
| TextInput | `text_input` | `ax-input` | `components/forms/TextInput.d.ts` |
| Select | `select` | `ax-select` (spec-002 dropdown path) | `components/forms/Select.d.ts` |
| Checkbox | `checkbox` | `ax-checkbox` | `components/forms/Checkbox.d.ts` |
| Toggle | `toggle` | `ax-toggle` | `components/forms/Toggle.d.ts` |
| Badge | `badge` | `ax-badge` (+ intent modifier) | `components/feedback/Badge.d.ts` |
| StatusDot | `status_dot` | `ax-status-dot` | `components/feedback/StatusDot.d.ts` |
| Alert | `alert` | `ax-alert` (+ intent) | `components/feedback/Alert.d.ts` |
| Spinner | `spinner` | `ax-spinner` | `components/feedback/Spinner.d.ts` |
| Tabs | `tabs` | `ax-tabs` | `components/navigation/Tabs.d.ts` |
| Card | `card` | `ax-card` | `components/layout/Card.d.ts` |
| Dialog | `dialog` | `ax-dialog` | `components/layout/Dialog.d.ts` |
| Table | `table` | `ax-table` | `components/data/Table.d.ts` |

> Class names keep the `ax-` prefix as a namespace only — they carry **new-token** styling.
> This is deliberate: existing behavioural JS (`dropdown.js`, `shell.js`) and the
> `test_ui_consistency.py` `ax-select` guard already key off these classes, so keeping the
> prefix preserves behaviour (FR-025) while the *styling* migrates. The prohibition is on
> `--ax-*` **tokens** (FR-008), not on the class namespace.

**Check**: `test_design_system_docs.py` (rewritten) parses `_ds_manifest.json` and asserts
each listed component name has a corresponding macro defined in `macros.html` (FR-023). It
also asserts the design-system docs (README/AGENTS.md) reference `ui/design-system/readme.md`.

## Macro parameter contracts (mirror the `.d.ts`)

Parameters that mirror the React contract; visual/behaviour props map to markup + class.

### `button` (Button.d.ts)
- `label` (children), `intent` ∈ {primary, danger, success, warning} (default primary),
  `outlined` (bool), `disabled` (bool), `loading` (bool → shows `spinner`), `icon`,
  `right_icon`, `type` (submit|button), `attrs` (extra HTML attrs).
- Emits `<button class="ax-btn ax-btn--{intent}[ ax-btn--outlined]">`.

### `text_input` (TextInput.d.ts)
- `label`, `name`, `value`, `placeholder`, `disabled`, `invalid` (bool → validation error
  state, FR-025), `attrs`. Emits `<input class="ax-input">` with optional label + error slot.

### `select` (Select.d.ts) — spec-002 dropdown, behaviour frozen
- `label`, `name`, `value`, `options` (list of `str` or `{value,label}`), `disabled`, `attrs`.
- Emits `<select class="ax-select">…`; page/module still calls `dropdown.enhanceSelect()`
  (FR-025; guarded by `test_ui_consistency.py`).

### `checkbox` (Checkbox.d.ts)
- `label`, `name`, `checked`, `disabled`. Emits `class="ax-checkbox"`, teal-checked.

### `toggle` (Toggle.d.ts)
- `label`, `name`, `checked`, `disabled`. Emits `class="ax-toggle"`, teal active.

### `badge` (Badge.d.ts)
- `label` (required), `intent` ∈ {running, success, error, warning, queued, scheduled,
  default, primary, lime} (default `default`). Retired magenta maps here: queued→`queued`
  (gray), template/scheduled→`scheduled` (lime) (FR-014).

### `status_dot` (StatusDot.d.ts)
- `state` (status), `label` (a11y). Colored dot from status tokens.

### `alert` (Alert.d.ts)
- `intent` ∈ {info, warning, error(, success)}, `title`, `message`/children.

### `spinner` (Spinner.d.ts)
- `size` (optional). Loading spinner; used by `button loading`.

### `tabs` (Tabs.d.ts)
- `tabs` (list of `{id,label}`), `active`. Bottom-border indicator (Dagster style).

### `card` (Card.d.ts)
- `title` (optional), body (caller block). Border, no shadow (readme Cards).

### `dialog` (Dialog.d.ts)
- `title`, body, actions. Modal + backdrop blur; renders into the existing modal root.

### `table` (Table.d.ts)
- `columns`, `rows` (or caller-composed header/body blocks). Grid-based header + rows.

## Composition rules (FR-006, FR-024)

- No page template defines its own button, card, select, or table styling — it calls the macro.
- Every `<select>`, `<button>`, and `<table>` in rendered pages carries its design-system class
  (verified by `test_ui_consistency.py`, extended per FR-024).
- The agent form (`agents/form.html` + `agent-form.js`) renders every select, toggle,
  checkbox, input, and button through these macros/classes, preserving keyboard navigation and
  validation error states (FR-002 US2, FR-025).
