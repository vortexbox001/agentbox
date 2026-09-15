# Contract: Agents list view (store row, tabs/toolbar/columns, activity JSON)

Covers FR-012–020. The page renders store-backed columns server-side and fills Dagster-derived
columns after first paint. Two producers: the extended store row (server) and the activity
endpoint (after paint).

## A. Extended store row — `agents_store.list_agents()`

Each row in `{"agents": [...]}` MUST additionally carry (beyond today's fields):

```jsonc
{
  "name": "categorize-commits",
  "harness": "claude-code",           // null on parse error
  "model": "sonnet",                  // null on parse error
  "enabled": true,                    // null on parse error
  "is_asset": true,                   // declares produces.asset
  "is_job": false,                    // job: true
  "crons": [                           // one per configured cron; [] if none
    {"type": "asset_schedule", "expr": "0 17 * * *", "dagster_name": "<schedule/sensor name>"}
  ],
  "checks": [{"name": "lint"}, {"name": "tests"}],  // declared checks; [] if none
  "parse_error": null,
  "name_mismatch": false,
  "dagster_path": "/assets/...",      // asset page for an asset agent, else job page
  "dagster_url": "http://.../assets/..."
}
```

- `type` ∈ {`job_schedule`, `asset_schedule`}; asset agents use the sensor icon, jobs the clock
  icon (FR-016). `dagster_name` MUST follow the factory's registration (the job `agent_<stem>`
  naming helper and the asset key), so the activity read and the toggle address the same
  instigator (FR-021).
- On parse error the row keeps `parse_error` set with data fields null; the template spans the
  message across the data columns (FR-015, US1 scenario 9).
- Tab counts are computed **server-side** from these rows (FR-013): Assets=`is_asset`,
  Jobs=`is_job` (both-kind counts in both), Scheduled=`crons != []`, Disabled=`enabled is False`,
  All=every row (subject to show-disabled). Counts MUST be correct with Dagster unreachable.

## B. Page render (server-side, `GET /agents`)

- No page header (title only in `<title>`); full-bleed table sorted by name (FR-012, FR-015).
- Tabs All/Assets/Jobs/Scheduled/Disabled with counts (via the extended `tabs` macro,
  `design-system-sync.md §C`). Default tab All; the client reflects the active tab in `?tab=`.
- Toolbar: left = Filter control + "Show disabled agents" checkbox; right = "New agent" primary
  button (moved from the old page header) (FR-014).
- Columns in order: Name, Harness, Model, Kind, Schedules/Sensors, Latest run, Checks, Run
  history (FR-015). Columns 1–5 render from the row (Schedules/Sensors renders the pills, icon,
  and cron-to-text label live; only the toggle state fills later — research R6).
- Empty store → the existing "No agents yet" card renders **below the toolbar**, inside the list
  view (FR-020).
- The old Status column and old Dagster runs-button column are **removed**; enabled/disabled is
  shown by row style + the Disabled tab + the show-disabled toggle (FR-018).

## C. Activity endpoint — `GET /api/agents/activity`

Always **200** (outcome is data, mirroring `/api/dagster/status`).

```jsonc
{
  "reachable": true,
  "agents": {
    "categorize-commits": {
      "latest_run": {"run_id": "…", "status": "SUCCESS", "start_time": 1.0, "end_time": 2.0},
      "history": ["SUCCESS","FAILURE", "…"],            // newest-first, ≤10; render newest-at-right
      "checks": [{"name":"lint","status":"pass"},{"name":"tests","status":"fail-blocking"}],
      "schedules": {"<dagster_name>": {"running": true}}
    }
  }
}
```

- Any field MAY be `null` (unknown) → em-dash / disabled control; never a fabricated `0`.
- `reachable: false` → the client shows the warning alert "Run data unavailable: Dagster is not
  reachable", leaves columns 6–8 as em-dashes and pills disabled (FR-020, SC-002). Columns 1–5
  are unaffected.
- Backed by **one** aliased GraphQL read (`dagster-activity.md`); never one request per agent
  (SC-005).

## D. Client behaviour — `ui/static/agents-list.js`

- After first paint, fetch `C` once and fill columns 6–8 + each pill's toggle state.
- Tab/filter/show-disabled narrow the already-rendered rows **client-side**; the active tab
  syncs to `?tab=` (default All, survives reload/shared URL); show-disabled persists in
  `localStorage` and, when off, hides disabled rows from every tab except Disabled; filter is a
  case-insensitive substring over name/harness/model, empty = no filter (FR-013/014).
- Latest-run text links to the run in Dagster; Run-history bars titled with status + time;
  Checks icons wrap four per row, each titled with check name + status (FR-017).
