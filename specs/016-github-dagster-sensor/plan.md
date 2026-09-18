# Implementation Plan: GitHub Project Status Trigger — Board-Driven Agent Launches

**Branch**: `016-github-dagster-sensor` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-github-dagster-sensor/spec.md`

## Summary

Turn a GitHub Projects board column into an agent launch signal. An agent gains an optional
`triggers.on_project_status` block (`owner`, `project`, `status`, optional `label`, `repo`,
`interval_seconds`). Each agent carrying it gets one dedicated **polling `SensorDefinition`** named
`project_status_<name>` (paused by default) that on each tick makes **outbound-only** GitHub GraphQL
calls to read the board's items and their Status, follows pagination, and decides which issues to
launch. When an issue enters the target status it launches the agent **exactly once** and hands the
run the issue's identity — number, `owner/repo`, URL, a control-stripped 256-char title, a derived
feature key, and the issue body as a read-only file — reusing the spec 013 handoff machinery.

This is deliberately **not** the spec-013 automation-condition path. `on_upstream`/`on_missing` ride
`AutomationConditionSensorDefinition`, which is driven by Dagster's own asset-graph state and cannot
make outbound calls or hold an external cursor. A board trigger needs to poll GitHub, keep a durable
cursor of what it has seen, and emit run-keyed `RunRequest`s — so it is a genuine custom sensor. Once
a run is launched it flows through the **same op, handoff, tags, and governor gate** as every other
automated run (FR-018/FR-022): observation (what is on the board) is separated from admission (what
gets launched) so a later feature can re-home the observer without changing behaviour.

The sensor is the single point of exactly-once, first-tick suppression, one-at-a-time admission, and
filtering. Its cursor records the items currently seen in the target status, each with the time it
was first seen there and whether it has launched. An item is **eligible** when it appears and was not
present on the previous tick; it is **forgotten** when it leaves the status (re-entry re-launches);
the run key `<project_item_id>:<entered_at>` makes a restart or a repeated tick a no-op. One
**slot per agent**: while a launched issue is still in the status the slot is held and other eligible
issues are reported held (oldest-first release), because the board — not any downstream signal — is
the source of truth for "active".

The feature key is a pure function of the issue (`NNN` + `-` + slugged title, `a-z0-9` and single
hyphens, ≤48 chars; `NNN` alone when the slug is empty). The board token is read only from
`GITHUB_PROJECT_TOKEN` in the daemon (no fallback to `GITHUB_TOKEN`), is never forwarded to a
container / tag / log / file, and passes through the existing redaction. The UI schema gains the
`on_project_status` field group (schema **7→8**, identity migration), the sensor appears in the
Automation view with a plain-words description and a start/stop toggle, held issues surface with
their reason, and a sensor-launched run shows the sensor as launcher with the issue number linked.

**Decisions taken unattended** (recorded in [research.md](research.md); no human was available to
clarify — the spec's own Clarifications of 2026-09-17 resolved the five product questions): a custom
`SensorDefinition`, not an automation condition (R1); GitHub Projects v2 read via GraphQL with a
Status single-select match by option name, case-insensitively (R2); the cursor shape and the
`<item_id>:<entered_at>` run key for exactly-once + first-tick suppression + restart safety (R3);
the per-agent slot computed purely from the board + cursor, released by the card leaving the status
(R4); issue identity handed to the op via `RunRequest` tags + `run_config`, with the body written to
a `:ro` file by the same handoff pattern spec 013 uses (R5); the feature-key/title pure functions
(R6); token isolation and redaction (R7); resilience — skip-with-reason leaves the cursor untouched,
pagination is followed, and a per-tick board cache shares one query across sensors on the same board
(R8); load-time validation as a per-agent reject (R9); schema field group + emitter + migration
(R10); the Automation-view + run-page UI, with the editor **form fields** as the null-action flex
point (R11); the `github_projects` module boundary that makes observation re-homable (R12).

## Technical Context

**Language/Version**: Python 3.12 — orchestrator (`factory.py`, `definitions.py`, a new
`github_projects.py`) and UI (`schema.py`, `agents_store.py`, `main.py`, `dagster.py`, templates,
`static/`, tests). Browser ES-module JavaScript (no build step) for the trigger card and the
Automation-view held-issues surface. Same toolchain as 004–015; see AGENTS.md **Stack and tests**.

**Primary Dependencies**: Dagster **1.13.21** (pinned by the orchestrator image). New surface used:
`dagster.sensor` / `SensorDefinition`, `SensorEvaluationContext.cursor` / `update_cursor`,
`RunRequest(run_key=…, tags=…, run_config=…, asset_selection=…|job_name=…)`, `SkipReason`,
`DefaultSensorStatus.STOPPED`, `minimum_interval_seconds`. Existing and unchanged:
`make_run_op` / the container launch, `build_materializing_job`, the spec-013 handoff dir + `:ro`
mount pattern (`_prepare_upstream_handoff` / `_launch_mounts` / `_build_agent_cmd`), `governor_gate`
+ `is_automated_run` + `derive_chain_depth` + `record_chain_depth`, `redact`, `run_capture`. **New
runtime need**: outbound HTTPS from the `dagster-daemon` to `api.github.com`; the board token in the
daemon's environment. GraphQL is issued with the already-pinned `httpx` (also used by the UI); no new
Python package is added. FastAPI + Jinja + `httpx` + `pyyaml` + `croniter` + `pytest`/`TestClient`
on the UI side, unchanged.

**Storage**: `agents/*.yaml` under the config root (single source of truth; no database) gains the
`triggers.on_project_status` block. The **sensor cursor** is durable Dagster instigator state under
`$DAGSTER_HOME` (a JSON blob via `context.cursor`), keyed by the `project_status_<name>` sensor
name, together with Dagster's own per-sensor run-key ledger — the two give exactly-once across ticks
and restarts. The per-run **issue handoff** (body file) lives in an ephemeral per-run dir under
`$AGENTBOX_DATA` (host==container mount), mounted read-only at `/issue` and `--rm`-cleaned exactly
like the spec-013 upstream handoff. Title and body travel from sensor to op via `RunRequest.run_config`
(Dagster run storage — never a command line or env value). The board token lives only in the daemon
process environment (`.env`, gitignored), never written anywhere by AgentBox.

**Testing**: `pytest`. Orchestrator unit tests over `github_projects` + `factory`/`definitions` with
the GitHub client **faked** and no network call (SC-010): the admission function across enter / stay
/ leave / re-enter / first tick / restart-with-cursor / held + oldest-first release; feature-key and
title derivation over punctuation, emoji, path separators, `..`, 200-char and empty-slug titles;
filters (label, `owner/repo` case-insensitive, PR + draft exclusion, and that excluded items never
hold the slot); pagination followed; each failure mode (GitHub error / rate-limit / timeout →
skip-with-reason, cursor unchanged; missing status option / board / field → skip naming what was not
found; missing `GITHUB_PROJECT_TOKEN` → skip naming it, no fallback); the op-side issue handoff
(env values, the five run tags, the `:ro` body file and its path, the body never on the command line
/ env, and the token absent from container env / tags / logs / transcript); the sensor built paused
and only for agents carrying the block; `RunRequest` targeting an asset-kind vs a job-kind agent
(FR-002); load-time reject of a bad block naming the file+field while other agents load. UI `pytest`
via `TestClient`: schema exposes the `on_project_status` group; `validate` enforces required
fields + `project`≥1 int + `interval_seconds`≥30 int; the emitter writes the nested block with its
inline comment and round-trips; migration 7→8 identity; `/api/schema` shape; golden files
regenerated; the Automation view lists the sensor with its plain-words description and toggle and
surfaces held issues; a sensor-launched run shows the sensor as launcher and links the issue number;
design-system conformance for the new UI. End-to-end board→run behaviour is validated by
[quickstart.md](quickstart.md) against a live board (same posture as 006/008/012/013).

**Target Platform**: Docker Compose on the Raspberry Pi host (arm64, Debian/Bookworm). The
`dagster-daemon` runs the polling sensor and needs outbound HTTPS to GitHub (the box is not
reachable from the internet — outbound only, no tunnel or webhook receiver). Dagster UI at
`http://10.0.0.100:3000`; the `ui` service serves the management UI.

**Project Type**: Web service (management UI) + orchestrator (Dagster code location). Two packages,
`orchestrator/` and `ui/`. No new data directory; the issue handoff reuses the existing
`$AGENTBOX_DATA` host==container mount, the same boundary the pipes/staging/upstream dirs rely on.

**Performance Goals**: One GitHub GraphQL query per board per tick (shared across sensors on the same
board by a short-TTL process cache), paginated at 100 items/page — a handful of round trips for a
board of any realistic size, at a ≥30 s cadence. Admission is pure in-memory work over the page set.
Per launch: writing one small body file and the existing op path. No new per-run compute beyond the
body file write.

**Constraints**:
- **Outbound-only polling** (FR-003): a custom `SensorDefinition` making GitHub GraphQL calls; no
  inbound endpoint, tunnel, or webhook receiver anywhere.
- **Exactly-once per entry** (FR-005/FR-006/FR-007): the cursor tracks items seen in the status with
  first-seen time + launched flag; eligibility = "appeared and was not present last tick"; the run
  key `<item_id>:<entered_at>` dedupes across repeated ticks and restarts; first tick (no cursor)
  seeds seen-and-not-eligible and launches nothing.
- **One feature in flight per agent** (FR-008/FR-009/FR-010): the slot is held while a launched issue
  is still in the status; other eligible issues are reported held naming the holder; release is
  oldest-first by entered_at and requires only the board move — no downstream knowledge.
- **Only intended items** (FR-004): keep only issues (never PRs or drafts) in the status passing the
  optional `label` and `owner/repo` (case-insensitive) filters; excluded items never launch and never
  hold the slot.
- **Pure feature key** (FR-011): `NNN` + `-` + slug(`a-z0-9`, single hyphens, no leading/trailing,
  ≤48 total); non-ASCII/emoji dropped, not transliterated; empty slug ⇒ `NNN` alone.
- **Handoff reuse** (FR-012/FR-013/FR-014/FR-015): five `agentbox/issue_*` run tags; five
  `AGENTBOX_ISSUE_*` env values; the body written to a `:ro` file addressed by
  `AGENTBOX_ISSUE_BODY_FILE`, never on the command line or in an env value; title/body are data,
  never substituted into config/paths/commands/tags beyond the feature key; title control-stripped
  and capped to 256 chars.
- **Token isolation** (FR-016/FR-017): read only from `GITHUB_PROJECT_TOKEN` (no `GITHUB_TOKEN`
  fallback); used only by the sensor process; never forwarded / tagged / logged / filed; redacted.
- **Automated run** (FR-018): the sensor RunRequest carries `dagster/sensor_name` (Dagster-set), so
  the run is automated, counts toward the launch-rate governor, and starts a chain at depth 1.
- **Resilience** (FR-019/FR-020/FR-021): GitHub error/rate-limit/timeout ⇒ skip-with-reason,
  cursor untouched; unresolvable board/status/field ⇒ skip naming it, not a crash loop and not a
  load failure that takes other agents down; pagination followed; one shared query per board per tick.
- **Re-homable** (FR-022): observation (`GitHubProjectsClient`) and admission (a pure
  `plan_tick`) are separate; the cursor + run keys are durable; the launch goes through the existing
  op request path.
- **Load-time safety** (FR-023): `owner`/`project`/`status` required, `project` a positive int,
  `interval_seconds` ≥30 int; a bad block rejects that one agent with a file+field message in the
  `depends_on`/`checks` style, others load.
- **Docs track reality** (FR-024/README): schema re-stamped 7→8 with golden files regenerated; the
  README documents `on_project_status`, the env/tags/body-file handoff, the token variable, and the
  sensor; the agent templates gain the commented block.

**Scale/Scope**: One board, one feature at a time, no partitions or templating (spec Out of Scope).
Feature touches: `orchestrator/github_projects.py` (new), `orchestrator/factory.py`,
`orchestrator/definitions.py`, `orchestrator/tests/*`, `ui/schema.py`, `ui/agents_store.py`,
`ui/main.py`, `ui/dagster.py`, `ui/static/agent-form.js`, `ui/static/agents-list.js`,
`ui/templates/agents/form.html`, `ui/templates/agents/list.html`, the run-detail template, the
golden files, `ui/tests/*`, `examples/config/agents/_template-*.yaml`, `.env.example`, and
`README.md`. No compose change beyond the daemon already having egress; the board token is added to
`.env.example`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Agent Isolation** — Respected and reinforced. The launched agent's grants are unchanged; the
  only additions are the five `AGENTBOX_ISSUE_*` env values (issue identity, not credentials) and a
  **read-only** (`:ro`) body-file mount — a downstream can read the brief but not modify it
  (Constitution V). The board token is **never** placed in the container's environment, tags, logs,
  or files (FR-017): it stays in the daemon process only, so no agent gains a credential it should
  not see. The sensor's outbound GitHub reach belongs to the daemon, not to any run.
- **II. Configuration over Code** — Central. `on_project_status` is pure declarative agent YAML,
  discovered at reload with no orchestrator code change per agent; turning a board column into a
  launch signal is auditable in the agent file. The sensor code is generic over the block.
- **III. Secrets Never in the Open** — This is a first-class requirement of the feature (US6). The
  token is passthrough-by-name from `GITHUB_PROJECT_TOKEN`, never committed, never on a command
  line, never logged (it passes through `redact`), and never handed to a run. Issue body/title are
  data, not secrets, and are redacted in the captured `context.json` like everything else.
- **IV. Uniform Interface, Diverse Runtimes** — Respected. The trigger, the `AGENTBOX_ISSUE_*`
  convention, and the body-file handoff are harness-agnostic and identical across
  claude-code/pi/api/codex; adding a runtime touches none of them. The op launch is unchanged apart
  from the added `:ro /issue` mount and the `AGENTBOX_ISSUE_*` env values (mirrors spec 013).
- **V. Ephemeral Runs, Immutable Outputs** — Reinforced. The issue body is delivered read-only; each
  run still produces its own uniquely identified output and reads no prior run's output.
- **VI. Docs Track Reality** — Served. README documents the trigger, the handoff, the token variable,
  and the sensor; schema re-stamped 7→8 with golden files regenerated; skip reasons (missing token,
  missing status option, held issues) are surfaced on the sensor's ticks for the headless operator;
  `.env.example` gains `GITHUB_PROJECT_TOKEN`.
- **VII. One Design System** — Served. The `on_project_status` trigger card, the Automation-view
  held-issues surface, and the run-page issue link are composed from the shared Jinja macros
  (`card`, `text_input`, `select`, `toggle`, `badge`, `table`) and design-system tokens — no literal
  colours/px, no inline styles, no hand-rolled controls (per the agentbox-design skill).

**Result**: PASS. No violations. The deliberate cross-package duplications (the `on_project_status`
field-shape + validation constants stated once in `ui/schema.py` and once as the orchestrator load
backstop; the `AGENTBOX_ISSUE_*` env/tag names in the orchestrator writer mirrored in the README)
continue the 004–013 discipline — stated once per image and pinned by tests. See Complexity Tracking.

*Post-design re-check (after Phase 1)*: still PASS. The design adds no per-harness code path (the
handoff is one shared mechanism), introduces no secret to any file or log (the token is daemon-only),
mounts the body read-only, and leaves the container launch byte-for-byte unchanged apart from the
added `:ro /issue` mount and the `AGENTBOX_ISSUE_*` env values. The polling sensor is the one new
Dagster surface; it reuses the existing op, governor gate, tags, and handoff rather than
re-implementing any of them.

## Project Structure

### Documentation (this feature)

```text
specs/016-github-dagster-sensor/
├── plan.md                          # This file
├── research.md                      # Phase 0: decisions R1–R12
├── data-model.md                    # Phase 1: the trigger block, board item, cursor, active
│                                    #   feature, feature key, run handoff
├── quickstart.md                    # Phase 1: end-to-end validation (launch, once-per-entry,
│                                    #   one-at-a-time, filters, key, token isolation, resilience)
├── contracts/
│   ├── agent-model.md               # agent YAML: on_project_status; validation; schema 7→8 +
│   │                                #   migration; emitter + inline comment
│   ├── orchestrator-model.md        # the polling sensor, the pure admission function, the cursor,
│   │                                #   the run key, per-kind RunRequest, the issue handoff, tokens
│   ├── github-projects-query.md     # the GitHub Projects v2 GraphQL read + pagination + Status match
│   └── ui-automation-and-runs.md    # schema group + form card; Automation-view toggle + held
│                                    #   issues; run-page launcher + issue link
├── checklists/
│   └── requirements.md              # From /speckit-specify (already present)
└── tasks.md                         # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
orchestrator/
├── github_projects.py   # NEW: the re-homable observation+admission core (FR-022).
│                        #   - GitHubProjectsClient: outbound GraphQL read of a Projects v2 board's
│                        #     items + Status, following pagination (FR-003/FR-021); token from
│                        #     GITHUB_PROJECT_TOKEN only (FR-016); raises typed BoardError /
│                        #     RateLimited / Unresolvable(status|board|field).
│                        #   - plan_tick(cursor_state, items, cfg, now) -> TickPlan: PURE admission —
│                        #     first-tick seeding, eligibility, per-agent slot, oldest-first release,
│                        #     held report, next cursor, run keys (FR-004..FR-010). No I/O.
│                        #   - feature_key(number, title) / sanitize_title(title): pure helpers
│                        #     (FR-011/FR-015). ISSUE_ENV_NAMES / ISSUE_TAG_NAMES constants.
├── factory.py           # EDIT: NEW build_project_status_sensor(cfg) -> SensorDefinition
│                        #   (name project_status_<name>, STOPPED, minimum_interval_seconds from
│                        #   cfg): each tick calls the client + plan_tick, emits per-kind RunRequests
│                        #   (asset_selection for asset-kind, job_name=agent_<name> for job-kind,
│                        #   FR-002) carrying run_key, the five agentbox/issue_* tags, and run_config
│                        #   with {title, body, identity}; SkipReason on no-launch/held/error/missing
│                        #   token; update_cursor(next_state). NEW _prepare_issue_handoff(cfg,
│                        #   context) mirrors _prepare_upstream_handoff: reads the issue payload off
│                        #   run_config, writes body to <dir>/body.md (0644) in a STAGING_ROOT
│                        #   tempdir (0777), returns (dir, {AGENTBOX_ISSUE_*: …}); wire the mount via
│                        #   _launch_mounts ({source, target:/issue, mode:ro}) and env via the same
│                        #   merge as upstream_env in make_run_op; op gains an optional `issue` config
│                        #   field the sensor populates. project_status_supported() build-time lever.
├── definitions.py       # EDIT: NEW _project_status(cfg) reads+validates the block (structural
│                        #   backstop, FR-023: required owner/project/status, project int>0,
│                        #   interval_seconds int>=30) → RejectAgent(file, field) on a bad block,
│                        #   others load; when valid, sensors.append(build_project_status_sensor(cfg))
│                        #   for both asset- and job-kind agents; composes with existing triggers.
└── tests/
    ├── test_github_projects.py  # NEW: plan_tick state machine, feature_key/sanitize_title,
    │                            #   filters, pagination, client error mapping — GitHub faked.
    ├── test_factory.py          # EDIT: sensor built paused + per-kind RunRequest; issue handoff
    │                            #   env/tags/:ro body file; body never on cmdline/env; token absent.
    └── test_definitions.py      # EDIT: sensor created for the block; bad block rejects one agent.

ui/
├── schema.py            # EDIT: + the on_project_status field group (section="project_status",
│                        #   nested under triggers): owner/status/label/repo (str), project/
│                        #   interval_seconds (int, interval default 60). validate() enforces
│                        #   required + project>=1 + interval>=30 + repo owner/repo shape, keyed by
│                        #   field id in the depends_on/checks style. SCHEMA_VERSION 7->8 +
│                        #   migrate_7_to_8 (identity). PROJECT_STATUS_BLOCK_HELP + per-field help.
├── agents_store.py      # EDIT: lift/emit triggers.on_project_status as a nested block with the
│                        #   block-line comment + per-field comments; round-trip stable; other keys
│                        #   preserved.
├── main.py              # EDIT: pass the sensor's plain-words description + latest-tick held issues
│                        #   into the Automation view; expose the issue link on the run detail.
├── dagster.py           # EDIT: read the project_status_<name> sensor's latest tick
│                        #   status/skip-reason (held issues) for the Automation view; set_instigation
│                        #   already toggles sensors by name.
├── static/
│   ├── agent-form.js    # EDIT: render the GitHub Projects trigger card (six inputs), gated like
│   │                    #   other trigger fields; collect()/omit rules nest under on_project_status.
│   └── agents-list.js   # EDIT: recognise project_status for the schedules/sensors column pill.
├── templates/
│   ├── agents/form.html # EDIT: mount the trigger card (JS-driven), shared macros only.
│   ├── agents/list.html # EDIT: a "board" pill in the automation column; plain-words tooltip.
│   └── runs/…           # EDIT: run detail links the issue number to AGENTBOX_ISSUE_URL / the tag.
└── tests/
    ├── test_schema.py       # EDIT: the group; validation; migration 7->8.
    ├── test_agents_store.py # EDIT: emit/lift the nested block; round-trip; GOLDEN sample.
    ├── test_api.py          # EDIT: /api/schema shape; form renders the card; Automation view lists
    │                        #   the sensor + held issues; run page links the issue.
    ├── test_conformance.py  # EDIT (if needed): golden/token coverage of the new UI.
    └── golden/*.yaml        # REGENERATE: schema-8 header (+ the sample carrying the block).

examples/config/agents/_template-*.yaml  # EDIT: commented on_project_status: block under triggers:,
                                          #   same help text, re-stamped to schema 8.

.env.example              # EDIT: document GITHUB_PROJECT_TOKEN (board read scope; sensor-only).

README.md                 # EDIT: document on_project_status, the AGENTBOX_ISSUE_* env + tags + body
                          #   file, GITHUB_PROJECT_TOKEN, and the project_status_<name> sensor.
```

**Structure Decision**: Keep the two packages separate, each owning its half, exactly as 004–015.
The orchestrator owns turning `on_project_status` into a polling sensor, the pure admission core, the
GitHub client, and the read-only issue handoff; the new `github_projects.py` isolates observation +
admission so the sensor is a thin wire and a later feature can re-home the observer (FR-022). The UI
owns authoring (the trigger card + validation), the Automation-view surface (toggle, plain-words
description, held issues), and the run-page issue link. The cross-boundary duplications stay stated
once per package (the `on_project_status` field shape + validation; the `AGENTBOX_ISSUE_*` names) and
are pinned by tests. No new data directory: the issue handoff dir reuses the existing `$AGENTBOX_DATA`
host==container mount, the same boundary the pipes/staging/upstream dirs already rely on.

## Complexity Tracking

No constitution violations. The deliberate cross-boundary duplications continue the 004–013
discipline — each stated once per package (the two ship as separate images with no shared import) and
pinned to its twin by a test:

| Duplication | Why Needed | Simpler Alternative Rejected Because |
|-------------|------------|--------------------------------------|
| `on_project_status` field shape + validation rules (required owner/project/status; `project`≥1 int; `interval_seconds`≥30 int; `owner/repo` shape) in `ui/schema.py` and as the `definitions.py` load backstop | Both containers must accept/reject the same block with no shared module — the UI at author time (FR-023 message), the orchestrator at load time (hand-edited files) | A shared package across two independently-built images is more machinery than a small validator + a load-time twin; each names the same file+field |
| `AGENTBOX_ISSUE_*` env names + `agentbox/issue_*` tag names in `orchestrator/factory.py` (writer) mirrored by the README | The container consumes the env vars and the run page reads the tags; the convention must be documented verbatim where authors read it | The convention is a fixed short list; pinning it by a test + documenting it once is cheaper than a shared config surface (same rationale as the 013 `AGENTBOX_UPSTREAM_<KEY>` transform) |
| Feature-key grammar/cap stated in `orchestrator/github_projects.feature_key` and in the README/spec | The key is a pure function used only by the sensor today; #22/#24 inherit its grammar and will re-state it against the same test vectors | One authoritative implementation + documented grammar is the single source; no duplication in code today, only the documented grammar it must match |
