# Contract: UI — Automation page + shared shell/dropdown/notice

Governs `ui/main.py`, `ui/automation_store.py`, `ui/static/automation.js`,
`ui/static/agent-form.js`, `ui/static/app.css`, `ui/templates/*`, and the reuse of
`ui/static/dropdown.js` and `ui/static/shell.js`. Companion: [agent-model.md](agent-model.md).

## §1. Agent form — Asset card + Job card (US1)

- Two independent cards, each gated by its own checkbox:
  - **Asset card** — checkbox "make agent an asset". When on: the Produces fields (asset key,
    partition) are enabled and the asset key is required (FR-002); an **asset schedule** cron
    field (`asset_schedule`) is enabled and optional (FR-003). When off: Produces + asset
    schedule are disabled and no `produces` block is written.
  - **Job card** — checkbox "create agent job". When on: `job: true` is written and a **job
    schedule** cron field (`job_schedule`) is enabled and optional (FR-004). When off: no job.
- The two are independent; a client-side hint warns when neither is ticked, but the **server is
  the authority** — `POST/PUT /api/agents` rejects neither-ticked with the nature-invariant
  message (agent-model §3, FR-005). Rendered by `agent-form.js` into the existing form mounts;
  no new server-rendered fields required.

## §2. Automation page — per-kind rows, grouped (US3)

### `GET /api/automation`

Returns `{"agents": [ row, … ]}`. Each **agent** contributes an object carrying its kind(s) and
one entry per applicable schedule:

```json
{
  "name": "list-commits-pi-kimi",
  "harness": "pi",
  "enabled": true,
  "kinds": ["asset"],
  "schedules": [
    { "kind": "asset", "cron": "20 17 * * *", "fallback": false }
  ]
}
```

- `schedules` holds an `asset` entry iff the agent is an asset, a `job` entry iff it has a job,
  or both for a both-kind agent (FR-017). `cron` is null/absent when that schedule is on-demand.
- `fallback: true` on an `asset` entry marks that the partition Null-Action fallback was applied
  (orchestrator-model §4, FR-015) — rendered as a visible marker on that row.
- Templates (`_`-prefixed) are excluded (unchanged).

### `PUT /api/automation`

Body: `{"triggers": { "<name>": { "asset_schedule"?: "<cron>|null", "job_schedule"?: "<cron>|null" }, … }}`.
- Validates each cron's shape and that the schedule matches the agent's kind (asset_schedule
  only for assets, job_schedule only for jobs), reusing the schema/cron rules; a rejection names
  the offending agent+field (400, `{"error":"validation","fields":{…}}`).
- Writes each change **onto the agent definition** via `agents_store` (the `triggers` block),
  **not** a separate store — editing one schedule leaves the other untouched (FR-020). Then
  reloads Dagster and returns the shared reload shape `{ok, message, reload}`.
- Removes the old `automation/migrated.yaml` writer; `automation_store.write` now edits
  `agents/*.yaml`. `per_agent_view` reads triggers off each agent file.
- **Scope**: this page edits only cron presence (on-demand ↔ cron / the `triggers:` block).
  A trigger's paused/running (on/off) state is Dagster instigator state — preserved by name
  across reloads (FR-012) and toggled in the Dagster UI, not here.

### Rendering (`automation.js`)

- One visual group per agent; a both-kind agent shows its asset-schedule row and job-schedule
  row grouped together as one unit (FR-019).
- Each row: a trigger `<select>` (on-demand / cron) + a cron input + a reserved warning slot.
- **Shared dropdown (§4)**: every row `<select>` has `class="ax-select"` and is enhanced via
  `dropdown.enhanceSelects` after rendering (and for any dynamically added rows).
- **Shared notice (§5)**: save/reload/error notices use `shell.showStatus`, not a bespoke
  banner.
- The partition-fallback marker renders on the asset row when `fallback` is true, with a
  tooltip explaining the fallback.

## §3. App shell — fixed sidebar + pinned top bar, responsive (US4)

`app.css` + `base.html`:

- `.ax-app` uses `height: 100dvh` so the grid fills the viewport and does not grow the page.
- `.ax-sidebar` gets `overflow-y: auto` (its own scroll) and stays fixed by the fixed-height
  grid column (FR-023).
- `.ax-topbar` is `position: sticky; top: 0` above `.ax-content` (FR-024); `.ax-content` remains
  the sole scroller (`overflow-y: auto; flex: 1`).
- One viewport media query `@media (max-width: 640px)` collapses `.ax-app` to a single column,
  renders the sidebar as a non-overlapping top strip, and keeps the top bar sticky — nothing
  overlaps or hides content at phone width (FR-025/SC-006).

## §4. One shared dropdown (FR-026/SC-004)

- `dropdown.js` `enhanceSelect(s)` is the only dropdown implementation. Every `<select>` in the
  app is enhanced through it — the agent form already does; the Automation page now does.
- No raw `<select>` may remain to be restyled later. A test asserts no `ax-select` select goes
  un-enhanced and no page renders a bespoke dropdown.

## §5. One shared notice + reserved warning space (FR-021/022/027/SC-005/SC-007)

- `shell.js` `showStatus`/`flashStatus`/`toast` is the only notice pattern. The Automation
  page's `#ax-automation-banner`/`.ax-banner` **save notice** is removed; the Automation save
  notice is now pixel-identical to the agent-save notice (rendered in `#ax-status-region`).
- The cron-shape warning slot (`.ax-field-error` under each cron input) reserves a fixed
  one-line `min-height` so toggling it never reflows the row (SC-007). (The `.ax-banner` class
  may remain in CSS only if still used for a non-notice inline element; it must not be the save
  notice.)

## §6. Test surface

- `/api/schema` includes the `job` field and the `triggers` block fields; the form renders the
  two cards.
- Automation page: grouped rows per agent, correct rows per kind, shared dropdown, shared
  notice, reserved warning space; `GET/PUT /api/automation` round-trip including per-kind
  validation and writing back to `agents/*.yaml`.
- Consistency grep test: no raw `<select>` outside the shared-component path; no `.ax-banner`
  used as a save notice (SC-004/SC-005).
