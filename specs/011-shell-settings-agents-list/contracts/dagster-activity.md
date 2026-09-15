# Contract: Dagster activity read + schedule toggle

Covers FR-019, FR-021, US4. Two additions to `ui/dagster.py`, both following the module's
existing rule: **map every transport and Dagster-side failure onto plain data**, never raise to
the caller, short timeout, one client.

## 0. Canonical instigator vocabulary (resolves the type/kind drift)

There is **one** authoritative cron `type` — the store row's `crons[].type` — and every other
surface derives from it. Confirmed against `orchestrator/factory.py`:

| store `crons[].type` | Dagster instigator | `dagster_name` pattern | pill icon | toggle `kind` | start / stop mutation | GraphQL selector |
|----------------------|--------------------|------------------------|-----------|---------------|-----------------------|------------------|
| `job_schedule`  | `ScheduleDefinition` (`build_schedule`) | `sched_<stem>` | `clock` | `schedule` | `startSchedule` / `stopRunningSchedule` | `scheduleSelector` |
| `asset_schedule`| `AutomationConditionSensorDefinition` (`build_asset_automation_sensor`) | `autocond_<stem>` | `sensor` | `sensor` | `startSensor` / `stopSensor` | `sensorSelector` |

- `<stem>` is the agent filename stem with `-` → `_` (factory: `cfg['name'].replace('-', '_')`).
  The store MUST emit `dagster_name` already in this form so `activity` and `set_instigation`
  address the exact registered instigator (FR-021).
- **An asset schedule is a Dagster _sensor_** (`AutomationConditionSensorDefinition`), not a
  schedule — so it uses the `startSensor`/`stopSensor` mutations and `sensorSelector` (resolves
  the A1 ambiguity). It is still cron-driven for display purposes, so the cron-to-text label
  applies to both types (FR-016).
- `set_instigation`'s `kind` argument is exactly this table's `toggle kind` column
  (`schedule` / `sensor`), derived by the front end from the row's `type`. The `schedule_pill`
  macro is given the store `type` directly and maps it to the icon; no third vocabulary exists.

**Selector identity (all reads and mutations).** Every `*Selector` uses
`repositoryLocationName: config.DAGSTER_LOCATION` (default `"definitions.py"`) and
`repositoryName: "__repository__"`. Cron labels render in the box timezone
`os.environ.get("TZ") or "UTC"` — the same source as the factory's `cron_timezone()` — never the
browser's zone (FR-016).

**T002 verified vocabulary (Dagster 1.13.21 on the box, `curl {DAGSTER_URL}/graphql`, 2026-09-15).**

| Item | Confirmed value |
|------|-----------------|
| Repository name | `__repository__` (via `repositoriesOrError { nodes { name location { name } } }`) |
| Location name | `definitions.py` (= `config.DAGSTER_LOCATION`) |
| Runs union | `pipelineRunsOrError` → `... on Runs { results { runId status startTime endTime } }` |
| Instigation read | `instigationStateOrError(instigationSelector: {repositoryName, repositoryLocationName, name})`; arms: `InstigationState { id selectorId status hasStartPermission hasStopPermission }`, `InstigationStateNotFoundError`, `PythonError` — the last two → `null` |
| Asset checks | **NOT top-level.** `assetNodeOrError(assetKey: {path: […]}) { ... on AssetNode { assetChecksOrError { ... on AssetChecks { checks { name blocking executionForLatestMaterialization { status evaluation { severity } } } } } }`; union `AssetChecksOrError` also has `AssetCheckNeedsMigrationError` / `AssetCheckNeedsUserCodeUpgrade` / `AssetCheckNeedsAgentUpgradeError` → treat as `null` |
| Start mutations | `startSchedule(scheduleSelector: ScheduleSelector!)`, `startSensor(sensorSelector: SensorSelector!)` — **selector-keyed** |
| **Stop mutations** | `stopRunningSchedule(id: String)` and `stopSensor(id: String)` — **NOT selector-keyed**; pass the `InstigationState.id` (or `scheduleSelectorId`/`jobSelectorId` = `InstigationState.selectorId`). Because stop needs the id, `activity`'s instigation sub-read MUST also return `id` per cron so `set_instigation` can stop without a second lookup. |

This resolves finding U1. The stop-mutation shape differs from the original §A/§B draft (which
assumed `stopRunningSchedule(scheduleSelector)`); §B below is corrected to the verified id-keyed form.

## A. `activity(agents) -> dict` — one bounded aliased read (FR-019, SC-005)

**Input.** The store rows (names, job names `agent_<stem>`, asset keys, per-cron `dagster_name`).

**Behaviour.** Build **one** GraphQL document that aliases, per agent, the three sub-reads below,
POST it once to `{config.DAGSTER_URL}/graphql` with a short timeout, and shape the response into
the `agents-list-view.md §C` payload. On timeout/HTTP/parse error return
`{"reachable": False, "agents": {}}`. Never issue one request per agent.

**Sub-reads (per agent, aliased).**

1. **Latest run + last ten** — filter runs by the agent's job name:
   ```graphql
   pipelineRunsOrError(filter: {pipelineName: "agent_<stem>"}, limit: 10) {
     ... on Runs { results { runId status startTime endTime } }
   }
   ```
   `results[0]` → `latest_run`; the ten `status` values → `history` (newest-first).
2. **Instigation state** — per configured cron's `dagster_name`:
   ```graphql
   instigationStateOrError(instigationSelector: {
     repositoryName: "__repository__", repositoryLocationName: "<DAGSTER_LOCATION>", name: "<dagster_name>"
   }) { ... on InstigationState { id selectorId status } }
   ```
   `RUNNING` → `{"running": true, "id": <id>}`, `STOPPED` → `{"running": false, "id": <id>}`, any
   error arm (incl. `InstigationStateNotFoundError`) → `null`. The `id` is carried so
   `set_instigation` can address the id-keyed stop mutation (§B) without a second read.
3. **Latest-materialization asset checks** — asset agents with declared checks only, by asset key,
   **through `assetNodeOrError`** (there is no top-level `assetChecksOrError` on this version):
   ```graphql
   assetNodeOrError(assetKey: {path: [<segments>]}) {
     ... on AssetNode {
       assetChecksOrError {
         ... on AssetChecks {
           checks { name blocking executionForLatestMaterialization { status evaluation { severity } } }
         }
       }
     }
   }
   ```
   Map to `{name, status}`: `pass` (succeeded); `warn` (failed, `severity: WARN` → non-blocking);
   `fail-blocking` (failed, `severity: ERROR`, or `error`/`timeout`); `not-run` (no execution).
   Non-`AssetChecks` arms (`AssetCheckNeedsMigrationError`, etc.) → `null`.

**Null semantics.** Any sub-read arm that is missing or an error type yields `null` for that
field (unknown), never `0` or a fabricated value (shared contract; edge case: partial Dagster
ships columns 1–5 live and 6–8 as em-dashes).

**VERSION NOTE — RESOLVED by T002 (2026-09-15, Dagster 1.13.21 on the box).** The union type
names, asset-check query path, selector argument names, stop-mutation shape, and `repositoryName`
value are all confirmed and pinned in §0's verified-vocabulary table above. No further
verification is needed before coding `activity`/`set_instigation`.

## B. `set_instigation(kind, name, running) -> dict` — start/stop (FR-021, US4)

**Input.** `kind` ∈ {`schedule`, `sensor`} (from §0's toggle-kind column), the Dagster instigator
`name` (`sched_<stem>` or `autocond_<stem>`), and desired `running`. For a **stop**, the
instigation `id` from `activity`'s sub-read 2 (the stop mutations are id-keyed, not
selector-keyed — see §0 T002 note).

**Behaviour.** POST the matching mutation (per §0):
- **start** is selector-keyed:
  - `schedule` (job_schedule): `startSchedule(scheduleSelector: {repositoryName: "__repository__", repositoryLocationName: config.DAGSTER_LOCATION, scheduleName: name})`
  - `sensor` (asset_schedule): `startSensor(sensorSelector: {repositoryName: "__repository__", repositoryLocationName: config.DAGSTER_LOCATION, sensorName: name})`
- **stop** is **id-keyed** (verified T002 — no selector arg):
  - `schedule`: `stopRunningSchedule(id: <instigation id>)`
  - `sensor`: `stopSensor(id: <instigation id>)`

  When the id is unknown (state never resolved), stop is not attempted — the toggle stays
  disabled per §C. (`scheduleSelectorId` / `jobSelectorId` = `InstigationState.selectorId` are the
  documented fallbacks if an id is unavailable.)
Return `{"ok": bool, "running": bool|None, "message": str}`. Treat `... on PythonError`,
`UnauthorizedError`, and GraphQL `errors` as `ok: false`.

**Exposed endpoint** (`main.py`): a POST (e.g. `POST /api/schedules/toggle`, body
`{name, kind, running}`) returning `set_instigation(...)`, always **200** (outcome is data).

## C. Degradation (FR-016, FR-021, edge cases)

The pill toggle MUST render **disabled** with an explanatory title, and MUST NOT attempt a state
change, when **any** of:
- the agent is disabled,
- Dagster is unreachable (`activity` returned `reachable: false`),
- the instigation state is unknown (`running: null`),
- the mutation is unauthorised/unavailable → title **"Turn on from Dagster"** (matching the
  existing "starts paused, turn on from Dagster" wording).

Otherwise the toggle reflects `running` and, on flip, calls `B` and updates to the returned
state (FR-021, US4 scenario 1).
