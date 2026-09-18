# Phase 0 Research: Runs Overview Page

Decisions that resolve the plan's Technical Context. Each is **Decision / Rationale / Alternatives
considered**. No open `NEEDS CLARIFICATION` remains. Where the spec left a choice unattended, the
default chosen is stated and noted back in [plan.md](./plan.md) → *Planning decisions*.

## R1 — Where and how true status is joined (server-side, best-effort, before partition)

**Decision**: Enrich the disk-derived run list from Dagster **server-side** during `GET /runs`,
with a single batched GraphQL read (see R6), computed over the whole text-/agent-/date-filtered set
**before** the tab partition and pagination. Enrichment supplies each run's true status, Target,
Launched by, and Checks; on Dagster timeout/HTTP/parse failure, or for a run id Dagster has no
record of, that row falls back to the local `report.json` status and is marked **last-known**
(FR-002, FR-003). To keep a single render bounded on a very large history, enrichment (and thus the
truthful tab counts) is capped at the most recent **N = 500** runs of the filtered set; any older
rows are shown last-known and the cap is surfaced (a visible note), never silently truncated. This
surfacing is a requirement — **FR-035** — rendered by **T045** (A3); it is not left implicit.

**Rationale**: Tab membership and the count badges are defined over the filtered set *before*
partition (FR-005/FR-006, clarifications). If status were enriched only client-side after paint, the
first-paint partition and counts would use self-reported disk status — exactly the "everything is
`ok`" bug the feature exists to kill (US1). Doing it server-side makes the very first render
truthful. The existing agents-list pattern already proves a bounded, best-effort Dagster read that
degrades cleanly (`dagster.activity`); this mirrors it. The N-cap keeps the Pi single-box render
predictable while the 30-per-page view and newest-first ordering mean the visible page is always
within the enriched window.

**Alternatives considered**:
- *Client-side enrichment via `/api/runs` after paint* (like agents columns 6–8): rejected because
  tab partition + counts must be truthful on first paint, and partitioning client-side would reflow
  the table and badges on every load. Kept as the **refresh** path only (the JS re-queries for live
  updates without a full reload).
- *No cap, enrich every filtered run*: rejected — an unbounded history would make one render
  proportional to total runs. The 500-cap with a visible note is a safe, honest bound.
- *Persist Dagster status onto disk*: rejected — violates the read-path-only scope and *Ephemeral
  Runs, Immutable Outputs*; the spec forbids run-record changes.

## R2 — Join key and the Dagster deep link

**Decision**: The join key is the **run id**. The run-directory name
(`runs/<agent>/<date>/<run-id>/`) is `context.run_id`, which is the Dagster run id (verified in
`orchestrator/run_capture.py` and `factory.py:1249`, where `RunCapture(name, stamp[:10],
context.run_id)` names the directory). The overview reads run ids from `runs_store`, batches them
into one Dagster read, and matches responses by `runId`. The per-row Dagster deep link is
`{public_dagster_url}/runs/{run_id}` opened in a new tab (`target="_blank" rel="noopener"`),
right-justified in the Run column as an indigo link icon. When Dagster is not configured the icon is
**not rendered** (no dead link) — FR-022/FR-024.

**Rationale**: A direct id match needs no extra correlation data and reuses the browser-facing base
URL already computed by `public_dagster_url(request)` and threaded as `dagster_url` (the same base
the Agents list uses for `data-runs-base`). "Not configured" is the same condition the shell already
treats as unreachable/absent Dagster.

**Alternatives considered**: correlating by agent+timestamp (fragile, ambiguous for bursts) —
rejected; the id is exact and already present.

## R3 — Text filter semantics

**Decision**: The `q` text filter matches a **case-insensitive substring** against **agent, model,
target, and run id** (FR-009, clarification). Agent, model, and run id come from the disk row;
target participates only for rows where enrichment supplied it (an em-dash target never matches).
Matching is applied server-side (for first paint and shareable URLs) and mirrored client-side in
`runs-list.js` for instant narrowing, exactly as the Agents overview filters its rows.

**Rationale**: Matches the clarified requirement and the Agents overview's single-field
"filter-as-you-type" model, so the two overviews "read as one system" (US2). Substring (not prefix)
matches operator expectation of a quick find box.

**Alternatives considered**: per-field filter inputs (heavier UI, diverges from Agents overview) —
rejected; the single ghost-Filter text box is the established pattern.

## R4 — Settings consolidation (staged, per FR-031)

**Decision**: Remove the **Settings** item from the primary nav; the **single** Settings entry is
the foot button that opens the user-settings modal (already present in `base.html`). Keep the
`GET /settings` route as an **unlinked** page so the modal can link to it for the server-backed
Retention + Governors controls (FR-031's staged path). Full consolidation of those controls into the
modal is **deferred**.

**Rationale**: The foot modal today carries only the Theme preference (client-side localStorage).
The `/settings` page carries Retention and Governors, which POST to `/api/settings/retention` and
`/api/settings/governors` and render server state — moving them into the modal is materially more
than relocating controls, which FR-031 explicitly allows deferring. Shipping the nav tidy now with
the modal linking to the existing page satisfies FR-030/FR-031 without a risky settings rewrite in a
presentation-focused feature. "Exactly one Settings entry in the nav" is met: the foot button is the
one entry, and `/settings` is no longer a nav destination.

**Alternatives considered**: full move of Retention + Governors into the modal now — rejected for
this feature's scope; it risks the settings POST flows and their tests for no gain to the Runs
overview. Tracked as a follow-up.

## R5 — Pagination as a design-system component (FR-034)

**Decision**: Add a **Pagination** component to the design system *first* — component source under
`ui/design-system/components/navigation/Pagination.jsx` with a specimen card, registered in
`_ds_manifest.json`, rebuilt into `_ds_bundle.js`, and documented in `readme.md` — then expose a
shared `pagination(...)` Jinja macro in `components/macros.html`, and only then use it on the Runs
page. It renders Prev / page indicator / Next as token-styled controls composed from the existing
button treatment; page state is a link/`?page=` so it works without JS and syncs via
`runs-list.js`.

**Rationale**: Principle VII is explicit — a new component lands in the design system first and the
shared macro second; FR-034 restates it for pagination specifically. The manifest/bundle/readme
trio is exactly what `test_design_system_sync.py` and `test_design_system_docs.py` verify, so the
component must be registered there or the suite fails (SC-009).

**Alternatives considered**: hand-rolled pagination markup on the Runs page only — rejected; it
violates VII/FR-034 and would fail conformance.

## R6 — The Dagster read: fields, batching, and degradation

**Decision**: Add `dagster.run_status(run_ids)` performing **one** GraphQL POST:
`runsOrError(filter: {runIds: [...]}, limit: N)` selecting, per run: `runId`, `status`, `startTime`,
`endTime`, the **Target** (from `assetSelection { path }` for an asset materialization, else the
job/`pipelineName`), the **Launched by** source (from run `tags` — `dagster/schedule_name`,
`dagster/sensor_name`, else a manual launch), and **Checks** (the run's asset-check evaluations,
mapped to the shared check-status vocabulary the Agents overview uses via the existing
`_check_status` helper). Any transport/HTTP/parse failure, or a `PythonError`/non-`Runs` arm,
returns `{"reachable": False, "runs": {}}`, so the caller falls back to last-known for every row.
Status strings map to the presented tab states and the existing run-status-tag intents through a
single mapping table (see [data-model.md](./data-model.md)).

**Rationale**: Mirrors `dagster.activity`'s proven shape — one bounded, aliased/batched read whose
failures are plain data — so the overview never sees an exception from a reachable-or-not Dagster
(the module's contract). Selecting Target/Launched by/Checks in the same read avoids N extra calls.
The check-status mapping already exists (`dagster._check_status`) and the Agents overview's Checks
column renders it, satisfying FR-016 "the same way."

**Alternatives considered**:
- *Reuse `pipelineRunsOrError` per pipeline* (as `activity` does for history): rejected here — the
  overview wants specific known run ids, and `runsOrError(filter:{runIds})` fetches exactly those in
  one call regardless of which pipeline launched them.
- *Separate reads for status vs checks*: rejected — one read with all selected fields is fewer round
  trips and matches the module's "one bounded read" convention.

## R7 — Created / Duration formatting

**Decision**: **Created** is a single local-time label `Sep 17, 1:15 PM` (`%b %-d, %-I:%M %p`) with
the full ISO timestamp on `title=` hover (FR-017, SC-005). **Duration** is elapsed run time computed
at render: `endTime − startTime` for a finished run, `now − startTime` for an in-progress run (no
live per-second ticker; advances on refresh — FR-018, clarification). When start/end are unknown the
cell shows `—`. Cost shows `—` for a null/absent cost, never `0` (FR-019), reusing the existing
`_fmt_cost` em-dash-for-null rule.

**First paint vs. browser timezone** (A8): the server has no browser timezone at first paint, so each
row carries a **machine-readable timestamp** (the `started` epoch / `created_iso`, data-model) in a
data attribute *and* a server-rendered fallback label. `runs-list.js` re-localises that timestamp to
the browser's timezone on load, replacing the server label. SC-005's exact literal `Sep 17, 1:15 PM`
is therefore evaluated in the operator's local timezone (the environment under test). This keeps the
"truthful on first paint" goal (R1 — status/counts/partition are server-computed) and the
operator-local timestamp requirement (FR-017) from conflicting: only the timestamp *presentation* is
localised client-side; nothing about status or ordering depends on it.

**Rationale**: Matches FR-017/FR-018/FR-019 and SC-005 exactly. Local-time formatting is done in the
template/JS against the browser's timezone; the disk row already carries a `started` epoch, and
Dagster start/end refine it when enrichment is present. Reusing `_fmt_cost` keeps the em-dash-vs-zero
distinction consistent with the run detail page.

**Alternatives considered**: server-rendered UTC only (wrong tz for the operator) — rejected;
FR-017 requires the operator's local time. A live ticker — explicitly not required (clarification).

## R8 — Status vocabulary and the tab partition

**Decision**: Normalise Dagster's `RunStatus` (`QUEUED`, `NOT_STARTED`, `STARTING`, `STARTED`,
`SUCCESS`, `FAILURE`, `CANCELED`, `CANCELING`) and the local report statuses (`ok`, `failed`,
`timeout`, `running`, `unknown`) into one presented status set: **succeeded, failed, timed out,
cancelled, queued, in progress, unknown**. The tab partition (FR-005) is then:

- **In progress** = in progress **or** queued (Dagster `STARTED`/`STARTING`/`QUEUED`/`NOT_STARTED`;
  local `running`).
- **Succeeded** = succeeded (`SUCCESS`; local `ok`).
- **Failed** = all non-success terminal states: failed, timed out, cancelled (`FAILURE`/`CANCELED`;
  local `failed`/`timeout`).
- **All** = every run. A run whose status is **`unknown`** (a fallback state — local `unknown`/missing
  and no Dagster record) counts in **All only**, in none of the three sub-tab badges, so
  `all ≥ in_progress + succeeded + failed` (matches data-model, contract §D, FR-005).

Colours/labels reuse the existing run-status-tag intents (FR-004): success → success, failed/timed
out/cancelled → failure/error, in progress → running, queued → the `run_status_tag` `queued` status
(which renders the neutral gray **idle** dot — see clarification A1), unknown → idle. A last-known
row keeps its intent and adds a visible last-known marker (a badge/`title`), so a stale status is
never mistaken for a live one.

**Rationale**: One normalisation table keeps Dagster's richer vocabulary and the local report
vocabulary rendering through the same intents (FR-004) and makes the partition rule (FR-005 +
clarification) a pure lookup. `timeout`/`canceled` folding into Failed matches the clarified "all
non-success terminal states."

**Alternatives considered**: a fifth "Queued" tab — rejected; the clarification folds queued into In
progress and the spec fixes the four-tab set.
