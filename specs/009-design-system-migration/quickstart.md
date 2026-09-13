# Quickstart & Validation: Design System Migration

Runnable validation that proves the migration meets its spec. Details live in
[data-model.md](./data-model.md) and [contracts/](./contracts/); this is the run guide.

## Prerequisites

- Project virtualenv at `.venv/` (Python 3.12) with `ui/requirements.txt` installed — see
  `CLAUDE.local.md` "Running the UI tests". Do not recreate it if present.
- Run all commands from the repo root unless noted.

## 1. Automated checks (fastest gate)

```bash
cd ui && ../.venv/bin/python -m pytest -q
```

Expected after migration:
- **`test_conformance.py`** passes on the clean tree (FR-022 / SC-005).
- **`test_design_system_docs.py`** (rewritten) passes: every manifest component has a macro;
  README/AGENTS.md reference `ui/design-system/readme.md` (FR-023).
- **`test_ui_consistency.py`** passes: every select/button/table carries its design-system
  class; the spec-002 dropdown enhancement guards still hold (FR-024, FR-025).
- All pre-existing suites stay green (behaviour preserved — SC-006).

**Negative test for SC-005** — the checks must catch non-conformance:

```bash
# Insert a literal colour, a literal px, and an --ax-* token into an app CSS/template file,
# then re-run pytest and confirm test_conformance.py FAILS; revert and confirm it PASSES.
cd ui && ../.venv/bin/python -m pytest test_conformance.py -q
```

## 2. Static egress grep (SC-003)

```bash
# No served CSS/HTML/JS references an external font/icon/asset host.
grep -rEn 'googleapis|unpkg|cdn|https?://[^ "'\'')]*\.(woff2?|ttf|otf|css|svg|png)' \
  ui/templates ui/static ui/design-system/tokens ui/design-system/styles.css \
  && echo "FAIL: external URL found" || echo "PASS: no external asset URL"
```

Expected: `PASS`. In particular the Google-Fonts `@import` is gone from
`ui/design-system/tokens/typography.css` and no `unpkg` Lucide reference remains.

## 3. Run the app and walk the pages (SC-001, SC-002, SC-008)

Start the UI (per project run instructions / `ui/Dockerfile`, or a scratch uvicorn — see the
`ui-browser-verification-on-host` memory for the headless driver). Then, for each existing page
— agents list, agent create/edit form, automation list, 404:

1. **Both themes render** (SC-001): load with OS dark → dark theme, no wrong-theme flash;
   toggle Light/Dark/System in the sidebar foot → switches with no reload; reload → choice
   persisted (SC-008). Set preference = System, flip OS theme → UI follows live, no flash.
2. **Sibling of Dagster** (SC-002): side-by-side with Dagster (:3000) in dark — sidebar width,
   font, surface/border gray scale, and status red/yellow/green match; only the accent differs.
3. **No Archon remnants** (SC-001): inspect rendered CSS — no `--ax-*` token resolves, no
   serif (Playfair) font loads.
4. **Sidebar collapse** (SC-008): collapse to narrow and back; state persists across navigation
   and reload.

## 4. Component & form behaviour (SC-004, SC-006)

1. Inspect markup on each page: every `<select>`, `<button>`, `<table>` carries its
   design-system class; no page defines its own button/card styling (US2).
2. On the agent form, exercise the spec-002 dropdown by keyboard (open, arrow, select, Escape)
   — behaviour matches pre-migration (FR-025). Submit with an invalid field — the validation
   error renders through the shared component styling.
3. Confirm the retired magenta is gone: queued status shows the gray badge, template/scheduled
   shows the lime badge (FR-014).

## 5. Design system in repo, skill, and docs (SC-007)

1. Open `/design-system` in the app → the developer reference app is served (not the old Archon
   doc) (FR-003).
2. In a Claude Code session in the repo, list skills → the design skill appears and points at
   `ui/design-system/readme.md` (FR-019). Ask it to add a card → produced markup uses the
   shared `card` macro (SC-007).
3. Read `README.md`, `AGENTS.md`, and `.specify/memory/constitution.md` → all describe the new
   design-system location and the "sibling of Dagster / use tokens and macros" rule, and the
   constitution has the new **Design** principle (FR-020, FR-021).

## 6. Accessibility (SC-009)

Check text and interactive-UI colour contrast on every existing page in **both** themes against
WCAG 2.1 AA (e.g. a contrast checker on the resolved token values). All pairs meet AA (FR-026).

## 7. Manual pre-release: offline render (SC-003)

Block egress on the box and reload every page: fonts and icons still render (self-hosted /
system fallback + local sprite) and no outbound request is issued. This runtime check stays
manual by design (spec Out of Scope); the automated gate is step 2.
