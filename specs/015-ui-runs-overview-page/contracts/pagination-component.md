# Contract: Pagination (design-system component + shared macro)

FR-034 and constitution Principle VII: pagination MUST land in the design system **first** and be
provided as a shared macro **before** the Runs page uses it. This contract fixes what "in the design
system" means for this repo so the conformance and design-system-sync suites pass (SC-009).

## §A — Design-system registration (first)

The component MUST exist as a first-class design-system entry, parallel to `Tabs` and `Table`:

1. **Component source** under `ui/design-system/components/navigation/` — `Pagination.jsx` plus its
   sibling `Pagination.d.ts` and `Pagination.prompt.md`, matching every other component's file set
   (`Tabs.jsx`/`Tabs.d.ts`/`Tabs.prompt.md` live in the same `navigation/` folder).
2. **A specimen** — a `pagination.card.html` in `components/navigation/` (parallel to the existing
   `tabs.card.html`) so it appears in the served gallery and thumbnail.
3. **Manifest entry** in `ui/design-system/_ds_manifest.json` under `components` (`{"name":
   "Pagination", "sourcePath": "components/navigation/Pagination.jsx"}`) and a matching
   `startingPoints` entry (section `Components`, a subtitle, a viewport) like every other component.
4. **Rebuilt bundle** `ui/design-system/_ds_bundle.js` regenerated so the manifest ↔ bundle parity
   check (`test_design_system_sync.py`) holds.
5. **Readme** `ui/design-system/readme.md` documents Pagination: purpose, anatomy (Prev · indicator
   · Next), states (first/last page disabling), and that page state lives in the URL.

The specimen pages are the *sole* place literal values are allowed (they render offline as
standalone documents — Principle VII exception); everywhere else is tokens-only.

## §B — Shared macro (second)

`ui/templates/components/macros.html` gains:

```jinja
{% macro pagination(page=1, pages=1, base_query="", attrs={}) -%}
```

| Param | Meaning |
|-------|---------|
| `page` | current 1-based page |
| `pages` | total pages (≥ 1) |
| `base_query` | current query string (tab + filters) so Prev/Next preserve view state |
| `attrs` | optional extra HTML attributes (the shared-macro convention) |

**Rendered anatomy**
- A container `<nav class="ax-pagination" aria-label="Pagination">`.
- **Prev** control — a shared-button-styled link/button to `?{base_query}&page={page-1}`; disabled
  (and non-navigating) on page 1.
- A **page indicator** — `Page {page} of {pages}` (text only).
- **Next** control — to `?{base_query}&page={page+1}`; disabled on the last page.

**Rules**
- Composed from the shared button treatment / tokens only — no literal colours, pixel values, or
  `font-family`; no inline `style` (Principle VII; enforced by `test_conformance.py`).
- Works **without JavaScript**: Prev/Next are real links carrying the preserved query so a copied URL
  restores the page (SC-004, US5 AC3). `runs-list.js` MAY enhance them (intercept + `history` sync)
  but MUST NOT be required for correctness.
- On page 1 the Prev control is `aria-disabled`/non-focusable-target; on the last page the Next
  control likewise — never a dead link that navigates nowhere.
- `pages` is always ≥ 1 (a zero-result set is 1 page showing the empty state; pagination MAY be
  hidden when `pages == 1`).

## §C — Styling

`.ax-pagination` and its parts are styled in `ui/static/app.css` using design-system tokens only
(colour, spacing, radius from `var(--…)`). The indigo/accent treatment for the active/hover control
uses the same accent ramp the design system already exposes. No new token is required; if one were,
it would be added to the token stylesheets first.

## §D — Conformance obligations (must stay green)

- `ui/tests/test_conformance.py` — no literal colours/pixels/`font-family`, no inline styles, controls
  macro-composed (covers the new macro + its use on `/runs`).
- `ui/tests/test_design_system_docs.py` — the readme documents the component.
- `ui/tests/test_design_system_sync.py` — manifest ↔ bundle ↔ macro parity includes Pagination.

A new component that skips any of §A steps fails these suites; that is the design-system-first gate
made executable.
