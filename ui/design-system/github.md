# GitHub source

repo: leeclemmer/agentbox
branch: 009-design-system-migration
path: ui/design-system

This project (AgentBox Design System) is associated with the AgentBox repository. On the `009-design-system-migration` branch, `ui/design-system/` contains this AgentBox design system (tokens, components, guidelines cards, and the agentbox-app UI kit) — it mirrors this project's structure.

Source URL: https://github.com/leeclemmer/agentbox/tree/009-design-system-migration/ui/design-system

## Last sync

date: 2026-09-14T04:15:46Z
commit: 1070223c4b94 (branch tip; treat as tree ref)

### Updated in this project
- Checked upstream: branch tip unchanged at 1070223c4b94 — no new commits since association, nothing to pull.
- Pulled the two files the project was missing vs the repo: root `index.html` (specimen gallery) and `assets/logo-dark.svg` / `assets/logo-light.svg`.
- Added `--brand-lockup-width` token (missing upstream) so the gallery header lockup renders.
- Project remains AHEAD of the branch (not pushed upstream): RunStatusTag + SchedulePill components, Table `fullBleed` rename (repo still has old `bordered`), logo/wordmark updates. Left local files as-is to avoid regressing this work.

## Screen map

| Project screen / file | Repo source files |
| --- | --- |
| tokens/*.css | ui/design-system/tokens/*.css |
| components/**/*.jsx | ui/design-system/components/**/*.jsx |
| guidelines/*.html | ui/design-system/guidelines/*.html |
| ui_kits/agentbox-app/* | ui/design-system/ui_kits/agentbox-app/* |
| index.html | ui/design-system/index.html |

## Sync history

- 2026-09-14T04:07:12Z — initial association to `main` (ui/design-system held the upstream "Archon" design system).
