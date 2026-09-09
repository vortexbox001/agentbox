# Data Model: Agent Form Layout

No new persistent data. This feature changes the *organisation* of the existing agent schema: which section each field belongs to, which group each section belongs to, and therefore the order of keys and headers in written YAML. Field types, defaults, validation, help text, and harness applicability are unchanged (spec FR-016).

## Group

A named column of the form. Fixed, ordered, three entries.

| id | label | Purpose |
|---|---|---|
| `runs` | Runs | Whether and when the agent runs; run limits. Reserved to hold a compact recent-runs list later. |
| `job` | Job | What the agent does: prompt, directories, environment, tools. |
| `box` | Box | What runs it: harness, model, container. |

Exposed by `GET /api/schema` as `groups: [{id, label}]` in this order.

## Section (card)

A titled set of fields. Each section belongs to one group, or to none (rendered in the lead strip, written first in YAML). Fixed, ordered.

| order | id | label | group | fields (in order) |
|---|---|---|---|---|
| 1 | `identity` | Identity | *(none — lead strip)* | `name` |
| 2 | `schedule` | Schedule | `runs` | `enabled`, `schedule` |
| 3 | `limits` | Limits | `runs` | `timeout_seconds`, `max_turns` |
| 4 | `prompt` | Prompt | `job` | `prompt_file`, `append_system_prompt` |
| 5 | `directories` | Directories | `job` | `workspace`, `wipe_workspace`, `output_dir` |
| 6 | `environment` | Environment | `job` | `env_file`, `env` |
| 7 | `tools` | Tools & permissions | `job` | `permission_mode`, `allowed_tools`, `disallowed_tools`, `mcp_config` |
| 8 | `harness_model` | Harness & model | `box` | `harness`, `model`, `effort`, `fallback_model`, `max_tokens` |
| 9 | `container` | Container | `box` | `network`, `memory`, `cpus` |

Rules:
- A section renders as a card only if at least one of its fields applies to the selected harness. `identity`, `schedule`, `prompt`, `harness_model`, and `container` apply to every harness; every group therefore always has at least one card.
- A section's YAML block is written only if at least one of its fields has a value (existing emitter rule), under the header `# --- <label> ---`.
- `SECTIONS` order is the order of cards within a group, and of blocks within the file.
- Within a section, field order is `FIELDS` order. `FIELDS` must list fields contiguously by section, in `SECTIONS` order (a schema test enforces this).

Exposed by `GET /api/schema` as `sections: [{id, label, group}]` where `group` is a group id or `null`.

## Field re-homing

Every field keeps its id, type, label, help, default, validation, and `harnesses`. Only `section` changes:

| field | old section | new section |
|---|---|---|
| `name` | identity | identity |
| `enabled` | identity | schedule |
| `harness` | identity | harness_model |
| `model`, `effort`, `fallback_model`, `max_tokens` | model | harness_model |
| `prompt_file`, `append_system_prompt` | prompt_output | prompt |
| `output_dir` | prompt_output | directories |
| `workspace`, `wipe_workspace` | workspace | directories |
| `timeout_seconds`, `max_turns` | execution | limits |
| `permission_mode`, `allowed_tools`, `disallowed_tools`, `mcp_config` | execution | tools |
| `schedule` | scheduling | schedule |
| `network`, `memory`, `cpus` | resources | container |
| `env_file`, `env` | environment | environment |

Card presence per harness (derived from unchanged applicability):

| card | claude-code | pi | api | codex |
|---|---|---|---|---|
| Schedule | ✓ | ✓ | ✓ | ✓ |
| Limits | timeout, max turns | timeout | timeout | timeout |
| Prompt | ✓ | ✓ | prompt file only | ✓ |
| Directories | ✓ | ✓ | output dir only | ✓ |
| Environment | ✓ | ✓ | ✓ | ✓ |
| Tools & permissions | all four | allowed tools only | — | — |
| Harness & model | harness, model, effort, fallback | harness, model, effort | harness, model, max tokens | harness, model, effort |
| Container | ✓ | ✓ | ✓ | ✓ |

## Layout arrangement

Derived from the content pane's inline size; not stored.

| arrangement | pane inline size | grid areas | column tracks |
|---|---|---|---|
| one column | < 720px | `"runs" "job" "box"` | `minmax(0,1fr)` |
| two columns | 720px – 1319px | `"runs job" "box job"` | `minmax(0,1fr) minmax(0,1fr)` |
| three columns | ≥ 1320px | `"runs job box"` | `minmax(0,1fr) minmax(0,1.4fr) minmax(0,1fr)` |

## Written YAML order

Header comments (harness description, generated marker, schema version) unchanged, then blocks in `SECTIONS` order, then the Unmanaged block if any. For a fully populated claude-code agent:

```
# --- Identity ---        name
# --- Schedule ---        enabled, schedule
# --- Limits ---          timeout_seconds, max_turns
# --- Prompt ---          prompt_file, append_system_prompt
# --- Directories ---     workspace, wipe_workspace, output_dir
# --- Environment ---     env_file, env
# --- Tools & permissions ---  permission_mode, allowed_tools, disallowed_tools, mcp_config
# --- Harness & model --- harness, model, effort, fallback_model
# --- Container ---       network, memory, cpus
# --- Unmanaged (not edited by the UI) ---   (only if present)
```

Note that `harness` moves from the top of the file to the Harness & model block. The first line of every file is still the harness description comment, so a reader sees the runtime immediately.
