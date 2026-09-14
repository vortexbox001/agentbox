---

description: "Task list for Design System Migration"
---

# Tasks: Design System Migration

**Input**: Design documents from `/specs/009-design-system-migration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature's automated **conformance checks** (FR-022/023/024) are first-class
deliverables, not optional TDD scaffolding — they are placed inside the story they verify and
must pass on the migrated tree. No additional TDD test-first tasks are generated.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project — server-rendered UI under `ui/`. Design-system bundle authoritative in
`ui/design-system/`; templates in `ui/templates/`, static assets in `ui/static/`, tests in
`ui/tests/`. Run tests from repo root: `cd ui && ../.venv/bin/python -m pytest -q`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the working baseline and clear retired artefacts before styling work.

- [X] T001 Establish the test baseline: run `cd ui && ../.venv/bin/python -m pytest -q` and record which suites are red (expect `tests/test_design_system_docs.py` red — it references deleted Archon files) versus green, so later regressions are attributable.
- [X] T002 [P] Confirm the retired Archon artefacts are removed (FR-001): verify the Archon doc, its token file, the three specimen files, and its support script no longer exist under `ui/`, and remove any lingering served mount or reference to them in `ui/main.py` (the broken `/design-system/archon-tokens.css` `<link>` is rewired in T004, not here).

**Checkpoint**: Baseline known; no retired Archon files remain to serve.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Guarantee the design-system source (tokens + manifest) is complete and serves, so all visual stories build on resolvable tokens.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [X] T003 [P] Verify the design-system token source is complete and serves at `/design-system/` (FR-002/FR-003): confirm `ui/design-system/tokens/theme.css` defines the Light palette on bare `:root` and the Dark palette under `[data-theme="dark"]`, that `colors.css`/`typography.css`/`spacing.css`/`shadows.css`/`animations.css`/`base.css` expose the `--color-*/--type-*/--space-*/--radius-*/--shadow-*/--nav-width/--icon-size` tokens the migration references, and that `ui/design-system/_ds_manifest.json` lists the thirteen components (button, text input, select, checkbox, toggle, badge, status dot, alert, spinner, tabs, card, dialog, table). Note any gap for the story that needs it.

**Checkpoint**: Token source confirmed resolvable and served — user story implementation can begin.

---

## Phase 3: User Story 1 - Management UI reads as a sibling of Dagster (Priority: P1) 🎯 MVP

**Goal**: Rewire the app shell and styling onto the new design-system tokens — 240px collapsible sidebar with no top bar, page header in the content area, Inter/Source Code Pro typography, neutral surfaces/borders, red/yellow/green status semantics, teal accent — with Light/Dark/System theme resolved before first paint and persisted.

**Independent Test**: Open agents list, agent form, automation list, and 404 in both light and dark. The sidebar/typography/surfaces/borders/status colours match the Dagster reference; the theme control switches and persists with no wrong-theme flash; no page shows the old dark-only cyan/magenta/serif Archon styling and no `--ax-*` token resolves.

- [X] T004 [US1] Rewrite `ui/templates/base.html` shell per [contracts/theme-and-shell.md](./contracts/theme-and-shell.md): remove the hard-coded `data-theme="dark"` on `<html>`; replace the broken `/design-system/archon-tokens.css` `<link>` with links to the new token stylesheets (base, colors, theme, typography, spacing, shadows, animations); add the inline pre-paint `<head>` theme script (read `localStorage` preference, fall back to `matchMedia('(prefers-color-scheme: dark)')`, stamp/remove `data-theme="dark"` before first paint); remove the `<header class="ax-topbar">`; add the 240px collapsible left sidebar (`--nav-width` expanded, 68px collapsed per readme; brand block, primary nav Agents/Automation with 16×16 Lucide `<use>` icons, foot holding the Dagster status link + theme control + collapse toggle); add a `page_header` block region (title + optional actions; breadcrumb slot present but empty on the current flat pages — populated deferred to later nav) at the top of the content area; keep the `#ax-status-region`, `#ax-toast-region`, `#ax-modal-root`, and `#ax-dagster-*` IDs; and replace the logo SVG's `--ax-cyan/--ax-magenta/--ax-green/--ax-yellow/--ax-text-ghost` fills with new tokens or `currentColor`.
- [X] T005 [US1] Rewrite `ui/static/app.css` (~669 lines) onto the new tokens (FR-008/FR-013/FR-014): express every colour/space/type/radius/shadow/transition as a `var(--…)` token (no literals); drop all `--ax-*` token usage and top-bar styles; add sidebar, collapsed-sidebar (68px), nav-item (32px height, 8px radius, `--color-background-blue` active fill, `--color-background-lighter` hover), content-area (flex 1, `overflow-y:auto`, ~24px padding via token, 64px bottom clearance), and page-header styles; remove all serif (Playfair) typography including the former italic-serif "thinking" treatment; and remap the two retired magenta uses to the queued (gray) and scheduled/template (lime) badge intents so no magenta value survives.
- [X] T006 [US1] Update `ui/static/shell.js` for theme + sidebar behaviour per the theme-and-shell contract: the sidebar-foot control offers Light/Dark/System, writes the `localStorage` preference, re-resolves and re-stamps `<html>` with no full reload; a `matchMedia('(prefers-color-scheme: dark)')` `change` listener re-stamps live while preference = system; the sidebar collapse toggle persists `collapsed` in `localStorage` across navigation/reload; and the existing Dagster status link/`#ax-dagster-*` polling behaviour is preserved, restyled on the new tokens (FR-012).
- [X] T007 [US1] Create `ui/tests/test_conformance.py` (FR-022, styling-hygiene portion) as a static-grep pytest module mirroring `ui/secret_scan.py`/`tests/test_secrets.py`, scanning `ui/templates/`, `ui/static/`, and served bundle CSS under `ui/design-system/` while exempting the token files (`ui/design-system/tokens/*.css`) and the font-face file: fail on any literal colour (`#hex`, `rgb(`/`rgba(`/`hsl(`, named colours), any literal `\d+px` outside the exempt files, any `--ax-*` custom-property definition or `var(--ax-…)` reference, and any `font-family` declared outside the font file — and pass on the migrated tree. (The external-font/CDN/asset-URL assertion of FR-022 is added to this same module by US4/T025, keeping US1 fully green on its own; see US4.)
- [X] T008 [US1] Verify WCAG 2.1 AA text and interactive-UI contrast (FR-026/SC-009) against the resolved `theme.css` token values in both light and dark; record the checked pairs and fix any token mapping in `app.css`/`base.html` that fails AA.

**Checkpoint**: The shell and every existing page render in the new visual language in both themes with persisted, flash-free theme switching — US1 independently testable.

---

## Phase 4: User Story 2 - Every page is built from shared component macros (Priority: P1)

**Goal**: Provide one shared Jinja2 macro per manifest component and recompose every page onto them, so control styling lives in one place and the agent form's keyboard and validation behaviour is preserved.

**Independent Test**: Render each page — every `<select>`, `<button>`, `<table>` carries its design-system class and no page defines its own button/card styling. On the agent form, the spec-002 dropdown keyboard flow (open/arrow/select/Escape) and validation error states still work.

**Depends on**: US1 shell/tokens (T004–T005) for full-fidelity rendering; macros can be authored in parallel with US1.

- [X] T009 [US2] Create `ui/templates/components/macros.html` with the thirteen shared macros per [contracts/component-macros.md](./contracts/component-macros.md): `button` (`ax-btn` + intent/outlined/loading→spinner), `text_input` (`ax-input`, `invalid` error slot), `select` (`ax-select`, spec-002 dropdown path), `checkbox` (`ax-checkbox`), `toggle` (`ax-toggle`), `badge` (`ax-badge` + intent incl. queued/scheduled/lime), `status_dot` (`ax-status-dot`), `alert` (`ax-alert` + intent), `spinner` (`ax-spinner`), `tabs` (`ax-tabs`), `card` (`ax-card`), `dialog` (`ax-dialog`), `table` (`ax-table`) — parameters mirroring each component's `.d.ts`, emitting markup + the design-system root class only (no event props).
- [X] T010 [P] [US2] Recompose `ui/templates/agents/list.html` onto the macros (`table`, `badge`, `status_dot`, `button`), using the `page_header` block for its title/actions and defining no bespoke button/card/table styling (FR-006).
- [X] T011 [US2] Recompose `ui/templates/agents/form.html` — the most control-dense page — onto the macros: render every input via `text_input`, every select via `select` (keeping the `ax-select` + `enhanceSelect` spec-002 path), every toggle/checkbox/button via their macros, preserve the responsive form-grid re-expressed on the new spacing scale (FR-007), and route validation error states through `text_input`'s `invalid` slot (FR-025).
- [X] T012 [P] [US2] Recompose `ui/templates/automation/list.html` onto the macros (`table`, `badge`, `button`, `toggle` as used), via the `page_header` block, defining no bespoke control styling.
- [X] T013 [P] [US2] Recompose `ui/templates/404.html` onto the shell/macros so it uses the page header and shared `button`/`card` styling rather than bespoke markup.
- [X] T014 [US2] Update `ui/static/agent-form.js`, `ui/static/automation.js`, and `ui/static/dropdown.js` to restyle hooks only — swap class/token hooks to the design-system classes while freezing behaviour: the spec-002 dropdown keyboard model and all form-validation states are unchanged, and any JS-created button/select sets its design-system class (`ax-btn`/`ax-select`) (FR-025).
- [X] T015 [US2] Extend `ui/tests/test_ui_consistency.py` (FR-024): keep the existing guard that every `<select>` carries `ax-select` and every JS-created select is enhanced (do not loosen), and add that every `<button>` in `ui/templates/**` carries `ax-btn` (and JS-created buttons set it) and every `<table>` carries `ax-table`.
- [X] T016 [US2] Verify behaviour preservation (SC-006): exercise the agent-form spec-002 dropdown by keyboard (open/arrow/select/Escape) and trigger a validation error, confirming both match pre-migration; confirm queued status renders the gray badge and template/scheduled renders the lime badge (FR-014).

**Checkpoint**: Every page composes shared macros; all selects/buttons/tables carry the design-system class; dropdown and validation behaviour unchanged — US2 independently testable.

---

## Phase 5: User Story 3 - The design system lives in the repo for humans and agents (Priority: P2)

**Goal**: Make the in-repo bundle the discoverable source of truth — served developer reference, an auto-discovered design skill, docs and a constitution principle that record the location and the tokens-and-macros rule.

**Independent Test**: Open `/design-system` → the developer reference app (not the old Archon doc). List skills in a repo Claude Code session → the design skill appears pointing at `ui/design-system/readme.md`; asked to add a card it produces markup using the shared `card` macro. README, AGENTS.md, and the constitution describe the new location and rule.

### Brand lockup & nav-surface refinements (do before T017–T022)

These three refine the US1 shell (T004–T006) that US3 documents, so land them before the rest of
User Story 3 so the served bundle, docs, and constitution record the final look. They depend on the
shell/tokens (T004–T005) already in place.

- [X] T031 Replace the split logo mark + wordmark with the theme-aware horizontal lockups: in `ui/templates/base.html` (lines 37–39) swap the two `<img>` (`/design-system/assets/logo.svg` + `wordmark.svg`) for the combined lockup, showing `/design-system/assets/logo-dark.svg` under the dark theme and `/design-system/assets/logo-light.svg` under light (theme-toggled via `[data-theme]`/`prefers-color-scheme` CSS on `.ax-brand`, matching the pre-paint theme model so there is no wrong-theme flash), sized to **130px wide** (auto height, expressed via the spacing/size tokens per FR-013 — add a `--brand-lockup-width: 130px` token to the design system rather than a literal in `app.css`); update `.ax-brand-mark`/`.ax-brand-name` in `ui/static/app.css` (lines 54–55, 155–160) accordingly, and preserve a sensible collapsed-sidebar (68px) state by keeping the standalone `logo.svg` mark for the collapsed rail while the 130px lockup shows only when expanded.
- [X] T032 Make the left-hand nav background match the main window: in `ui/static/app.css` change `.ax-sidebar` (line 30) from `var(--color-nav-background)` to the main content surface token (`--color-background-default`) so the sidebar and content area share one ground in both themes, and remove/restyle the navy-specific chrome that assumed a dark rail — revisit the nav-item hover/active fills and nav text/icon colours (the `--color-nav-*` tokens at `app.css:70–74`, plus the sidebar-foot Dagster/theme/collapse controls and the `--color-keyline-default` right-edge inset) so they read correctly against the flat surface and keep WCAG AA in light and dark (re-run the T008 contrast pairs for any pair that changed).
- [X] T033 [US3] Update the design system to reflect T031–T032: in `ui/design-system/readme.md` revise the brand-assets line (line 11) and the assets tree (lines 175–178) to name `assets/logo-dark.svg`/`assets/logo-light.svg` as the theme lockups (130px) and note their usage, and revise the Sidebar layout line (line 150) so it no longer says "dark background (`--color-nav-background`)" but "same surface as the content area (`--color-background-default`)"; mirror the change in `ui/design-system/guidelines/brand-logo.html` and `ui/design-system/SKILL.md` if either states the old brand/nav treatment, and add the `--brand-lockup-width` token from T031 to the token docs.

- [X] T017 [US3] Wire the design skill under `.claude/skills/agentbox-design/` (FR-019) from `ui/design-system/SKILL.md`, with instructions pointing at `ui/design-system/readme.md`, so a repo Claude Code session auto-discovers it; then validate SC-007 (per quickstart §5.2) — in a repo Claude Code session confirm the design skill is listed and, asked to add a card, it produces markup using the shared `card` macro from `ui/templates/components/macros.html` (requires T009). If session validation is not runnable in the working environment, record it as the manual acceptance step for SC-007.
- [X] T018 [P] [US3] Confirm `ui/main.py` serves the design-system bundle at `/design-system/` and that the path opens the developer reference app rather than the old Archon doc (FR-003); adjust the mount/entry if it still targets a retired file.
- [X] T019 [P] [US3] Update `README.md` and `AGENTS.md` (FR-020) to describe the design-system location (`ui/design-system/`), name `ui/design-system/readme.md` as the source of truth, and state the "sibling of Dagster / use tokens and macros" rule.
- [X] T020 [P] [US3] Add a "Design" principle to `.specify/memory/constitution.md` (FR-021) requiring every screen to use design-system tokens and component macros, forbidding literal colours/fonts/pixel values in app styling and templates, and requiring new components to land in the design system first and the shared macro set second — with a MINOR version bump per governance rules.
- [X] T021 [US3] Rewrite `ui/tests/test_design_system_docs.py` (FR-023) to replace the stale Archon-file assertions: parse `ui/design-system/_ds_manifest.json` and assert each `components[].name` has a corresponding macro in `ui/templates/components/macros.html` (`Tab` covered by `tabs`); assert `README.md` and `AGENTS.md` reference `ui/design-system/readme.md`; and assert no test or served file references the retired Archon artefacts.
- [X] T022 [P] [US3] Apply the design system's content rules to UI text across `ui/templates/**` (FR-018): sentence case, no emoji, lowercase status text, numeric counts in mono, relative timestamps under a day, and page titles of one or two words.

### Served specimen gallery (rebuild the `/design-system` reference page on the new design)

The retired Archon doc rendered a scrollable gallery of specimen cards at `/design-system`; T018
replaced it with a plain links landing. These tasks rebuild the full specimen gallery on the new
AgentBox design — the manifest already carries every specimen (`_ds_manifest.json` `cards[]`, 23
entries: Brand, Colors, Type, Spacing, Components, AgentBox App), and all preview files exist. They
depend on the final shell/tokens (T004–T005) and the brand/nav refinements (T031–T033), and on the
served mount (T018); they must obey the US4 no-egress rule (T023–T025), so the gallery and its
previews carry no external/CDN reference.

- [X] T034 [US3] Rebuild the served **specimen gallery** at `ui/design-system/index.html`, replacing the T018 placeholder landing with a rendered gallery like the retired `/design-system` doc: `fetch('_ds_manifest.json')` and render every `cards[]` entry as a labelled specimen (card `name` + `subtitle`) inside a same-origin **sandboxed `<iframe src="<card.path>">`** sized to its `viewport`, grouped and ordered by `group` (Brand → Colors → Type → Spacing → Components → AgentBox App). Page chrome resolves entirely from the design-system tokens (`styles.css`), mirrors the app's pre-paint light/dark model with a theme toggle (write `agentbox.theme`, stamp `data-theme` before first paint), and uses **inline JS/CSS only — no external or CDN `<script>`/`<link>`** (FR-017/US4). Keep the readme + token links from the placeholder as a header or footer so the page stays a reference entry point.
- [X] T035 [P] [US3] Make the component specimens render on the production design **offline**: the seven preview cards `components/{buttons,data,feedback,forms,layout,navigation}/*.card.html` and `ui_kits/agentbox-app/index.html` currently render the React reference kit (`_ds_bundle.js`) via **unpkg** (`react`, `react-dom`, `@babel/standalone` — 3 CDN `<script>` each). Rebuild each as static HTML showing the same controls the running app renders, using the design-system component classes (`ax-btn`, `ax-input`, `ax-select`, `ax-checkbox`, `ax-toggle`, `ax-badge`, `ax-status-dot`, `ax-alert`, `ax-spinner`, `ax-tabs`, `ax-card`, `ax-table`) with `styles.css` plus the single source of the component styles at `/static/app.css` — so each card needs no CDN, works with egress blocked, and matches the live UI. Preserve each file's leading `@dsCard` comment (the manifest is parsed from it) and remove the last `unpkg`/CDN references from the bundle.
- [X] T036 [US3] Serve and guard the gallery: confirm `/design-system/` opens the rebuilt gallery (the `html=True` mount from T018 already serves `index.html`); update the T018 comment in `ui/main.py` and the File Structure section of `ui/design-system/readme.md` to name `index.html` as the served specimen gallery; and extend the UI tests (`ui/tests/test_api.py` and/or `ui/tests/test_design_system_docs.py`) to assert the gallery lists the manifest groups (e.g. its text contains `Components` and `Colors`), that every `cards[].path` in `_ds_manifest.json` resolves under the mount (HTTP 200), and that no served specimen file references `unpkg`/`cdn`/an external `http(s)://` asset URL (locking in the offline guarantee alongside US4/T025).

**Checkpoint**: The bundle is served and discoverable — the `/design-system` specimen gallery renders every component and foundation on the new design and works offline; skill, docs, and constitution record the system — US3 independently testable.

---

## Phase 6: User Story 4 - The UI works with no internet access (Priority: P2)

**Goal**: Self-host fonts and icons and remove every external asset URL so the UI renders fully with egress blocked.

**Independent Test**: Block egress and reload every page — fonts and icons render (self-hosted or system fallback + local sprite) and no `googleapis`/`unpkg`/`cdn` request leaves the box; the static egress grep passes.

- [X] T023 [US4] Self-host the brand fonts (FR-015): add `.woff2` files for Inter + Source Code Pro under `ui/design-system/fonts/`, replace the `@import url('https://fonts.googleapis.com/...')` at `ui/design-system/tokens/typography.css:6` with local `@font-face` rules pointing at those files — or, if the licence path is blocked, take the null action (ship no font files, keep the system-font fallback stack, leave an explanatory comment where the `@import` was, and never restore the external import).
- [X] T024 [P] [US4] Vendor the needed Lucide icons into the local `ui/static/icons.svg` sprite (FR-016), extending the current sprite, referenced via `<use href="/static/icons.svg#name">` with `currentColor` + `stroke-width:2`; remove the bundle readme's `unpkg.com/lucide-static` CDN-fallback line so no doc invites an external reference.
- [X] T025 [US4] Scrub remaining external asset URLs from served CSS/HTML/JS (FR-017) across `ui/templates/`, `ui/static/`, and `ui/design-system/tokens/`/`styles.css`, then add the external-font/CDN/asset-URL assertion to `ui/tests/test_conformance.py` (from T007) — fail on any `googleapis`, `unpkg`, `cdn`, or `http(s)://` font/icon/asset URL outside the exempt files — completing FR-022 and confirming it passes on the migrated tree.

**Checkpoint**: No served file references an external host; fonts and icons resolve locally — US4 independently testable (offline render is the manual pre-release check in Polish).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full validation across stories per quickstart.md.

- [X] T026 Run the full suite green: `cd ui && ../.venv/bin/python -m pytest -q` — `test_conformance.py`, rewritten `test_design_system_docs.py`, and extended `test_ui_consistency.py` pass, and all pre-existing suites stay green (SC-006). Result: **334 passed**. Fixed one regression en route — `ui/design-system/ui_kits/agentbox-app/index.html` was the last specimen still loading React via unpkg (missed by T035); rebuilt it as static HTML using the production shell + `ax-*` classes (`../../static/app.css`), no CDN/React, so `test_design_system_docs.py::test_specimen_gallery_has_no_external_assets` passes.
- [X] T027 Negative conformance check (SC-005): inserted a literal colour (`#ff00ff`), a named colour (`red`), a literal `px` (`12px`), and an `--ax-*` token (`--ax-legacy`) into `ui/static/app.css`; `tests/test_conformance.py` FAILED (4 of 7 checks — hex, named, px, `--ax-*`), then reverted via `git checkout` and it PASSED (7 passed).
- [X] T028 [P] Static egress grep (SC-003): ran the quickstart grep over `ui/templates ui/static ui/design-system/tokens ui/design-system/styles.css` → **PASS: no external asset URL**.
- [X] T029 Run the app and walk every page (SC-001/SC-002/SC-008) per quickstart §3: verified headlessly (chromium DevTools driver against the live compose UI at :8080) across agents list, agent form, automation, and the custom 404 in both themes — both themes render with the pre-paint stamp matching preference (no wrong-theme flash), no `--ax-*` token resolves, no serif/Playfair font loads, theme choice and sidebar-collapse persist across reload, and the `matchMedia` System listener is wired to re-stamp live. The dark-mode side-by-side with Dagster (sidebar width/font/surface-border grays/status colours, accent-only difference — SC-002) is recorded as the manual visual acceptance step.
- [X] T030 Manual pre-release offline render (SC-003 §7): the automated egress gates pass (T028 grep + `test_conformance.py` external-URL assertion + `test_design_system_docs.py` specimen-gallery guard, all green) and no served file references an external host. The true egress-blocked reload of every page on the box stays the manual pre-release gate by design (spec Out of Scope).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — confirms token source before styling.
- **User Stories (Phase 3–6)**: Depend on Foundational.
  - US1 (shell/tokens/theme) is the visual foundation the other stories render on.
  - US2 macros can be authored in parallel with US1; page recomposition renders best after US1's tokens/shell land.
  - US3 and US4 depend on the token/macros/served-bundle work but are otherwise independent of each other.
- **Polish (Phase 7)**: Depends on all desired stories; T026/T028 fully green only after US4 (T023–T025).

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependency on other stories.
- **US2 (P1)**: Macros independent; page recomposition (T010–T014) consumes US1's shell/tokens.
- **US3 (P2)**: `test_design_system_docs.py` (T021) needs the macro set (T009) to assert coverage, and the SC-007 validation in T017 needs T009 for the card-macro check; docs/skill-wiring/constitution otherwise independent. The brand-lockup/nav-surface refinements (T031–T033) come first: they retune the US1 shell (depend on T004–T005; T032's token changes re-touch the T008 contrast work) and T033 records them in the bundle the rest of US3 documents.
- **US4 (P2)**: Independent; T025 authors the external-URL assertion onto `test_conformance.py` (started by T007), completing FR-022. US1's T007 is fully green on its own before this.

### Within Each Story

- US1: base.html shell (T004) and app.css (T005) before shell.js wiring (T006); conformance check (T007) after the token migration exists; contrast audit (T008) last.
- US2: macros (T009) before page recomposition (T010–T013) and JS restyle (T014); consistency check (T015) and behaviour check (T016) after.
- US3: brand-lockup/nav-surface refinements (T031 → T032 → T033) before the rest of US3 (T017–T022), so docs record the final shell; docs edits (T019) before the docs-reference assertion in T021; macros (T009) before the T021 coverage assertion and the T017 SC-007 card-macro validation; mount/constitution independent. The specimen gallery (T034–T036) comes after the refinements (T031–T033) and the mount (T018): T034 (gallery shell) and T035 (offline component cards) are independent files and run in parallel; T036 (serve/guard) after both.
- US4: fonts (T023) and sprite (T024) before the URL scrub/verify (T025).

### Parallel Opportunities

- Setup: T002 [P].
- Foundational: T003 [P].
- US2: T010, T012, T013 [P] (different page files) once macros (T009) exist.
- US3: T018, T019, T020, T022 [P] (different files); T017 skill-wiring is file-independent but its SC-007 validation needs T009; T021 after T009 + T019. Gallery: T034, T035 [P] (different files).
- US4: T024 [P] alongside T023.
- Polish: T028 [P].

---

## Parallel Example: User Story 2

```bash
# After macros.html (T009) exists, recompose independent page files together:
Task: "Recompose ui/templates/agents/list.html onto the macros"
Task: "Recompose ui/templates/automation/list.html onto the macros"
Task: "Recompose ui/templates/404.html onto the shell/macros"
```

## Parallel Example: User Story 3

```bash
# Different files, no ordering between them:
Task: "Wire the design skill under .claude/skills/agentbox-design/"
Task: "Confirm ui/main.py serves the bundle at /design-system/"
Task: "Update README.md and AGENTS.md with the new location and rule"
Task: "Add the Design principle to .specify/memory/constitution.md"
Task: "Apply the content rules to UI text across ui/templates/**"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup → 2. Phase 2: Foundational → 3. Phase 3: US1 (shell/tokens/theme).
4. **STOP and VALIDATE**: open every page in both themes; confirm sibling-of-Dagster shell, flash-free persisted theme, no Archon remnants.
5. This is the largest, most visible slice and can ship on its own.

### Incremental Delivery

1. Setup + Foundational → token source ready.
2. US1 → shell/tokens/theme → validate → MVP.
3. US2 → shared macros + recomposed pages → validate consistency + behaviour.
4. US3 → served bundle, skill, docs, constitution → validate discoverability.
5. US4 → self-hosted fonts/icons → validate offline.
6. Polish → full suite green, negative conformance, egress grep, app walk, offline pre-release.

### Parallel Team Strategy

After Foundational: one developer drives US1 (shell/tokens) while another authors US2 macros; US3 (docs/skill/constitution) and US4 (fonts/sprite) proceed independently; converge at Polish.

---

## Notes

- [P] tasks = different files, no dependencies.
- The `ax-` **class** prefix is kept as a namespace (behavioural JS + tests key off it); the prohibition is on `--ax-*` **tokens**, not the class namespace (see component-macros.md).
- Behaviour is frozen: spec-002 dropdown keyboard model and all validation states are preserved (FR-025) — the existing `test_ui_consistency.py` guards are the regression fence; do not loosen them.
- Commit after each task or logical group; stage the `specs/009-design-system-migration/` artifacts with the work.
