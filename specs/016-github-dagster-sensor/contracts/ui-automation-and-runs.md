# Contract: UI — schema group, Automation view, and the run page

The management-UI surface this feature adds. Authority: `ui/schema.py`, `ui/agents_store.py`,
`ui/main.py`, `ui/dagster.py`, `ui/static/*`, `ui/templates/*`. The mandatory parts are the schema
field group (FR-024), the Automation-view toggle + held issues (FR-025), and the run-page launcher +
issue link (FR-026); the editor **form card** is the spec's null-action flex point (research R11).

## §1 Schema field group (FR-024) — mandatory

`ui/schema.py` gains the `on_project_status` group (see [agent-model.md](agent-model.md) §2–§3):
`/api/schema` exposes `owner`/`project`/`status`/`label`/`repo`/`interval_seconds` under
`section="project_status"`; `validate` enforces required + `project`≥1 + `interval_seconds`≥30 +
`owner/repo` shape; `SCHEMA_VERSION` is 8 with `migrate_7_to_8` identity; the emitter round-trips the
nested block with its inline comments; golden files are regenerated with the schema-8 header.

## §2 Editor form card (FR-024) — flex point (research R11)

`ui/static/agent-form.js` + `ui/templates/agents/form.html` render a **GitHub Projects trigger** card
from the shared macros (`card`, `text_input`, a number input, `toggle` to enable the block) — six
inputs bound to the group, gated on the block being enabled, with `collect()` nesting them under
`triggers.on_project_status` and omitting the block when disabled. Design-system tokens + macros only
(Constitution VII; `test_conformance.py`).

**Null-action fallback** (spec Assumption "UI scope"): the schema group + Automation toggle +
validation already make the trigger usable YAML-only. If the card proves more than a field group,
ship YAML-only now and add the card later — the trigger still round-trips through the emitter and is
operable from the Automation view.

## §3 Automation view — toggle, description, held issues (FR-025) — mandatory

- **Listing + toggle**: the `project_status_<name>` sensor appears alongside the agent's other
  instigators (schedules, `autocond_<name>`), STOPPED by default, started/stopped by the existing
  sensor toggle — `POST /api/schedules/toggle` with `kind: "sensor"`, routed to
  `ui/dagster.py:set_instigation(kind="sensor", name=…, running=…)` (the real signature is
  `set_instigation(kind, name, running)` — `ui/dagster.py:632`, called positionally at
  `ui/main.py:735`). `ui/static/agents-list.js` recognises
  `project_status` for the automation-column pill; `ui/templates/agents/list.html` renders a "board"
  pill.
- **Plain-words description**: a small formatter renders the block as
  *"When an issue enters {status} on {owner}/{project}"* (e.g. *"When an issue enters In progress on
  vortexbox001/1"*), shown as the pill tooltip / automation row label (FR-025).
- **Held issues**: `ui/dagster.py` reads the sensor's latest tick (`instigationStateOrError` →
  `ticks` / `sensorOrError` latest evaluation) and surfaces its `SkipReason` — which names the held
  issues and the holder (orchestrator-model §2) — in the Automation view, so the operator sees what is
  waiting and why. No new persistence: the tick history is the source.

## §4 Run page — launcher + issue link (FR-026) — mandatory

A sensor-launched run carries `dagster/sensor_name` and the five `agentbox/issue_*` tags. The run
detail:
- names the sensor as the launcher (existing `ui/main.py:_launched_by_label`, which already
  distinguishes schedule / sensor / manual from the run tags), and
- links the **issue number** (`agentbox/issue_number`) to the issue at `agentbox/issue_url`, rendered
  with the shared macros. The board token never appears (it is not a tag — FR-017).

## §5 Tests (`ui/tests/`)

- `test_schema.py`: the group present in `FIELDS`/`/api/schema`; validation messages for missing
  required fields, `project`<1, `interval_seconds`<30, bad `repo`; `migrate_7_to_8` identity;
  `SCHEMA_VERSION == 8`.
- `test_agents_store.py`: the nested block emits with its comments and round-trips; a GOLDEN sample
  carries the block; `test_golden_file_matches_emitter` regenerated for schema 8.
- `test_api.py`: `/api/schema` shape; the form renders the card; the Automation view lists the sensor
  with its plain-words description + held issues; the run page links the issue.
- `test_conformance.py`: the new template/JS pass the token/macro/no-inline-style checks; no external
  URL literals beyond the issue link built from the run tag.
