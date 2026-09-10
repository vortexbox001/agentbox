# Data Model: Agent Produces Asset

The single source of truth remains `agents/*.yaml` (no database). This feature adds one
optional block to that file and defines how the orchestrator represents it.

---

## Entity: Produces declaration

The optional block in an agent definition stating the agent produces a tracked asset.

| Field       | Type   | Required | Default | Rules |
|-------------|--------|----------|---------|-------|
| `asset`     | string | yes (if `produces` present) | — | Valid asset key: `^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$`. Slash segments form the asset key path (grouping/prefix). |
| `partition` | enum   | no       | `none`  | One of `none`, `daily`. |

**Placement in YAML**: top-level `produces:` mapping. In UI-emitted files it appears in the
**Runs** section (FR-013/FR-017) with one comment per field.

**Validation** (both UI and orchestrator, FR-011):
- `produces` present but no `asset` → **invalid** (empty declaration rejected; edge case).
- `asset` not matching the asset-key regex → **invalid**; the orchestrator names the offending
  file in the message (FR-012).
- `partition` not in {`none`, `daily`} → **invalid**.
- `partition` omitted → treated as `none` (unpartitioned).

**Example**:
```yaml
produces:
  asset: repo-review/agentbox   # asset key this agent materializes (kebab segments, / for grouping)
  partition: daily              # none | daily — daily exposes a per-day partition (a tracking label only)
```

## Entity: Asset (orchestrator-side)

The orchestrator's representation of a declared output. Not stored in a file; derived at load.

| Attribute        | Source | Notes |
|------------------|--------|-------|
| key              | `produces.asset` | `AssetKey(asset.split("/"))`. |
| partitions_def   | `produces.partition` | `DailyPartitionsDefinition(start_date=<epoch>)` when `daily`; none otherwise. |
| compute step     | `make_run_op(cfg)` | The same op used for jobs; named `run_<name>` (FR-010). |
| points to        | `cfg.output_dir` | A pointer to existing files; no copy is made (FR-007). |
| history          | Dagster | Materialization history per key/partition (empty before first run). |

**Uniqueness (FR-019)**: an asset key is unique across enabled agents. Two or more enabled
agents declaring the same key → all declaring files rejected by name; others load.

## Entity: Materialization record

Produced each time the asset is materialized; carries this metadata (FR-008):

| Metadata field  | Source | Type |
|-----------------|--------|------|
| `output_files`  | before/after snapshot of `output_dir` (FR-008a) | list of paths (may be empty) |
| `transcript`    | `<AGENT_LOG_ROOT>/<agent>/<date>/<run-id>.jsonl` | path |
| `run_stamp`     | `AGENTBOX_RUN_STAMP` (existing) | string |
| `session_id`    | `AGENTBOX_SESSION_ID` (existing) | string |
| `harness`       | `cfg.harness` | string |
| `model`         | `cfg.model` | string |
| `partition`     | `context.partition_key` when partitioned (FR-008b) | string (optional) |

The metadata dict is open-ended: feature 005 adds token/cost fields here with **no** change to
the `produces` block schema (FR-009).

## Entity: Agent definition (amended)

The existing agent file, now optionally carrying `produces`. Still the sole source of truth.

- `produces` **absent** → job named `agent_<name>`, behavior identical to today (FR-004/FR-018).
- `produces` **present** → asset as above (FR-003).
- `enabled: false` → skipped at startup whether or not `produces` is present (edge case).

## UI schema additions (`ui/schema.py`)

- **Section**: `{"id": "produces", "label": "Produces", "group": "runs"}` (a new card in the Runs column).
- **Fields** (both `harnesses = _ALL`; part of a `produces` block):

  | id | type | choices | help (verbatim comment / README source) |
  |----|------|---------|------|
  | `asset` | string | — | "Asset key this agent materializes, e.g. repo-review/agentbox. Kebab segments joined by / for grouping. Leave empty to stay a plain job." |
  | `partition` | enum | `none`, `daily` | "Partition set for the asset: none (single) or daily. A tracking label only — it does not change the run or output. Default none." |

- **Version**: `SCHEMA_VERSION = 2`; `MIGRATIONS` gains `(2, <identity>)` — schema-1 files have
  no `produces`, so nothing transforms and they load without noise (SC-005).
- Field applicability matrix is unchanged for existing fields; the two new fields apply to all
  harnesses (any agent may produce an asset).

## State transitions

```
job-mode  --add produces-->  asset-mode
asset-mode --remove produces--> job-mode   (reversible, no other change — SC-004)
```

No in-place data migration is triggered by either transition; the representation is recomputed
from the file at each orchestrator reload.
