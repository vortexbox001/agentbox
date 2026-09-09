# Contract: Schema groups and YAML section order

Amends `specs/001-agent-management-ui/contracts/http-api.md` (the `/api/schema` payload) and `specs/001-agent-management-ui/contracts/agent-yaml.md` §2 (section order). Everything not mentioned here is unchanged.

## 1. `GET /api/schema` additions

```json
{
  "schema_version": 1,
  "groups": [
    {"id": "runs", "label": "Runs"},
    {"id": "job",  "label": "Job"},
    {"id": "box",  "label": "Box"}
  ],
  "sections": [
    {"id": "identity",      "label": "Identity",            "group": null},
    {"id": "schedule",      "label": "Schedule",            "group": "runs"},
    {"id": "limits",        "label": "Limits",              "group": "runs"},
    {"id": "prompt",        "label": "Prompt",              "group": "job"},
    {"id": "directories",   "label": "Directories",         "group": "job"},
    {"id": "environment",   "label": "Environment",         "group": "job"},
    {"id": "tools",         "label": "Tools & permissions", "group": "job"},
    {"id": "harness_model", "label": "Harness & model",     "group": "box"},
    {"id": "container",     "label": "Container",           "group": "box"}
  ],
  "fields": [ "... unchanged shape; each field's `section` is one of the ids above ..." ],
  "harnesses": [ "... unchanged shape; each `fields` list is in the new FIELDS order ..." ]
}
```

Guarantees:
- `groups` and `sections` are in display order.
- Every `sections[].group` is `null` or one of `groups[].id`. Exactly one section (`identity`) has `null`.
- Every `fields[].section` names an entry in `sections`.
- `fields` is contiguous by section, in `sections` order; `harnesses[].fields` preserves that order filtered to the harness.
- No field id, type, label, help, default, validation rule, or `harnesses` entry changes.
- `schema_version` stays `1`: files written under the old order load unchanged, and the version marker gates only key semantics, not order.

## 2. Written YAML (amends agent-yaml.md §2)

After the three header comment lines, blocks appear in this fixed order, each introduced by a blank line and `# --- <label> ---`, and each omitted if none of its fields apply to the harness or carry a value:

1. Identity — `name`
2. Schedule — `enabled`, `schedule`
3. Limits — `timeout_seconds`, `max_turns`
4. Prompt — `prompt_file`, `append_system_prompt`
5. Directories — `workspace`, `wipe_workspace`, `output_dir`
6. Environment — `env_file`, `env`
7. Tools & permissions — `permission_mode`, `allowed_tools`, `disallowed_tools`, `mcp_config`
8. Harness & model — `harness`, `model`, `effort`, `fallback_model`, `max_tokens`
9. Container — `network`, `memory`, `cpus`
10. Unmanaged (not edited by the UI) — verbatim keys the schema does not define

Unchanged rules: one help comment per field, unset optionals written as commented-out keys, `schedule: ""` always written, deterministic output, and the golden files in `ui/tests/golden/` are the byte-exact reference for one populated agent per harness.

Migration: a file written under the old order is loaded by key, so it round-trips with identical values; its next save rewrites it in the new order. No data migration step exists or is needed.
