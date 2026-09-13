# Phase 0 Research: Design System Migration

The spec had a clarification session and the tech stack is fully determined by the existing
`ui/` codebase, so there were no open `NEEDS CLARIFICATION` markers. Research here records the
decisions that shape the migration and resolves the two internal conflicts between the
already-committed bundle and the spec's no-egress requirements.

## Decision 1 — Components become Jinja2 macros, not shipped React

- **Decision**: Re-express each of the thirteen manifest components as a Jinja2 macro in
  `ui/templates/components/macros.html`. The bundle's `.jsx` + `.d.ts` files are the
  parameter **contract**; they are never served to the browser.
- **Rationale**: The app is server-rendered Jinja2 with no bundler (confirmed in `main.py`:
  `Jinja2Templates`, `StaticFiles`, no npm build). Shipping React would add a runtime and a
  build step this project deliberately avoids. Spec Assumptions state the same ("each
  design-system component is re-expressed as a shared template macro").
- **Alternatives considered**: (a) Ship the React kit — rejected: adds a bundler/runtime,
  violates the offline/small-footprint constraint and the "no feature behaviour change" scope.
  (b) Per-page CSS classes with no macro — rejected: that is exactly the drift FR-006 forbids.

## Decision 2 — Self-host fonts; replace the Google-Fonts `@import`

- **Decision**: Remove the `@import url('https://fonts.googleapis.com/...')` from
  `ui/design-system/tokens/typography.css` and load Inter + Source Code Pro from local
  `@font-face` rules pointing at self-hosted `.woff2` files under the design-system bundle.
  The existing `--font-default` / `--font-mono` stacks already end in system fallbacks, so
  the page is correct even before a face loads.
- **Font-licence null-action (from spec Assumptions)**: If self-hosting Inter / Source Code
  Pro under a licence-compatible path is blocked, take the *null action*: ship no font files,
  keep the `@font-face`-less stack (system fonts render), leave an explanatory comment where
  the `@import` used to be, and **never restore the external import in served CSS**. Inter and
  Source Code Pro are both under the SIL Open Font License, so self-hosting is expected to be
  fine; the null-action is the documented fallback, not the plan of record.
- **Rationale**: `tokens/typography.css` is served at `/design-system/` and is therefore
  "served CSS" under FR-017 — the external `@import` must go regardless of whether the app
  links this file directly. FR-015 requires the fonts to render with no internet.
- **Alternatives considered**: Google Fonts `@import` (current state) — rejected: outbound
  request, fails offline (FR-015/017). A CDN `<link>` — same rejection.

## Decision 3 — Local Lucide sprite; drop the CDN fallback

- **Decision**: Vendor the needed Lucide icons into a local SVG sprite
  (`ui/static/icons.svg`, extending the current 6-symbol sprite) referenced via
  `<use href="/static/icons.svg#name">`. Remove the bundle readme's "Lucide CDN as fallback:
  unpkg.com/lucide-static" line (or mark it not-used for AgentBox) so no doc invites an
  external reference.
- **Rationale**: FR-016 (icons from a locally vendored sprite, no runtime CDN) and FR-017
  (no unpkg URL). `currentColor` + `stroke-width:2` outline style matches Dagster and the
  readme's Iconography rules.
- **Alternatives considered**: Per-icon inline SVG in every template — rejected: duplication,
  and harder to keep on one stroke style. Icon font — rejected by the bundle's own rules.

## Decision 4 — Theme resolved before first paint (no framework)

- **Decision**: A tiny **inline** `<script>` in `<head>` (before the stylesheets’ effect is
  visible) reads the stored preference (or falls back to `matchMedia('(prefers-color-scheme:
  dark)')`) and stamps `data-theme="dark"` / removes it on `<html>` before first paint. The
  base template must **not** hard-code `data-theme="dark"` (it currently does — line 2 of
  `base.html`). A `matchMedia` change listener keeps System mode following the OS live. The
  Light/Dark/System control lives in the sidebar foot and writes `localStorage`; the sidebar
  collapse state persists the same way.
- **Rationale**: FR-009 + Edge Cases require pre-paint resolution with no wrong-theme flash,
  default to OS, and live OS-follow in System mode — all achievable with ~15 lines of inline
  JS, no framework. The bundle's `theme.css` already defines Light on bare `:root` and Dark
  under `[data-theme="dark"]`, so stamping the attribute is all that is needed.
- **Alternatives considered**: CSS-only `@media (prefers-color-scheme)` — rejected: cannot
  honour a stored Light/Dark override or a toggle. Deferred (non-inline) script — rejected:
  guarantees a flash.

## Decision 5 — Conformance enforced as pytest static-grep modules

- **Decision**: Implement FR-022/023/024 as pytest modules mirroring the existing
  `test_secrets.py` / `secret_scan.py` pattern (static greps over `ui/templates` + `ui/static`,
  and over `ui/design-system` for served CSS). Replace the now-red `test_design_system_docs.py`
  (it references deleted `ARCHON-DESIGN-SYSTEM.md` / `Archon Design System.dc.html`) with
  manifest⇄macro + README-reference checks.
- **Rationale**: Constitution VI prefers automated verification; the repo already uses
  static-grep-as-test. No headless browser is needed (spec Out of Scope excludes automated
  runtime egress testing; offline render stays a manual pre-release check).
- **Alternatives considered**: Headless-browser assertions — rejected by scope. Manual review
  only — rejected by Constitution VI.

## Decision 6 — Retired magenta maps to new badge intents

- **Decision**: The two former magenta uses map to existing manifest Badge intents — queued →
  `queued` (gray), template/scheduled → `scheduled` (lime). No magenta token survives in any
  served CSS/template/JS.
- **Rationale**: FR-014 + Edge Case. `Badge.d.ts` already defines both `queued` and
  `scheduled` intents plus `lime`, so no new component work is needed — only the call sites move.
- **Alternatives considered**: Keep a neutral magenta token — rejected: FR-014 requires its
  removal and the conformance check would flag the literal/token.

## Cross-cutting notes carried into design

- The running app currently consumes `--ax-*` tokens from a **missing**
  `/design-system/archon-tokens.css` (`base.html:8`), and `app.css` defines zero tokens of its
  own — the app is effectively unstyled today. The migration is completing an in-flight change,
  not modifying a working Archon UI.
- Spec 002 dropdown (`dropdown.js`) keyboard model and all form-validation states are
  **frozen**: only class/token hooks change (FR-025). `test_ui_consistency.py` already guards
  the `ax-select` enhancement path — extend, don't loosen it.
- The `agentbox-design` skill exists only at `ui/design-system/SKILL.md`; it must be wired
  under `.claude/skills/` to be auto-discovered (FR-019).
