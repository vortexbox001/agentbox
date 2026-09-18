# Feature Specification: GitHub Project Status Trigger — Board-Driven Agent Launches

**Feature Branch**: `016-github-dagster-sensor`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "Let a GitHub Projects board drive AgentBox. When an issue is moved into a chosen status on a chosen project (first use: 'In progress' on `vortexbox001` project 1), AgentBox launches an agent for that issue, once, with the issue's identity available to the run. GitHub only delivers `projects_v2_item` events to org webhooks and Apps, never to Actions, and the box is not reachable from the internet, so this is a polling sensor: outbound calls only, no tunnel, no webhook receiver. This is deliberately the smallest version that gets one real issue from the board to a pull request: one board, one feature at a time, no partitions, no templating, no project files."

## Clarifications

### Session 2026-09-17

- Q: When a title slugs to empty (all punctuation/emoji/control characters), what feature key does the issue get? → A: The three-digit issue number alone, with no trailing hyphen (e.g. issue 38 → `038`).
- Q: What maximum length caps the `AGENTBOX_ISSUE_TITLE` environment value after control characters are stripped? → A: 256 characters (truncate longer titles).
- Q: Is the one-feature-in-flight slot per agent (per sensor) or shared globally across every board-driven agent? → A: Per agent — each agent's sensor holds its own single slot independently.
- Q: What form does the `repo` filter (and the `AGENTBOX_ISSUE_REPO` value / `agentbox/issue_repo` tag) take? → A: The full `owner/repo` name, matched case-insensitively.
- Q: In the feature-key slug, are non-ASCII letters and emoji transliterated to ASCII (e.g. `é`→`e`) or dropped? → A: Dropped — only `a-z0-9` characters survive; there is no transliteration.

### Session 2026-09-17 (task-generation review)

Gaps surfaced by the requirements-quality checklist while generating `tasks.md`, each resolved by
adopting the most reasonable default consistent with the plan and contracts:

- Q: How is the run handed the issue body when the body is empty or absent? → A: The `:ro` body file is **always** written (an empty file when the body is empty/absent); `AGENTBOX_ISSUE_BODY_FILE` always points at a readable file, never unset (CHK001).
- Q: Is the issue-body size written to the read-only file bounded? → A: No — the body file is written **unbounded**; only the title is capped (256 chars). The body is data delivered as a file, not an env value (CHK002).
- Q: How is an issue in the target column that carries no Status value (null option) treated? → A: As **not matching** the configured status — it is dropped exactly like any non-matching option and neither launches nor holds the slot (CHK003).
- Q: What GitHub scopes must `GITHUB_PROJECT_TOKEN` hold? → A: Board read scope — a classic PAT with `read:project` + repo read, or a fine-grained token with Projects: read + Contents/Issues: read (CHK004).
- Q: What happens if a board item's repository (`owner/repo`) cannot be resolved? → A: A launch candidate is only an Issue, which always resolves `repository.nameWithOwner`; if it is ever absent the item is **skipped defensively** rather than launched with a blank repo (CHK005).
- Q: What upper bound does "within about a minute" carry? → A: One poll interval — the run launches within `interval_seconds` (default ≤60s) of the board reflecting the move (CHK008).
- Q: Is the 256-char title cap applied before or after control-character stripping, and is truncation multi-byte-safe? → A: Control characters are stripped **first**, then the result is truncated to 256 Unicode code points (code-point-safe, never splitting a character) (CHK013).
- Q: Does the slot stay held when a launched run fails, errors, or is terminated while the issue remains in the status? → A: Yes — the board is the sole source of truth; the slot is released **only** when the card leaves the status, so a failed/stuck run is cleared by moving the card (generalizes US3 #4) (CHK026).
- Q: What happens to an item that enters and leaves the status entirely between two ticks? → A: It is **never observed in-status**, so it never launches and never holds the slot; only moves visible on a tick are acted on (CHK027).
- Q: Can the same item re-enter the status before its prior run's slot is released? → A: No — leaving the status forgets the item and frees the slot in the same tick, so a re-entry is always a fresh entry observed after release (CHK030).
- Q: What happens to an issue that is closed or deleted while sitting in the target status? → A: A closed issue still shown in the column is treated as in-status until it leaves; once the board no longer returns it in-status it is forgotten and frees the slot like any other leave (CHK031).

### Session 2026-09-17 (analysis remediation)

Decisions taken while acting on `analysis-report.md` findings; see the report for the full rationale.

- Q: How does the sensor cursor tell a **held** item (entered while the slot was busy — must launch
  when the slot frees, FR-010) apart from a **first-tick-seeded / pre-existing** item (must never
  launch, FR-007) when both are carried unlaunched? → A: The cursor entry gains a third field,
  `eligible`. First-tick-seeded items are recorded `{entered_at, launched: false, eligible: false}`
  and are **never** admission candidates; a genuine new arrival is recorded
  `{entered_at, launched: false, eligible: true}`. Admission considers only `launched: false && eligible: true`
  ids, so a pre-existing item never launches on any later tick while a held item launches oldest-first
  when the slot frees. A leave-then-re-enter is a fresh `eligible: true` entry, so re-entry still
  launches. (Resolves F1; applied in `data-model.md` and `contracts/orchestrator-model.md`.)
- Q: Is the optional `label` filter matched case-sensitively or case-insensitively, and by list
  membership or substring? → A: By **exact membership** of the issue's label-name list, matched
  **case-insensitively** — consistent with the `status` and `repo` filters, both of which are
  case-insensitive. (Resolves F6/F7; applied in FR-001, `data-model.md`, and `tasks.md` T018/T019.)
- Q: How does the sensor discriminate its **first tick** — off the **absence of the cursor** or off
  `seen` being empty — and what must a first tick against an **empty column** do? → A: By the
  **presence of the cursor string only** (`context.cursor` falsy ⇒ `plan_tick` gets `cursor_state ==
  {}`), **never** by `seen` being empty. A first tick against an empty board (`S = {}`) seeds nothing
  but still persists a non-empty `{"version": 1, "seen": {}}`, so the *next* tick reads a present
  cursor and is a normal tick — a genuine arrival is `eligible: true` and launches. This protects the
  US1 turn-on-then-move-in MVP path, which an `is seen empty?` reading would regress (the arrival would
  be mis-seeded `eligible: false` and never launch). (Resolves N1; aligned across FR-007,
  `data-model.md`, `contracts/orchestrator-model.md §2`, and covered by `tasks.md` T014/T015.)
- Q: Does the persisted cursor's top-level `version` field get emitted and round-tripped by
  `plan_tick`, given the orchestrator contract described the cursor only in terms of `seen`? → A: Yes —
  `plan_tick` **always** returns `next_cursor = {"version": 1, "seen": {…}}`, setting `version: 1` when
  seeding and preserving a carried `version`, matching the shape in `data-model.md`. Keeping the cursor
  non-empty also makes the N1 first-tick discriminator robust. (Resolves N2; applied in
  `contracts/orchestrator-model.md §2`, `data-model.md`, and `tasks.md` T014/T015.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch an agent when an issue enters a status (Priority: P1)

An operator wires an agent to a GitHub Projects board by adding an `on_project_status` trigger that
names the board owner, the board number, and a Status option (first use: `In progress` on
`vortexbox001` project `1`). They turn the trigger on. When someone moves an issue into that status,
AgentBox launches that agent exactly once for that issue and hands the run the issue's identity — its
number, repository, URL, title, a derived feature key, and its body — so the agent has everything it
needs to act on the brief. Nothing reacts to board changes today (triggers are cron, `on_upstream`,
and `on_missing`); this turns a board column into a launch signal without any inbound endpoint.

**Why this priority**: This is the core promise — getting one real issue from the board to a run.
Without it none of the reliability, filtering, or UI work has anything to protect. It is the MVP and
delivers value on its own: a brief written on the board becomes a running agent.

**Independent Test**: Configure the trigger on a hello-style agent that echoes
`AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_FEATURE_KEY`, and the first line of the body file. Turn the
sensor on. Move an issue into the target status. Confirm exactly one run launches within about a
minute carrying the correct number, title, key, and body.

**Acceptance Scenarios**:

1. **Given** an agent with an `on_project_status` trigger for `In progress` on `vortexbox001/1` and
   its sensor turned on, **When** an issue is moved into `In progress`, **Then** exactly one run of
   that agent launches within about a minute.
2. **Given** the launched run, **When** it starts, **Then** its container sees
   `AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_ISSUE_REPO`, `AGENTBOX_ISSUE_URL`, `AGENTBOX_ISSUE_TITLE`, and
   `AGENTBOX_FEATURE_KEY` set to the issue's values, and `AGENTBOX_ISSUE_BODY_FILE` pointing at a
   read-only file whose contents are the issue body.
3. **Given** the launched run, **When** its run record is inspected, **Then** it carries tags
   `agentbox/issue_number`, `agentbox/issue_repo`, `agentbox/issue_url`, `agentbox/project_item_id`,
   and `agentbox/feature_key`.
4. **Given** a job-kind agent and an asset-kind agent each with the trigger, **When** a matching
   issue enters the status, **Then** the job-kind agent is launched by job name and the asset-kind
   agent is materialized — the same launch distinction the UI already makes.
5. **Given** an agent whose `on_project_status` trigger has never been turned on, **When** a matching
   issue enters the status, **Then** nothing launches until an operator turns the sensor on (new
   triggers start paused).

---

### User Story 2 - Launch exactly once per entry into the status (Priority: P1)

An operator relies on a board move launching one run and only one run — never a duplicate on the next
poll, never a fresh stampede when the daemon restarts, never a launch for issues that were already
sitting in the status when the trigger was first turned on. Moving an issue out of the status and
back in is a new event and launches again.

**Why this priority**: A trigger that double-launches or stampedes on restart is worse than no
trigger — it wastes runs and corrupts the one-feature-at-a-time promise. Exactly-once entry
semantics are what make the launch signal trustworthy.

**Independent Test**: Move one issue in and confirm one run. Leave it for ten minutes and confirm no
further runs. Restart the daemon and confirm no further runs. Move the issue out and back in and
confirm exactly one more run.

**Acceptance Scenarios**:

1. **Given** an issue that entered the status and launched, **When** the sensor keeps polling for ten
   minutes with the issue still in the status, **Then** no further run launches for it.
2. **Given** an issue that already launched, **When** the daemon restarts and the sensor resumes,
   **Then** no further run launches for it.
3. **Given** an issue that launched and then left the status, **When** it is moved back into the
   status, **Then** exactly one more run launches.
4. **Given** a board that already has three issues in the target status, **When** the sensor runs for
   the very first time (no cursor yet, or after a cursor reset), **Then** none of the three launch
   and none hold the slot; an issue moved in afterwards does launch.

---

### User Story 3 - One feature in flight at a time (Priority: P1)

Because the agents a board trigger starts share one workspace and one branch today, two features in
flight would collide. So while one issue's run is active, other eligible issues wait. An issue is
active from the moment its run launches until it leaves the target status; the board is the source of
truth. Held issues are reported so the operator can see what is waiting and why. When the active
issue moves on (to review, to done, or back out), the next held issue launches, oldest first.

**Why this priority**: This is the safety rail that lets the MVP ship with a single shared workspace.
Without it, two board moves in quick succession would overwrite each other's work.

**Independent Test**: With one issue active, move a second issue in and confirm it is reported as
held with nothing launched. Move the first issue on and confirm the second launches on the next tick.
Move three in at once and confirm they launch one at a time, oldest first.

**Acceptance Scenarios**:

1. **Given** an issue whose run is active, **When** a second eligible issue enters the status,
   **Then** nothing launches for it and it is reported as held, naming the issue that is holding it.
2. **Given** a held issue, **When** the active issue leaves the target status, **Then** the held
   issue launches on the next tick and becomes the active one.
3. **Given** three eligible issues that entered while an issue was active, **When** the slot frees
   repeatedly, **Then** they launch one at a time in the order they entered the status (oldest
   first).
4. **Given** an active issue whose downstream work is stuck, **When** the operator moves its card out
   of the target status, **Then** the slot frees and the next held issue launches — no knowledge of
   the downstream chain is required.

---

### User Story 4 - Only the intended items launch (Priority: P2)

An operator narrows a busy board to just the items the agent should act on. An optional `label`
restricts launches to issues carrying that label; an optional `repo` restricts them to a single
repository. Board items that are not issues — pull requests and draft items — never launch, and never
hold the one-at-a-time slot.

**Why this priority**: Boards mix issues, pull requests, drafts, and many labels. Without filtering
and type exclusion, the trigger would launch on the wrong items and let a non-launchable item block
the queue.

**Independent Test**: With a `brief` label filter set, move in an issue without the label, a pull
request, and a draft item; confirm none launch and none hold the slot. Move in an issue with the
label and confirm it launches.

**Acceptance Scenarios**:

1. **Given** a trigger with `label: brief`, **When** an issue without that label enters the status,
   **Then** it does not launch and does not hold the slot.
2. **Given** a trigger with `repo: vortexbox001/agentbox`, **When** an issue from a different
   repository enters the status, **Then** it does not launch and does not hold the slot.
3. **Given** any trigger, **When** a pull request or a draft board item is in the target status,
   **Then** it never launches and never holds the slot.

---

### User Story 5 - Every launch gets a stable feature key (Priority: P2)

Each launched run carries a feature key derived from the issue: the issue number zero-padded to three
digits, a hyphen, and a slug of the title (lowercase `a-z0-9`, single hyphens, no leading/trailing
hyphen, at most 48 characters total). The derivation is a pure function of the issue — no
configuration — so the same issue always produces the same key, and two issues with the same title
still get different keys because the number differs.

**Why this priority**: The feature key is the handle later work hangs on (#22 makes it substitutable,
#24 makes it a partition key). Its grammar and cap are inherited downstream, so they must be pinned
now, but the trigger works without them being consumed anywhere yet.

**Independent Test**: Feed titles with punctuation, emoji, path separators, `..`, and 200 characters
and confirm every key matches the grammar and length cap; feed two issues with the same title and
confirm the keys differ.

**Acceptance Scenarios**:

1. **Given** issue 38 titled "UI Update: Runs overview page…", **When** its key is derived, **Then**
   it is `038-ui-update-runs-overview-page`.
2. **Given** a title containing punctuation, emoji, path separators, `..`, or 200 characters, **When**
   its key is derived, **Then** the key contains only lowercase `a-z0-9` and single hyphens, has no
   leading or trailing hyphen, and is at most 48 characters long.
3. **Given** two issues with different numbers but the same title, **When** their keys are derived,
   **Then** the keys differ.

---

### User Story 6 - The board token stays isolated (Priority: P2)

The sensor reads its GitHub credential from one dedicated host variable, `GITHUB_PROJECT_TOKEN`, and
nothing else — there is no fallback to `GITHUB_TOKEN`. The token is used only by the sensor process:
it is never forwarded to a container, tagged onto a run, logged, or written to a file, and it passes
through the existing redaction.

**Why this priority**: The board token has broad read scope. Leaking it into a launched agent's
environment, run tags, or logs would hand every agent a credential it should never see. Isolation is
a security requirement, not a nicety.

**Independent Test**: Unset `GITHUB_PROJECT_TOKEN` while `GITHUB_TOKEN` is set and confirm the tick
skips with a message naming the missing variable (no fallback). Inspect a launched container's
environment, the run tags, the logs, and the transcript and confirm the board token appears in none
of them.

**Acceptance Scenarios**:

1. **Given** `GITHUB_PROJECT_TOKEN` is unset and `GITHUB_TOKEN` is set, **When** the sensor ticks,
   **Then** it skips with a message naming the missing `GITHUB_PROJECT_TOKEN` and does not fall back.
2. **Given** a run launched by the sensor, **When** its container environment, run tags, logs, and
   transcript are inspected, **Then** the board token is absent from all of them.

---

### User Story 7 - A GitHub outage or bad board degrades safely (Priority: P2)

When GitHub errors, rate-limits, or times out, the tick becomes a skip with a reason and leaves the
cursor untouched, so nothing is lost or re-fired. When the board, status name, or field cannot be
resolved, the tick is a skip whose message names what was not found — not a crash loop, and not a
load failure that takes other agents down with it. Boards larger than one page of items are followed
to completion, and several agents watching the same board share one query per tick.

**Why this priority**: A polling sensor lives with transient GitHub failures and operator typos. If
those crash the sensor or re-fire launches, the trigger is unusable in practice.

**Independent Test**: Set `status` to a name the board does not have and confirm ticks skip with a
message naming the missing option while other agents and sensors keep running. Simulate a GitHub
error and confirm the cursor is unchanged and nothing re-fires.

**Acceptance Scenarios**:

1. **Given** a GitHub error, rate-limit response, or timeout on a tick, **When** the tick ends,
   **Then** it is a skip with a reason and the cursor is unchanged, so no launch is lost or repeated.
2. **Given** a `status` option the board does not have, **When** the sensor ticks, **Then** it skips
   with a message naming the missing option, and other agents and sensors are unaffected.
3. **Given** a board with more than one page of items, **When** the sensor queries it, **Then** it
   follows pagination so items beyond the first page are considered.
4. **Given** several agents watching the same board, **When** they tick, **Then** the board is
   queried once per tick and shared among them.

---

### User Story 8 - Misconfiguration fails one agent, not the box (Priority: P2)

When an operator writes an invalid `on_project_status` block, only that one agent fails to load, with
a message naming the file and the offending field, in the same style as the existing `depends_on` and
`checks` validation. Every other agent still loads.

**Why this priority**: A resilient loader is an existing guarantee (Agent Isolation). A bad new block
must not regress it by taking unrelated agents down.

**Independent Test**: Write a YAML file with `on_project_status` missing `project`; confirm it fails
to load with a message naming the file and field while every other agent still loads.

**Acceptance Scenarios**:

1. **Given** an `on_project_status` block missing a required field (`owner`, `project`, or `status`),
   **When** definitions load, **Then** that one agent fails with a file-and-field message and every
   other agent still loads.
2. **Given** `project` that is not a positive integer or `interval_seconds` below 30, **When**
   definitions load, **Then** that one agent fails with a message naming the offending field.

---

### User Story 9 - Operate the trigger from the UI (Priority: P3)

An operator manages the trigger through the management UI the same way as every other automation. The
agent editor can read and write the field group and round-trips it unchanged on save-and-reload. The
sensor appears alongside the agent's other instigators, starts paused, and can be started and stopped
with the existing sensor toggle. Its purpose is described in plain words ("When an issue enters *In
progress* on vortexbox001/1"), held issues are visible there with their reason, and a run launched
this way shows the sensor as its launcher and links the issue number on its run page.

**Why this priority**: The trigger is usable as YAML-only, so the UI work is valuable but not
blocking — the brief's null action allows shipping YAML-only with the Automation-view toggle and
adding editor fields later.

**Independent Test**: Save the agent from the UI, reload, and confirm the block round-trips
unchanged; toggle the sensor from the Automation view and confirm the change takes effect; open a
launched run and confirm the sensor is named as launcher and the issue number links to the issue.

**Acceptance Scenarios**:

1. **Given** an agent with an `on_project_status` block edited in the UI, **When** it is saved and
   reloaded, **Then** the block round-trips unchanged.
2. **Given** the sensor in the Automation view, **When** the operator toggles it, **Then** it starts
   and stops, and it starts paused by default.
3. **Given** issues held behind an active one, **When** the operator views the automation, **Then**
   the held issues are shown with the reason.
4. **Given** a run launched by the sensor, **When** its run page is opened, **Then** the sensor is
   named as the launcher and the issue number links to the issue.

---

### Edge Cases

- **Same issue re-entering:** An issue moved out and back in is forgotten on leaving and eligible
  again on return, so it launches once more.
- **Board with items already in status at first start:** Pre-existing items are recorded as
  seen-and-not-eligible and neither launch nor hold the slot; only moves observed after that launch.
- **Non-issue items (PRs, drafts):** Excluded from launching and from holding the slot even when they
  sit in the target status.
- **Title edge cases:** Punctuation, emoji, path separators, `..`, and very long titles all still
  yield a key matching the grammar and length cap; non-ASCII letters and emoji are dropped rather than
  transliterated. A title that slugs to empty yields the three-digit issue number alone with no
  trailing hyphen (e.g. `038`).
- **Duplicate titles:** Two issues with identical titles produce different keys because the issue
  number leads the key.
- **Missing token:** `GITHUB_PROJECT_TOKEN` unset is a skip naming the variable, with no fallback to
  `GITHUB_TOKEN`.
- **Unresolvable board/status/field:** A skip naming what was not found, not a crash loop.
- **Transient GitHub failure:** A skip with a reason that leaves the cursor untouched.
- **Multi-page board:** Pagination followed so items beyond the first page count.
- **Stuck active feature:** The slot is released only by the board (the card leaving the status), not
  by any downstream completion signal — including when the launched run itself fails, errors, or is
  terminated while the issue is still in the status.
- **Empty or absent body:** The read-only body file is always written (empty when the body is empty),
  so `AGENTBOX_ISSUE_BODY_FILE` always points at a readable file; the body is written unbounded (only
  the title is capped).
- **Closed or deleted issue in status:** A closed issue still shown in the column is treated as
  in-status until it leaves; once the board stops returning it in-status it is forgotten and frees the
  slot like any other leave.
- **Same board, different statuses:** Several agents may watch the same board on different Status
  options; the one shared per-tick query returns the whole board and each sensor applies its own
  status/label/repo filter, so they never cross-contaminate.

## Requirements *(mandatory)*

### Functional Requirements

**Trigger configuration**

- **FR-001**: An agent's `triggers` block MUST accept an optional `on_project_status` entry with
  fields `owner` (board owner), `project` (board number), `status` (Status option name, matched
  case-insensitively), optional `label` (only issues carrying it — matched by exact membership of the
  issue's label-name list, case-insensitively), optional `repo` (only issues from
  it, given as the full `owner/repo` name and matched case-insensitively), and optional
  `interval_seconds` (default 60, minimum 30).
- **FR-002**: The `on_project_status` trigger MUST be valid for both agent kinds — a job-kind agent is
  launched by job name and an asset-kind agent is materialized — using the same launch distinction the
  UI already makes, and it MUST compose with the other triggers rather than replace them.

**Observation and launch decision**

- **FR-003**: Each agent carrying the trigger MUST get one dedicated polling sensor, named
  `project_status_<name>`, that on each tick queries the board's items and their Status value using
  only outbound calls — no inbound endpoint, tunnel, or webhook receiver.
- **FR-004**: On each tick the sensor MUST keep only items that are issues (not pull requests or
  draft items) in the configured status and passing the optional `label` and `repo` filters, and MUST
  decide from those which to launch.
- **FR-005**: The sensor MUST fire once per entry into the status: it MUST track the items currently
  seen in the target status with the time each was first seen there and whether it has been launched;
  an item becomes eligible when it appears and was not present on the previous tick; an item is
  forgotten when it leaves the status, so moving an issue out and back in makes it eligible again.
- **FR-006**: The run key for a launch MUST be derived from the item id plus the time it entered the
  status, so a sensor restart or a repeated tick never double-launches the same entry.
- **FR-007**: On the sensor's first tick with no cursor (first start or after a cursor reset), it MUST
  record the items already in the status as seen-and-not-eligible and launch nothing; only moves
  observed after that MUST launch.

**One feature at a time**

- **FR-008**: An issue MUST be treated as active from the moment its run launches until it leaves the
  target status. While any issue is active, other eligible issues MUST be held rather than launched.
  The single in-flight slot is scoped per agent: each agent's sensor holds its own slot independently,
  so two different board-driven agents may each have one issue active at the same time.
- **FR-009**: Held issues MUST be reported on the tick as held, naming the issue that is holding them.
- **FR-010**: When the active issue leaves the target status, the held issues MUST be launched
  oldest-first (by the time they entered the status), one at a time as the slot frees. Releasing the
  slot MUST require no knowledge of any downstream chain — only the board move.

**Feature key**

- **FR-011**: For each launch the sensor MUST derive a feature key as a pure function of the issue:
  the issue number zero-padded to three digits, a hyphen, then a slug of the title using only
  lowercase `a-z0-9` and single hyphens, with no leading or trailing hyphen and at most 48 characters
  total (e.g. issue 38 "UI Update: Runs overview page…" → `038-ui-update-runs-overview-page`). The
  derivation MUST take no configuration. Non-ASCII letters and emoji MUST be dropped, not
  transliterated — only `a-z0-9` characters survive slugging. When the slug is empty (a title that is
  entirely punctuation, emoji, or control characters), the key MUST be the three-digit issue number
  alone with no trailing hyphen (e.g. `038`).

**What the run receives**

- **FR-012**: The launched run MUST carry tags `agentbox/issue_number`, `agentbox/issue_repo`,
  `agentbox/issue_url`, `agentbox/project_item_id`, and `agentbox/feature_key`.
- **FR-013**: The launched container MUST receive environment values `AGENTBOX_ISSUE_NUMBER`,
  `AGENTBOX_ISSUE_REPO`, `AGENTBOX_ISSUE_URL`, `AGENTBOX_ISSUE_TITLE`, and `AGENTBOX_FEATURE_KEY`.
  `AGENTBOX_ISSUE_REPO` (and the matching `agentbox/issue_repo` tag) MUST be the full `owner/repo`
  name.
- **FR-014**: The issue body MUST be written to a read-only file whose path is provided as
  `AGENTBOX_ISSUE_BODY_FILE`; the body MUST never be placed on the command line or in an environment
  variable. This MUST reuse the mechanism the upstream handoff (spec 013) already uses to place files
  and env keys into a run.
- **FR-015**: Issue title and body MUST be treated as data, not configuration: they MUST be handed to
  the agent as input only, never substituted into agent configuration, paths, commands, or tags
  beyond the sanitized feature key; the title MUST be stripped of control characters and length-capped
  to at most 256 characters (longer titles truncated) before becoming the `AGENTBOX_ISSUE_TITLE`
  environment value.

**Token isolation**

- **FR-016**: The sensor MUST read its GitHub token only from `GITHUB_PROJECT_TOKEN`, with no
  fallback to `GITHUB_TOKEN`; if it is missing, the tick MUST skip with a message naming the missing
  variable.
- **FR-017**: The board token MUST be used only by the sensor process — never forwarded to a
  container, tagged onto a run, logged, or written to a file — and MUST pass through the existing
  redaction.

**Governors and lineage**

- **FR-018**: A sensor-launched run MUST be treated as an automated run: it MUST carry
  `dagster/sensor_name`, count toward the existing launch-rate governor, and start a chain at depth 1
  like any other root.

**Failure behaviour and resilience**

- **FR-019**: A GitHub error, rate-limit response, or timeout on a tick MUST make the tick a skip
  with a reason and leave the cursor untouched, so no launch is lost or re-fired.
- **FR-020**: A board, status name, or field that cannot be resolved MUST make the tick a skip whose
  message names what was not found — not a crash loop, and not a load failure that affects other
  agents.
- **FR-021**: Board pagination MUST be followed so boards with more than one page of items work, and
  several agents watching the same board MUST share one query per tick.

**Re-homability**

- **FR-022**: Observation (what is on the board) and admission (what gets launched) MUST be separate
  steps; the cursor and deduplication keys MUST be durable; and launches MUST go through the same
  request path as spec 013's event-driven triggers, so a later feature can adopt this as an external
  observer without changing its behaviour or re-firing anything.

**Load-time validation**

- **FR-023**: When the `on_project_status` block is present, `owner`, `project`, and `status` MUST be
  required; `project` MUST be a positive integer; `interval_seconds` MUST be an integer ≥ 30. A bad
  block MUST fail that one agent with a file-and-field message in the same style as the existing
  `depends_on` and `checks` validation, leaving every other agent loadable.

**Schema and editor**

- **FR-024**: The UI schema MUST gain the `on_project_status` field group so the agent editor can
  read and write it; the generated YAML MUST carry the usual inline comment for it; and the schema
  version MUST be bumped with a migration that leaves existing files unchanged apart from the version.

**Automation view and runs**

- **FR-025**: The sensor MUST appear alongside the agent's other instigators, MUST start paused, and
  MUST be startable and stoppable with the existing sensor toggle; its trigger MUST be described in
  plain words (e.g. "When an issue enters *In progress* on vortexbox001/1"); and held issues MUST be
  visible there with their reason.
- **FR-026**: A run launched this way MUST show the sensor as its launcher, and its run page MUST show
  the issue number as a link to the issue.

### Key Entities *(include if feature involves data)*

- **`on_project_status` trigger**: The declarative configuration on an agent — `owner`, `project`,
  `status`, optional `label`, `repo`, and `interval_seconds` — that turns a board column into a launch
  signal for that agent.
- **Board item**: An item on the GitHub Projects board with a content type (issue, pull request, or
  draft) and a Status value. Only issues are launch candidates; the item id anchors deduplication.
- **Sensor cursor**: The durable record of items currently seen in the target status, each with the
  time first seen there and whether it has been launched — the basis for exactly-once entry, first-
  tick suppression, and restart safety.
- **Active feature**: The one issue whose run is in flight (from launch until it leaves the status),
  which holds the single slot; other eligible issues wait behind it.
- **Feature key**: The pure-function-derived identifier for a launch (three-digit issue number,
  hyphen, slugged title, capped at 48 characters), inherited by later features as a substitution and
  partition key.
- **Run handoff**: The set of tags, environment values, and the read-only body file placed into the
  launched run, reusing the spec 013 handoff mechanism.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Moving a matching issue into the target status launches exactly one run within about a
  minute, carrying the correct issue number, title, feature key, and body.
- **SC-002**: An issue left in the target status for ten minutes, and a daemon restart, each produce
  zero additional runs for that issue.
- **SC-003**: Moving an issue out of the target status and back in produces exactly one more run.
- **SC-004**: With one issue active, additional eligible issues produce zero launches and are all
  reported as held; when the slot frees they launch one at a time, oldest first.
- **SC-005**: On a board that already has three issues in the target status at first sensor start,
  zero launch and zero hold the slot; an issue moved in afterward launches.
- **SC-006**: Issues without the required label, pull requests, and draft items produce zero launches
  and never hold the slot.
- **SC-007**: Every derived feature key matches the grammar and the 48-character cap for titles with
  punctuation, emoji, path separators, `..`, and 200 characters, and two issues sharing a title
  produce different keys.
- **SC-008**: The board token appears in none of a launched container's environment, the run tags,
  the logs, or the transcript; an unset `GITHUB_PROJECT_TOKEN` produces a skip naming it with no
  fallback.
- **SC-009**: A missing status option, a GitHub failure, and an invalid config block each affect only
  the offending agent/tick — every other agent and sensor keeps loading and running, and no launch is
  lost or re-fired.
- **SC-010**: The full behaviour set — cursor (enter, stay, leave, re-enter, first tick, restart,
  held, release order), key derivation, filters, pagination, and each failure mode — is covered by
  unit tests with the GitHub client faked, and no test makes a network call.

## Assumptions

These resolve the brief's "decisions to confirm," adopting its proposals; each is a reasonable
default that later slices (#22, #23, #24) may revisit.

- **Re-entry re-launches**: An issue moved out and back into the status launches again (proposed:
  yes), rather than launching only once ever.
- **Release rule**: "Active until it leaves the status" is the release rule for the one-at-a-time
  limit — it needs no knowledge of the downstream chain, and a stuck chain is released by moving the
  card, rather than waiting on a named final asset.
- **Poll cadence**: `interval_seconds` defaults to 60 with a floor of 30.
- **Status matching**: The status is matched by option name, case-insensitively (readable, but breaks
  if the column is renamed), rather than by opaque option id.
- **Feature-key grammar and cap**: Three-digit zero-padded issue number, hyphen, slugged title,
  lowercase `a-z0-9` and single hyphens only, capped at 48 characters — the grammar #22 and #24
  inherit. The env and tag names are the brief's proposals and are adopted as-is.
- **Handoff reuse (null action)**: The issue body is delivered as a read-only file through the spec
  013 handoff mechanism; if that cannot be reused cleanly, the fallback is to ship the env keys and
  tags only and have the agent fetch the body itself.
- **UI scope (null action)**: If the editor work is more than adding a field group, the trigger ships
  YAML-only with load-time validation and the Automation-view toggle, and the editor fields follow
  later.
- **Board ownership**: Boards owned by a user rather than an org may work through the same query but
  are not a requirement.
- **Feature-key hand-off by convention**: Until #22 lands, carrying the feature key down a chain is
  handled in the config repository by convention (the first agent records it in the shared workspace,
  later prompts read it), not by AgentBox.

### Out of Scope

- A webhook receiver or any inbound endpoint.
- Reacting to board fields other than Status, to labels alone, to pull requests, or to comments.
- Writing back to GitHub (moving the card, commenting, assigning).
- More than one feature in flight, per-feature workspaces, and partitions of any kind (#24).
- Substituting the feature key into agent configuration (#22).
- Project files, repository aliases, and credential roles (#23).
- Creating branches, or changing the speckit agents to use the feature key.
