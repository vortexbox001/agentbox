# Phase 1 Data Model: Shell, Settings Modal, Tabbed Agents List

No persistent server-side schema changes (the agent YAML schema is untouched — spec Out of
Scope). These are the **render-time view models** the feature assembles: two per-row shapes
(store-backed vs Dagster-derived), plus two per-browser preferences. "Missing data is unknown,
not zero" throughout: unknown fields are `null` and render as an em-dash / disabled control.

## 1. Agent (store view) — rendered server-side, never waits on Dagster

Extends the row `agents_store.list_agents()` returns today (`name, file, enabled, harness,
model, dagster_job, dagster_path, dagster_url, parse_error, name_mismatch, editable`) with the
kind/crons/checks the tabbed list needs. Source: the agents store, at page render time.

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | Filename stem; the Name cell (mono link to `/agents/{name}`), with the name-mismatch badge preserved. |
| `harness` | str \| null | Harness id (Harness cell, mono). Null on parse error. |
| `model` | str \| null | Model (Model cell, mono, truncated with full value in `title`). Null on parse error. |
| `enabled` | bool \| null | `enabled: false` → Disabled tab + row style; null on parse error. |
| `is_asset` | bool | True when the agent declares `produces.asset`. Feeds the Kind "asset" badge and the Assets tab count. |
| `is_job` | bool | True when `job: true`. Feeds the Kind "job" badge and the Jobs tab count. An agent may be **both** (a badge per grouped sub-row, counts in both tabs). |
| `crons` | list of `{type, expr, dagster_name}` | One per configured cron. `type` ∈ {`job_schedule`, `asset_schedule`} is the **one canonical vocabulary** (`contracts/dagster-activity.md §0`): it drives the pill icon (clock vs sensor), the `dagster_name` to select (`sched_<stem>` vs `autocond_<stem>`, `-`→`_`), and the toggle `kind` (`schedule` vs **`sensor`** — an asset schedule is a Dagster sensor). Empty list → Schedules/Sensors cell shows an em-dash and the agent is excluded from the Scheduled tab count. |
| `checks` | list of `{name}` | Declared checks (from `produces.checks`), used to lay out the Checks cell placeholders (results fill from activity). Empty → Checks cell shows an em-dash. |
| `parse_error` | str \| null | When set, the row shows the existing parse-error treatment (message spans the data columns). |
| `name_mismatch` | bool | Preserves the existing name-mismatch badge. |
| `dagster_path` / `dagster_url` | str | Per-agent Dagster deep link (asset page for an asset agent, job page otherwise) — reused by the Latest-run and Run-history links (FR-018). |
| `editable` | bool | Unchanged; a too-new file stays view-only. |

**Derived tab counts** (server-side, FR-013): `All` = every row (subject to show-disabled);
`Assets` = `is_asset`; `Jobs` = `is_job`; `Scheduled` = `len(crons) > 0` (regardless of Dagster
on/off state); `Disabled` = `enabled is False`.

## 2. Agent activity (Dagster view) — fetched after first paint, one bounded call

Assembled by `dagster.activity(...)` (research R1) and served by `GET /api/agents/activity`.
Keyed by agent name. Every field may be `null` (unknown); the whole payload carries a
`reachable` flag.

| Field | Type | Notes |
|-------|------|-------|
| `reachable` | bool (top-level) | False when the single read failed/timed out → columns 6–8 em-dash, pills disabled, "Run data unavailable" warning (FR-020). |
| `latest_run` | `{run_id, status, start_time, end_time}` \| null | Latest run of the agent's job (asset agents: the run that materialized the asset). Drives the Latest-run status dot + relative time ("2 hours ago", "running now") and the Dagster deep link. Null → em-dash. |
| `history` | list of status (≤10) \| null | Last ten run statuses, **newest-first** from the read; rendered newest-**at-right** as bars: green success, red failure, neutral for empty/in-progress. |
| `checks` | list of `{name, status}` \| null | From the latest materialization. `status` → pass (green), fail-non-blocking (yellow warn), fail-blocking (red; error/timeout count as failed), not-run (grey). Four icons per row, wrapping; each `title` = check name + status. |
| `schedules` | map `dagster_name -> {running: bool\|null}` | Per-schedule/sensor instigation state. `running` seeds the pill toggle's checked state; `null`/unknown → toggle disabled with an explanatory title. |

**Status vocabulary.** Run `status` follows Dagster's run states (SUCCESS/FAILURE/STARTED/…);
check `status` maps onto the shared-contract check vocabulary (`pass|fail|error|timeout` →
pass / fail-blocking / warn-non-blocking / not-run) as in FR-017.

## 3. Theme preference — per-browser, localStorage only

| Field | Type | Notes |
|-------|------|-------|
| `localStorage["agentbox.theme"]` | `"light"` \| `"dark"` \| `"system"` | Existing key (FR-009). The pre-paint head script resolves all three and stamps `data-theme="dark"` or removes the attribute (light), with no flash. `system` follows `prefers-color-scheme` live. **No `indigo` value exists** — indigo is an accent ramp within Light and Dark (FR-010), not a theme. Not persisted server-side; no `config/settings.yaml` theme key. |

The settings-modal dropdown reads and writes this key; selecting an option applies immediately
(no reload, no Save) and a reload keeps it.

## 4. UI view state — transient list choices

| Field | Type | Persistence | Notes |
|-------|------|-------------|-------|
| active tab | `All`\|`Assets`\|`Jobs`\|`Scheduled`\|`Disabled` | URL `?tab=` | Filters rows client-side, survives reload, shareable, defaults to All (FR-013). |
| filter text | str | transient (not persisted) | Case-insensitive substring over name, harness, model; empty = no filter (FR-014). |
| show-disabled | bool | `localStorage` | Defaults off; when off, disabled agents hidden from every tab except Disabled; persists across reloads (FR-014). |

None of these are persisted server-side (spec Out of Scope).

## Relationships & invariants

- A row's **store view (1)** always renders; its **activity (2)** overlays after paint and only
  ever fills columns 6–8 and the col-5 toggle state. The page never blocks on (2).
- An agent that is **both** asset and job renders as a grouped pair of sub-rows: Name/Harness/Model
  span both (rowspan), then one sub-row per nature — the asset sub-row carries the asset Kind badge
  and its asset-schedule pills, the job sub-row carries the job Kind badge and its job-schedule
  pills; both sub-rows share the same run data and it counts in both the Assets and Jobs tabs (FR-013).
- Tab counts (1) come from the store and are correct even when Dagster is unreachable (SC-002).
- The primary "Dagster connection points" — the foot Dagster block and the schedule/sensor toggle
  checked track — carry the **indigo accent** in both themes (FR-010). Other elements keep the
  theme's own accent, including the Latest-run link (theme link accent / teal) and the Run-history
  bars (run-status colours), even though both deep-link to Dagster.
