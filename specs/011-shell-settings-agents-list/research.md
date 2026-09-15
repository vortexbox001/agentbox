# Phase 0 Research: Shell, Settings Modal, Tabbed Agents List

All unknowns from Technical Context resolved below. Each decision names what was chosen, why,
and the alternatives rejected. The riskiest item is R1 (the single bounded Dagster read); the
GraphQL field names there are the one place to verify against the running webserver version
before coding.

## R1 — One bounded Dagster activity read for all agents (FR-019, SC-005)

**Decision.** Add `dagster.activity(agents) -> dict` to `ui/dagster.py`: a **single** `httpx`
POST to `{DAGSTER_URL}/graphql` carrying **one aliased query** that batches every agent's
run/check/instigation facts into one round trip, with a short timeout (reuse
`config.RELOAD_TIMEOUT_S` or a new `ACTIVITY_TIMEOUT_S`). It maps transport and Dagster-side
failures onto plain data (like `reload()`/`status()` already do) and returns `null` for any
field it cannot resolve — never a guess, never a disk scan.

The query is assembled from the store rows (job name `agent_<stem>` from `_dagster`, asset key
from `produces.asset`, schedule/sensor names from the factory's registration). Per agent it
aliases:
- **Latest run + last ten** — `pipelineRunsOrError(filter: {pipelineName: "agent_<stem>"},
  limit: 10)` → `... on Runs { results { runId status startTime endTime } }`. `results[0]` is
  the latest (id, status, start/end for relative time and the Dagster deep link); the ten
  `status` values are the run-history bars newest-first.
- **Instigation state** — `instigationStateOrError(instigationSelector: {repositoryName,
  repositoryLocationName: config.DAGSTER_LOCATION, name: "<schedule/sensor name>"})` →
  `... on InstigationState { status }` (RUNNING/STOPPED). Drives the pill toggle's checked
  state; absent/unknown → toggle disabled.
- **Latest-materialization asset checks** (asset agents with declared checks) —
  `assetChecksOrError(assetKey: {path: [...]})` plus the check evaluations on the latest
  materialization → per check `{name, status}` mapped to pass / fail-non-blocking (warn) /
  fail-blocking / not-run.

**Rationale.** FR-019/SC-005 mandate one aliased query, never one-per-agent; `ui/dagster.py`
already establishes the "map failure to data, one client, short timeout" pattern, so this
extends a proven module rather than adding a second client. Store-derived names mean no extra
lookups. Returning `null` (unknown) honours the shared contract "missing data is unknown, not
zero" and lets the front end degrade cleanly.

**Alternatives rejected.** *One request per agent* — violates SC-005 and multiplies latency and
failure surface. *Scanning `/data/dagster/...` run dirs* — explicitly forbidden (edge cases:
"never scans run directories on disk to fabricate data"); Dagster owns run state. *Server-side
blocking fetch before render* — would make the page fail/stall when Dagster is slow or down;
FR-020 requires the store-backed columns to ship first and the run data to fill after paint.

**To verify before coding** (against the deployed webserver, one throwaway `curl` to
`/graphql`): the exact union type names (`Runs` vs `PipelineRuns`), the asset-check query field
and its evaluation shape, and the `instigationSelector` argument names. These vary by Dagster
version; the shape above matches the 1.13.x line the box runs. Encode the resolved names in
`contracts/dagster-activity.md`.

## R2 — Live schedule/sensor start-stop mutation (FR-016, FR-021, US4)

**Decision.** Add `dagster.set_instigation(kind, name, running) -> dict` posting the matching
mutation and returning `{"ok": bool, "running": bool|None, "message": str}`, and expose it as a
new write endpoint (see R7). Mutations: schedules `startSchedule` / `stopRunningSchedule`,
sensors `startSensor` / `stopSensor`, each selected by `scheduleSelector`/`sensorSelector`
(`{repositoryName, repositoryLocationName, <name>}`). Handle the `... on PythonError` /
`UnauthorizedError` / `... on UnauthorizedError` union arms as failure and return `ok: false`.

**Degradation.** When the mutation errors, is unauthorised, or the current state is unknown, the
pill renders as a **disabled** control titled **"Turn on from Dagster"** (matching the existing
"starts paused, turn on from Dagster" wording), and the front end never attempts a state
change (FR-016, FR-021, edge case). The toggle is likewise disabled when the agent is disabled
or Dagster is down.

**Rationale.** This is the brief's only behaviour addition; a small server endpoint keeps the
Dagster URL and any future auth server-side (Principle III) and mirrors the existing
`reload()` mutation handling. The instigation state returned by R1 seeds the initial checked
state so the toggle is correct on first fill.

**Alternatives rejected.** *Read-only pills* — the clarification chose a live write endpoint.
*Browser-direct GraphQL to Dagster* — the browser cannot reach the in-network `DAGSTER_URL`,
and it would leak the endpoint and bypass server-side error normalisation.

## R3 — Icon sprite resolution mechanism (FR-023)

**Decision.** **Inline the icon sprite once in `base.html`** (a hidden `<svg>` of `<symbol>`s)
and make every `<use href="#id">` **document-relative** (`#id`), dropping the
`/static/icons.svg#id` absolute references currently in `base.html` and `dropdown.js`. Add the
icons the mocks need and the sprite lacks: `filter`, `settings`, `check-circle`, `warn-tri`,
`x-circle`, `overview`, `runs`, `clock`, `sensor`, `search`.

**Rationale.** FR-023 recommends exactly this. The design-system mocks reference symbols by bare
`#id` and inline their own sprite; matching that removes the served/design-system divergence in
how icons resolve, guarantees icons render with egress blocked (SC-007) without a separate
sprite fetch, and lets the theme dropdown and pill icons use the same `#id` convention as the
mock. The served `ui/static/icons.svg` stays as the design-system's canonical sprite source and
is what the sync test compares.

**Alternatives rejected.** *Keep `/static/icons.svg#id` absolute refs* — works offline but keeps
two divergent resolution mechanisms (mock uses inline `#id`), which FR-023 asks to unify.
*Fetch the sprite via JS* — extra request, offline-fragile, and unnecessary.

## R4 — Design-system sync test (FR-024, SC-006)

**Decision.** New `ui/tests/test_design_system_sync.py` compares each served shared asset to its
`ui/design-system/static/` sibling and **fails on divergence beyond one documented
substitution**:
- `ui/static/app.css` ⇄ `ui/design-system/static/app.css`
- `ui/static/dropdown.js` ⇄ `ui/design-system/static/dropdown.js`
- `ui/static/icons.svg` ⇄ `ui/design-system/static/icons.svg`

The **one documented substitution** is the icon-href form: the served copies resolve icons by
document-relative `#id` while the design-system gallery copies may use their own path; the test
normalises that single transform (e.g. strips a leading `/static/icons.svg` prefix from `href`)
and then requires byte-equality. The substitution rule lives as a constant in the test with a
comment, so "documented" is literal. The current copies (app.css 944 vs 850, dropdown.js 403 vs
344) are **ahead**; bringing the served copies level is the FR-023 work that makes this test
pass, and editing only the design-system copy afterwards re-fails it.

**Rationale.** SC-006 requires the test to fail when a design-system asset is edited without its
served counterpart. Comparing files directly (mirroring the existing static-grep test style in
`test_conformance.py`) is the simplest durable guard. A single, named substitution keeps the
"they may differ in exactly one recorded way" contract precise.

**Alternatives rejected.** *Serve one physical copy* (symlink or serve the design-system file
directly) — would eliminate drift entirely but changes the serving story and 010's file layout;
out of scope, and the brief frames this as "bring level + prevent drift", i.e. a test.
*Fuzzy/normalised diff* — hides real drift; the point is exact parity but for one recorded
transform.

## R5 — Settings-modal theme dropdown as a custom listbox (FR-005–011)

**Decision.** The theme control is a **custom listbox** built on the design-system
`.ax-dropdown` chrome (trigger with a lead icon showing the current option, `role="listbox"`
panel of `role="option"` rows each with a lead icon), **not** a native `<select>`, reusing
`ui/static/dropdown.js`'s listbox behaviour. Options: Light, Dark, Use system setting — **the
mock's fourth "Dagster Indigo" option is dropped** per the resolved clarification. `settings.js`
opens the modal into `#ax-modal-root`, moves focus in and traps Tab, and on close returns focus
to the Settings foot link. Escape closes an open dropdown **panel first**, then (second Escape,
no open panel) the modal; Done and backdrop click also close, with no Save step. Choosing an
option applies the theme immediately (stamp/clear `data-theme` on `<html>`) and writes
`localStorage["agentbox.theme"]`.

**Rationale.** The mock (`tabbed-list/Sidebar.dc.html`) renders the theme control with the
`.ax-dropdown` listbox chrome and a per-option lead icon — a native `<select>` can't show
per-option icons or the trigger glyph (FR-007). Reusing `dropdown.js` keeps one keyboard model
(spec 002) and satisfies the manifest⇄macro rule (Dropdown is a form of Select — FR-025, no new
component). The theme-accessibility assertion moves here from the removed foot radiogroup
(FR-003).

**Alternatives rejected.** *Native `<select>`* — no per-option/trigger icons; loses the mock's
look. *Three radio buttons in the modal* — FR-006/007 specify a single dropdown row.

## R6 — Shared cron-to-text helper and where columns render (FR-016, FR-019)

**Decision.** Add **one shared server-side helper** (`ui/cron_text.py`, exposed to Jinja) that
turns a cron expression into a human-readable label ("Every day at 7:00 AM") in the box's
timezone. The **Schedules/Sensors cell renders server-side** (column 5): the store already
holds each agent's crons, so the pills, type-driven icon, and label ship with first paint. Only
the **toggle's on/off state** (instigation) is Dagster-derived and fills after paint. Latest run
(6), Checks (7), Run history (8) are entirely Dagster-derived and fill after paint.

**Rationale.** Resolves the apparent tension between FR-019 ("columns 5–8 filled after first
paint") and the edge case ("ships columns 1–5 live"): the cell's *content* (crons → text) is
store data and renders live; its *toggle state* is the only run-derived part and fills with the
activity read. One shared helper satisfies FR-016 ("via one shared cron-to-text helper") and
keeps the label identical wherever a schedule is shown. Server-side keeps it out of the
offline-fragile client path.

**Alternatives rejected.** *Client-side cron parsing* — duplicates logic, risks egress (a cron
lib), and would delay the label to after paint. *A heavyweight cron library* — a bounded helper
covers the daily/weekly patterns the box uses; note timezone comes from box config, not the
browser.

## R7 — After-first-paint fetch and toggle endpoints (FR-019, FR-020, US4)

**Decision.** Two new endpoints in `ui/main.py`, plus `ui/static/agents-list.js`:
- `GET /api/agents/activity` → `{"reachable": bool, "agents": {"<name>": {latest_run,
  history[], checks[], schedules:{"<name>": {running|null}}}}}`, built from
  `dagster.activity(...)`. Always **200** (the outcome is data, like `/api/dagster/status`).
  When `reachable` is false the front end shows the "Run data unavailable: Dagster is not
  reachable" warning and leaves columns 6–8 as em-dashes / pills disabled.
- A **POST toggle** endpoint (e.g. `POST /api/schedules/toggle` with `{name, kind, running}`) →
  `dagster.set_instigation(...)`; returns the new state or the disabled-degradation signal.

`agents-list.js` also owns tab/filter/show-disabled narrowing (client-side), `?tab=` URL sync
(default All, survives reload), and reading/writing the show-disabled `localStorage` flag.

**Rationale.** Matches the existing `/api/dagster/*` "always 200, outcome is data" convention and
keeps the page renderable when Dagster is down (FR-020, SC-002). Client-side narrowing over
server-rendered rows keeps the URL shareable and avoids a server round trip per tab click.

**Alternatives rejected.** *Server-side re-render per tab* — loses instant client narrowing and
shareable state without reload. *Folding activity into the page GET* — reintroduces the
Dagster dependency on first paint.

## R8 — Automation page removal (FR-022)

**Decision.** Remove the page (`templates/automation/list.html`), script
(`static/automation.js`), store (`automation_store.py`), routes (`GET /automation`, `GET/PUT
/api/automation`) and their `automation_store`/`AutomationError` imports in `main.py`, the nav
item in `base.html`, and the Automation-only tests (`test_automation_store.py`,
`test_migrate_automation.py`) plus the two automation assertions inside
`test_ui_consistency.py`. **Keep** the `schedule_pill` macro and the schema's
`asset_schedule`/`job_schedule` fields — they are shared with the agent form's Triggers section
and the new list, not Automation-owned.

**Rationale.** The clarification confirmed schedule editing already lives in the agent form's
schema-driven Triggers block, so removing the standalone page loses no function (FR-022). The
explore inventory confirmed the shared surface (`schedule_pill`, trigger fields) so removal
stays scoped.

**Alternatives rejected.** *Leave the page as a dead nav link* — FR-001 forbids dead/placeholder
links; the page duplicates the form's Triggers section.
