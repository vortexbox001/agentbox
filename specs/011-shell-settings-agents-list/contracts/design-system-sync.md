# Contract: Design-system sync, macro extensions, icons, no-inline-styles

Covers FR-023–027, US5, SC-006/SC-007. Brings the served shared assets level with their
design-system copies and prevents future drift, extends the shared macros per the mocks, and
keeps the tree free of inline styles and external URLs.

## A. Sync test — `ui/tests/test_design_system_sync.py` (FR-024, SC-006)

Compares each served shared asset to its `ui/design-system/static/` sibling and **fails on any
divergence beyond one documented substitution**:

| Served | Design-system copy |
|--------|--------------------|
| `ui/static/app.css` | `ui/design-system/static/app.css` |
| `ui/static/dropdown.js` | `ui/design-system/static/dropdown.js` |
| `ui/static/icons.svg` | `ui/design-system/static/icons.svg` |

- **The one documented substitution** is the icon-href form: served copies resolve icons by
  document-relative `#id`; the test applies a single named normalisation (a module constant with
  a comment — e.g. strip a `/static/icons.svg` prefix from `href`) and then requires
  byte-equality. Any other difference fails.
- **Negative gate (SC-006):** editing a design-system copy without its served counterpart MUST
  fail this test. The copies are currently ahead (`app.css` 944 vs 850, `dropdown.js` 403 vs
  344); the FR-023 work brings the served copies level so the test passes on the new tree.

## B. Icon sprite (FR-023, SC-007, research R3)

- **Inline the sprite once in `base.html`** and make every `<use href>` **document-relative**
  (`#id`), replacing the current `/static/icons.svg#id` absolute refs in `base.html` and
  `dropdown.js` (the "one recorded mechanism").
- **Add the missing icons:** `filter`, `settings`, `check-circle`, `warn-tri`, `x-circle`,
  `overview`, `runs`, plus `clock`, `sensor`, `search`.
- Everything renders with egress blocked; `test_no_external_urls` (in `test_conformance.py`)
  still passes and the /design-system gallery stays external-asset-free (SC-007).

## C. Macro extensions — `ui/templates/components/macros.html` (FR-025)

No new manifest component (Dropdown is a form of Select). Extend three existing macros; keep
their current signatures back-compatible:

- **`schedule_pill(type, label, on, name, id, attrs)`** — gains the **type-driven icon**: clock
  for `type="schedule"` (job), sensor for `type="asset"`/asset schedule. Icon by `#id`.
- **`select(name, value, options, disabled, id, attrs)`** — options pass through a **per-option
  icon**, a **trailing note**, and **sticky filter-row** data, so the same macro backs the
  theme dropdown's iconed options and any filter-in-panel affordance.
- **`tabs(items, active, attrs)`** — renders a **tab count** (`items[].count`) next to each
  label. (The macro already accepts `count?`; ensure it renders the `.ax-tab-count` span.)

The manifest⇄macro test (`test_design_system_docs.py`) MUST still pass (the component set is
unchanged).

## D. No inline styles + conformance (FR-026, Constitution VII, SC-006)

- Every placeholder the mocks express as inline style (em-dash cell colour, mono link colour,
  dropdown list reset, the mock's `style="…"` attributes) MUST become **token-based classes** in
  `app.css`. Served templates carry **no** inline `style` attribute and **no** `<style>` block.
- `test_conformance.py` continues to enforce this: `test_no_inline_styles_in_app_templates`,
  `test_no_literal_*`, `test_no_named_colours_in_css`, `test_no_stray_font_family`,
  `test_no_external_urls` all pass on the new tree and still fail on an inserted literal /
  inline style / external URL (SC-006 negative gate).
- **Theme-accessibility assertion moves** to the modal theme dropdown: repoint
  `test_theme_control_is_accessible_icon_buttons` (in `test_ui_consistency.py`) from the removed
  foot radiogroup to the modal dropdown (`role="listbox"`/`role="option"`, labelled, iconed
  options) (FR-003, SC-006).
- DS-class conformance (`test_ui_consistency.py`) extends to the new list: tabs, toolbar
  buttons, checkbox, table, and pills carry their design-system classes.

## E. Automation removal (FR-022)

Remove `templates/automation/list.html`, `static/automation.js`, `automation_store.py`, the
`GET /automation` + `GET/PUT /api/automation` routes and their imports in `main.py`, the nav
item in `base.html`, `test_automation_store.py`, `test_migrate_automation.py`, and the two
automation assertions in `test_ui_consistency.py`. **Keep** the `schedule_pill` macro and the
schema `asset_schedule`/`job_schedule` fields (shared with the agent form and the new list).

## F. Docs (FR-027)

`README.md` gains short sections for: the tabbed list view, the settings modal, the foot links,
and the indigo Dagster accent. `README.md`/`AGENTS.md` continue to name
`ui/design-system/readme.md` as the source of truth (`test_design_system_docs.py`).
