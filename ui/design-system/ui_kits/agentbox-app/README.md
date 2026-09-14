# AgentBox App UI Kit

Static recreation of the AgentBox application interface. Demonstrates the full app shell including:

- **Sidebar navigation** — 240px collapsible sidebar matching Dagster's layout (68px collapsed)
- **Agent list view** — data table with harness/status badges and per-agent Dagster links
- **Navigation** — nav items with active state highlighting

It uses the production `ax-*` markup and classes styled by the vendored `../../static/app.css`
(the same stylesheet the running app serves) — no React, no CDN — so it renders offline and
matches the live UI (spec 009 US3/US4).

## Files
- `index.html` — the specimen: the full app shell + agents list as static `ax-*` HTML

## Usage
Open `index.html` in a browser. The sidebar-foot theme control toggles Light/Dark/System and
persists the choice (mirroring the app's pre-paint theme model).
