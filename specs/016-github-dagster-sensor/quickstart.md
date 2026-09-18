# Quickstart: GitHub Project Status Trigger — Board-Driven Agent Launches

Runnable validation for the feature. Fast, deterministic checks run as unit tests with the GitHub
client faked and **no network call** (SC-010); the end-to-end board→run behaviour is validated against
a live board, matching the 006/008/012/013 posture. Paths are project-relative; run commands from the
repo root.

## Prerequisites

- The stack builds and runs: `docker compose build && docker compose up -d` (orchestrator + daemon +
  UI). Dagster UI at `http://10.0.0.100:3000`, management UI at the `ui` service. The `dagster-daemon`
  can reach `api.github.com` (outbound only).
- `GITHUB_PROJECT_TOKEN` is set in `.env` (board read scope) — the daemon's environment only.
- A GitHub Projects board with a **Status** field including an `In progress` option (first use:
  `vortexbox001` project `1`).
- A demo agent with the trigger — `agents/board-hello.yaml`:
  ```yaml
  triggers:
    on_project_status:
      owner: vortexbox001
      project: 1
      status: In progress
      label: brief          # optional
  ```
  a trivial prompt that echoes `AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_FEATURE_KEY`, and the first line of
  `AGENTBOX_ISSUE_BODY_FILE`.

## §0 Static checks (unit tests)

```bash
.venv/bin/python -m pytest -q orchestrator/tests   # github_projects, factory, definitions
.venv/bin/python -m pytest -q ui/tests             # schema, agents_store, api, conformance
```

Expected: green. Key assertions — see [contracts/](contracts/):
- `plan_tick` state machine: enter (launch), stay (no relaunch), leave (forgotten), re-enter
  (relaunch), first tick (seed + launch none), restart (cursor reload ⇒ no relaunch), held + release
  order (oldest-first).
- `feature_key`/`sanitize_title`: `038-ui-update-runs-overview-page`; punctuation/emoji/`..`/200-char
  ⇒ `^[0-9]{3}(-[a-z0-9]+)*$` and ≤48; all-punctuation title ⇒ `038`; two same-title issues differ by
  number; title control-stripped and ≤256.
- Filters: label, `owner/repo` case-insensitive, PR + draft excluded, excluded items never held.
- Pagination followed; each failure mode → skip-with-reason, cursor unchanged.
- Schema: the `on_project_status` group in `/api/schema`; `migrate_7_to_8` identity; the emitter
  round-trips the nested block; golden files carry the schema-8 header.

## §1 US1 — launch an agent when an issue enters a status (P1)

1. In the UI (or YAML), confirm `board-hello` carries the block; save. In the Automation view, turn
   **on** the `project_status_board_hello` sensor (new sensors start paused).
2. Move an issue into **In progress** on `vortexbox001/1`.
3. **Expected** (SC-001 / US1 #1): within ~a minute exactly one run of `board-hello` launches.
4. Open the run. **Expected** (US1 #2): the container saw `AGENTBOX_ISSUE_NUMBER`,
   `AGENTBOX_ISSUE_REPO` (full `owner/repo`), `AGENTBOX_ISSUE_URL`, `AGENTBOX_ISSUE_TITLE`,
   `AGENTBOX_FEATURE_KEY`, and `AGENTBOX_ISSUE_BODY_FILE` pointing at a **read-only** file whose
   contents are the issue body.
5. Inspect the run tags. **Expected** (US1 #3): `agentbox/issue_number`, `agentbox/issue_repo`,
   `agentbox/issue_url`, `agentbox/project_item_id`, `agentbox/feature_key`.
6. Paused-by-default (US1 #5): with the sensor off, moving an issue in launches nothing until it is
   turned on.
7. Both kinds (US1 #4): repeat with a job-kind agent and an asset-kind agent — the job is launched by
   job name, the asset is materialized.

## §2 US2 — exactly once per entry (P1)

1. Move one issue in ⇒ one run (§1). Leave it ten minutes. **Expected** (SC-002 / US2 #1): no further
   run.
2. Restart the daemon (`docker compose restart dagster-daemon`). **Expected** (US2 #2): no further run
   for that issue (the cursor + run-key ledger persist).
3. Move the issue **out** and back **in**. **Expected** (SC-003 / US2 #3): exactly one more run.
4. First-tick suppression (US2 #4): with three issues already in **In progress**, turn the sensor on
   for the first time (or reset its cursor). **Expected** (SC-005): none of the three launch and none
   hold the slot; an issue moved in afterward does launch.

## §3 US3 — one feature in flight at a time (P1)

1. With one issue active, move a **second** eligible issue in. **Expected** (SC-004 / US3 #1): nothing
   launches for it; the Automation view shows it **held**, naming the holder.
2. Move the first issue **out** of the status. **Expected** (US3 #2): the held issue launches on the
   next tick and becomes active.
3. Move three in while one is active. **Expected** (US3 #3): they launch one at a time, oldest-first,
   as the slot frees.
4. Stuck active feature (US3 #4): with a run wedged, move its card out of the status. **Expected**: the
   slot frees and the next held issue launches — no downstream knowledge required.

## §4 US4 — only intended items launch (P2)

1. With `label: brief` set, move in an issue **without** the label, a **pull request**, and a **draft**
   item. **Expected** (SC-006 / US4 #1/#3): none launch and none hold the slot.
2. Move in an issue **with** the label ⇒ it launches.
3. With `repo: vortexbox001/agentbox`, an issue from another repo does not launch and does not hold
   the slot (US4 #2).

## §5 US5 — every launch gets a stable feature key (P2)

Covered by unit tests (§0). Live spot-check: issue 38 titled "UI Update: Runs overview page…" ⇒
`AGENTBOX_FEATURE_KEY=038-ui-update-runs-overview-page`; an all-emoji title ⇒ `038`.

## §6 US6 — the board token stays isolated (P2)

1. Unset `GITHUB_PROJECT_TOKEN` (leave `GITHUB_TOKEN` set) and let the sensor tick. **Expected**
   (SC-008 / US6 #1): the tick skips with a message naming the missing `GITHUB_PROJECT_TOKEN` — no
   fallback.
2. For a launched run, inspect the container environment, the run tags, the daemon logs, and the
   transcript. **Expected** (US6 #2): the board token appears in none of them.

## §7 US7 — degrade safely (P2)

1. Set `status` to a name the board does not have. **Expected** (US7 #2): ticks skip naming the missing
   option, while other agents and sensors keep loading and running.
2. Simulate a GitHub error/timeout (unit test, or a bad token scope live). **Expected** (SC-009 /
   US7 #1): the tick skips with a reason and the cursor is unchanged — nothing re-fires.
3. A board with more than one page of items (unit test with paged fixtures): items beyond the first
   page are considered (US7 #3).
4. Two agents on the same board tick near-simultaneously: one board query is shared (US7 #4).

## §8 US8 — misconfiguration fails one agent, not the box (P2)

Write an `on_project_status` block missing `project`; reload. **Expected**: that one agent fails to
load with a message naming the file and field, while every other agent still loads (unit test in
`test_definitions.py`; live: the Dagster code location still loads the rest).

## §9 US9 — operate from the UI (P3)

1. Save `board-hello` from the UI, reload. **Expected** (US9 #1): the `on_project_status` block
   round-trips unchanged.
2. Toggle the sensor from the Automation view. **Expected** (US9 #2): it starts/stops; it starts
   paused by default.
3. With issues held (§3), the Automation view shows them with the reason (US9 #3).
4. Open a launched run. **Expected** (US9 #4): the sensor is named as launcher and the issue number
   links to the issue.
