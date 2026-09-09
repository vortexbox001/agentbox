# Data Model: Agent Management UI

All persistent data is files under the repository checkout, bind-mounted into the `ui` container. There is no database; the schema module (`ui/schema.py`) is the in-code description of the agent file format.

## Entities

### AgentDefinition

One agent = one file `agents/<name>.yaml`. The UI reads it with a safe YAML loader and always writes it back whole via the emitter (see [contracts/agent-yaml.md](contracts/agent-yaml.md)).

The "Explanation" column below is **illustrative**; the authoritative help text is `field_help()` in `ui/schema.py`, which is the single source rendered in the form (`GET /api/schema`), emitted as each field's YAML comment, and mirrored by the README's YAML reference — the three must not diverge (Constitution VI, FR-003). Where a field has a bounded set or numeric range, its help states those values and the default (e.g., `timeout_seconds`, `memory`, `cpus`). The `name` stem and every user-supplied filename are also path-checked before any filesystem access — a separator or `..` is rejected (FR-010a).

| Field | Type | Applies to | Required | Default (when omitted) | Validation | Explanation shown in UI / emitted as comment |
|---|---|---|---|---|---|---|
| `name` | string | all | yes | — | `^[a-z0-9]+(-[a-z0-9]+)*$`; unique among `agents/*.yaml`; immutable after create; the filename stem is the identity — a stored `name` that differs is shown as a mismatch warning and normalised to the filename on save (FR-010) | Unique kebab-case identifier. Becomes the Dagster job `agent_<name>` (hyphens become underscores). |
| `enabled` | bool | all | yes | `true` | choice `true`/`false` | Disabled agents are skipped when Dagster loads the workspace. |
| `harness` | enum | all | yes | — | one of `claude-code`, `pi`, `api`, `codex` | Which runtime runs this agent; determines the available fields and models below. |
| `model` | string | all | no | harness-specific (see below) | per-harness rule (R4) | Model the harness talks to. |
| `effort` | enum | claude-code, pi, codex | no | CLI default | per-harness choice list (R4) | Reasoning/thinking effort level. |
| `fallback_model` | string | claude-code | no | none | same rule as claude-code `model` | Model to use if the primary is overloaded. |
| `max_tokens` | int | api | no | `1024` | 1 … 200000 | Cap on response tokens. |
| `prompt_file` | string | all | yes | — | must exist in `prompts/` (or be created in the same save) | File in `prompts/` read at launch and given to the agent as its prompt. |
| `append_system_prompt` | string | claude-code, pi, codex | no | none | free text | Extra text appended to the system prompt (for codex: appended to the prompt message, since codex has no system-prompt flag). |
| `output_dir` | string | all | yes | — (form placeholder suggests `/data/outputs/<name>`) | absolute path | Host directory mounted at `/output`; every run writes its result files here. |
| `workspace` | string | claude-code, pi, codex | no | `/data/workspaces/<name>` | absolute path | Host directory mounted at `/workspace`; scratch space for the run. |
| `wipe_workspace` | bool | claude-code, pi, codex | no | `false` | choice | Empty the workspace before every run so each run starts clean. |
| `schedule` | string | all | no | `""` (manual only) | empty or valid 5-field cron (`croniter`) | Cron expression for automatic runs; leave empty for manual-only. |
| `timeout_seconds` | int | all | no | `900` | 1 … 86400 | The run is killed after this many seconds. 1 to 86400; default 900. |
| `max_turns` | int | claude-code | no | `10` | 1 … 1000 | Cap on agentic turns. |
| `permission_mode` | enum | claude-code | no | CLI default | `default`, `acceptEdits`, `auto`, `bypassPermissions`, `dontAsk`, `plan` | Claude Code permission mode. |
| `allowed_tools` | list[string] | claude-code, pi | no | unrestricted / pi default set | claude-code: any tool names (suggestions `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebFetch`, `WebSearch`); pi: subset of `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls` | Tool allowlist. |
| `disallowed_tools` | list[string] | claude-code | no | none | tool names | Tool denylist (pi has no such flag). |
| `mcp_config` | string | claude-code | no | none | path | Path to an MCP server config JSON inside the container. |
| `network` | enum | all | yes (always written) | pre-filled from `Harness.default_network` (`bridge` for claude-code/codex, `agentnet` for pi, `agentnet-isolated` for api); the orchestrator's own fallback when the key is absent is `agentnet`, which the UI never relies on | `agentnet-isolated`, `agentnet`, `bridge`; harness/network mismatch produces a non-blocking warning (FR-024) | Docker network: agentnet-isolated (LiteLLM only, no internet), agentnet (LiteLLM + internet), bridge (full internet — needed by claude-code and codex). Default depends on harness. |
| `memory` | string | all | no | `1g` | `^\d+[kmg]$` | Container memory limit (e.g. 512m, 1g). Default 1g. |
| `cpus` | number | all | no | `1.5` | 0.1 … 64 | Container CPU limit (e.g. 1.5). Default 1.5. |
| `env_file` | string | all | no | none | absolute path | Host path to an env file passed to the container (keeps secrets off the command line). Applies to every harness. |
| `env` | map[string,string] | all | no | `{}` | keys `^[A-Z_][A-Z0-9_]*$`; values free; secret-like plain values require confirmation (R7) | Environment variables for the container. `${NAME}` forwards the host variable by name without exposing its value. |

**Per-harness field sets** (derived from the table; this is what the form shows and the emitter writes):

| Section | claude-code | pi | api | codex |
|---|---|---|---|---|
| Identity: `name` | ✓ | ✓ | ✓ | ✓ |
| Schedule: `enabled`, `schedule` | ✓ | ✓ | ✓ | ✓ |
| Limits: `timeout_seconds` | ✓ | ✓ | ✓ | ✓ |
| Limits: `max_turns` | ✓ | — | — | — |
| Prompt: `prompt_file` | ✓ | ✓ | ✓ | ✓ |
| Prompt: `append_system_prompt` | ✓ | ✓ | — | ✓ |
| Directories: `workspace`, `wipe_workspace` | ✓ | ✓ | — | ✓ |
| Directories: `output_dir` | ✓ | ✓ | ✓ | ✓ |
| Environment: `env`, `env_file` | ✓ | ✓ | ✓ | ✓ |
| Tools & permissions: `permission_mode`, `disallowed_tools`, `mcp_config` | ✓ | — | — | — |
| Tools & permissions: `allowed_tools` | ✓ | ✓ | — | — |
| Harness & model: `harness`, `model` | ✓ | ✓ | ✓ | ✓ |
| Harness & model: `effort` | ✓ | ✓ | — | ✓ |
| Harness & model: `fallback_model` | ✓ | — | — | — |
| Harness & model: `max_tokens` | — | — | ✓ | — |
| Container: `network`, `memory`, `cpus` | ✓ | ✓ | ✓ | ✓ |

Source of truth for this matrix: `orchestrator/factory.py` (which keys each harness branch reads, and which are applied in the common section) — the README's YAML reference is descriptive and must be corrected if it disagrees with the code.

**Derived (read-only) attributes** used by the list page: `file` (path), `dagster_job` (`agent_` + name with `-`→`_`), `dagster_url` (`${DAGSTER_URL}/jobs/<job>`), `is_template` (filename starts with `_`), `parse_error` (message when the file is not valid YAML or not a mapping).

**Lifecycle**: `draft (form) → saved (file exists) → [reloaded into Dagster] → deleted (file removed)`. `enabled: false` is a saved state, not a separate lifecycle stage.

**Schema versioning**: each emitted file carries `# agentbox-schema: <N>`; on read, `MIGRATIONS` in `schema.py` (ordered, forward-only, pure dict → dict) bring older files up to the current version in memory; the file is rewritten only on save. Keys the schema does not define are kept as `unmanaged: dict` on the in-memory definition and emitted back verbatim (research R12). A file stamped newer than this UI supports raises `SchemaTooNew` and is reported as an uneditable `parse_error` (still deletable); a migration function that raises on a file is caught and reported as a `parse_error` ("schema migration failed: …") with the file left untouched — read never writes (research R12).

### Prompt

One file `prompts/<filename>.md`.

| Field | Type | Validation |
|---|---|---|
| `filename` | string | `^[a-z0-9][a-z0-9._-]*\.md$`; unique in `prompts/` |
| `content` | string | non-empty |
| `size`, `modified` | derived | shown in the selector |

Relationship: `AgentDefinition.prompt_file` → `Prompt.filename` (many agents may share one prompt). Creating a prompt inline during an agent save is two writes: the prompt first, then the agent; if the agent write fails the prompt remains (it is independently valid and listed).

### Harness (static, in `schema.py`)

| Field | Meaning |
|---|---|
| `id` | `claude-code`, `pi`, `api`, `codex` |
| `label`, `description` | shown in the harness selector (e.g., "Claude Code CLI in a container with a workspace") |
| `image` | the agent image it runs (`agentbox/agent-claude`, `agentbox/agent-pi`, `agentbox/agent-python`, `agentbox/agent-codex`) — informational |
| `fields` | the ordered set of applicable field ids |
| `model_rule` | `{choices: [...], custom: "none" \| "claude-id" \| "provider-model" \| "any", blank_ok: bool}` |
| `effort_choices` | list or empty |
| `default_network` | recommended network shown as the default (`bridge` for claude-code/codex, `agentnet` for pi, `agentnet-isolated` for api) |

### SchemaField (static, in `schema.py`)

`id`, `section`, `label`, `type` (`string`/`int`/`number`/`bool`/`enum`/`list`/`map`/`path`/`cron`), `required`, `default`, `choices` (or a choice source: `litellm_aliases`, `prompts`), `pattern`, `min`/`max`, `help` (the explanation), `harnesses` (applicability). Emitted to the browser via `GET /api/schema` and used by the emitter for comments and ordering.

### Schema module constants (static, in `schema.py`)

| Name | Meaning |
|---|---|
| `SCHEMA_VERSION: int` | Current version, stamped into every emitted file (starts at `1`) |
| `MIGRATIONS: list[tuple[int, Callable[[dict], dict]]]` | `(target_version, fn)` pairs; `fn` transforms a definition dict from `target_version - 1` to `target_version`. Empty at v1. |

## State & validation summary

- **Create**: validate all applicable fields → check name uniqueness → secret check (409 unless confirmed) → optional prompt create → write file → optional Dagster reload → respond with agent + reload outcome.
- **Edit**: same minus uniqueness (name immutable) → overwrite file whole.
- **Delete**: confirm in UI → remove file → optional reload. Missing file → 404.
- **Preview**: validate → emit YAML text without writing.
