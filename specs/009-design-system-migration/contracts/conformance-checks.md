# Contract: Automated Conformance Checks

Three automated checks (FR-022, FR-023, FR-024), implemented as pytest static-grep modules
under `ui/tests/`, mirroring the existing `test_secrets.py` / `secret_scan.py` pattern. Run
with `cd ui && ../.venv/bin/python -m pytest -q`. No headless browser (spec Out of Scope).

Scanned trees: `ui/templates/`, `ui/static/`, and served bundle CSS under `ui/design-system/`.
**Exempt files** (literals allowed): the token files `ui/design-system/tokens/*.css` and the
font-face/font file. Everything else is app styling and is held to the token rule.

## Check 1 — Styling hygiene (FR-022) → `test_conformance.py`

MUST **fail** when served CSS/templates (outside the exempt token + font files) contain any of:

| Violation | Grep intent |
|-----------|-------------|
| Literal colour | `#hex`, `rgb(`/`rgba(`/`hsl(`, or named colours in app CSS/templates |
| Literal pixel value | `\d+px` outside the token and font files |
| `--ax-*` token | any `--ax-` custom property definition or `var(--ax-…)` reference |
| External font/CDN URL | `googleapis`, `unpkg`, `cdn`, or any `http(s)://` font/icon/asset URL |
| Stray `font-family` | any `font-family` declared outside the font file |

MUST **pass** on the migrated tree. This check is the acceptance gate for SC-005: it fails on a
deliberately inserted literal colour, literal pixel value, and `--ax-*` token, and passes clean.

> Implementation note: allow `px` inside `@font-face`/font metrics and the token files only;
> everything else must be a `var(--…)` token. Keep the allow-list explicit and small so an
> inserted literal in an app file is always caught (Edge Case: deliberately non-conforming
> markup).

## Check 2 — Docs & manifest coverage (FR-023) → `test_design_system_docs.py` (rewritten)

Replaces the current module (which references the deleted `ARCHON-DESIGN-SYSTEM.md` and
`Archon Design System.dc.html` — currently red). New assertions:

- Parse `ui/design-system/_ds_manifest.json`; for each `components[].name`, assert a
  corresponding macro is defined in `ui/templates/components/macros.html`
  (name-mapping per [component-macros.md](./component-macros.md); `Tab` covered by `tabs`).
- Assert the project design-system docs reference the new README: `README.md` and `AGENTS.md`
  point at `ui/design-system/readme.md` as the source of truth (FR-020).
- Assert no test or served file references the retired Archon artefacts (FR-001).

## Check 3 — Class adoption in rendered pages (FR-024) → extend `test_ui_consistency.py`

Extends the existing module (which already asserts every template `<select>` carries
`ax-select` and every JS-created select is enhanced). Add:

- Every `<button>` in `ui/templates/**` carries the button design-system class (`ax-btn`), and
  every JS-created button sets it.
- Every `<table>` in `ui/templates/**` carries the table design-system class (`ax-table`).
- (Existing) every `<select>` carries `ax-select` and stays on the shared-dropdown path — keep,
  do not loosen (FR-025).

Together these satisfy SC-004: 100% of selects, buttons, and tables in rendered pages carry the
design-system class.

## Behaviour-preservation guardrails (FR-025, referenced not new)

The migration must keep the existing behaviour tests green — in particular the
`test_ui_consistency.py` dropdown-enhancement guards and any spec-002/003 form tests. These are
the regression fence for "no feature behaviour changes"; the conformance checks above are
additive.
