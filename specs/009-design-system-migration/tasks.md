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

- [ ] T009 [US2] Create `ui/templates/components/macros.html` with the thirteen shared macros per [contracts/component-macros.md](./contracts/component-macros.md): `button` (`ax-btn` + intent/outlined/loading→spinner), `text_input` (`ax-input`, `invalid` error slot), `select` (`ax-select`, spec-002 dropdown path), `checkbox` (`ax-checkbox`), `toggle` (`ax-toggle`), `badge` (`ax-badge` + intent incl. queued/scheduled/lime), `status_dot` (`ax-status-dot`), `alert` (`ax-alert` + intent), `spinner` (`ax-spinner`), `tabs` (`ax-tabs`), `card` (`ax-card`), `dialog` (`ax-dialog`), `table` (`ax-table`) — parameters mirroring each component's `.d.ts`, emitting markup + the design-system root class only (no event props).
- [ ] T010 [P] [US2] Recompose `ui/templates/agents/list.html` onto the macros (`table`, `badge`, `status_dot`, `button`), using the `page_header` block for its title/actions and defining no bespoke button/card/table styling (FR-006).
- [ ] T011 [US2] Recompose `ui/templates/agents/form.html` — the most control-dense page — onto the macros: render every input via `text_input`, every select via `select` (keeping the `ax-select` + `enhanceSelect` spec-002 path), every toggle/checkbox/button via their macros, preserve the responsive form-grid re-expressed on the new spacing scale (FR-007), and route validation error states through `text_input`'s `invalid` slot (FR-025).
- [ ] T012 [P] [US2] Recompose `ui/templates/automation/list.html` onto the macros (`table`, `badge`, `button`, `toggle` as used), via the `page_header` block, defining no bespoke control styling.
- [ ] T013 [P] [US2] Recompose `ui/templates/404.html` onto the shell/macros so it uses the page header and shared `button`/`card` styling rather than bespoke markup.
- [ ] T014 [US2] Update `ui/static/agent-form.js`, `ui/static/automation.js`, and `ui/static/dropdown.js` to restyle hooks only — swap class/token hooks to the design-system classes while freezing behaviour: the spec-002 dropdown keyboard model and all form-validation states are unchanged, and any JS-created button/select sets its design-system class (`ax-btn`/`ax-select`) (FR-025).
- [ ] T015 [US2] Extend `ui/tests/test_ui_consistency.py` (FR-024): keep the existing guard that every `<select>` carries `ax-select` and every JS-created select is enhanced (do not loosen), and add that every `<button>` in `ui/templates/**` carries `ax-btn` (and JS-created buttons set it) and every `<table>` carries `ax-table`.
- [ ] T016 [US2] Verify behaviour preservation (SC-006): exercise the agent-form spec-002 dropdown by keyboard (open/arrow/select/Escape) and trigger a validation error, confirming both match pre-migration; confirm queued status renders the gray badge and template/scheduled renders the lime badge (FR-014).

**Checkpoint**: Every page composes shared macros; all selects/buttons/tables carry the design-system class; dropdown and validation behaviour unchanged — US2 independently testable.

---

## Phase 5: User Story 3 - The design system lives in the repo for humans and agents (Priority: P2)

**Goal**: Make the in-repo bundle the discoverable source of truth — served developer reference, an auto-discovered design skill, docs and a constitution principle that record the location and the tokens-and-macros rule.

**Independent Test**: Open `/design-system` → the developer reference app (not the old Archon doc). List skills in a repo Claude Code session → the design skill appears pointing at `ui/design-system/readme.md`; asked to add a card it produces markup using the shared `card` macro. README, AGENTS.md, and the constitution describe the new location and rule.

- [ ] T017 [US3] Wire the design skill under `.claude/skills/agentbox-design/` (FR-019) from `ui/design-system/SKILL.md`, with instructions pointing at `ui/design-system/readme.md`, so a repo Claude Code session auto-discovers it; then validate SC-007 (per quickstart §5.2) — in a repo Claude Code session confirm the design skill is listed and, asked to add a card, it produces markup using the shared `card` macro from `ui/templates/components/macros.html` (requires T009). If session validation is not runnable in the working environment, record it as the manual acceptance step for SC-007.
- [ ] T018 [P] [US3] Confirm `ui/main.py` serves the design-system bundle at `/design-system/` and that the path opens the developer reference app rather than the old Archon doc (FR-003); adjust the mount/entry if it still targets a retired file.
- [ ] T019 [P] [US3] Update `README.md` and `AGENTS.md` (FR-020) to describe the design-system location (`ui/design-system/`), name `ui/design-system/readme.md` as the source of truth, and state the "sibling of Dagster / use tokens and macros" rule.
- [ ] T020 [P] [US3] Add a "Design" principle to `.specify/memory/constitution.md` (FR-021) requiring every screen to use design-system tokens and component macros, forbidding literal colours/fonts/pixel values in app styling and templates, and requiring new components to land in the design system first and the shared macro set second — with a MINOR version bump per governance rules.
- [ ] T021 [US3] Rewrite `ui/tests/test_design_system_docs.py` (FR-023) to replace the stale Archon-file assertions: parse `ui/design-system/_ds_manifest.json` and assert each `components[].name` has a corresponding macro in `ui/templates/components/macros.html` (`Tab` covered by `tabs`); assert `README.md` and `AGENTS.md` reference `ui/design-system/readme.md`; and assert no test or served file references the retired Archon artefacts.
- [ ] T022 [P] [US3] Apply the design system's content rules to UI text across `ui/templates/**` (FR-018): sentence case, no emoji, lowercase status text, numeric counts in mono, relative timestamps under a day, and page titles of one or two words.

**Checkpoint**: The bundle is served and discoverable; skill, docs, and constitution record the system — US3 independently testable.

---

## Phase 6: User Story 4 - The UI works with no internet access (Priority: P2)

**Goal**: Self-host fonts and icons and remove every external asset URL so the UI renders fully with egress blocked.

**Independent Test**: Block egress and reload every page — fonts and icons render (self-hosted or system fallback + local sprite) and no `googleapis`/`unpkg`/`cdn` request leaves the box; the static egress grep passes.

- [ ] T023 [US4] Self-host the brand fonts (FR-015): add `.woff2` files for Inter + Source Code Pro under `ui/design-system/fonts/`, replace the `@import url('https://fonts.googleapis.com/...')` at `ui/design-system/tokens/typography.css:6` with local `@font-face` rules pointing at those files — or, if the licence path is blocked, take the null action (ship no font files, keep the system-font fallback stack, leave an explanatory comment where the `@import` was, and never restore the external import).
- [ ] T024 [P] [US4] Vendor the needed Lucide icons into the local `ui/static/icons.svg` sprite (FR-016), extending the current sprite, referenced via `<use href="/static/icons.svg#name">` with `currentColor` + `stroke-width:2`; remove the bundle readme's `unpkg.com/lucide-static` CDN-fallback line so no doc invites an external reference.
- [ ] T025 [US4] Scrub remaining external asset URLs from served CSS/HTML/JS (FR-017) across `ui/templates/`, `ui/static/`, and `ui/design-system/tokens/`/`styles.css`, then add the external-font/CDN/asset-URL assertion to `ui/tests/test_conformance.py` (from T007) — fail on any `googleapis`, `unpkg`, `cdn`, or `http(s)://` font/icon/asset URL outside the exempt files — completing FR-022 and confirming it passes on the migrated tree.

**Checkpoint**: No served file references an external host; fonts and icons resolve locally — US4 independently testable (offline render is the manual pre-release check in Polish).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full validation across stories per quickstart.md.

- [ ] T026 Run the full suite green: `cd ui && ../.venv/bin/python -m pytest -q` — `test_conformance.py`, rewritten `test_design_system_docs.py`, and extended `test_ui_consistency.py` pass, and all pre-existing suites stay green (SC-006).
- [ ] T027 Negative conformance check (SC-005): insert a literal colour, a literal `px`, and an `--ax-*` token into an app CSS/template file, run `test_conformance.py`, confirm it FAILS, then revert and confirm it PASSES.
- [ ] T028 [P] Static egress grep (SC-003): run the quickstart grep over `ui/templates ui/static ui/design-system/tokens ui/design-system/styles.css` and confirm no `googleapis`/`unpkg`/`cdn` or external font/icon/asset URL is found.
- [ ] T029 Run the app and walk every page (SC-001/SC-002/SC-008) per quickstart §3: both themes render with no wrong-theme flash, theme switches/persists, System follows OS live, sidebar collapse persists, and a dark-mode side-by-side with Dagster matches sidebar width/font/surface-border grays/status colours with only the accent differing.
- [ ] T030 Manual pre-release offline render (SC-003 §7): block egress on the box and reload every page — fonts and icons still render and no outbound request is issued (documented as the manual gate; automated gate is T028).

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
- **US3 (P2)**: `test_design_system_docs.py` (T021) needs the macro set (T009) to assert coverage, and the SC-007 validation in T017 needs T009 for the card-macro check; docs/skill-wiring/constitution otherwise independent.
- **US4 (P2)**: Independent; T025 authors the external-URL assertion onto `test_conformance.py` (started by T007), completing FR-022. US1's T007 is fully green on its own before this.

### Within Each Story

- US1: base.html shell (T004) and app.css (T005) before shell.js wiring (T006); conformance check (T007) after the token migration exists; contrast audit (T008) last.
- US2: macros (T009) before page recomposition (T010–T013) and JS restyle (T014); consistency check (T015) and behaviour check (T016) after.
- US3: docs edits (T019) before the docs-reference assertion in T021; macros (T009) before the T021 coverage assertion and the T017 SC-007 card-macro validation; mount/constitution independent.
- US4: fonts (T023) and sprite (T024) before the URL scrub/verify (T025).

### Parallel Opportunities

- Setup: T002 [P].
- Foundational: T003 [P].
- US2: T010, T012, T013 [P] (different page files) once macros (T009) exist.
- US3: T018, T019, T020, T022 [P] (different files); T017 skill-wiring is file-independent but its SC-007 validation needs T009; T021 after T009 + T019.
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
