# Contract: Runs Overview — page route, JSON refresh, and the Dagster read

The UI surfaces this feature exposes: the `GET /runs` page, its `GET /api/runs` refresh endpoint,
and the internal `dagster.run_status(run_ids)` read. All read-only; no run data is written.

## §A — `GET /runs` (the overview page)

**Query parameters** (all optional; the full shareable view state — data-model *Filter state*):

| Param | Type | Default | Behaviour |
|-------|------|---------|-----------|
| `tab` | enum | `all` | ∈ {`all`,`in_progress`,`succeeded`,`failed`}. Unknown value → `all`. |
| `q` | string | `""` | Case-insensitive substring over agent, model, target, run id (FR-009). |
| `agent` | string | `""` | Existing agent filter (FR-010). |
| `date_from` | `YYYY-MM-DD` | `""` | Existing lower bound (FR-010). |
| `date_to` | `YYYY-MM-DD` | `""` | Existing upper bound (FR-010). |
| `page` | int ≥ 1 | `1` | 30 rows/page (FR-025). Past the last page → clamped to the last valid page (edge case). |

The removed `status` param MUST NOT drive filtering; if present it is ignored (FR-007).

**Response**: `200 text/html` rendering `runs/list.html` with:
- the shared `tabs` header (four tabs, each a count badge over the filtered set — FR-005/FR-006);
- the ghost **Filter** button + text input, plus agent and date-range controls (FR-008/FR-010);
- a table with columns, in order: **Run, Status, Agent, Model, Target, Launched by, Checks, Created,
  Duration, Cost** (FR-012); no Date, Time, or Attempts columns (FR-013);
- the `pagination` macro below the table when `pages > 1` (FR-025);
- for each row: run id linking to `/runs/{run_id}` (FR-023) and, when Dagster is configured, a
  right-justified indigo Dagster link icon to `{public_dagster_url}/runs/{run_id}` opening a new tab
  (FR-022); no icon when Dagster is not configured (FR-024).

**Ordering & processing** (FR-026): filter (text + agent + date) → per-tab counts over the filtered
set → partition by `tab` → sort newest-first → paginate 30. Enrichment (see §C) is applied to the
filtered set (capped, research R1) before partition so status, counts, and partition are truthful on
first paint.

**Degradation** (FR-002, SC-002): the page MUST render with Dagster stopped. Every row then shows
the local `report.json` status marked **last-known**, no Dagster link icon is a dead link, and
Target / Launched by / Checks show `—` where enrichment could not supply them.

**Guarantees**
- `GET /runs` with no params returns `200` and the `all` tab, page 1, even with zero runs (empty
  state, not an error).
- A copied URL with any combination of `tab`/`q`/`agent`/`date_from`/`date_to`/`page` reopens to the
  identical view (SC-004).
- Changing `tab`, `q`, `agent`, or the date range resets to `page=1` (FR-027) — enforced by the
  client on control change and by the server clamping an out-of-range page.

## §B — `GET /api/runs` (JSON refresh)

Backs `runs-list.js` live refresh without a full reload. Accepts the same query params as §A.

**Response**: `200 application/json`:

```jsonc
{
  "runs": [ /* presented Run rows for the current tab+filter+page, newest first */ ],
  "counts": { "all": N, "in_progress": N, "succeeded": N, "failed": N },
  "page": 1,
  "pages": 4,
  "reachable": true          // false → rows are last-known (client marks them)
}
```

Each `runs[]` element carries the data-model *Run (as presented)* fields
(`run_id`, `status`, `last_known`, `agent`, `model`, `target`, `launched_by`, `checks`, `created`,
`created_iso`, `duration`, `cost_usd`, `dagster_url`). The endpoint MUST NOT fail when Dagster is
down — it returns `reachable:false` and last-known rows.

## §C — `dagster.run_status(run_ids: list[str]) -> dict` (internal)

One bounded, batched GraphQL read (research R6), matching `dagster.py`'s existing convention: every
transport/HTTP/parse failure and every non-`Runs` error arm collapses to plain data — the caller
never sees an exception from a reachable-or-not Dagster.

**Request**: a single POST to `{DAGSTER_URL}/graphql`:

```graphql
query {
  runsOrError(filter: { runIds: [ "<id>", ... ] }, limit: <N>) {
    __typename
    ... on Runs {
      results {
        runId
        status                         # RunStatus enum
        startTime
        endTime
        assetSelection { path }        # → Target (asset key) when present
        pipelineName                   # → Target (job name) otherwise
        tags { key value }             # → Launched by (dagster/schedule_name | dagster/sensor_name)
        assetChecks {                  # → Checks (mapped via _check_status)
          name
          executionForLatestMaterialization { status evaluation { severity } }
        }
      }
    }
  }
}
```

> The exact check sub-selection mirrors the Agents overview read; the precise GraphQL field names
> are verified against this Dagster version during implementation (as `dagster.activity` did) and
> the parser degrades to `checks: null` on any unexpected arm.

**Response shape**: the *Enrichment payload* in [data-model.md](../data-model.md):
`{"reachable": bool, "runs": {run_id: {status, start_time, end_time, target, launched_by, checks}}}`.

**Guarantees**
- Exactly **one** GraphQL POST per call — never one request per run.
- Failure (`httpx.HTTPError`, `ValueError`, `PythonError`/non-`Runs` arm, no `data`) →
  `{"reachable": False, "runs": {}}`.
- A run id present in the request but absent from `results` is simply omitted from `runs` (caller
  treats it as last-known — FR-002 edge case).
- Bounded by `limit=N` (research R1 cap) and `config.RELOAD_TIMEOUT_S`.

## §D — Status normalisation (presented ↔ sources)

The presented status set and tab partition (FR-004/FR-005, research R8). One mapping table drives
both the tag intent and the tab bucket:

| Presented | Dagster `RunStatus` | Local report | Tag intent | Tab |
|-----------|--------------------|--------------|-----------|-----|
| succeeded | `SUCCESS` | `ok` | success | Succeeded |
| failed | `FAILURE` | `failed` | failure | Failed |
| timed_out | (none; local) | `timeout` | error | Failed |
| cancelled | `CANCELED` / `CANCELING` | — | error | Failed |
| in_progress | `STARTED` / `STARTING` | `running` | running | In progress |
| queued | `QUEUED` / `NOT_STARTED` | — | queued (gray idle dot) | In progress |
| unknown | (fallback) | `unknown` / missing | idle | shown under All only |

A `last_known` row keeps its mapped intent and adds a visible last-known marker (FR-002).
