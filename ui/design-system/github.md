# GitHub source

repo: vortexbox001/agentbox
branch: main
path: ui/design-system

This project (AgentBox Design System) is associated with the AgentBox repository. `ui/design-system/` on the repo mirrors this project's structure (tokens, components, guidelines cards, the agentbox-app UI kit, and the tabbed-list/agentbox templates). The `ui-lhn-agent-listing` feature branch (agent-listing UI work) has been merged to `main`.

Source URL: https://github.com/vortexbox001/agentbox/tree/main/ui/design-system

## Last sync

date: 2026-09-15T17:56:12Z
commit: (main tip @ tree 87abd0a6317d; commit sha unknown)

### Updated in this project
- Switched tracked branch from `010-file-layout-overhaul` to `main` per user request.
- main tip 87abd0a6317d has blob hashes IDENTICAL to branch `ui-lhn-agent-listing` across all 122 `ui/design-system/` files — the agent-listing session work (indigo tokens + Dagster Indigo theme, nav divider Overview/Runs · Agents, checks column, slim buttons, tabbed-list + agentbox templates) is fully merged to main.
- Spot-checked the two heaviest session-edited files (`tokens/colors.css`, `templates/tabbed-list/Sidebar.dc.html`): both match the project's content exactly. Nothing to pull; project is in sync with main.

### History (earlier this session)
- Adopted the upstream `ax-*` specimen `index.html` + component cards; vendored `static/app.css`+icons and rewrote server-absolute `/static/…` paths to project-relative (see LOCAL ADAPTATION note below).
- LOCAL ADAPTATION (re-apply after any future sync of these files): `/static/…` → `static/…` in `index.html`, `../../static/…` in `components/*/*.card.html` (app.css + icons.svg refs). Needed because a leading-slash path resolves to the sandbox origin root here, not the project root.
- Pulled self-hosted fonts + typography.css (local @font-face), readme.md, spacing.css border-width tokens.

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

- 2026-09-14T22:52:40Z — on branch 010-file-layout-overhaul: 52 files changed across 7 commits but all outside ui/design-system/; nothing pulled.
- 2026-09-14T12:38:30Z — checked upstream, no changes since bf66c0d761d8.
- 2026-09-14T12:16:00Z — adopted upstream ax-/app.css specimen index.html + cards; vendored static/; rewrote /static/ paths to relative.
- 2026-09-14T12:13:30Z — pulled spacing.css border-width tokens.
- 2026-09-14T11:54:30Z — pulled self-hosted fonts + typography.css (local @font-face) + readme; MISjudged index.html/cards as an iframe conflict (corrected 12:16 — they are ax-/app.css markup, now pulled).
- 2026-09-14T11:45:00Z — verified 1070223c4b94→3fe54e126a8a was the round-trip of session work (spacing.css, Sidebar.jsx byte-identical); nothing pulled.
- 2026-09-14T04:15:46Z — pulled missing index.html + logo-dark/light.svg from branch; project was ahead on Table/RunStatusTag/SchedulePill/lockup work (later pushed upstream).
- 2026-09-14T04:07:12Z — initial association to `main` (ui/design-system held the upstream "Archon" design system).
