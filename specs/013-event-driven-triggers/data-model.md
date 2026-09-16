# Phase 1 Data Model: Event-Driven Triggers — Asset Dependency Graph

There is no database. `agents/*.yaml` + `ui/schema.py` is the agent data model; `config/settings.yaml`
+ `ui/settings_store.py` is the instance-settings model. This document describes the entities this
feature adds or changes and their rules. See [contracts/](contracts/) for the wire/YAML shapes.

---

## Entity: Agent definition (changed)

The declarative description of an agent (`agents/<name>.yaml`), extended with a dependency
declaration and two new asset-kind triggers.

| Aspect | Representation | Rules |
|--------|----------------|-------|
| Asset identity | `produces.asset`, `produces.partition` | Unchanged (spec 004/006). |
| **Dependencies** | `produces.depends_on:` — list of asset keys (new) | Optional. Each entry MUST match `ASSET_KEY_RE` and MUST name an asset produced by some loaded agent (FR-001/FR-002). Only meaningful when the agent is an asset. Empty/absent ⇒ no dependencies. |
| Checks | `produces.checks` | Unchanged (spec 008); blocking checks gate downstream automation (FR-006). |
| **Upstream trigger** | `triggers.on_upstream: true\|false` (new bool) | Materialize when any declared upstream materializes and passes its blocking checks. Applies only to assets. Default false. Behind `autocond_<name>`; starts paused (FR-004/FR-005). |
| **Missing trigger** | `triggers.on_missing: true\|false` (new bool) | Materialize the current/latest expected partition when it has never been produced. Applies only to assets. Default false. Behind `autocond_<name>`; starts paused; never re-fires once the partition exists (FR-008/FR-009). |
| Asset schedule | `triggers.asset_schedule` | Unchanged (spec 006); the third contributor to the one composed condition. |
| Job schedule | `triggers.job_schedule` | Unchanged (spec 006). |
| Schema stamp | `# agentbox-schema: 7` | Bumped this feature; `migrate_6_to_7` (identity) on read. |
| Everything else | prompt, dirs, env, tools, harness/model, container, `job` flag | Unchanged. |

### Rules

- **depends_on validity** (FR-001/FR-002): a list of strings, each matching `ASSET_KEY_RE`; each
  must resolve to a produced asset at load. A dangling entry ⇒ the agent is rejected at load,
  naming the missing key. The UI blocks saving a dangling reference.
- **Acyclic** (FR-003): the graph formed by all `depends_on` edges must be acyclic; any asset on a
  cycle is rejected at load, naming the assets in the cycle. The UI blocks saving a cycle.
- **Trigger kind** (FR-005/FR-009): `on_upstream`/`on_missing` are asset-kind — validation rejects
  them on a non-asset agent (mirror of `asset_schedule`).
- **Combined triggers** (FR-010): any combination of `asset_schedule`, `on_upstream`, `on_missing`
  is allowed; all live behind the single `autocond_<name>` sensor.

---

## Entity: Dependency edge & graph (new, derived)

A directed edge `downstream asset key → upstream asset key`, one per `depends_on` entry. The set of
all edges across loaded agents is the **dependency graph**.

| Aspect | Representation | Rules |
|--------|----------------|-------|
| Edge | one `depends_on` entry | Downstream depends on upstream; drives a Dagster `dep` + partition mapping. |
| Node | an asset key | Must be produced by exactly one loaded agent (duplicate keys already rejected, spec 006). |
| Partition mapping | identity `TimeWindowPartitionMapping` (daily→daily) | One-to-one by kind (FR-007); today→today. Non-identity out of scope. |
| Validity | acyclic + all referenced keys exist | Enforced in `definitions.discover()` at load (R5). |

Rejection cascades: rejecting a cycle member or a dangling-ref agent leaves its dependents with a
now-dangling edge, so they are rejected too; unrelated agents load normally.

---

## Entity: Upstream handoff record (new)

The read-only JSON file referenced by `AGENTBOX_UPSTREAM_<KEY>`, one per declared upstream,
describing that upstream's latest materialization for the downstream's matching partition. Full
shape: [contracts/upstream-handoff.schema.json](contracts/upstream-handoff.schema.json).

| Field | Meaning | When no materialization (FR-012a) |
|-------|---------|-----------------------------------|
| `asset_key` | the upstream asset key (e.g. `notes/daily`) | present |
| `partition` | the matching partition (date string) or null | present |
| `materialized` | `true` when a matching materialization exists | `false` |
| `output_files` | list of the upstream's output file paths | `[]` |
| `report` | the spec-007 report metadata (status, tokens, cost, …) | `null` |
| `materialized_at` | ISO-8601 materialization time | `null` |
| `chain_depth` | the producing run's chain depth (for R7) | `null` |
| `automated` | whether the producing run was automated (for R7) | `null` |

Rules: exactly one file per `depends_on` entry (FR-011); the file is always present even when the
upstream has no matching-partition materialization (FR-012a); mounted read-only (FR-013); reflects
the **latest** materialization when several exist (edge case).

**Env-var name transform**: `AGENTBOX_UPSTREAM_` + the asset key upper-snaked (`/` and `-` → `_`,
uppercased). `notes/daily` → `AGENTBOX_UPSTREAM_NOTES_DAILY`.

---

## Entity: Chain depth (new, per-run)

A tag/metadata value on every automated run recording how deep in a trigger chain it sits.

| Aspect | Rule |
|--------|------|
| Root automated run | `chain_depth = 1` — schedule- or `on_missing`-initiated, or fired by a **manual** upstream (FR-015). |
| Downstream automated run | `max(automated upstreams' chain_depth) + 1` (R7). |
| Manual upstream contribution | 0 (a manual upstream makes its downstream a root, depth 1). |
| Storage | recorded in the run's materialization metadata (`build_metadata`) and as run tags `agentbox/chain_depth` + `agentbox/automated`; read by downstreams via the handoff query. |
| Compared against | `max_chain_depth` (governor). |

---

## Entity: Run governor (new)

Instance-level limits in `config/settings.yaml`, applied to automated runs and bypassed by manual
runs. See [contracts/ui-settings-and-form.md](contracts/ui-settings-and-form.md).

| Field | Default | Rule |
|-------|---------|------|
| `governors.max_runs_per_hour` | 12 | Rolling 60-minute window count of automated runs that **actually launched**; a run that would exceed it is refused, logged, skipped, and does not consume a slot (FR-014). |
| `governors.max_chain_depth` | 5 | An automated run whose `chain_depth` would exceed it is refused and logged (FR-016). |

Rules: both are positive integers with sane upper bounds (validated by `settings_store`); manual
runs bypass both (FR-017); editable on the Settings page and persisted, taking effect on reload
(FR-018); the file is the single source of the live value, the defaults are the fallback when the
block/key is absent.

---

## Entity: Instance settings document (changed)

`config/settings.yaml` — already holds `retention:` (spec 012); now also holds `governors:`.
Unknown keys are preserved on write (existing `settings_store` behavior), so the two blocks coexist
and future blocks extend the same file.

```yaml
retention:
  mode: prune_after_days
  days: 30
governors:
  max_runs_per_hour: 12
  max_chain_depth: 5
```

---

## Schema version & migration

`SCHEMA_VERSION` 6 → 7. `migrate_6_to_7` is the **identity** function: `depends_on`,
`on_upstream`, and `on_missing` are additive — a schema-6 file simply has none, so it loads with
zero migration noise and re-stamps to 7 only when next saved from the UI (same posture as
`migrate_4_to_5` / `migrate_5_to_6`). No field is renamed or moved.
