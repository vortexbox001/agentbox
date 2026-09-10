# Contract: Schema, YAML emission, and the `/api/schema` payload

Additions to `ui/schema.py` and the `ui/agents_store.py` emitter for the `produces` block.
This amends the feature-001 YAML contract and the feature-003 section order.

---

## 1. Schema version

- `SCHEMA_VERSION` becomes `2`.
- `MIGRATIONS` gains `(2, migrate_1_to_2)` where `migrate_1_to_2` is the identity function
  (schema-1 files have no `produces`; nothing to transform).
- Emitted files carry `# agentbox-schema: 2`.
- A schema-1 file (any current agent) loads with **zero** warnings and **zero** migration noise
  (SC-005) and is re-stamped to 2 only when next saved from the UI.

## 2. New section and fields

Section (a new card in the **Runs** group, FR-013):
```python
{"id": "produces", "label": "Produces", "group": "runs"}
```

Fields (both apply to every harness; both belong to the `produces` block):
```python
SchemaField("asset", "produces", "Asset key", "string",
    "Asset key this agent materializes, e.g. repo-review/agentbox. Kebab segments joined by / "
    "for grouping. Leave empty to stay a plain job.",
    _ALL, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$")
SchemaField("partition", "produces", "Partition", "enum",
    "Partition set for the asset: none (single) or daily. A tracking label only — it does not "
    "change the run or output. Default none.",
    _ALL, default="none", choices=["none", "daily"])
```

`produces` is **not** in `ALWAYS_WRITTEN`: when `asset` is empty the whole block is emitted
commented-out (opt-in), matching the templates (FR-016).

## 3. Nested-block handling

`asset` and `partition` are children of a `produces` block. The store and emitter treat them as
a nested mapping, not two flat top-level keys.

**Read** (`agents_store.read_agent`): a `produces:` mapping in the file is lifted into the flat
`asset`/`partition` fields of the returned definition so the form shows them and they count as
*managed* (never routed to "Unmanaged").

**Write** (`agents_store.emit_yaml`): the two flat fields are emitted as a nested block in the
Runs section:
```yaml
# --- Runs ---
...
produces:                       # (block header)
  asset: repo-review/agentbox   # Asset key this agent materializes, e.g. repo-review/agentbox. ...
  partition: daily              # Partition set for the asset: none (single) or daily. ...
```
When `asset` is unset the block is emitted commented:
```yaml
#produces:                      # declare an output asset (see asset/partition below)
#  asset:                       # Asset key this agent materializes, e.g. repo-review/agentbox. ...
#  partition: none              # Partition set for the asset: none (single) or daily. ...
```

**Round-trip (FR-017/SC-007)**: emit → `yaml.safe_load` → `read_agent` → emit is byte-stable,
and the values shown on reopening the form equal the values saved.

## 4. Validation (UI, FR-011)

In `schema.validate`:
- If `asset` is set, it must match the asset-key regex (§2) → else field error on `asset`.
- `partition` must be one of `none`/`daily` (enum rule, already generic) → else field error.
- If `produces` is present in the source file with no `asset`, that is an empty declaration →
  error on `asset` ("an asset declaration must name an asset").
- The asset-key regex here is the **same** string as the orchestrator's (research R6); a test
  pins both against shared accept/reject fixtures.

The check is per-field so the UI rejects an invalid key before save (Story 4, AC-1).

## 5. `/api/schema` payload (`to_public`)

- `sections` includes the `produces` section.
- `fields` includes `asset` and `partition` with their `pattern`/`choices`/`help`.
- `schema_version` is `2`.
- Every harness's `fields` list (from `applicable_fields`) includes `asset` and `partition`.

No other payload shape changes.

## 6. Templates and README (FR-015/FR-016)

- Each `agents/_template-*.yaml` gains a commented-out `produces` block in its Runs section so an
  author can uncomment to opt in.
- The README key table gains `produces.asset` and `produces.partition` rows, derived from the
  schema help text (the schema stays authoritative; the table matches it — Constitution VI).

## 7. Golden files

The four `ui/tests/golden/*.yaml` are regenerated: header becomes `# agentbox-schema: 2` and a
commented `produces` block appears in the Runs section (or a real block in whichever fixture
exercises a set asset). Values of existing fields are unchanged.
