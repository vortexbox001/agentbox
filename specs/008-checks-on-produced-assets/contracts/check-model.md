# Contract: `produces.checks` model — schema, UI, validation, load rules

This contract governs how a check is **declared, validated, edited, and loaded**. The runtime
(container launch + Dagster asset-check mapping) is in [check-execution.md](./check-execution.md).

## §1 YAML shape

`checks` is an optional list under an agent's `produces:` block:

```yaml
produces:
  asset: <asset-key>            # REQUIRED for checks to be legal (FR-010)
  partition: none | daily
  checks:
    - name: <kebab>             # REQUIRED, unique within the agent
      command: <shell string>   # REQUIRED, run as: sh -c "<command>"
      image: <docker ref>       # OPTIONAL, default: the agent's harness image
      blocking: true | false    # OPTIONAL, default: true
      timeout_seconds: <int>    # OPTIONAL, 1..86400
      network: agentnet-isolated | agentnet | bridge   # OPTIONAL, default: no network
```

## §2 Field rules

1. `name` — required; matches `^[a-z0-9]+(-[a-z0-9]+)*$`; **unique** among the agent's checks.
2. `command` — required; non-empty string; interpreted as a shell command line.
3. `image` — optional string; when omitted the producing agent's harness image is used.
4. `blocking` — optional bool; **defaults to `true`** when the key is absent (FR-001, US2 scenario 3).
5. `timeout_seconds` — optional integer in `1..86400`.
6. `network` — optional; one of the three agent network choices; when omitted the check gets **no**
   network.

## §3 Validation (both the UI `schema.validate` and orchestrator load agree)

- **Checks require an asset (FR-010)**: `checks` present with no valid `produces.asset` ⇒ error /
  `RejectAgent`, naming the file.
- **Per-item**: missing `name` or `command`, a `name` failing the pattern, a `blocking` that is not
  a bool, a `timeout_seconds` out of range, or a `network` not in the enum ⇒ error.
- **Duplicate names**: two checks with the same `name` ⇒ error / `RejectAgent`.
- A **job-only** agent (no `produces`) that carries `checks` ⇒ rejected (there is no asset to attach
  to). The UI does not render the Checks card for such an agent (FR-011).

The orchestrator copy is the structural backstop at load; the UI copy is the authoring guard. One
bad agent file is skipped and logged by name; every other agent still loads (FR-010).

## §4 UI (FR-011)

- The **Checks card** renders **inside the asset nature card** (`buildAssetCard()`), so it is shown
  only when the agent is an asset and **hidden** for a job-only agent.
- The card is a repeatable-object-rows editor (add / remove a check), each row exposing `name`,
  `command`, `image`, `blocking`, `timeout_seconds`, `network`. It follows the add/remove
  scaffolding of the existing map editor (`renderMap`).
- On collect, when the asset gate is off the checks are dropped along with the rest of the produces
  block; when on, the checks list is written under `produces.checks`.

## §5 Emission (YAML writer)

- `_produces_block_lines` gains a branch that, when checks are present, emits a nested
  `checks:` sequence-of-mappings under `produces:` with a header comment; each check is emitted as
  `  - name: …` / `    command: …` / … with only its set fields.
- When no checks are present, nothing is emitted for `checks` (the block is unchanged from today).
- Help/comment text for the checks list lives beside `PRODUCES_BLOCK_HELP` in `schema.py` and is
  emitted verbatim (Constitution VI — the file documents itself).

## §6 Schema version

`SCHEMA_VERSION` 4 → 5; `migrate_4_to_5` is identity. A schema-4 file (no checks) loads with zero
migration noise and re-stamps to 5 only when next saved.

## §7 Documentation (FR-012)

The README agent-YAML reference (the `produces.*` rows) and the `produces:` narrative, and the
`_template-*.yaml` produces-block comments, document the `checks:` list and every check field. The
authoritative wording is the `schema.py` help strings.
