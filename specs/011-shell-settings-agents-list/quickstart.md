# Quickstart: Validating the shell, settings modal, and tabbed agents list

Runnable validation scenarios that prove the feature end-to-end, one per user story plus the
offline/GraphQL success criteria. Details of shapes and behaviour live in `contracts/` and
`data-model.md`; this is the run guide.

## Prerequisites

- Project `.venv/` (Python 3.12) present with `ui/requirements.txt` installed (see
  `CLAUDE.local.md`). If missing:
  `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r ui/requirements.txt`.
- Tests: `cd ui && ../.venv/bin/python -m pytest -q`.
- For live browser checks: the served UI running against the example config, and a Dagster
  webserver (reachable and, separately, stopped) to exercise the degradation paths. The test
  suite's `dagster_stub` fixture fakes Dagster for endpoint tests without a live server.

## Automated gate

```bash
cd ui && ../.venv/bin/python -m pytest -q
```

Expected: green, including the new `test_design_system_sync.py`, the extended
`test_conformance.py` / `test_ui_consistency.py`, and activity/toggle coverage in
`test_api.py`; the removed Automation tests are gone. Then confirm the **negative gates**:

- Edit `ui/design-system/static/app.css` without editing `ui/static/app.css` → the sync test
  fails (SC-006). Revert.
- Insert `style="margin:0"` into `ui/templates/agents/list.html` →
  `test_no_inline_styles_in_app_templates` fails. Revert.
- Insert a literal `#ff0088` / `12px` into `ui/static/app.css` → the conformance colour/px tests
  fail. Revert.

## US1 — Agents page answers the four glance questions (P1)

Load `/agents` with the example config.

1. Page renders **server-side** with no page header, a full-bleed table sorted by name, and tabs
   All/Assets/Jobs/Scheduled/Disabled each with a count from the store (an asset+job agent
   counts in both Assets and Jobs; an on-demand agent is excluded from Scheduled).
2. Columns 1–5 (Name, Harness, Model, Kind badges, Schedules/Sensors pills + human-readable
   label) are present on first paint; a both-kind agent shows two Kind badges and two pills; an
   on-demand agent's schedule cell shows an em-dash.
3. Columns 6–8 (Latest run, Checks, Run history) **fill after first paint**: Latest run shows a
   status dot + relative time linking to Dagster; Checks show per-check icons (green pass /
   yellow warn / red fail / grey not-run, wrapping four per row, titled); Run history shows ≤10
   bars newest-at-right.
4. `?tab=scheduled` reloads onto the Scheduled tab; selecting a tab updates the URL and survives
   reload. Typing in Filter narrows rows by substring over name/harness/model. Toggling "Show
   disabled agents" reveals/hides disabled rows everywhere except the Disabled tab and persists
   across reloads.
5. A parse-error agent and a name-mismatch agent keep their existing badge/row treatment inside
   the new table.

Covers SC-001.

## US2 — Revised sidebar and foot on every page (P2)

Load `/agents`, `/agents/new`, `/agents/{name}`, and a 404 URL.

1. Nav shows **only Agents** below the divider keyline; no dead/placeholder links.
2. Foot shows, top to bottom: the Dagster status block (indigo, ok/down/unknown dot, opens
   Dagster in a new tab), a keyline, "Hide navigation" (collapse icon), "Settings" (gear icon).
   No theme radiogroup.
3. Activate "Hide navigation" → collapses to the 68px rail; foot links centre icons and hide
   labels; brand shows only its mark; Dagster block keeps only its dot; nothing overflows; the
   link's accessible name becomes "Show navigation". Reload → still collapsed.
4. In both Light and Dark, the Dagster connection points (foot block, Latest-run/Run-history
   links, schedule toggles) use the indigo accent; other elements use the theme accent.

Covers SC-004.

## US3 — User settings modal with theme control (P2)

1. Activate Settings → a `role="dialog"`, modal, "User settings" panel opens in `#ax-modal-root`
   with square corners, default-background surface, full-bleed header/actions keylines, one
   Preferences section, one Theme dropdown, and a single "Done" (no Save).
2. The Theme dropdown offers Light, Dark, Use system setting — each with a lead icon; the trigger
   shows the current option's icon. (No "Dagster Indigo" option.)
3. Select Light then Dark → theme switches immediately (no reload); reload keeps it.
4. Select "Use system setting", flip the OS theme → the UI follows live.
5. With the dropdown panel open, Escape closes the panel and the modal stays open; a second
   Escape closes the modal and focus returns to the Settings foot link. Done and a backdrop
   click also close, with no save.
6. Open a dirty agent form and trigger the confirm/dirty-form modal → it uses the new square
   keylined chrome.

Covers SC-003.

## US4 — Live schedule toggles from the list (P3)

1. With Dagster reachable, flip a schedule pill's toggle → Dagster's schedule page shows it
   running; the pill reflects the new state. Flip back.
2. Stop Dagster, reload `/agents` → columns 1–5 still render; a warning alert reads "Run data
   unavailable: Dagster is not reachable"; Latest run / Checks / Run history show em-dashes and
   the pills are disabled with an explanatory title. The page never fails to render.
3. A disabled agent's pill, or an unknown-state pill, is disabled with an explanatory title
   ("Turn on from Dagster" when the mutation is unavailable) and attempts no state change.

Covers SC-002.

## US5 — Design system stays in sync (P3)

1. Run the sync-test negative gate above (edit the design-system copy only → fail).
2. Run the inline-style and literal negative gates above.
3. Confirm the theme-accessibility assertion now targets the modal dropdown
   (`test_theme_control_is_accessible_icon_buttons`).

Covers SC-006.

## Offline (SC-007)

With egress blocked, reload every page and confirm fonts, icons, and the inlined sprite render
and **no request leaves the box** (`test_no_external_urls` + the served-gallery external-asset
test back this in CI).
