# Phase 1 Data Model: Runs Overview Page

Presentation model only. This feature **adds and changes no stored data** — it reads the runs tree
and Dagster and shapes what already exists. Entities below are view models built at request time;
none is persisted (spec Assumptions; constitution *Ephemeral Runs, Immutable Outputs*).

## Entity: Run (as presented)

One row of the overview. Built by joining a disk row (`runs_store.list_runs`) with best-effort
Dagster enrichment (`dagster.run_status`, R6) on the run id.

| Field | Source | Notes |
|-------|--------|-------|
| `run_id` | disk (dir name = Dagster run id, R2) | Links to the AgentBox run page `/runs/{run_id}` (FR-023). |
| `dagster_url` | `public_dagster_url(request)` + `run_id` | `{base}/runs/{run_id}`; the indigo link icon, new tab. Absent → no icon (FR-022/FR-024). |
| `status` | Dagster (true) → local fallback | Presented status ∈ {succeeded, failed, timed_out, cancelled, queued, in_progress}. Fallback marked `last_known` (FR-001/FR-002/FR-003). |
| `last_known` | derived | `True` when status came from the local record (Dagster unreachable, or no record for this id). Renders a visible marker (R8). |
| `agent` | disk (`context`/dir) | Mono treatment; **links to the agent** `/agents/{agent}` (FR-020). |
| `model` | disk (`context.model.model` / `report.model`) | Mono treatment (FR-020); `—` when absent. |
| `target` | Dagster (`assetSelection.path` join, else job/`pipelineName`) | Asset key or job name exactly as Dagster lists it (FR-014); `—` when unobtainable for a historical run (FR-021). |
| `launched_by` | Dagster run tags | `dagster/schedule_name` → schedule; `dagster/sensor_name` → sensor; else **manual launch** (FR-015); `—` when unobtainable (FR-021). |
| `checks` | Dagster (asset-check evaluations) | Same shape/rendering as the Agents overview Checks column (FR-016), via `dagster._check_status`. `—`/none when not applicable. |
| `created` | disk `started` epoch, refined by Dagster `startTime` | Label `Sep 17, 1:15 PM` in operator local time; full ISO on hover (FR-017, SC-005). |
| `duration` | Dagster `startTime`/`endTime`, else disk | `end − start` finished; `now − start` in-progress (no ticker, advances on refresh, FR-018); `—` when unknown. |
| `cost_usd` | disk `report.cost_usd` | `$x.xxxx`; `—` when null — never `0` (FR-019), via existing `_fmt_cost`. |

**Removed from the row** (FR-013): separate `date`, `started_time` (Time), and `attempts` columns.
They may remain in the store row's dict but are not rendered.

**Validation / derivation rules**:
- The presented `status` prefers Dagster while reachable and holding a record; otherwise local,
  marked `last_known` (FR-002/FR-003).
- `target` and `launched_by` are `—` when enrichment cannot supply them; never guessed (FR-021).
- `cost_usd` distinguishes unknown (`—`) from a real `0` (FR-019).
- Ordering: newest first by created (existing `started` desc sort).

## Entity: Tab

A partition of the **filtered** run set by presented status (R8). Not persisted; computed per
request over the text-/agent-/date-range-filtered set **before** partition and pagination
(FR-005/FR-006, clarification).

| Tab id | Members | Count badge |
|--------|---------|-------------|
| `all` | every run in the filtered set | `len(filtered)` |
| `in_progress` | in progress **or** queued | count within filtered set |
| `succeeded` | succeeded | count within filtered set |
| `failed` | failed, timed out, or cancelled (all non-success terminal) | count within filtered set |

Rendered with the shared `tabs` macro (FR-005); each carries a count badge (FR-006). An empty tab
shows count `0` and an empty-table state, not an error (edge case). Counts are over the whole
filtered set, independent of the current page (FR-006, US5 AC4).

## Entity: Filter state

The complete, shareable view state — every field encoded in the URL (FR-011, SC-004).

| Param | Meaning | Default | Notes |
|-------|---------|---------|-------|
| `tab` | active tab id | `all` | ∈ {all, in_progress, succeeded, failed}; unknown → `all`. |
| `q` | text filter | `""` | Case-insensitive substring over agent, model, target, run id (FR-009, R3). |
| `agent` | agent filter | `""` | Existing filter, retained through the ghost-Filter control (FR-010). |
| `date_from` / `date_to` | date range (`YYYY-MM-DD`) | `""` | Existing range, retained (FR-010); lexicographic compare (existing). |
| `page` | 1-based page | `1` | 30/page (FR-025). A page past the last resolves to a valid page (edge case). |

**Rules**:
- Changing `tab`, `q`, `agent`, or the date range resets `page` to 1 (FR-027, US5 AC2).
- Applying: filter (text + agent + date) → count per tab → partition by `tab` → paginate 30 → render
  (FR-026). The `status` dropdown query param is **removed**; tabs replace it (FR-007).
- The URL is the single source of truth for a shareable/bookmarkable view (FR-011); `runs-list.js`
  keeps it in sync via `history.replaceState`, degrading to a full navigation when history is
  unavailable (mirrors `agents-list.js`).

## Enrichment payload (transient, `dagster.run_status`)

Not an entity — the transient shape returned by the Dagster read (R6), merged into the presented
rows and discarded.

```jsonc
{
  "reachable": true,                 // false on any transport/parse/error arm → all rows last-known
  "runs": {
    "<run_id>": {
      "status": "SUCCESS",           // Dagster RunStatus (normalised by the caller, R8)
      "start_time": 1726579200.0,    // epoch seconds or null
      "end_time":   1726579320.0,    // epoch seconds or null
      "target":     "my_asset",      // asset key ("a/b") or job name; null when absent
      "launched_by": {"kind": "schedule|sensor|manual", "name": "sched_x"|null},
      "checks":     [{"name": "...", "status": "pass|warn|fail-blocking|not-run"}]  // or null
    }
  }
}
```

A run id absent from `runs` (Dagster reachable but no record — pruned/historical) is treated exactly
as unreachable for that row: local status, marked `last_known` (FR-002, edge case).

## Design-system component: Pagination

Not run data — the new shared UI component the page depends on (FR-034, R5). See
[contracts/pagination-component.md](./contracts/pagination-component.md) for its full contract.

| Prop | Meaning |
|------|---------|
| `page` | current 1-based page |
| `pages` | total page count (≥ 1) |
| `base_query` | the current filter/tab query, so Prev/Next links preserve state |

Renders Prev / `page of pages` / Next as token-styled, macro-composed controls; Prev disabled on
page 1, Next disabled on the last page. Works without JS (links carry `?page=`); enhanced by
`runs-list.js`.
