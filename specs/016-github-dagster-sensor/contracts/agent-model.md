# Contract: Agent model — the `on_project_status` trigger

The agent YAML addition this feature introduces, its validation, the schema bump, and the emitter.
Authority: `ui/schema.py` (authoring guard) with `orchestrator/definitions.py` as the load-time
structural backstop. See [../data-model.md](../data-model.md) for the entities.

## §1 New block

Under the existing `triggers:` block, a new nested mapping:

```yaml
triggers:
  on_project_status:            # NEW — launch this agent when an issue enters a board status (FR-001)
    owner: vortexbox001         # board owner (org login)
    project: 1                  # board number (positive integer)
    status: In progress         # Status option name (matched case-insensitively)
    label: brief                # optional — only issues carrying this label
    repo: vortexbox001/agentbox # optional — only issues from this owner/repo (case-insensitive)
    interval_seconds: 60        # optional — poll cadence, default 60, minimum 30
  # asset_schedule / job_schedule / on_upstream / on_missing — unchanged, may coexist (FR-002)
```

Absent ⇒ no board trigger. When present, `owner`/`project`/`status` are required; `label`/`repo`/
`interval_seconds` are optional. The block composes with the other triggers rather than replacing them.

## §2 SchemaField definitions (`ui/schema.py`)

A new `section="project_status"`, all fields lifting from / nesting into `triggers.on_project_status`,
harnesses `_ALL`:

- `owner` — `type="text"`, required when the block is on.
  Help: *"GitHub org (or user) that owns the Projects board."*
- `project` — `type="int"`, required, ≥1.
  Help: *"The Projects board number (positive integer)."*
- `status` — `type="text"`, required.
  Help: *"The Status column option name; an issue entering it launches this agent (matched case-insensitively)."*
- `label` — `type="text"`, optional.
  Help: *"Optional — only issues carrying this label launch."*
- `repo` — `type="text"`, optional.
  Help: *"Optional — only issues from this owner/repo launch (matched case-insensitively)."*
- `interval_seconds` — `type="int"`, optional, default 60, ≥30.
  Help: *"Poll cadence in seconds (default 60, minimum 30)."*

`PROJECT_STATUS_BLOCK_HELP` documents the block for the emitter's block-line comment. `ALWAYS_WRITTEN`
is unchanged (the block is written only when set). `to_public()` gains the group automatically via
`FIELDS`.

## §3 Validation rules (`schema.validate`)

Added to the existing rules, keyed by field id in the `depends_on`/`checks` style (FR-023):

1. **Presence**: when the block is on, missing `owner`/`project`/`status` ⇒
   `errors["owner"|"project"|"status"] = "<field> is required for a GitHub Projects trigger."`
2. **`project`**: not a positive integer ⇒ `errors["project"] = "project must be a positive integer."`
3. **`interval_seconds`**: present and not an integer ≥30 ⇒
   `errors["interval_seconds"] = "interval_seconds must be an integer of at least 30."`
4. **`repo`**: present and not of the form `owner/repo` ⇒
   `errors["repo"] = "repo must be a full owner/repo name."`
5. Existing trigger/cron rules unchanged; `on_project_status` applies to both agent kinds, so no
   asset/job kind guard is added (unlike `asset_schedule`).

## §4 Emitter (`ui/agents_store.py`)

- `_triggers_block_lines` gains a nested `on_project_status:` mapping (a new nesting depth under
  `triggers:`), emitted when set, with `PROJECT_STATUS_BLOCK_HELP` as the block-line comment and each
  sub-field's help as its inline comment. Optional sub-fields are emitted only when set.
- Round-trip: read (lift `triggers.on_project_status.*` → flat fields) then write (nest flat → block)
  reproduces the file; unknown keys preserved (existing behaviour).

## §5 Load-time backstop (`orchestrator/definitions.py`)

- A new `_project_status(cfg)` reads and validates the block (§3's shape rules) and rejects the agent
  via `RejectAgent(file, message)` naming the file and offending field on a malformed block — the
  structural twin of the UI guard. Every other agent still loads (US8).
- A valid block causes `build_project_status_sensor(cfg)` to be appended to the sensors list for both
  asset- and job-kind agents (see [orchestrator-model.md](orchestrator-model.md)).

## §6 Schema version & migration

`SCHEMA_VERSION` 7 → 8. `migrate_7_to_8(data)` returns `data` unchanged (identity): the block is
additive. `MIGRATIONS` gains `(8, migrate_7_to_8)`. Golden files regenerate with the
`# agentbox-schema: 8` header. Files stamped 8 by a newer UI still raise `SchemaTooNew`.

## §7 Agent templates

`_template-*.yaml` gain, commented, an `on_project_status:` block under `triggers:` with the same help
text, and re-stamp to schema 8 — so a hand-authored file documents the new surface.
