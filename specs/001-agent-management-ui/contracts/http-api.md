# Contract: HTTP surface of the agentbox UI

Base: `http://<host>:8080`. Pages return HTML; everything under `/api/` returns JSON (`Content-Type: application/json`). Errors under `/api/` use `{"error": "<code>", "message": "<human text>", ...extra}` with the HTTP status codes listed. `{name}` in a path is the agent's filename without `.yaml` (its identity per FR-010); the stored `name` key is normalised to it on save. Every user-supplied filename or stem — `{name}` on the agent routes, `?from=` on the create page, `prompt_file`, and a new prompt's filename — is path-checked before any filesystem access: a value containing a separator (`/`, `\`) or `..` is refused consistently at every endpoint (FR-010a), an unsafe agent stem as `404 not_found` and an unsafe prompt filename as `400` validation.

Storage failures (permission denied, read-only mount, missing directory that cannot be created) on any endpoint return `507` `{"error": "storage", "message": "cannot <read|write|delete> <agents|prompts>/<file>: <os error>"}` so the operator can identify the mount and operation.

## Pages

| Method & path | Renders | Notes |
|---|---|---|
| `GET /` | 302 → `/agents` | |
| `GET /agents` | Agents list in the app shell | Lists non-template agents; each row links to `/agents/{name}`; "New agent" → `/agents/new`; files with parse errors render with an error badge |
| `GET /agents/new` | Create form | Optional `?from=<template-file>` pre-fills from an `_`-prefixed template |
| `GET /agents/{name}` | Edit form | 404 page if no such file; parse-error case renders form defaults + error banner + raw file block (R9) |
| `GET /design-system` | 302 → `/design-system/` | Trailing slash so the document's relative `./support.js` / `./archon-tokens.css` resolve inside the mount |
| `GET /design-system/` | `ui/design-system/Archon Design System.dc.html` | Not linked from navigation |
| `GET /design-system/{file}` | Static files from `ui/design-system/` | tokens css, support.js, prototype documents |
| `GET /static/{file}` | Static files from `ui/static/` | |

Page JavaScript performs all reads/writes through the API below; pages themselves are side-effect free.

## Schema

### `GET /api/schema`

Returns the field and harness definitions the form renders from. Its `prompts` array is the source the form uses to populate the prompt selector (the same set as `GET /api/prompts`, filenames only); a prompt created inline is written before the agent in the same save and appears in this list for any form loaded afterward (SC-005), so no separate refresh call is defined.

Feature 003 added a `groups` array and a `group` key on every section (Runs/Job/Box); the full group and section list is defined in [`specs/003-agent-form-layout/contracts/schema-and-yaml.md` §1](../../003-agent-form-layout/contracts/schema-and-yaml.md).

```json
{
  "groups": [{"id": "runs", "label": "Runs"}, {"id": "job", "label": "Job"}, {"id": "box", "label": "Box"}],
  "sections": [{"id": "identity", "label": "Identity", "group": null}, {"id": "schedule", "label": "Schedule", "group": "runs"}, "..."],
  "fields": [
    {"id": "permission_mode", "section": "tools", "label": "Permission mode", "type": "enum",
     "required": false, "default": null, "choices": ["default", "acceptEdits", "auto", "bypassPermissions", "dontAsk", "plan"],
     "help": "Claude Code permission mode.", "harnesses": ["claude-code"]},
    "..."
  ],
  "harnesses": [
    {"id": "claude-code", "label": "Claude Code", "description": "...", "image": "agentbox/agent-claude",
     "fields": ["name", "enabled", "schedule", "timeout_seconds", "..."],
     "model_rule": {"choices": ["sonnet", "opus", "haiku", "fable"], "custom": "claude-id", "blank_ok": true},
     "effort_choices": ["low", "medium", "high", "xhigh", "max"], "default_network": "bridge"},
    "..."
  ],
  "litellm_aliases": ["cheap", "smart", "opus", "kimi", "kimi-k3"],
  "prompts": ["repo-librarian.md", "repo-librarian2.md"]
}
```

## Agents

### `GET /api/agents`

```json
{"agents": [
  {"name": "repo-librarian-agentbox", "file": "repo-librarian-agentbox.yaml", "enabled": true,
   "harness": "claude-code", "model": "claude-opus-4-8[1m]", "schedule": "30 2 * * *",
   "dagster_job": "agent_repo_librarian_agentbox", "dagster_url": "http://dagster-webserver:3000/jobs/agent_repo_librarian_agentbox",
   "parse_error": null, "name_mismatch": false}
 ],
 "templates": [{"file": "_template-pi.yaml", "harness": "pi"}]}
```

Files that fail to parse appear with `"parse_error": "<message>"` and other fields `null`; the list page renders such a row with an "error" badge and the message inline (in place of the harness/model/schedule metadata), and the row still links to the detail page where the raw contents are shown. `name_mismatch` is `true` when the stored `name` key differs from the filename. A file whose schema-version marker is newer than the UI supports has `"parse_error": "written by a newer agentbox (schema N)"` and `"editable": false`; all other entries carry `"editable": true`.

### `GET /api/agents/{name}`

`200` → `{"agent": {<all fields as stored, plus "unmanaged": {...}>}, "file": "...", "parse_error": null, "raw": null, "name_mismatch": false, "editable": true}`; for an unparsable file `agent` is `null` and `raw` holds the file text. `404` if absent. Template files are addressable here (for `?from=`).

### `POST /api/agents` — create

Request:
```json
{
  "agent": {"name": "my-agent", "enabled": true, "harness": "pi", "model": "smart", "...": "..."},
  "new_prompt": {"filename": "my-agent.md", "content": "..."},
  "confirm_not_secret": ["GITHUB_USER"],
  "reload_dagster": true
}
```
- `new_prompt` optional; when present it is created first and `agent.prompt_file` is set to its filename.
- `confirm_not_secret` optional; lists env keys the user has confirmed are not secrets.
- `reload_dagster` optional, default `true`.

Responses:
- `201` `{"agent": {...}, "file": "my-agent.yaml", "warnings": ["claude-code needs network: bridge to reach its provider; agentnet-isolated has no internet"], "reload": {"requested": true, "ok": true, "message": "Workspace reloaded"}}` — `warnings` is the (possibly empty) list of non-blocking FR-024 notices
- `400` `{"error": "validation", "fields": {"schedule": "not a valid cron expression", "model": "..."}}`
- `409` `{"error": "exists", "message": "agents/my-agent.yaml already exists"}`
- `409` `{"error": "secret_confirmation_required", "flagged": ["GITHUB_TOKEN"]}` — resend with those keys in `confirm_not_secret`
- `409` `{"error": "prompt_exists", "message": "..."}`

When the write succeeded but the reload failed: still `201`, with `"reload": {"requested": true, "ok": false, "message": "<dagster error>"}`.

### `PUT /api/agents/{name}` — update

Same body as create minus the ability to change `agent.name` (`400` `{"error": "validation", "fields": {"name": "name cannot be changed; delete and recreate"}}`). `200` with the same shape as create's `201`. `404` if the file does not exist.

### `DELETE /api/agents/{name}`

Query/body `reload_dagster` (default `true`). `200` `{"deleted": "my-agent.yaml", "reload": {...}}`. `404` if absent. Never touches workspace/output directories.

### `POST /api/agents/preview`

Body `{"agent": {...}}`. `200` `{"yaml": "<text exactly as it would be written>", "warnings": [...]}`; `400` validation shape as above. Does not write, does not run the secret check.

## Prompts

### `GET /api/prompts`
`{"prompts": [{"filename": "repo-librarian.md", "size": 2140, "modified": "2026-09-08T18:02:11Z"}]}`

### `GET /api/prompts/{filename}`
`{"filename": "...", "content": "..."}`; `404` if absent. Path traversal (`..`, `/`) → `400`.

### `POST /api/prompts`
Body `{"filename": "my-agent.md", "content": "..."}`. `201` `{"filename": "my-agent.md"}`; `400` for an invalid name or empty content; `409` if it exists. Creates `prompts/` if missing.

## Dagster

### `POST /api/dagster/reload`
`200` `{"ok": true, "message": "Workspace reloaded"}` or `200` `{"ok": false, "message": "<error from Dagster or 'Dagster unreachable (timeout after 10s)'>"}`. Always 200 so the client treats the outcome as data, not transport failure.

### `GET /api/dagster/status`
`{"url": "http://dagster-webserver:3000", "reachable": true}` — used by the sidebar status block.
