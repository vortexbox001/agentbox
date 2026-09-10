# Contract: Automation file format, merge, and migration

## §1 File shape

A file under `automation/` is a YAML **map keyed by agent name**. Each value is a mapping
with exactly one trigger key:

```yaml
<agent-name>:
  cron: "<m> <h> <dom> <mon> <dow>"   # OR
<agent-name>:
  on_demand: true
```

- Keys are agent `name`s (kebab-case, `^[a-z0-9]+(-[a-z0-9]+)*$`).
- `cron`: exactly five whitespace-separated fields; `@`-macros unsupported.
- `on_demand`: the literal `true`.
- One or more files may live in `automation/`; `migrated.yaml` is the **canonical** file —
  the one-off migration creates it and the UI thereafter owns it (every `PUT /api/automation`
  rewrites it). Its name is historical (it began as the migration's output) and does not
  change once the UI manages it; additional hand-authored files may coexist and are merged
  read-only by the orchestrator but are not rewritten by the UI.

## §2 Merge and default

Loading merges all `automation/*.yaml` into one `{name → trigger}` map. An agent absent from
the merged map is on-demand (FR-006). `on_demand: true` and "absent" are behaviorally
identical.

## §3 Validation (at orchestrator load and in the UI before save)

Applied in order; the **orchestrator raises** (failing the reload) and the **UI refuses the
save**, both naming the offender:

| # | Condition | Result | Requirement |
|---|-----------|--------|-------------|
| 1 | Same agent keyed in ≥2 files (or twice in one file) | Reject, naming the agent + files | FR-011 |
| 2 | Key not in the known-agent-name set | Reject, naming the entry + file — reload FAILS | FR-010 |
| 3 | Entry has both `cron` and `on_demand` | Reject, naming the entry | FR-005 |
| 4 | Entry has neither `cron` nor `on_demand` | Treat as on-demand (no error) | Assumption |
| 5 | `cron` fails the five-field / no-macro rule | Reject, naming the entry | FR-009 |

The five-field rule is the exact rule the removed `schedule` field enforced. It is stated
once in the orchestrator and once in the UI's `automation_store.py` (deliberate duplication
across the container boundary; a test pins both against shared fixtures).

**Known-agent-name set** (row 2): every `name` declared by any `agents/*.yaml` — templates
and disabled agents **included** (the file exists, so the entry is not "unknown"). A disabled
agent's entry attaches to nothing and produces no trigger (spec edge case), and is not a
dangling-agent error. The management UI lists only non-template agents (ui-automation §3), so
it never offers a template name; a template-named entry can only arise from a hand-edit, and
the orchestrator accepts it as "known" (it just resolves to a skipped/disabled file).

Unknown-agent handling **differs from 004**: 004 skips one bad file; here a dangling entry
FAILS the reload (FR-010), because the UI already refuses to write one, so its only source
is a hand-edit the operator should be told about loudly.

## §4 Migration (`scripts/migrate-schedules.py`)

Run once; idempotent.

1. For **every** `agents/*.yaml`: remove the `schedule:` line and normalize the schema stamp
   to `3` — bump an existing `# agentbox-schema:` line, or prepend one to a file that has none,
   so the whole `agents/` dir ends uniformly at schema 3. (Textual edit — preserves the file's
   other comments/formatting.)
2. For every **non-template** file (basename not starting with `_`) whose removed `schedule`
   was non-empty: add `‹name›:\n  cron: "‹value›"` to `automation/migrated.yaml`.
3. Manual-only (`schedule: ""`) → line removed, **no** entry (agent becomes on-demand).
4. Templates (`_template-*.yaml`) → line removed, **no** entry (FR-012 — they share the
   name `my-agent`).

**Idempotency**: a second run finds no `schedule:` lines, stamps already at `3`, and each
target entry already in `migrated.yaml` → zero file changes (SC-002).

**Post-conditions on the current repo**: `repo-librarian-agentbox` gains
`{cron: "30 2 * * *"}` in `migrated.yaml`; no `agents/*.yaml` (templates included) retains a
`schedule` key; no template contributes an entry (SC-001).
