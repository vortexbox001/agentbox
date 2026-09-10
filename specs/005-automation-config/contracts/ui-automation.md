# Contract: Management UI — Automation view & schema change

## §1 Agent form change (FR-017)

Removing the `schedule` field and its section from `ui/schema.py` removes the **Schedule
card** from the form automatically (the form renders sections from `/api/schema`). The Runs
column (group `runs`) then contains:

| Card (section) | Fields |
|----------------|--------|
| Enabled (`status`, formerly `schedule`) | `enabled` |
| Limits (`limits`) | `timeout_seconds`, `max_turns` |
| Produces (`produces`, from 004) | `asset`, `partition` |

`GET /api/schema` MUST NOT contain a `schedule` field or a `schedule` section. Golden files
regenerate with a `# agentbox-schema: 3` header and no `schedule:` line.

## §2 Schema migration (FR-002)

- `SCHEMA_VERSION = 3`; `MIGRATIONS` gains `(3, migrate_2_to_3)` where `migrate_2_to_3`
  pops `schedule`.
- On read, when a file carried a `schedule` key, `agents_store` logs a warning naming the
  file. Existing schema-2 files (no `schedule`) load with zero noise.
- `ALWAYS_WRITTEN` no longer contains `schedule`; the `_is_unset` special-case for
  `schedule` and the `_validate_schedule` call on the agent dict are removed. The five-field
  cron helper is kept and reused by §3.

## §3 Automation API

### `GET /api/automation`
Returns one row per **non-template** agent — disabled agents **included** (listed so a trigger
can be pre-set; it won't fire until the agent is enabled) — default missing → on-demand:

```json
{"agents": [
  {"name": "repo-librarian-agentbox", "harness": "claude-code", "mode": "job",
   "enabled": true, "trigger": {"cron": "30 2 * * *"}},
  {"name": "categorize-commits", "harness": "api", "mode": "job",
   "enabled": true, "trigger": {"on_demand": true}}
]}
```

`mode` is `"asset"` when the agent declares `produces`, else `"job"`. `enabled` mirrors the
agent's `enabled:` — a disabled agent is still listed (so a trigger can be pre-set) but the
view badges it and its trigger stays inert until the agent is enabled (a disabled agent is
skipped at orchestrator load, so nothing is built for it).

### `PUT /api/automation`
Body: the **full** desired trigger set as
`{"triggers": {"<name>": {"cron": "…"} | {"on_demand": true}, …}}` (whole-file replace — the
write rewrites the canonical file, so a partial/single-entry body is not the contract).
Behavior:

1. Validate every entry per automation-format §3: agent MUST be in the known-agent-name set
   (else `400 {error:"validation", fields:{<name>: …}}`, naming it — FR-010); `cron` MUST pass
   the five-field rule (else `400` — FR-009); exactly one trigger. (Status `400` matches the
   agent API's validation shape so the browser shares one error handler.)
2. Write the canonical `automation/migrated.yaml` (on-demand agents omitted; only `cron`
   entries are persisted).
3. Call `dagster.reload()`; return `{ "ok": bool, "message": str, "reload": {…} }`.

Errors use the existing `StorageError` / validation-error handlers (same JSON shape as the
agent API).

## §4 Pages & nav

- `GET /automation` renders `templates/automation/list.html` (the agent→trigger table with
  an inline editor), served through `_shell_context` like `/agents`.
- `base.html` gains an "Automation" nav link next to "Agents".
- `static/automation.js` fetches `GET /api/automation`, renders the table, and on save calls
  `PUT /api/automation`, surfacing the reload outcome with the same banner pattern the agent
  form uses.

## §5 Invariants

- Editing a trigger never writes to any `agents/*.yaml` — the agent stays listed and
  hand-runnable (FR-020 / Story 5).
- Saving on-demand for an agent removes its `cron` entry from `migrated.yaml` (it is simply
  absent), not the agent.
- The Automation view and the orchestrator apply the **same** validation rules, so a value
  the UI accepts always loads (and one it refuses never reaches a hand-edit that would fail
  the reload).
