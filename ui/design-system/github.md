repo: dagster-io/dagster
branch: master
path: js_modules

## Last sync
date: 2026-09-13T02:16:11Z

### Updated in this project
- Imported Dagster color palettes (CoreColorStyles.css, TranslucentColorStyles.css, DataVizColorStyles.css)
- Imported Dagster theme mapping (GlobalThemeStyle.css — light/dark semantic token structure)
- Imported Dagster navigation layout (AppContainer.module.css, MainNavigation.module.css — 240px/68px sidebar)
- Imported Dagster component patterns (Button.module.css, Tabs.module.css, Page.module.css)

## Screen map
| Project file | Repo source |
|---|---|
| tokens/colors.css | js_modules/ui-components/src/palettes/CoreColorStyles.css, TranslucentColorStyles.css |
| tokens/theme.css | js_modules/ui-components/src/theme/GlobalThemeStyle.css |
| tokens/typography.css | js_modules/ui-components/src/fonts/Fonts.css |
| components/buttons/Button.jsx | js_modules/ui-components/src/components/Button.tsx, css/Button.module.css |
| components/navigation/Tabs.jsx | js_modules/ui-components/src/components/Tabs.tsx, css/Tabs.module.css |
| ui_kits/agentbox-app/Sidebar.jsx | js_modules/ui-core/src/app/navigation/AppContainer.tsx, MainNavigation, css/*.module.css |
| ui_kits/agentbox-app/index.html | js_modules/ui-core/src/app/AppLayout.tsx |
