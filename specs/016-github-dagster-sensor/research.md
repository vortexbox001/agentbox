# Phase 0 Research: GitHub Project Status Trigger — Board-Driven Agent Launches

Decisions resolving the Technical Context unknowns. The feature extends existing surfaces (spec 006
`triggers` + the paused per-agent sensor, spec 013 the read-only handoff + governors + automated-run
lineage, spec 007 run reports/redaction), so most groundwork is carried forward; the new decisions
concern how a **polling** sensor reads a GitHub Projects board, keeps a durable cursor, admits
launches one-at-a-time, and hands the issue to a run.

**Unattended note**: `/speckit-plan` ran with no human to answer questions. Every choice a clarifying
question would have raised is decided here against the spec + repo and called out as **Decision
(unattended)**; the spec's own Clarifications (2026-09-17) already resolved the five product-level
questions (empty-slug key, 256-char title cap, per-agent slot, `owner/repo` filter, drop-not-
transliterate slugging).

---

## R1 — A custom polling `SensorDefinition`, not an automation condition (FR-003)

**Decision (unattended)**: Build a genuine Dagster `SensorDefinition` (via `@dagster.sensor` /
`SensorDefinition`), one per agent carrying the block, named `project_status_<name>`,
`default_status=DefaultSensorStatus.STOPPED`, `minimum_interval_seconds` from the block. On each tick
it makes outbound GitHub calls, reads its cursor, decides launches, emits `RunRequest`s, and calls
`context.update_cursor`.

This is deliberately **not** the spec-013 `on_upstream`/`on_missing` path. Those ride
`AutomationConditionSensorDefinition` (`factory.build_asset_automation_sensor`), which is evaluated by
Dagster against the **asset graph's own state** — it cannot issue an outbound HTTP request, hold an
external cursor, or key runs off an external event. A board trigger's whole job is to poll an external
system and fire once per external transition, which is exactly what a custom sensor with `cursor` +
`run_key` is for.

**Rationale**: The custom sensor is the only Dagster surface that can (a) call out to GitHub, (b)
persist a cursor across ticks and restarts, and (c) dedupe launches by run key. It reuses the same
STOPPED-by-default, per-agent, name-preserving posture as the existing `autocond_<name>` sensor so the
operator toggle model is unchanged (FR-025).

**Alternatives considered**: *An `AutomationCondition`* — rejected: no outbound calls, no external
cursor. *A schedule that runs a job that polls* — rejected: a schedule cannot emit run-keyed dedup,
would need its own ledger, and would not appear as a sensor the operator toggles. *A single global
board sensor for all agents* — rejected: FR-003 mandates one dedicated sensor per agent, and the
per-agent slot (FR-008) is per sensor.

## R2 — Reading the board: GitHub Projects v2 over GraphQL, Status by option name (FR-001/FR-004/FR-021)

**Decision (unattended)**: Read the board with a single GraphQL query against `api.github.com/graphql`
(Projects v2 lives only in GraphQL; the REST API does not expose it, matching the spec's premise).
Resolve the board by `organization(login: $owner).projectV2(number: $project)` with a documented
fallback attempt to `user(login: $owner).projectV2(...)` (spec Assumption "Board ownership"); page
through `items(first: 100, after: $cursor)` following `pageInfo.hasNextPage` (FR-021). For each item
read `content { __typename ... on Issue { number, title, body, url, repository { nameWithOwner },
labels } ... on PullRequest {…} ... on DraftIssue {…} }` and the item's Status via
`fieldValues(... on ProjectV2ItemFieldSingleSelectValue { name, field { name } })`.

- **Status match**: case-insensitively against the single-select **option name** the operator wrote
  in `status` (spec Assumption "Status matching" — readable, but breaks if the column is renamed;
  accepted, and a rename surfaces as an "unresolvable status option" skip, R8).
- **Issue-only**: keep only `content.__typename == "Issue"`; PRs and drafts are dropped before
  admission so they neither launch nor hold the slot (FR-004 / US4 #3).
- **Filters**: optional `label` (issue carries it) and optional `repo` (`repository.nameWithOwner`
  equals the configured `owner/repo`, case-insensitively — spec clarification).
- **Token**: `Authorization: Bearer $GITHUB_PROJECT_TOKEN` (R7).

**Rationale**: GraphQL is the only interface that exposes Projects v2 items + their Status; a single
query per board keeps the tick cheap and lets several sensors on one board share it (R8). Matching by
option name is what the operator wrote in YAML and is human-auditable.

**Alternatives considered**: *REST* — impossible for Projects v2. *Matching by opaque option id* —
rejected by the spec Assumption (unreadable in YAML), at the documented cost of rename-fragility.
*Server-side filtering by status* — Projects v2 has no such server filter; filtering is client-side
over the paged items.

## R3 — Cursor shape, eligibility, and the run key (FR-005/FR-006/FR-007)

**Decision (unattended)**: The cursor is a JSON object persisted via `context.cursor` /
`update_cursor`, mapping the durable **project item id** to `{entered_at, launched}`:

```json
{"version": 1, "seen": {"<item_id>": {"entered_at": "<iso8601>", "launched": true, "eligible": true}}}
```

Per tick, over the set `S` of item ids currently in the target status (issues passing filters):

1. **First tick** (no cursor, or after a reset): seed `seen` with every id in `S` as
   `{entered_at: now, launched: false, eligible: false}` and **launch nothing** — pre-existing items
   are recorded seen-and-**not**-eligible, so they are never admission candidates on a later tick
   (FR-007 / US2 #4). (Kept distinct from a normal tick by "cursor was empty".)
2. **Normal tick**: an id in `S` **not** in `seen` is a new entry → add `{entered_at: now,
   launched: false, eligible: true}` and mark it **eligible**. An id in `seen` but no longer in `S`
   has **left** the status → drop it from `seen` (so a later re-entry is a fresh new entry with a new
   `eligible: true`, FR-005 / re-entry edge). An id in both carries its stored
   `{entered_at, launched, eligible}` unchanged. Admission considers only `launched: false && eligible: true`
   ids, so a seeded item never launches and a held item launches when the slot frees (F1 resolution).
3. **Run key** for a launch = `f"{item_id}:{entered_at}"` (FR-006). Dagster remembers run keys per
   sensor, so a repeated tick or a daemon restart with the same `(item, entered_at)` never
   double-launches. `entered_at` changes on re-entry, so re-entry gets a new key and launches again.

Restart safety is doubly guaranteed: the cursor persists under `$DAGSTER_HOME` (so `launched: true`
survives), and the run-key ledger persists independently.

**Rationale**: Tracking first-seen time + launched flag per in-status item is the minimal state that
expresses "fire once per entry", "suppress the pre-existing set on first start", and "forget on
leave". The `<item_id>:<entered_at>` key ties dedup to the *entry event*, which is exactly the grain
FR-006 asks for.

**Alternatives considered**: *Keying runs on item id alone* — rejected: re-entry would never
re-launch (FR-005). *Keying on a tick timestamp* — rejected: a repeated tick would double-launch.
*Storing the whole board in the cursor* — rejected: only the in-status item ids + entry time + launched
flag are needed; the board is re-read each tick.

## R4 — One feature in flight per agent, released by the board (FR-008/FR-009/FR-010)

**Decision (unattended)**: The slot is computed purely from the current board + cursor, with **no run
state query** (US3 #4 — a stuck downstream is released by moving the card, not by any completion
signal):

- **Held?** The slot is occupied while any `seen` id with `launched: true` is still in `S` (the
  launched issue is still in the status ⇒ "active", FR-008). The active issue holds until it leaves.
- **Admission**: among eligible ids (new this tick) plus any previously-eligible-but-held ids that
  are still in `S` and not launched, if the slot is free, launch the **oldest by `entered_at`**
  (FR-010) and set its `launched: true`; the rest are **held** and reported (FR-009), the skip reason
  naming the holding issue. If the slot is occupied, launch nothing and hold all eligible.
- **Release order**: because release frees exactly one slot per tick and admission always takes the
  oldest, three issues that entered while one was active launch one-at-a-time oldest-first across
  successive ticks (US3 #3).

The slot is **per agent** (per sensor) — each sensor's cursor is independent, so two board-driven
agents may each have one issue active (spec clarification / FR-008).

**Rationale**: The board is the single source of truth for "active", so the slot is a pure function of
the board query + cursor — no coupling to Dagster run status, no knowledge of the downstream chain
(US3 #4). This is what lets the MVP ship on a single shared workspace/branch.

**Alternatives considered**: *Releasing the slot when the launched run finishes* — rejected by FR-010
/ US3 #4 (a stuck run would wedge the queue; release must come from the board move). *A global slot
across agents* — rejected by the spec clarification (per-agent).

## R5 — Handing the issue to the run (FR-012/FR-013/FR-014/FR-015)

**Decision (unattended)**: Split the identity across `RunRequest` metadata and reuse the spec-013
handoff for the body:

- The sensor emits `RunRequest(run_key, tags={…}, run_config={…}, <target>)` where **tags** carry the
  five small identity fields — `agentbox/issue_number`, `agentbox/issue_repo` (full `owner/repo`),
  `agentbox/issue_url`, `agentbox/project_item_id`, `agentbox/feature_key` (FR-012) — so the run
  carries them from creation and the run page can link the issue (FR-026). **`run_config`** carries
  the issue payload `{number, repo, url, title, feature_key, body}` for the op to consume (Dagster run
  storage — never a command line or env value). Title and body are placed in `run_config` **only**,
  never in a tag (FR-015: title/body are data, not tags).
- The op gains an optional `issue` config field. A new `_prepare_issue_handoff(cfg, context)` — the
  twin of spec-013's `_prepare_upstream_handoff` — reads that payload, writes the **body** to
  `<handoff_dir>/body.md` (`chmod 0644`) in a `tempfile.mkdtemp` under `STAGING_ROOT` (host==container,
  `chmod 0777`, `--rm`-cleaned), and returns `(handoff_dir, env_map)`. `env_map` sets
  `AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_ISSUE_REPO`, `AGENTBOX_ISSUE_URL`, `AGENTBOX_ISSUE_TITLE`
  (control-stripped, ≤256, FR-015), `AGENTBOX_FEATURE_KEY`, and `AGENTBOX_ISSUE_BODY_FILE=/issue/body.md`.
- Wiring reuses the existing path: the dir is mounted `:ro` at `/issue` via `_launch_mounts`
  (`{source, target: "/issue", mode: "ro"}`, FR-013), and `env_map` is merged into the launch exactly
  as `upstream_env` is in `make_run_op`. The **body never** goes on the command line or into an env
  value (FR-014) — only its path does.
- Per-kind launch (FR-002): for an **asset-kind** agent the `RunRequest` carries
  `asset_selection=[AssetKey(...)]` so it records a materialization (the same way `dagster.py:launch`
  materializes assets); for a **job-kind** agent it carries `job_name=f"agent_{name}"` (the same job
  the UI runs). This is the launch distinction the UI already makes.

**Rationale**: Tags are the right home for the small, indexable identity fields the run page needs;
`run_config` is the right transport for the variable-size title/body (kept out of tags/command lines);
the read-only file + `:ro` mount is the exact spec-013 mechanism the spec's "handoff reuse" assumption
calls for, enforcing read-only at the Docker layer. Splitting title/body from tags satisfies FR-015's
"title and body are data, never substituted into … tags".

**Alternatives considered**: *Putting the body in a tag or env value* — rejected by FR-014/FR-015.
*The sensor writing the body file directly to the data root and passing a path tag* — rejected: it
couples observation to data-root writes and adds durable state to clean up; `run_config` + the
existing op-side handoff is cleaner and matches spec 013. *Fetching the body inside the agent* — the
spec's null-action fallback only; rejected while the handoff reuse works cleanly.

## R6 — The pure feature-key and title functions (FR-011/FR-015)

**Decision (unattended)**: Two pure helpers in `github_projects.py`, no configuration:

- `feature_key(number, title)`: `f"{number:03d}"` + (`""` if the slug is empty else `"-" + slug`),
  where `slug` lowercases the title, keeps only `a-z0-9`, collapses every other run (punctuation,
  whitespace, dropped non-ASCII/emoji) to a single `-`, strips leading/trailing `-`, then truncates
  the **whole key** to ≤48 chars and strips any resulting trailing `-`. Non-ASCII letters and emoji
  are **dropped**, not transliterated (spec clarification). Empty slug ⇒ `NNN` alone, no trailing
  hyphen (spec clarification; e.g. issue 38 → `038`). Same title, different number ⇒ different key.
- `sanitize_title(title)`: strip control characters, then truncate to ≤256 chars → the
  `AGENTBOX_ISSUE_TITLE` value (FR-015). Independent of the 48-char key cap.

Both are pinned by test vectors: `038-ui-update-runs-overview-page`; punctuation/emoji/`..`/200-char
titles all matching `^[0-9]{3}(-[a-z0-9]+)*$` with total length ≤48; two same-title issues differing
by number.

**Rationale**: A pure function of the issue guarantees the same issue always yields the same key
(SC-007) and that #22 (substitution) and #24 (partition key) inherit a stable grammar. Dropping
non-ASCII keeps the key filesystem- and URL-safe without a transliteration dependency.

**Alternatives considered**: *Transliteration (`é`→`e`)* — rejected by the spec clarification.
*Capping the slug before prefixing* — rejected: the cap is on the whole key so `NNN-` always fits.

## R7 — Token isolation and redaction (FR-016/FR-017)

**Decision (unattended)**: The sensor reads `os.environ["GITHUB_PROJECT_TOKEN"]` and nothing else —
**no** fallback to `GITHUB_TOKEN`. If it is unset/empty the tick is a `SkipReason` naming the missing
`GITHUB_PROJECT_TOKEN` (FR-016 / US6 #1). The token is used only to sign the outbound GraphQL request
from the daemon; it is **never** placed in a `RunRequest` tag, `run_config`, env value, log line, or
file (FR-017). It rides through the existing `redact` on any captured surface (the `github_pat_` /
`ghp_` / `gho_` prefixes and the `*TOKEN*` name rule are already in `orchestrator/redact.py`), so even
an accidental appearance is masked. `.env.example` documents `GITHUB_PROJECT_TOKEN` (board read scope)
as sensor-only.

**Rationale**: A dedicated variable with no fallback makes the broad-scoped board token impossible to
confuse with the per-run `GITHUB_TOKEN`, and keeping it in the daemon process only means no agent ever
sees it — the security requirement of US6. Redaction is defence in depth.

**Alternatives considered**: *Falling back to `GITHUB_TOKEN`* — rejected by FR-016 (explicit, no
fallback). *A mounted credential file* — unnecessary; the daemon already receives env passthrough and
the token must never reach a run.

## R8 — Resilience: skip-with-reason, pagination, shared query (FR-019/FR-020/FR-021)

**Decision (unattended)**: Every failure is a **skip that leaves the cursor untouched**, so nothing is
lost or re-fired:

- **Transient** (HTTP error, GraphQL error, `403`/`429` rate-limit, timeout): the client raises a
  typed error; the sensor catches it, emits `SkipReason(<reason>)`, and **does not** call
  `update_cursor` (FR-019 / US7 #1). The next tick retries from the unchanged cursor.
- **Unresolvable** (board number not found, `status` option absent on the board, Status field
  missing): the client raises `Unresolvable(what)`; the sensor skips with a message naming what was
  not found (FR-020 / US7 #2). One agent's bad board never crashes the daemon or other sensors — the
  error is caught per tick, not raised out of the sensor.
- **Pagination**: the client follows `pageInfo.hasNextPage` to completion so items beyond the first
  page count (FR-021 / US7 #3).
- **Shared query**: a process-local cache in `github_projects` keyed by `(owner, project)` with a
  short TTL (a few seconds) memoises one board fetch, so several sensors ticking near-simultaneously
  on the same board reuse it (FR-021 / US7 #4). Best-effort — documented; correctness never depends
  on a cache hit.

**Rationale**: A polling sensor lives with transient GitHub failures and operator typos; making every
one a cursor-preserving skip is what keeps it usable (US7). Catching inside the sensor honours the
resilient-loader invariant (one bad agent costs only itself).

**Alternatives considered**: *Letting an error propagate out of the sensor* — rejected: it would fail
the tick loudly and risk re-firing/`update_cursor` skips. *A shared background poller feeding all
sensors* — heavier than a short-TTL memo and would break the one-sensor-per-agent model; deferred.

## R9 — Load-time validation as a per-agent reject (FR-023)

**Decision (unattended)**: In `definitions.discover()`, a new `_project_status(cfg)` reads the block
and validates it as the structural backstop for hand-edited files: `owner`, `project`, `status`
required; `project` a positive integer; `interval_seconds` (if present) an integer ≥30. A malformed
block raises the existing `RejectAgent(file, message)` naming the file and offending field — the same
skip-and-log path `depends_on`/`checks` use — so that one agent fails to load while every other agent
loads (US8). The UI's `schema.validate` is the author-time twin (R10). A valid block builds the sensor
and composes with the agent's other triggers (FR-002, "composes rather than replaces").

**Rationale**: Matches the established resilient loader and the `depends_on`/`checks` validation style
the spec explicitly asks to mirror; a bad new block must not regress the one-bad-file-costs-only-
itself guarantee (Constitution I).

**Alternatives considered**: *Raising out of `discover()`* — rejected (kills unrelated agents).
*UI-only validation* — rejected: FR-023 requires load-time rejection for hand-edited files.

## R10 — Schema field group, migration, emitter (FR-024)

**Decision (unattended)**:
- **Schema** (`ui/schema.py`): add the `on_project_status` group as a new `section="project_status"`
  whose fields lift from / nest into `triggers.on_project_status` — `owner`/`status` (str, required
  when the block is on), `label`/`repo` (str, optional), `project` (int, ≥1), `interval_seconds`
  (int, default 60, ≥30). `validate` enforces the same rules as the backstop (R9), keyed by field id
  in the `depends_on`/`checks` style (e.g. `"owner is required for a GitHub Projects trigger"`,
  `"interval_seconds must be an integer of at least 30"`). `SCHEMA_VERSION` **7→8** with
  `migrate_7_to_8` = **identity** (the block is additive), `MIGRATIONS` gains `(8, migrate_7_to_8)`.
- **Emitter** (`ui/agents_store.py`): `_triggers_block_lines` gains a nested `on_project_status:`
  mapping (a new nesting depth under `triggers:`) emitted when set, with `PROJECT_STATUS_BLOCK_HELP`
  as the block-line comment and each sub-field's help as its inline comment; round-trip is stable and
  unknown keys are preserved.
- **Golden files** regenerate with the `# agentbox-schema: 8` header; one golden sample carries the
  block so the emitter's nested output is pinned. Templates gain the commented block (R11).

**Rationale**: This mirrors the produces-block precedent (a nested block under a top-level key with
per-field comments) and the additive-migration posture of 5→6→7, so it is the minimal extension of
the field-driven schema. The nested mapping is the one new shape.

**Alternatives considered**: *Flattening to `triggers.project_status_owner` etc.* — rejected: FR-001
and the spec's YAML show `on_project_status` as a block with fields, and FR-023 names the fields; a
nested block is the honest representation. *A non-identity migration* — unnecessary; nothing is
renamed.

## R11 — Automation view, held issues, run page — with the editor form as the flex point (FR-025/FR-026)

**Decision (unattended)**:
- **Sensor surface** (FR-025): the `project_status_<name>` sensor appears in the Automation view
  alongside the agent's other instigators, STOPPED by default, toggled by the existing sensor toggle
  (`dagster.py:set_instigation` already toggles a sensor by name). Its purpose is rendered in **plain
  words** from the block — e.g. *"When an issue enters In progress on vortexbox001/1"* — built by a
  small formatter over `owner`/`project`/`status`.
- **Held issues** (FR-025): the sensor reports held issues in its tick `SkipReason` (naming the
  holder, R4). The UI reads the sensor's latest tick status/skip-reason via `dagster.py` and surfaces
  it in the Automation view, so the operator sees what is waiting and why. (No new persistence — the
  tick history is the source.)
- **Run page** (FR-026): a sensor-launched run already carries `dagster/sensor_name` (launcher) and
  the `agentbox/issue_*` tags; the run detail names the sensor as launcher (existing
  `_launched_by_label`) and links the issue number to `agentbox/issue_url`.
- **Editor form** — the **null-action flex point** (spec Assumption "UI scope"): the plan targets a
  full "GitHub Projects trigger" card (six inputs, shared macros), but the schema group + Automation
  toggle + validation already make the trigger fully usable YAML-only. If the card proves more than a
  field group during implementation, ship YAML-only + the Automation toggle now and add the editor
  fields later — recorded here as the sanctioned fallback, so no scope decision blocks the MVP.

**Rationale**: The schema group, the Automation toggle, and the run-page link are the MUST parts
(FR-024/FR-025/FR-026) and reuse existing UI plumbing; surfacing held issues from the tick history
avoids new state; the editor card is the one piece the spec pre-authorises deferring.

**Alternatives considered**: *Persisting held issues in a new store for the UI* — rejected: the tick
history already carries them. *Skipping the plain-words description* — rejected by FR-025.

## R12 — The `github_projects` module boundary (re-homability, FR-022)

**Decision**: Put observation and admission in one new module, `orchestrator/github_projects.py`,
with a hard seam between them: `GitHubProjectsClient.fetch_board(owner, project) -> list[BoardItem]`
(all I/O, pagination, token, error mapping) and `plan_tick(cursor_state, items, cfg, now) ->
TickPlan` (pure: `{launches: [...], held: [...], next_cursor, skip_reason}` — no I/O, no clock, `now`
injected). `factory.build_project_status_sensor` is a thin wire: call the client, call `plan_tick`,
emit `RunRequest`s from `plan.launches`, `SkipReason` from `plan.skip_reason`/held, `update_cursor`
from `plan.next_cursor`. The cursor + run keys are durable (R3).

**Rationale**: FR-022 requires observation and admission to be separate, the cursor/dedup durable, and
launches to go through the existing request path so a later feature can adopt this as an external
observer without changing behaviour or re-firing. A pure `plan_tick` is also what makes the whole
state machine unit-testable with a faked client and no network (SC-010).

**Alternatives considered**: *Inlining everything in the sensor closure* — rejected: not re-homable
and hard to test. *Two separate modules (client + admission)* — reasonable, but one module with a
clear internal seam keeps the small feature cohesive; can be split when #22/#23/#24 land.

---

## Decisions summary

| Question | Decision |
|----------|----------|
| Sensor kind? | Custom polling `SensorDefinition` `project_status_<name>`, STOPPED by default — not an automation condition (R1) |
| Board read? | GitHub Projects v2 GraphQL; Status by option name, case-insensitive; issue-only; paginated (R2) |
| Cursor + dedup? | `{item_id: {entered_at, launched}}` in `context.cursor`; run key `<item_id>:<entered_at>`; first tick seeds seen-not-eligible (R3) |
| One-at-a-time? | Slot held while a launched issue is still in the status; oldest-first release; per agent; board is the source of truth (R4) |
| Hand issue to run? | Five `agentbox/issue_*` tags + `run_config` payload; body written to a `:ro` `/issue/body.md` via the spec-013 handoff; per-kind RunRequest (R5) |
| Feature key / title? | Pure `feature_key(number, title)` (≤48, drop non-ASCII, `NNN` when empty) + `sanitize_title` (strip control, ≤256) (R6) |
| Token? | `GITHUB_PROJECT_TOKEN` only, no fallback; daemon-only; never tagged/logged/filed; redacted (R7) |
| Resilience? | Skip-with-reason leaves cursor untouched; unresolvable names what was missing; pagination followed; shared per-tick board cache (R8) |
| Load validation? | `_project_status(cfg)` rejects one agent naming file+field; others load (R9) |
| Schema/emitter? | `on_project_status` group; nested emit; schema 7→8 identity migration; golden regenerated (R10) |
| UI? | Automation toggle + plain-words description + held issues; run-page launcher + issue link; editor card is the null-action flex point (R11) |
| Re-homable? | `github_projects.py`: `GitHubProjectsClient` (I/O) + pure `plan_tick` (admission); durable cursor + run keys (R12) |
