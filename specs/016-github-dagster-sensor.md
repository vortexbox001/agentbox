**Intent.** Let a GitHub Projects board drive AgentBox. When an issue is moved into a chosen status on a chosen project (first use: "In progress" on `vortexbox001` project 1), AgentBox launches an agent for that issue, once, with the issue's identity available to the run. Today triggers are cron, `on_upstream`, and `on_missing` — nothing reacts to an outside event. GitHub only delivers `projects_v2_item` events to org webhooks and Apps, never to Actions, and the box is not reachable from the internet, so this is a polling Dagster sensor: outbound calls only, no tunnel, no webhook receiver.

This is deliberately the smallest version that gets one real issue from the board to a pull request: one board, one feature at a time, no partitions, no templating, no project files. Parameterized agents (#22), projects and authority boundaries (#23), and dynamic partitions and external assets (#24) each build on it and say so.

**What changes.**

*A new trigger, `on_project_status`*
- **Config (#173).** An agent's `triggers` block gains an optional `on_project_status` entry:
  ```yaml
  triggers:
    on_project_status:
      owner: vortexbox001          # org or user that owns the board
      project: 1                   # board number
      status: In progress          # option name of the board's Status field, matched case-insensitively
      label: brief                 # optional: only issues carrying this label
      repo: vortexbox001/agentbox  # optional: only issues from this repository
      interval_seconds: 60         # optional, default 60, minimum 30
  ```
  It is valid for both agent kinds: a job-kind agent is launched by job name, an asset-kind agent is materialized, the same way the UI's launch path distinguishes them. It composes with the other triggers rather than replacing them.
- **Sensor (#174).** Each agent with this trigger gets one Dagster sensor, `project_status_<name>`. On each tick it queries the GitHub GraphQL API for the board's items and their Status value, keeps the items that are issues (not pull requests or draft items) in the configured status and passing the optional `label` / `repo` filters, and decides which of them to launch.
- **Fire once per entry into the status (#175).** The sensor cursor holds the items currently seen in the target status, each with the time it was first seen there and whether it has been launched. An item becomes eligible when it appears and was not there on the previous tick; it is forgotten when it leaves the status, so moving an issue out and back in makes it eligible again. The run key is derived from the item id plus the time it entered the status, so a sensor restart or a repeated tick never double-launches.
- **One feature at a time (#176).** The agents a board trigger starts today share one workspace and one hardcoded branch, so two features in flight would collide. An issue is *active* from the moment its run is launched until it leaves the target status. While any issue is active, other eligible issues are held — reported on the tick as held, with the issue that is holding them — and are launched oldest-first as the slot frees. The board is the source of truth: moving the active issue on (to review, to done, or back) is what releases the next one. Nothing tracks the downstream chain.
- **First tick does not stampede (#177).** When the sensor has no cursor yet (first start, or after a cursor reset), it records the items already in the status as seen-and-not-eligible without launching anything. Only moves observed after that launch runs.
- **Feature key (#178).** For each launch the sensor derives a feature key from the issue: the issue number zero-padded to three digits, a hyphen, and a slug of the title — lowercase `a-z0-9` and single hyphens only, no leading or trailing hyphen, at most 48 characters in total (issue 38 "UI Update: Runs overview page…" → `038-ui-update-runs-overview-page`). The derivation is a pure function with no configuration. In this brief the key is only a value handed to the run; #22 makes it substitutable and #24 makes it a partition key, and both rely on this grammar.
- **What the run receives (#179).** The launched run carries tags `agentbox/issue_number`, `agentbox/issue_repo`, `agentbox/issue_url`, `agentbox/project_item_id`, `agentbox/feature_key`. The container receives `AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_ISSUE_REPO`, `AGENTBOX_ISSUE_URL`, `AGENTBOX_ISSUE_TITLE`, `AGENTBOX_FEATURE_KEY`, and the issue body is written to a read-only file whose path is given as `AGENTBOX_ISSUE_BODY_FILE`. The body goes in a file, never on the command line or in an environment variable, because briefs run to several KB. This reuses the mechanism the upstream handoff already uses to place files and env keys into a run.
- **Issue content is data, not configuration (#180).** The title and body are written by whoever can edit the issue. They are handed to the agent as input and nothing else: they are never substituted into agent configuration, paths, commands, or tags beyond the sanitized feature key, and the title is length-capped and stripped of control characters before it becomes an env value.
- **Token (#181).** The sensor reads its GitHub token from one dedicated host variable, `GITHUB_PROJECT_TOKEN`, and nothing else — there is no fallback to `GITHUB_TOKEN`. It needs `read:project` (classic) or org "Projects: read" (fine-grained), plus read access to the issues. The token is used only by the sensor process: it is never forwarded to a container, tagged onto a run, logged, or written to a file, and it goes through the existing redaction.
- **Governors (#182).** A sensor-launched run is an automated run: it carries `dagster/sensor_name`, counts toward the existing launch-rate governor, and starts a chain at depth 1 like any other root.
- **Failure behaviour (#183).** A GitHub error, rate-limit response, or timeout makes the tick a skip with a reason; the cursor is left untouched so nothing is lost or re-fired. A board, status name, or field that cannot be resolved is a skip with a message naming what was not found — not a crash loop, and not a load failure that takes other agents down with it. Board pagination is followed so boards with more than one page of items work. Several agents watching the same board share one query per tick.
- **Built to be re-homed (#184).** Observation (what is on the board) and admission (what gets launched) are separate steps, the cursor and deduplication keys are durable, and launches go through the same request path as spec 013's event-driven triggers — so #24 can adopt this as one of its external observers without changing its behaviour or re-firing anything.

*Validation and UI*
- **Load-time validation (#185).** `owner`, `project`, and `status` are required when the block is present; `project` is a positive integer; `interval_seconds` is an integer ≥ 30. A bad block fails that one agent with a file-and-field message, in the same style as `validate_depends_on` and `validate_checks`.
- **Schema and editor (#186).** The UI schema gains the field group so the agent editor can read and write it, the generated YAML carries the usual inline comment for it, and the schema version is bumped with a migration that leaves existing files unchanged apart from the version.
- **Automation view (#187).** The sensor appears alongside the agent's other instigators and can be started and stopped with the existing sensor toggle. Like the automation-condition sensors, it starts paused. The trigger is described in plain words ("When an issue enters *In progress* on vortexbox001/1"), and held issues are visible there with the reason.
- **Runs (#188).** A run launched this way shows the sensor as its launcher, and its run page shows the issue number as a link to the issue.

**What I'd check.**
- Configure the trigger on a hello-style agent that echoes `AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_FEATURE_KEY`, and the first line of the body file. Start the sensor. Move an issue with the `brief` label into In progress: exactly one run launches within about a minute, with the right number, title, key, and body.
- Leave it there for ten minutes: no further runs. Restart the Dagster daemon: no further runs.
- Move a second issue in while the first is still In progress: it is reported as held and nothing launches. Move the first issue on: the second launches on the next tick. Move three in at once: they launch one at a time, oldest first.
- Move the issue to another status and back: one more run.
- Move in an issue without the `brief` label, a pull request, and a draft item: none launch, and none hold the slot.
- Start the sensor for the first time on a board that already has three issues In progress: none launch and none hold the slot; the fourth one moved in afterwards does launch.
- Titles with punctuation, emoji, path separators, `..`, and 200 characters all produce a key matching the grammar and the length cap; two issues with the same title produce different keys.
- Set `status` to a name the board does not have: the ticks report a skip naming the missing option; other agents and sensors are unaffected.
- Unset `GITHUB_PROJECT_TOKEN` while `GITHUB_TOKEN` is set: skip with a message naming the missing variable — it does not fall back. Inspect a launched container's environment, the run tags, logs, and transcript: the board token is absent from all of them.
- A YAML file with `on_project_status` missing `project` fails to load with a message naming the file and field, and every other agent still loads.
- Save the agent from the UI and reload: the block round-trips unchanged. Toggle the sensor from the Automation view: Dagster reflects it.
- Unit tests cover the cursor (enter, stay, leave, re-enter, first tick, restart, held, release order), key derivation, filters, pagination, and each failure mode with the GitHub client faked — no test calls the network.

**Out of scope.** A webhook receiver or any inbound endpoint. Reacting to other board fields, to labels alone, to pull requests, or to comments. Writing back to GitHub (moving the card, commenting, assigning). More than one feature in flight, per-feature workspaces, and partitions of any kind (#24). Substituting the feature key into agent configuration (#22). Project files, repository aliases, and credential roles (#23). Creating branches, or changing the speckit agents to use the feature key — until #22 lands, carrying the key down a chain is handled in the config repository by convention (the first agent records it in the shared workspace and later prompts read it), not by AgentBox. Boards owned by a user rather than an org may work through the same query but are not a requirement.

**Null action.** If passing the issue body as a file cannot reuse the handoff mechanism cleanly, ship the env keys and tags only and have the agent fetch the body itself with its own token. If the UI editor work is more than adding a field group, ship the trigger as YAML-only with load-time validation and the Automation-view toggle, and add the editor fields in a follow-up.

**Decisions to confirm when this is specified.**
- Whether re-entering the status should re-launch (proposed: yes) or an issue should only ever launch once.
- Whether "active until it leaves the status" is the right release rule for the one-at-a-time limit (proposed: yes — it needs no knowledge of the chain, and a stuck chain is released by moving the card) or the sensor should instead wait on a named final asset.
- The poll interval default and floor (proposed: 60s / 30s).
- Whether the status match should be by option name (proposed: readable, breaks if the column is renamed) or by option id (stable, opaque).
- The feature-key grammar and length cap, since #22 and #24 inherit them. The env and tag names are proposals.

**Delivery notes.** Stage "Build one useful change". It comes before #23 slice A, #22, and #24, each of which replaces a deliberate simplification here: the dedicated host token (#23), the by-convention hand-off of the feature key (#22), and the one-at-a-time limit (#24).

