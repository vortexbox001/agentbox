# GitHub source

repo: leeclemmer/agentbox
branch: 010-file-layout-overhaul
path: ui/design-system

This project (AgentBox Design System) is associated with the AgentBox repository. On the `009-design-system-migration` branch, `ui/design-system/` contains this AgentBox design system (tokens, components, guidelines cards, and the agentbox-app UI kit) — it mirrors this project's structure.

Source URL: https://github.com/leeclemmer/agentbox/tree/010-file-layout-overhaul/ui/design-system

## Last sync

date: 2026-09-14T22:52:40Z
commit: (branch tip 010-file-layout-overhaul @ tree 12a7d16dc105; commit sha unknown)

### Updated in this project
- Checked 010 tip 12a7d16dc105 — 52 files changed across 7 commits, but ALL outside `ui/design-system/` (config layout moved to examples/config, orchestrator path resolution, litellm generator, specs, ui/*.py backend + tests). No design-system files changed. Nothing to pull.

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

- 2026-09-14T12:38:30Z — checked upstream, no changes since bf66c0d761d8.
- 2026-09-14T12:16:00Z — adopted upstream ax-/app.css specimen index.html + cards; vendored static/; rewrote /static/ paths to relative.
- 2026-09-14T12:13:30Z — pulled spacing.css border-width tokens.
- 2026-09-14T11:54:30Z — pulled self-hosted fonts + typography.css (local @font-face) + readme; MISjudged index.html/cards as an iframe conflict (corrected 12:16 — they are ax-/app.css markup, now pulled).
- 2026-09-14T11:45:00Z — verified 1070223c4b94→3fe54e126a8a was the round-trip of session work (spacing.css, Sidebar.jsx byte-identical); nothing pulled.
- 2026-09-14T04:15:46Z — pulled missing index.html + logo-dark/light.svg from branch; project was ahead on Table/RunStatusTag/SchedulePill/lockup work (later pushed upstream).
- 2026-09-14T04:07:12Z — initial association to `main` (ui/design-system held the upstream "Archon" design system).
