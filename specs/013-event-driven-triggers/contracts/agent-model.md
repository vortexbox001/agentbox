# Contract: Agent model — `depends_on` & the two asset-kind triggers

The agent YAML additions this feature introduces, their validation, the schema bump, and the
emitter. The authority is `ui/schema.py` (authoring guard) with `orchestrator/factory.py` as the
load-time structural backstop. See [../data-model.md](../data-model.md) for the entities.

## §1 New fields

Under the existing `produces:` block:

```yaml
produces:
  asset: refined/daily
  partition: daily
  depends_on:                # NEW — list of upstream asset keys this asset depends on (FR-001)
    - notes/daily
    - extras/daily
  checks: [ ... ]            # unchanged (spec 008)
```

Under the existing `triggers:` block:

```yaml
triggers:
  asset_schedule: "0 6 * * *"   # unchanged (spec 006)
  on_upstream: true             # NEW — fire when a declared upstream materializes (FR-004)
  on_missing: true              # NEW — fire when the latest partition has never been produced (FR-008)
  job_schedule: "..."           # unchanged
```

Both `on_upstream` and `on_missing` default to **false** (absent ⇒ off). `depends_on` defaults to
an empty list (absent ⇒ no dependencies).

## §2 SchemaField definitions (`ui/schema.py`)

- `depends_on` — `section="produces"`, `type="list"`, `block="produces"`, harnesses `_ALL`.
  Help: *"Upstream asset keys this asset depends on (kebab segments joined by /). When on_upstream
  is set, a materialization of any of these fires this asset for the matching partition; each is
  also handed to the container as AGENTBOX_UPSTREAM_<KEY>. Needs an asset."*
- `on_upstream` — `section="triggers"`, `type="bool"`, `block="triggers"`, default `False`,
  choices `[True, False]`, harnesses `_ALL`.
  Help: *"Materialize this asset when any declared upstream materializes and passes its blocking
  checks. Applies only when the agent is an asset; starts paused behind the asset's automation
  sensor."*
- `on_missing` — `section="triggers"`, `type="bool"`, `block="triggers"`, default `False`,
  choices `[True, False]`, harnesses `_ALL`.
  Help: *"Materialize the current/latest partition (today for daily; the single partition when
  unpartitioned) when it has never been produced. Does not backfill history. Applies only when the
  agent is an asset; starts paused behind the asset's automation sensor."*

`ALWAYS_WRITTEN` is unchanged (the new fields are written only when set). `to_public()` gains the
three fields automatically via `FIELDS`.

## §3 Validation rules (`schema.validate`)

Added to the existing rules; `is_asset`/`is_job` are already computed there:

1. **depends_on shape** (FR-001/FR-002): if present and non-unset, must be a list; each entry must
   be a string matching `ASSET_KEY_RE`. Otherwise `errors["depends_on"]` names the offending entry.
   Existence + acyclicity across agents are enforced at **load** (§5 / orchestrator), not in the
   single-agent form validate — but the UI SHOULD additionally cross-check existence/cycles using
   the known set of agents when saving (best-effort author-time guard; the load-time check is the
   authority). A `depends_on` on a non-asset agent is rejected: *"depends_on requires an asset —
   declare an asset key above."*
2. **on_upstream / on_missing kind** (FR-005/FR-009): each must be a bool; and each applies only
   when `is_asset`. On a non-asset agent: *"on_upstream applies only when the agent is an asset"* /
   *"on_missing applies only when the agent is an asset"* (mirror of the `asset_schedule` rule).
3. Existing trigger/cron rules unchanged.

## §4 Emitter (`ui/agents_store.py`)

- `depends_on` is lifted from / emitted into the `produces:` block as a YAML sequence, alongside
  `asset`/`partition`/`checks`, with the field's help as the block-line comment.
- `on_upstream` / `on_missing` are lifted from / emitted into the `triggers:` block as booleans,
  alongside `asset_schedule`/`job_schedule`, each with its help comment.
- Round-trip: read (lift nested → flat) then write (nest flat → block) reproduces the file; unknown
  keys preserved (existing behavior).

## §5 Load-time backstop (`orchestrator/factory.py` / `definitions.py`)

- `validate_asset_key` unchanged. A new backstop validates `depends_on` shape (list of asset-key
  strings) and rejects the agent (naming the file) on a malformed entry — the structural twin of
  the UI guard, no `croniter`-style extras needed.
- **Existence + cycles** are graph properties across all agents and are enforced in
  `definitions.discover()` (see [orchestrator-model.md](orchestrator-model.md) §4), not per-file.

## §6 Schema version & migration

`SCHEMA_VERSION` 6 → 7. `migrate_6_to_7(data)` returns `data` unchanged (identity): the three new
fields are additive. `MIGRATIONS` gains `(7, migrate_6_to_7)`. Golden files regenerate with the
`# agentbox-schema: 7` header. Files stamped 7 by a newer UI still raise `SchemaTooNew` as before.

## §7 Agent templates

`_template-*.yaml` gain, commented, `depends_on:` under `produces:` and `on_upstream:` /
`on_missing:` under `triggers:`, with the same help text, and re-stamp to schema 7 — so a hand-
authored file documents the new surface.
