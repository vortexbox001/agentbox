---

description: "Task list for GitHub Project Status Trigger — Board-Driven Agent Launches"
---

# Tasks: GitHub Project Status Trigger — Board-Driven Agent Launches

**Input**: Design documents from `/specs/016-github-dagster-sensor/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED. The spec requests them explicitly — SC-010 requires the full behaviour set to be
covered by unit tests with the GitHub client **faked** and **no network call**, and the plan's Testing
section enumerates the orchestrator and UI suites. Test tasks are therefore first-class here.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
independently. P1 stories (US1–US3) are the MVP; P2/P3 follow.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1…US9); Setup/Foundational/Polish carry none
- Every task names an exact product-tree file path

## Path Conventions

AgentBox is a multi-package product tree (see AGENTS.md). Task paths are product-tree paths; tests sit
beside the code they cover:

- **Orchestrator** (Dagster code location): `orchestrator/*.py`, tests in `orchestrator/tests/`
- **Management UI** (FastAPI + Jinja2): `ui/*.py`, `ui/templates/`, `ui/static/`, tests in `ui/tests/`
  (schema golden files in `ui/tests/golden/`)
- **Seed samples**: `examples/config/agents/`
- Never write tasks against `config/` or `/data/…` — those are instance config and state.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Runtime prerequisites and shared test scaffolding

- [X] T001 [P] Document `GITHUB_PROJECT_TOKEN` in `.env.example` (board read scope — classic PAT with
  `read:project` + repo read, or fine-grained token with Projects: read + Contents/Issues: read;
  sensor-process only, no fallback to `GITHUB_TOKEN`).
- [X] T002 [P] Create `orchestrator/tests/test_github_projects.py` with a shared **FakeGitHubProjectsClient**
  and a board-fixture builder (nodes with `content.__typename`, Status field-value, labels, repo,
  pagination pages) so every orchestrator test runs with GitHub faked and **no network call** (SC-010).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `github_projects` module seam (FR-022) that every user story builds on — types,
exceptions, constants, and the pure key/title helpers the launch handoff needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Create `orchestrator/github_projects.py` with the module boundary: `BoardItem`
  (item_id, content_type, status, number, repo, url, title, body, labels), `ProjectStatusCfg` shape,
  `TickPlan`/`Launch`/`Held` result types, typed exceptions `BoardError` / `RateLimited` /
  `Unresolvable(what)`, and the constants `ISSUE_ENV_NAMES` and `ISSUE_TAG_NAMES` (contracts/orchestrator-model.md §1).
- [X] T004 Implement the pure helpers `feature_key(number, title)` and `sanitize_title(title)` in
  `orchestrator/github_projects.py` (contracts/orchestrator-model.md §5): `NNN` + `-` + slug of
  `a-z0-9`/single-hyphens, no leading/trailing hyphen, whole key capped at 48 then trailing hyphen
  stripped, empty slug ⇒ `NNN` alone; title control-stripped then capped to 256. (Grammar/cap pinned
  exhaustively by US5.)

**Checkpoint**: Module seam and pure helpers exist — user story implementation can begin.

---

## Phase 3: User Story 1 - Launch an agent when an issue enters a status (Priority: P1) 🎯 MVP

**Goal**: Moving a matching issue into the target status launches the agent exactly once and hands the
run the issue's identity (number, repo, URL, title, feature key) plus the body as a read-only file.

**Independent Test**: Configure the trigger on a hello-style agent that echoes `AGENTBOX_ISSUE_NUMBER`,
`AGENTBOX_FEATURE_KEY`, and the first line of the body file; turn the sensor on; move an issue into the
status; confirm one run launches within ~a minute carrying the correct number, title, key, and body.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T005 [P] [US1] In `orchestrator/tests/test_github_projects.py`, add tests: `fetch_board` happy
  path (single page) derives a `BoardItem` for **every** node (whole board, unfiltered); `filter_items`
  keeps only issues whose Status matches the configured option case-insensitively; `plan_tick`
  launches a newly-entered issue and emits a `Launch` with `run_key = "<item_id>:<entered_at>"`, the
  five `agentbox/issue_*` tags, and a `run_config` payload `{number, repo, url, title, feature_key, body}`
  (title/body never in tags).
- [X] T006 [P] [US1] In `orchestrator/tests/test_factory.py`, add tests: `build_project_status_sensor`
  yields a `SensorDefinition` that is **paused** (`DefaultSensorStatus.STOPPED`); a matching issue
  produces a `RunRequest` targeting an **asset-kind** agent by `asset_selection` and a **job-kind**
  agent by `job_name=agent_<name>` (FR-002); the issue handoff sets the five `AGENTBOX_ISSUE_*` env
  values, mounts `body.md` read-only at `/issue`, and the body appears **only** in the `:ro` file —
  never on the command line or in an env value.
- [X] T007 [P] [US1] In `orchestrator/tests/test_definitions.py`, add a test: a valid `on_project_status`
  block causes `discover()` to append a `project_status_<name>` sensor for both an asset-kind and a
  job-kind agent, composing with the agent's existing triggers.

### Implementation for User Story 1

- [X] T008 [US1] Implement `GitHubProjectsClient.fetch_board(owner, project)` happy path plus the pure
  `filter_items(items, cfg)` in `orchestrator/github_projects.py` (single page): `fetch_board` issues
  the outbound GraphQL `POST https://api.github.com/graphql` with `Authorization: Bearer` via the
  pinned `httpx` and a bounded timeout, and returns a `BoardItem` for **every** node (whole board,
  unfiltered, so the result is shareable — contracts/orchestrator-model.md §1/§3); `filter_items` keeps
  only issues (drops PRs/drafts) whose Status option name equals the configured `status`
  case-insensitively (contracts/github-projects-query.md §1–§2, §4). The `label`/`repo` filters land in
  US4; pagination/error mapping in US7.
- [X] T009 [US1] Implement `plan_tick(cursor_state, items, cfg, now)` core in
  `orchestrator/github_projects.py`: for a newly-appeared issue emit one `Launch` with the run key
  `<item_id>:<entered_at>`, build its tags + `run_config`, and return `next_cursor` with the item marked
  `launched: true` (contracts/orchestrator-model.md §2). Full cursor lifecycle and slot logic are
  extended in US2/US3.
- [X] T010 [US1] Add `_prepare_issue_handoff(cfg, context)` to `orchestrator/factory.py`, the twin of
  `_prepare_upstream_handoff`: read the `issue` payload off `context.op_config`/`run_config`; when
  absent return `(None, {})` (unchanged path); else make a `0777` tempdir under `STAGING_ROOT`, write
  the body to `body.md` (`0644`), and return `(handoff_dir, {AGENTBOX_ISSUE_*: …})` with
  `AGENTBOX_ISSUE_TITLE` = `sanitize_title(...)` and `AGENTBOX_ISSUE_BODY_FILE=/issue/body.md`
  (contracts/orchestrator-model.md §4).
- [X] T011 [US1] Wire the issue handoff into `make_run_op` in `orchestrator/factory.py`: add an optional
  `issue` op-config field; call `_prepare_issue_handoff`; merge `launch_env = {**runtime_env,
  **upstream_env, **issue_env}`; extend `_launch_mounts`/`_build_agent_cmd` to add `-v <dir>:/issue:ro`
  when the handoff dir is set; `--rm`-clean the dir in the op's `finally` (mirrors the upstream handoff).
- [X] T012 [US1] Implement `build_project_status_sensor(cfg)` in `orchestrator/factory.py`
  (contracts/orchestrator-model.md §3): `@sensor(name="project_status_<name>",
  minimum_interval_seconds=…, default_status=STOPPED)` with the per-kind target; each tick reads the
  cursor, calls `plan_tick`, yields per-kind `RunRequest`s (`asset_selection=` or `job_name=`) carrying
  run_key + the five tags + run_config, then `update_cursor(next_state)`. Add the
  `project_status_supported()` build-time lever.
- [X] T013 [US1] Add `_project_status(cfg)` to `orchestrator/definitions.py` and call it from
  `discover()`: when the block is valid, `sensors.append(build_project_status_sensor(cfg))` for both
  asset- and job-kind agents, composing with existing `on_upstream`/`on_missing`/schedules
  (contracts/orchestrator-model.md §8). (Structural validation/rejection is added in US8.)

**Checkpoint**: A board move launches the agent once with the full identity handoff — MVP is functional.

---

## Phase 4: User Story 2 - Launch exactly once per entry into the status (Priority: P1)

**Goal**: One run per entry — no duplicate on the next poll, no stampede on daemon restart, no launch
for issues already sitting in the status at first start; moving out and back in launches again.

**Independent Test**: Move one issue in → one run; leave 10 min → no further run; restart the daemon →
no further run; move out and back in → exactly one more run.

### Tests for User Story 2 ⚠️ (write first, ensure they fail)

- [X] T014 [P] [US2] In `orchestrator/tests/test_github_projects.py`, add `plan_tick` state-machine
  tests: **first tick** (empty cursor `{}`) seeds every in-status item `{entered_at, launched:false,
  eligible:false}` and launches nothing (FR-007); **empty-board first start** — first tick with `S={}`
  seeds nothing yet still returns a **non-empty** `next_cursor = {"version":1,"seen":{}}`, and the
  **next tick's new arrival is `eligible:true` and launches** (the US1 turn-on-then-move-in path; the
  arrival must not be re-classified as a first tick because the cursor keys off its **presence**, not
  off `seen` being empty — FR-007/SC-001); **second tick after first-tick seeding** (the same seeded
  items still in status, no new arrivals) still launches **none** and holds nothing — the seeded items
  are `eligible:false`, so they are never candidates (FR-007/SC-005, the case a two-field cursor got
  wrong); **stay** (carried, already launched) does not relaunch; **leave** drops the id from `seen`;
  **re-enter** gets a fresh `entered_at` with `eligible:true` and launches again; **restart** (same
  cursor reloaded) produces the same run key so no relaunch (FR-005/FR-006). Assert every returned
  `next_cursor` carries `{"version":1, …}`.

### Implementation for User Story 2

- [X] T015 [US2] Extend `plan_tick` in `orchestrator/github_projects.py` with the full cursor lifecycle:
  detect the first tick by the **empty cursor** (`cursor_state == {}` — the sensor passes `{}` when
  `context.cursor` is falsy), never by `seen` being empty; drop **left** ids, keep **carried** ids with
  their stored `{entered_at, launched, eligible}`, add **new** ids as
  `{entered_at: now, launched:false, eligible:true}`, and seed-only on the empty-cursor first tick as
  `{entered_at: now, launched:false, eligible:false}` with
  `skip_reason = "first tick: recorded N items already in status, launched none"` (FR-005/FR-007).
  Always return `next_cursor = {"version": 1, "seen": {…}}` — set `version:1` when seeding and preserve
  a carried `version` — so a seeded-but-empty board persists a non-empty cursor. The
  `eligible` flag distinguishes a genuine arrival (`true`, may launch) from a first-tick-seeded /
  pre-existing item (`false`, never a candidate), so a seeded item never launches on a later tick
  (admission uses it in T017). Keep the run key `<item_id>:<entered_at>` stable across ticks/restarts
  and new on re-entry (FR-006).

**Checkpoint**: Exactly-once-per-entry holds across ticks, restarts, and re-entries.

---

## Phase 5: User Story 3 - One feature in flight at a time (Priority: P1)

**Goal**: While one issue's run is active (launched and still in the status), other eligible issues are
held (not launched) and reported with the holder; when the active issue leaves the status the next held
issue launches, oldest first.

**Independent Test**: With one issue active, move a second in → held, nothing launched; move the first
out → the second launches on the next tick; move three in at once → they launch one at a time, oldest
first.

### Tests for User Story 3 ⚠️ (write first, ensure they fail)

- [X] T016 [P] [US3] In `orchestrator/tests/test_github_projects.py`, add slot tests: with a carried
  `launched:true` item still in status, a second eligible issue produces **no launch** and appears in
  `held` naming the holder's number (FR-009); when the active item leaves, the oldest held candidate
  launches (FR-010); three simultaneous entrants launch one-per-freed-slot in `entered_at` order.

### Implementation for User Story 3

- [X] T017 [US3] Extend `plan_tick` in `orchestrator/github_projects.py` with the per-agent slot: the
  slot is occupied iff any carried id has `launched:true`; candidates are ids with `launched:false`
  **and** `eligible:true` ordered by `(entered_at, number)` (first-tick-seeded `eligible:false` ids are
  never candidates, so a pre-existing item never launches — FR-007); if free, launch the oldest and
  mark it launched, else launch none; all non-launched candidates become `Held{item, holder_number}`;
  set `skip_reason` to the held report when there are held issues and no launch (FR-008/FR-009/FR-010).
  Release requires only the board move.

**Checkpoint**: All three P1 stories complete — the single-slot board-driven launcher is fully
functional and independently testable.

---

## Phase 6: User Story 4 - Only the intended items launch (Priority: P2)

**Goal**: `label` and `repo` filters and issue-only admission — PRs, drafts, and filtered-out issues
never launch and never hold the slot.

**Independent Test**: With `label: brief`, move in an unlabeled issue, a PR, and a draft → none launch
or hold; move in a labeled issue → it launches; with a `repo` filter, an issue from another repo does
not launch or hold.

### Tests for User Story 4 ⚠️ (write first, ensure they fail)

- [X] T018 [P] [US4] In `orchestrator/tests/test_github_projects.py`, add `filter_items` tests: PRs and
  drafts are dropped; the `label` filter matches by **exact membership** of the label-name list,
  **case-insensitively** (a substring of a label name does NOT match — F6/F7) and the `owner/repo`
  **case-insensitive** filter keep only matching issues; a null-Status item never matches; an issue
  whose `repository.nameWithOwner` is absent/blank is **skipped defensively** and never launches
  (CHK005 — F5); excluded items never reach `plan_tick`, so they never launch and never appear in
  `held` (FR-004 / US4 #3).

### Implementation for User Story 4

- [X] T019 [US4] Extend the pure `filter_items(items, cfg)` in `orchestrator/github_projects.py`
  (contracts/github-projects-query.md §4) with the optional filters: `label` (the issue's
  `labels.nodes[].name` list **includes** `label` by exact membership, matched **case-insensitively** —
  not a substring match, F6/F7) and `repo` (`repository.nameWithOwner` equals `repo`,
  case-insensitively). Also, in the same pure function: raise
  `Unresolvable("status option '<status>'")` when the configured `status` matches no option present
  anywhere on the board (FR-020 — this owns T024's status-option expectation, F2), and **defensively
  skip** any issue whose `repository.nameWithOwner` is absent/blank rather than launching it with a
  blank repo (CHK005 — F5). Return only issues-in-status passing all filters.

**Checkpoint**: The trigger only ever launches the intended issues.

---

## Phase 7: User Story 5 - Every launch gets a stable feature key (Priority: P2)

**Goal**: Pin the feature-key grammar and 256-char title cap exhaustively (the impl landed in
Foundational T004; #22/#24 inherit the grammar).

**Independent Test**: Feed titles with punctuation, emoji, path separators, `..`, and 200 characters and
confirm every key matches `^[0-9]{3}(-[a-z0-9]+)*$` and ≤48; two same-title issues differ by number.

### Tests for User Story 5 ⚠️

- [X] T020 [P] [US5] In `orchestrator/tests/test_github_projects.py`, add exhaustive `feature_key` /
  `sanitize_title` vectors: `038-ui-update-runs-overview-page`; punctuation/emoji/path-separator/`..`/
  200-char titles all satisfy the grammar and ≤48 cap; an all-punctuation/emoji title ⇒ `038` (no
  trailing hyphen); non-ASCII letters and emoji are **dropped**, not transliterated; two same-title
  issues with different numbers produce different keys; `sanitize_title` strips control chars and caps
  at 256 (FR-011/FR-015, SC-007).

**Checkpoint**: The key grammar and title cap are locked by test vectors.

---

## Phase 8: User Story 6 - The board token stays isolated (Priority: P2)

**Goal**: The sensor reads its token only from `GITHUB_PROJECT_TOKEN` (no `GITHUB_TOKEN` fallback); the
token is never forwarded to a container, tagged, logged, or filed, and passes through redaction.

**Independent Test**: Unset `GITHUB_PROJECT_TOKEN` with `GITHUB_TOKEN` set → tick skips naming the
missing variable; inspect a launched container's env, run tags, logs, and transcript → the token is in
none of them.

### Tests for User Story 6 ⚠️ (write first, ensure they fail)

- [X] T021 [P] [US6] In `orchestrator/tests/test_factory.py`, add token-isolation tests: with
  `GITHUB_PROJECT_TOKEN` unset (and `GITHUB_TOKEN` set) the sensor yields `SkipReason` naming the missing
  `GITHUB_PROJECT_TOKEN` with **no** fallback (FR-016); a launched run's container env, the five tags,
  the `run_config`, and the captured context contain no token value (FR-017).
- [X] T022 [P] [US6] In `orchestrator/tests/test_redact.py`, assert a `GITHUB_PROJECT_TOKEN`-shaped
  value (e.g. `github_pat_…` / `ghp_…`) is masked by `orchestrator/redact.py` (defence in depth).

### Implementation for User Story 6

- [X] T023 [US6] In `orchestrator/factory.py`, read the token only from `os.environ["GITHUB_PROJECT_TOKEN"]`
  inside the sensor and `SkipReason` naming it when unset (no `GITHUB_TOKEN` fallback); ensure the token
  is passed only to `GitHubProjectsClient` and never placed in a `RunRequest` tag/`run_config`/env value
  or logged (contracts/orchestrator-model.md §6). Confirm `orchestrator/redact.py` masks the token
  shape; add the `*TOKEN*`/prefix rule if any gap is found.

**Checkpoint**: The board token stays in the daemon process and nowhere else.

---

## Phase 9: User Story 7 - A GitHub outage or bad board degrades safely (Priority: P2)

**Goal**: GitHub errors/rate-limits/timeouts and unresolvable board/status/field become skips with a
reason that leave the cursor untouched; pagination is followed; agents on the same board share one query
per tick.

**Independent Test**: Set `status` to a name the board lacks → ticks skip naming the missing option while
other agents/sensors keep running; simulate a GitHub error → cursor unchanged, nothing re-fires.

### Tests for User Story 7 ⚠️ (write first, ensure they fail)

- [X] T024 [P] [US7] In `orchestrator/tests/test_github_projects.py`, add resilience tests: HTTP 5xx /
  connection error / timeout ⇒ `BoardError`; 403/429 or GraphQL `RATE_LIMITED` ⇒ `RateLimited`; null
  `organization`/`user`/`projectV2` ⇒ `Unresolvable("board …")`; missing Status field ⇒
  `Unresolvable("Status field")`; configured status matching no option ⇒
  `Unresolvable("status option '…'")`; multi-page fixtures are followed so a page-2 item is considered
  (FR-021); the sensor turns each into a `SkipReason` and leaves the cursor **unchanged** (FR-019/FR-020).
- [X] T025 [P] [US7] In `orchestrator/tests/test_factory.py`, assert the per-tick board cache serves one
  raw fetch across two sensors on the same `(owner, project)`, and that two sensors watching that board
  on **different statuses** each see only their own status's items (the cache stores the whole board;
  `filter_items` is per sensor) (FR-021, spec Edge Case "Same board, different statuses").

### Implementation for User Story 7

- [X] T026 [US7] Implement error mapping and pagination in `GitHubProjectsClient.fetch_board`
  (`orchestrator/github_projects.py`, contracts/github-projects-query.md §3/§5): loop `after`
  pagination to completion; raise `BoardError`/`RateLimited`/`Unresolvable(what)` per the table; retry
  with `user(login:)` when `organization(login:)` is null (best-effort user-owned board).
- [X] T027 [US7] In `orchestrator/factory.py`, catch `Unresolvable` → `SkipReason("could not resolve …")`
  and `RateLimited`/`BoardError` → `SkipReason("GitHub unavailable: …")`, both **returning before**
  `update_cursor` so the cursor is untouched; add `board_cache_get(owner, project)` as a short-TTL
  process-local memo storing the **whole board** keyed by `(owner, project)` (cache miss fetches and
  stores; `filter_items` runs per sensor after the cache so different-status sensors share one query
  without cross-contamination; correctness never depends on the cache).

**Checkpoint**: A GitHub outage or operator typo degrades to a skip without losing or re-firing launches.

---

## Phase 10: User Story 8 - Misconfiguration fails one agent, not the box (Priority: P2)

**Goal**: An invalid `on_project_status` block rejects only that one agent with a file-and-field message
in the `depends_on`/`checks` style; every other agent still loads.

**Independent Test**: Write a YAML file with `on_project_status` missing `project`; confirm it fails to
load with a file+field message while every other agent still loads.

### Tests for User Story 8 ⚠️ (write first, ensure they fail)

- [X] T028 [P] [US8] In `orchestrator/tests/test_definitions.py`, add rejection tests: a block missing
  `owner`/`project`/`status`, a non-positive-integer `project`, or `interval_seconds` below 30 / non-int
  each raise `RejectAgent(file, field-message)` for that agent while all other agents still load (US8,
  FR-023).

### Implementation for User Story 8

- [X] T029 [US8] Add structural validation to `_project_status(cfg)` in `orchestrator/definitions.py`
  (the load-time backstop, contracts/agent-model.md §5): require `owner`/`project`/`status`; `project`
  a positive integer; `interval_seconds` an integer ≥30; `repo` (if present) of the form `owner/repo`;
  raise `RejectAgent(file, message)` naming the offending field on a bad block, leaving others loadable.

**Checkpoint**: A bad block cannot take unrelated agents down.

---

## Phase 11: User Story 9 - Operate the trigger from the UI (Priority: P3)

**Goal**: The schema group + emitter round-trip the block; the sensor appears in the Automation view
(paused, toggleable, plain-words description, held issues surfaced); a sensor-launched run names the
sensor as launcher and links the issue number.

**Independent Test**: Save the agent from the UI and reload → block round-trips unchanged; toggle the
sensor from the Automation view → starts/stops (paused by default); open a launched run → sensor named
as launcher and issue number links to the issue.

### Tests for User Story 9 ⚠️ (write first, ensure they fail)

- [X] T030 [P] [US9] In `ui/tests/test_schema.py`: the `on_project_status` group is present in `FIELDS`
  and `/api/schema` under `section="project_status"`; `validate` returns the messages for missing
  required fields, `project`<1, `interval_seconds`<30, and bad `repo`; `migrate_7_to_8` is identity;
  `SCHEMA_VERSION == 8` (contracts/ui-automation-and-runs.md §5).
- [X] T031 [P] [US9] In `ui/tests/test_agents_store.py`: the nested `on_project_status` block emits with
  its block-line + per-field comments and round-trips read→write unchanged; add a GOLDEN sample carrying
  the block.
- [X] T032 [P] [US9] In `ui/tests/test_api.py`: `/api/schema` shape; the agent form renders the trigger
  card; the Automation view lists the `project_status_<name>` sensor with its plain-words description +
  held issues; the run page links the issue number to `agentbox/issue_url`.
- [X] T033 [P] [US9] In `ui/tests/test_conformance.py`: the new template/JS pass the token/macro/
  no-inline-style checks; no external URL literal beyond the issue link built from the run tag.

### Implementation for User Story 9

- [X] T034 [US9] In `ui/schema.py`: add the `on_project_status` field group (`section="project_status"`,
  nesting under `triggers.on_project_status`, harnesses `_ALL`) — `owner`/`status`/`label`/`repo` text,
  `project`/`interval_seconds` int (interval default 60), each with its help text, plus
  `PROJECT_STATUS_BLOCK_HELP` for the emitter (contracts/agent-model.md §2).
- [X] T035 [US9] In `ui/schema.py` `validate()`: enforce required `owner`/`project`/`status`, `project`
  a positive integer, `interval_seconds` an integer ≥30, and `repo` shape `owner/repo`, keyed by field
  id in the `depends_on`/`checks` style (contracts/agent-model.md §3).
- [X] T036 [US9] In `ui/schema.py`: bump `SCHEMA_VERSION` 7→8, add `migrate_7_to_8(data)` (identity),
  and append `(8, migrate_7_to_8)` to `MIGRATIONS` (contracts/agent-model.md §6).
- [X] T037 [US9] In `ui/agents_store.py`: extend `_triggers_block_lines` to emit the nested
  `on_project_status:` mapping (block-line comment = `PROJECT_STATUS_BLOCK_HELP`, per-field inline
  comments), optional sub-fields only when set; lift `triggers.on_project_status.*` on read; preserve
  unknown keys (contracts/agent-model.md §4).
- [X] T038 [P] [US9] In `ui/dagster.py`: read the `project_status_<name>` sensor's latest tick
  status/`SkipReason` (held issues) for the Automation view; confirm
  `set_instigation(kind="sensor", name=…, running=…)` toggles the sensor by name (the real signature
  is `set_instigation(kind, name, running)` — `ui/dagster.py:632`) (contracts/ui-automation-and-runs.md §3).
- [X] T039 [US9] In `ui/main.py`: pass the plain-words description
  (*"When an issue enters {status} on {owner}/{project}"*) and the latest-tick held issues into the
  Automation view; expose the issue link (`agentbox/issue_number` → `agentbox/issue_url`) on the run
  detail via the existing `_launched_by_label` sensor path (contracts/ui-automation-and-runs.md §3–§4).
- [X] T040 [P] [US9] In `ui/static/agent-form.js` and `ui/templates/agents/form.html`: render the GitHub
  Projects trigger card from the shared macros (`card`, `text_input`, number input, `toggle`) — six
  inputs gated on the block being enabled, `collect()` nesting under `triggers.on_project_status` and
  omitting the block when disabled (contracts/ui-automation-and-runs.md §2).
- [X] T041 [P] [US9] In `ui/static/agents-list.js` and `ui/templates/agents/list.html`: recognise
  `project_status` for the automation-column pill and render a "board" pill with the plain-words tooltip.
- [X] T042 [US9] In the run-detail template under `ui/templates/runs/`: link the issue number to
  `AGENTBOX_ISSUE_URL` / the `agentbox/issue_url` tag using the shared macros (no inline style).
- [X] T043 [US9] Regenerate `ui/tests/golden/*.yaml` from the emitter so every sample carries the
  `# agentbox-schema: 8` header (and the new sample carries the `on_project_status` block).

**Checkpoint**: The trigger is fully operable from the management UI.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and templates that track the new surface (Constitution VI), and final
validation.

- [X] T044 [P] Edit `examples/config/agents/_template-*.yaml`: add a commented `on_project_status:` block
  under `triggers:` with the same help text, and re-stamp each template to `# agentbox-schema: 8`
  (contracts/agent-model.md §7).
- [X] T045 [P] Update `README.md`: document `on_project_status` (fields + defaults), the
  `AGENTBOX_ISSUE_*` env values + `agentbox/issue_*` tags + read-only body file, `GITHUB_PROJECT_TOKEN`
  (board read scope, sensor-only, no fallback), the `project_status_<name>` sensor, and the feature-key
  grammar/cap.
- [X] T046 [P] Add an FR-018 verification test in `orchestrator/tests/test_factory.py`: a
  sensor-launched `RunRequest` yields an **automated** run — `is_automated_run(context)` is true (it
  carries `dagster/sensor_name`), `governor_gate` applies (the run counts toward `max_runs_per_hour`
  and is refused past `max_chain_depth`), and `derive_chain_depth` returns **1** (a root chain at
  depth 1). Pins FR-018's "no new code" claim so a later refactor cannot silently regress it
  (contracts/orchestrator-model.md §7).
- [X] T047 Run all five pytest suites from the repo root (`ui`, `orchestrator`, `images`, `litellm`,
  `scripts`) and the quickstart §0 checks; confirm green (SC-010: no test makes a network call).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — can start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories** (T003 creates the module
  every story imports; T004 provides the key/title helpers US1's handoff needs).
- **User Stories (Phase 3+)**: all depend on Foundational.
  - US1 (P1) is the MVP and lays down `plan_tick`, the sensor, the handoff, and the definitions wiring.
  - US2 and US3 (P1) extend `plan_tick` in `orchestrator/github_projects.py` and therefore build on
    US1's core (same file — sequential, not parallel with each other or with US1's T009).
  - US4 and US7 extend `GitHubProjectsClient.fetch_board` (US1's T008) — build on US1.
  - US5 is test-only over the T004 helpers — independent once Foundational is done.
  - US6 and US8 are largely additive (token guard / load-time validation) — build on US1's sensor +
    definitions wiring.
  - US9 (P3) is the UI layer — independent of the orchestrator internals except that the run-page link
    and Automation-view held-issues surface reflect US1/US3 behaviour.
- **Polish (Phase 12)**: depends on the schema bump (T036) and the shipped behaviour.

### Within Each User Story

- Tests are written first and expected to fail before implementation.
- In `github_projects.py`: US1 `plan_tick` core (T009) → US2 lifecycle (T015) → US3 slot (T017) are
  strictly sequential (same function).
- `fetch_board`: US1 happy path (T008) → US4 filters (T019) and US7 pagination/errors (T026).

### Parallel Opportunities

- Setup T001 and T002 run in parallel.
- All test-authoring tasks marked `[P]` within a story run in parallel (different files or
  independent test blocks).
- US5 (T020) can proceed in parallel with US2/US3 once Foundational T004 is done.
- Across the UI story, T030–T033 (tests) run in parallel; among implementation, T038/T040/T041 touch
  different files and run in parallel, while T034–T036 all edit `ui/schema.py` (sequential).
- Polish T044, T045, and T046 run in parallel; T047 (the full suite run) runs last.

---

## Parallel Example: User Story 1 tests

```bash
# Author US1 tests together (different files / independent blocks):
Task T005: fetch_board + plan_tick launch in orchestrator/tests/test_github_projects.py
Task T006: sensor paused + per-kind RunRequest + issue handoff in orchestrator/tests/test_factory.py
Task T007: definitions builds the sensor in orchestrator/tests/test_definitions.py
```

---

## Implementation Strategy

### MVP First (User Stories 1–3, all P1)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete US1 → a board move launches the agent once with the full identity handoff.
3. Complete US2 → exactly-once per entry across ticks, restarts, and re-entries.
4. Complete US3 → the single in-flight slot with oldest-first release.
5. **STOP and VALIDATE**: the P1 set is the shippable core (quickstart §1–§3).

### Incremental Delivery

1. MVP (US1–US3) → the trustworthy single-slot launcher.
2. Add US4 (filters), US5 (key vectors), US6 (token isolation), US7 (resilience), US8 (load safety) —
   each a P2 hardening increment, independently testable.
3. Add US9 (P3) — full UI operation; the trigger is usable YAML-only before this lands (spec's UI
   null-action flex point).
4. Polish: templates, README, and the full test-suite run.

---

## Notes

- Tests are included because the spec requests them (SC-010) — write them first and confirm they fail.
- `[P]` = different files or independent blocks, no dependency on incomplete tasks.
- `plan_tick` and `fetch_board` are each built up across stories; those tasks are sequential within
  their file even though they belong to different story phases.
- Commit after each task or logical group. The board token never appears in a tag, env value, log, or
  file — verify on every handoff task (FR-017).
