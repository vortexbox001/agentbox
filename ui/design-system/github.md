# GitHub source

repo: leeclemmer/agentbox
branch: 009-design-system-migration
path: ui/design-system

This project (AgentBox Design System) is associated with the AgentBox repository. On the `009-design-system-migration` branch, `ui/design-system/` contains this AgentBox design system (tokens, components, guidelines cards, and the agentbox-app UI kit) — it mirrors this project's structure.

Source URL: https://github.com/leeclemmer/agentbox/tree/009-design-system-migration/ui/design-system

## Last sync

date: 2026-09-14T12:16:00Z
commit: (branch tip 009-design-system-migration @ tree f5105a861f34; commit sha unknown)

### Updated in this project
- CORRECTION to the previous two syncs: the upstream `index.html` and component cards do NOT use iframes. They use production `ax-*` markup styled by `/static/app.css` (fully token-based — every value resolves from tokens/*.css). My earlier "iframe direction conflict" was wrong; there is no conflict.
- Vendored the stylesheet so the server-absolute paths resolve in this project: copied `ui/static/app.css` → `static/app.css`, `ui/static/icons.svg` → `static/icons.svg`, `ui/static/favicon.svg` → `static/favicon.svg`.
- REQUIRED LOCAL ADAPTATION (do not treat as drift; re-apply after every sync of these files): upstream references the stylesheet/icons with server-absolute `/static/…` paths (correct for the Flask server, where `/static/` maps to ui/static/). In this preview a leading-slash path resolves to the sandbox ORIGIN root, not the project root, so it 404s. Rewrote `/static/` → project-relative in the adopted files: `index.html` uses `static/…`; `components/*/*.card.html` (two levels deep) use `../../static/…` for both `app.css` and `icons.svg#…` icon refs. Verified: ax- rules load, buttons/badges/tags/pills/alert all styled.
- PULLED (now render correctly): upstream `index.html` (inline specimen, `ax-*` Components section, no iframes, no React/CDN) and all six component cards (buttons/data/feedback/forms/layout/navigation) — production `ax-*` markup. Verified the specimen page renders (Brand, Colors, Type, Spacing, Components all styled).
- NOT PULLED (this one really is an iframe): `ui_kits/agentbox-app/index.html` upstream is `<iframe src="/agents">`, which needs the live Flask server and violates the user's no-iframe rule. Kept the project's React app-kit recreation. Open question: rebuild the app kit as static `ax-*` HTML of the /agents view instead.
- PULLED earlier this session: self-hosted fonts + typography.css (local @font-face), readme.md, spacing.css border-width tokens. — added `fonts/Inter*.woff2` + `fonts/SourceCodePro*.woff2`, and `tokens/typography.css` now declares local `@font-face` and drops the Google Fonts `@import` (spec 009 FR-015 / US4: renders with egress blocked). Fonts now register as Inter + Source Code Pro. Also pulled the expanded `readme.md` (fonts/ + Lucide sprite sections).
- NOT PULLED (conflicts with this session's explicit work — left project versions in place, flagged for the user):
  1. `index.html` — upstream reverted to the iframe-based specimen gallery. The user explicitly instructed "DO NOT EVER USE IFRAMES", so the project keeps its inline, React-mounted, no-iframe specimen page.
  2. Component card HTMLs (`buttons/data/feedback/forms/layout/navigation`) — upstream rewrote them to production `ax-*` markup styled by `/static/app.css` (served by the Flask app). That absolute server path does not resolve in this design-system project, so the cards would render unstyled here. Project keeps its bundle-mounted React cards.
  3. `ui_kits/agentbox-app/index.html` — upstream replaced the React kit with an iframe to the live `/agents` route (same iframe + no-server-path issues).
- These three are a real divergence in direction (upstream = production HTML served by Flask; project = self-contained inline/React). Needs a decision on which wins — see caveat below.

## Screen map

| Project screen / file | Repo source files |
| --- | --- |
| tokens/*.css | ui/design-system/tokens/*.css |
| components/**/*.jsx | ui/design-system/components/**/*.jsx |
| guidelines/*.html | ui/design-system/guidelines/*.html |
| ui_kits/agentbox-app/* | ui/design-system/ui_kits/agentbox-app/* |
| index.html | ui/design-system/index.html |
| components/*/*.card.html | ui/design-system/components/*/*.card.html (production ax- markup) |
| static/app.css + static/icons.svg | ui/static/app.css + ui/static/icons.svg (vendored so /static/ paths resolve) |
| tokens/typography.css + fonts/*.woff2 | ui/design-system/tokens/typography.css + ui/design-system/fonts/*.woff2 |

## Sync history

- 2026-09-14T12:13:30Z — pulled spacing.css border-width tokens.
- 2026-09-14T11:54:30Z — pulled self-hosted fonts + typography.css (local @font-face) + readme; MISjudged index.html/cards as an iframe conflict (corrected 12:16 — they are ax-/app.css markup, now pulled).
- 2026-09-14T11:45:00Z — verified 1070223c4b94→3fe54e126a8a was the round-trip of session work (spacing.css, Sidebar.jsx byte-identical); nothing pulled.
- 2026-09-14T04:15:46Z — pulled missing index.html + logo-dark/light.svg from branch; project was ahead on Table/RunStatusTag/SchedulePill/lockup work (later pushed upstream).
- 2026-09-14T04:07:12Z — initial association to `main` (ui/design-system held the upstream "Archon" design system).
