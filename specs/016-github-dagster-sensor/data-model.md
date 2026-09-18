# Phase 1 Data Model: GitHub Project Status Trigger — Board-Driven Agent Launches

There is no database. `agents/*.yaml` + `ui/schema.py` is the agent data model; the **sensor cursor**
is durable Dagster instigator state under `$DAGSTER_HOME`; the **run handoff** is a set of run tags,
`run_config`, env values, and one read-only file. This document describes the entities this feature
adds or changes and their rules. See [contracts/](contracts/) for the wire/YAML/GraphQL shapes.

---

## Entity: Agent definition (changed)

The declarative description of an agent (`agents/<name>.yaml`), extended with one optional trigger
block.

| Aspect | Representation | Rules |
|--------|----------------|-------|
| **Board trigger** | `triggers.on_project_status:` — a nested mapping (new) | Optional. When present, `owner`, `project`, `status` are required; `label`, `repo`, `interval_seconds` optional. Builds one `project_status_<name>` sensor. Composes with the other triggers, does not replace them (FR-001/FR-002). |
| Existing triggers | `asset_schedule`, `job_schedule`, `on_upstream`, `on_missing` | Unchanged (spec 006/013). Any combination coexists with `on_project_status`. |
| Agent kind | `produces` (asset) / `job: true` (job) | Unchanged. The board trigger is valid for both: an asset-kind agent is materialized, a job-kind agent is launched by job name (FR-002). |
| Schema stamp | `# agentbox-schema: 8` | Bumped this feature; `migrate_7_to_8` (identity) on read. |
| Everything else | prompt, dirs, env, tools, harness/model, container | Unchanged. |

### `on_project_status` fields

| Field | Type | Required | Rule |
|-------|------|----------|------|
| `owner` | string | yes | The board owner (org login; a user login may work — spec Assumption "Board ownership"). |
| `project` | integer | yes | The board number; MUST be a positive integer (FR-001/FR-023). |
| `status` | string | yes | The Status single-select **option name**, matched case-insensitively (FR-001; spec Assumption "Status matching"). |
| `label` | string | no | Only issues whose label-name list includes this name launch; matched by exact membership, case-insensitively (FR-001/US4). |
| `repo` | string | no | Only issues from this repository launch; the full `owner/repo`, matched case-insensitively (FR-001, spec clarification). |
| `interval_seconds` | integer | no | Poll cadence; default 60, minimum 30 (FR-001/FR-023). |

### Rules

- **Validity** (FR-023): a bad block (missing a required field, `project` not a positive integer,
  `interval_seconds` below 30 or non-integer) rejects **that one agent** at load with a file+field
  message in the `depends_on`/`checks` style; every other agent still loads (US8). The UI blocks
  saving the same violations at author time.
- **Composition** (FR-002): `on_project_status` may coexist with any other trigger; it adds the
  polling sensor without touching the asset automation sensor or schedules.
- **Kind-agnostic** (FR-002): valid on asset-kind and job-kind agents alike.

---

## Entity: Board item (external, read each tick)

An item on the GitHub Projects board, read from the GraphQL query (not persisted). Full shape:
[contracts/github-projects-query.md](contracts/github-projects-query.md).

| Field | Meaning | Rule |
|-------|---------|------|
| `item_id` | the Projects v2 **item** id (opaque, stable) | Anchors deduplication and the cursor (FR-005). |
| `content_type` | `Issue` \| `PullRequest` \| `DraftIssue` | Only `Issue` is a launch candidate; PRs and drafts are dropped before admission and never hold the slot (FR-004). |
| `status` | the item's Status single-select option name | Kept only when it equals the configured `status` case-insensitively. |
| `number` | issue number | Feeds the feature key and `AGENTBOX_ISSUE_NUMBER`. |
| `repo` | `repository.nameWithOwner` (`owner/repo`) | The `repo` filter and `AGENTBOX_ISSUE_REPO`; matched case-insensitively. An issue whose `repository.nameWithOwner` is absent/blank is skipped defensively rather than launched with a blank repo (CHK005). |
| `url` | issue URL | `AGENTBOX_ISSUE_URL` + `agentbox/issue_url`; the run-page link. |
| `title` | issue title | Sanitized into `AGENTBOX_ISSUE_TITLE` and slugged into the feature key. |
| `body` | issue body | Written to the read-only body file; never on a command line, env value, or tag. |
| `labels` | issue label names | The `label` filter (exact membership, case-insensitive). |

Only issues in the configured status passing the optional `label` and `repo` filters reach admission.

---

## Entity: Sensor cursor (new, durable)

The durable record of items currently seen in the target status, persisted via `context.cursor`,
keyed by the `project_status_<name>` sensor. Shape:

```json
{"version": 1, "seen": {"<item_id>": {"entered_at": "2026-09-17T21:20:00Z", "launched": true, "eligible": true}}}
```

| Aspect | Rule |
|--------|------|
| `version` | Cursor schema marker, always `1` today. `plan_tick` **always** emits it and preserves it when a cursor is carried, so a persisted cursor is never `{}` (keeps the first-tick discriminator unambiguous). |
| `seen[item_id].entered_at` | ISO-8601 time the item was **first seen** in the status; part of the run key; drives oldest-first release (FR-006/FR-010). |
| `seen[item_id].launched` | Whether a run has been launched for this entry; makes the item the slot holder while still in status (FR-008). |
| `seen[item_id].eligible` | Whether this entry may ever launch: `true` for a genuine new arrival, `false` for a first-tick-seeded / pre-existing item that must never launch (FR-007). Admission candidates are exactly the `launched: false && eligible: true` ids, so a pre-existing item never launches on any later tick while a held item launches when the slot frees (FR-005/FR-010). |
| First tick (no persisted cursor) | Detected by the **absence of the cursor string** (`cursor_state == {}`), never by `seen` being empty. Seed every current in-status item as `{entered_at: now, launched: false, eligible: false}` and launch nothing (FR-007). An empty-board first start still persists `{"version": 1, "seen": {}}`, so the next tick reads a present cursor and treats a genuine arrival as `eligible: true` (launches). |
| Item newly in status | Added as `{entered_at: now, launched: false, eligible: true}` and marked eligible (FR-005). |
| Item left status | Dropped from `seen`, so a later re-entry is a fresh entry with a new `entered_at` (FR-005 / re-entry edge). |
| Transient/unresolvable error | Cursor **not** updated — the tick skips and the next tick retries from the unchanged cursor (FR-019/FR-020). |

Restart safety is double: the cursor persists under `$DAGSTER_HOME`, and Dagster's per-sensor run-key
ledger persists independently (FR-006 / US2 #2).

---

## Entity: Active feature & the slot (new, derived)

The one issue whose run is in flight for an agent, from launch until it leaves the status.

| Aspect | Rule |
|--------|------|
| Active | An item with `launched: true` in `seen` that is still in the current board's in-status set (FR-008). |
| Slot | Held while any active item exists; the slot is **per agent** (per sensor), independent across agents (FR-008, spec clarification). |
| Held issue | An unlaunched item with `eligible: true` that cannot launch because the slot is held; reported on the tick naming the holder (FR-009). First-tick-seeded items (`eligible: false`) are neither held nor candidates. |
| Release | The active item leaving the status frees the slot; the next held issue (oldest by `entered_at`) launches on the following tick (FR-010). Release needs only the board move — no downstream knowledge (US3 #4). |

---

## Entity: Feature key (new, pure-derived)

The identifier for a launch, a pure function of the issue (no configuration). Grammar
`^[0-9]{3}(-[a-z0-9]+)*$`, total length ≤48.

| Aspect | Rule |
|--------|------|
| Number part | The issue number zero-padded to three digits (`NNN`). |
| Slug part | The title lowercased, only `a-z0-9` kept, every other run collapsed to a single `-`, no leading/trailing `-`; non-ASCII letters and emoji **dropped**, not transliterated (spec clarification). |
| Cap | The whole key truncated to ≤48 chars, then any trailing `-` stripped (FR-011). |
| Empty slug | When the title slugs to empty, the key is `NNN` alone with no trailing hyphen (spec clarification; e.g. `038`). |
| Determinism | Same issue ⇒ same key; two same-title issues differ because the number leads (SC-007). |
| Consumers | Carried as `AGENTBOX_FEATURE_KEY` + `agentbox/feature_key`; #22 makes it substitutable, #24 a partition key — the grammar/cap are pinned now. |

---

## Entity: Run handoff (new; reuses the spec-013 mechanism)

The set of tags, `run_config`, env values, and the read-only body file placed into a sensor-launched
run. See [contracts/orchestrator-model.md](contracts/orchestrator-model.md).

| Surface | Contents | Rule |
|---------|----------|------|
| Run tags | `agentbox/issue_number`, `agentbox/issue_repo` (`owner/repo`), `agentbox/issue_url`, `agentbox/project_item_id`, `agentbox/feature_key` | Set on the `RunRequest` so the run carries them from creation (FR-012); the run page links the issue via `issue_url` (FR-026). Title/body are **never** tags (FR-015). |
| `run_config` | `{number, repo, url, title, feature_key, body}` | The op's transport for the variable-size title/body; Dagster run storage, never a command line or env value (FR-014/FR-015). |
| Env values | `AGENTBOX_ISSUE_NUMBER`, `AGENTBOX_ISSUE_REPO`, `AGENTBOX_ISSUE_URL`, `AGENTBOX_ISSUE_TITLE`, `AGENTBOX_FEATURE_KEY`, `AGENTBOX_ISSUE_BODY_FILE` | Set on the container by the op from the payload; `AGENTBOX_ISSUE_TITLE` is control-stripped and ≤256 (FR-013/FR-015). |
| Body file | `<handoff_dir>/body.md`, `chmod 0644`, mounted `:ro` at `/issue`; `AGENTBOX_ISSUE_BODY_FILE=/issue/body.md` | The body is delivered as a read-only file, never on the command line or in an env value (FR-014); reuses the spec-013 handoff dir + `:ro` mount + `--rm` cleanup. |
| Lineage | `dagster/sensor_name` (Dagster-set) | Marks the run automated: it counts toward the launch-rate governor and starts a chain at depth 1 (FR-018). |

The **board token** appears in none of these (FR-017): it stays in the daemon process only.

---

## Schema version & migration

`SCHEMA_VERSION` 7 → 8. `migrate_7_to_8(data)` returns `data` unchanged (identity): `on_project_status`
is additive — a schema-7 file simply has none, so it loads with zero migration noise and re-stamps to
8 only when next saved from the UI (same posture as `migrate_5_to_6` / `migrate_6_to_7`). `MIGRATIONS`
gains `(8, migrate_7_to_8)`. No field is renamed or moved.
