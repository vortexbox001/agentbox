# Contract: Agent-Definition Path Validation (`ui/schema.validate`)

Extends the existing UI authoring guard (`ui/schema.py:validate`, which today injects
`prompt_exists`) with a path rule. The orchestrator continues to trust validated files; no new
per-run path re-validation is added (matches the established "UI validates, orchestrator trusts"
split — the orchestrator keeps only its structural `validate_checks` backstop).

## §1 Rule (FR-025, US5)

For each of `output_dir`, `workspace`, `env_file` present on the agent:

| Value | Result |
|---|---|
| under the product tree | **reject** |
| absolute path outside the data root, not a documented default | **reject** |
| under the data root | accept |
| omitted, or equal to the documented default (`$AGENTBOX_DATA/outputs/<name>`, `$AGENTBOX_DATA/workspaces/<name>`) | accept, without requiring a named path |

Rejection message **MUST name the offending field and state the rule**, e.g.
`output_dir: must fall under the data root ($AGENTBOX_DATA); "/opt/agentbox/..." is under the
product tree`.

The roots come from the UI's single resolution point (`ui/config.py`), passed into `validate`
(or read from config), keeping the single-resolution-point rule.

## §2 Related schema changes

- `SCHEMA_VERSION` 5 → **6**; `migrate_5_to_6` is the identity function; migrations-list entry
  added; docstring records the root change (FR-026).
- `output_dir` becomes optional with the documented default above (was `required=True`).

## §3 Behavioural requirements

- **R-PV-1 (US5-1, SC-006)**: an `output_dir` under the product tree is rejected 100% of the time
  with a message naming the field and stating the rule.
- **R-PV-2 (US5-2, edge "documented-default paths")**: `output_dir`/`workspace`/`env_file` under
  the data root, or omitted (default), or the documented default value → accepted.
- **R-PV-3**: a file stamped schema 6 round-trips; a schema-5 file reads with zero migration noise
  and re-stamps to 6 only when next saved (matches the existing identity-migration pattern).

## §4 Tests (UI suite)

- `validate` with `output_dir` under the product tree → error dict names `output_dir`, states the
  data-root rule (R-PV-1).
- `validate` with each of {omitted, documented default, under data root} → no path error (R-PV-2).
- Migration round-trip: schema-5 fixture → read → version 6 in memory, unchanged fields; save →
  stamped 6 (R-PV-3).
