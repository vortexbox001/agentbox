# Phase 1 Data Model: Run Transparency

The feature is filesystem-backed; there is no database. The "model" is the set of files in a run
directory plus the two operator-facing config/derived shapes. Field-level JSON is in
`contracts/*.schema.json`; this document names the entities, their fields, relationships, and
rules.

## Entity map

```
Run directory  runs/<agent>/<date>/<run-id>/
├── transcript.jsonl   ── native stream (redacted)          [pruned by retention]
├── events.jsonl       ── Normalized events (redacted)      [pruned by retention]
├── context.json       ── Context snapshot (redacted)       [ALWAYS kept]
└── report.json        ── Run report (spec 007)             [ALWAYS kept]

config/settings.yaml   ── Retention policy (+ future settings)
Run (viewer model)     ── derived per-run row for the Runs list (not stored)
```

## 1. Run directory

- **Identity**: `<agent>` (name), `<date>` (`YYYY-MM-DD`, the run stamp's day), `<run-id>` (the
  Dagster run id).
- **Contents**: the four files above. Any file may be absent (partial write, pruning, or a legacy
  transcript-only run); the viewer renders what exists.
- **Rules**: immutable after the run (V); root-owned, world-readable so the ui service can read
  it; the unit of retention; the viewer's source of truth (independent of the orchestrator).
- **Relationships**: one directory per run; `report.transcript_path` and the Dagster
  run/materialization metadata (`run_dir`) both point back here (FR-002).

## 2. Normalized event  (`events.jsonl`, one per line — `contracts/normalized-event.schema.json`)

- **Common fields**: `kind` (system|user|assistant|tool_call|tool_result|final|error), `ts`
  (ISO-8601), `turn` (int ≥ 0), `tokens_in?`, `tokens_out?`, `cost_usd?` (each `null` = not
  reported, **distinct from 0**).
- **Kind-specific**:
  - `system` / `user` / `assistant` / `final`: `text` (string).
  - `tool_call`: `tool` (string), `args` (object).
  - `tool_result`: `result` (string); `diff` (unified-diff text) for a file edit; `missing`
    (bool, default false) — true when the harness cannot produce a faithful result (FR-008).
  - `error`: `text` (the error message).
- **Rules**: faithful order preserved; content never summarized (FR-007); produced by the harness
  image, redacted by the orchestrator before write (FR-013/014).
- **State**: none — an append-only, ordered log.

## 3. Context snapshot  (`context.json` — `contracts/context-snapshot.schema.json`)

Frozen at launch, immutable. Groups:
- **prompt**: `prompt_text` (as sent), `append_system_prompt` (the appended text, incl. the
  output convention).
- **model**: `model`, `effort?`, `fallback_model?`.
- **harness**: `harness`, `harness_version?`, `image_ref`, `image_digest`.
- **tools**: `allowed_tools[]?`, `disallowed_tools[]?`, `permission_mode?`,
  `mcp_servers[]?` (each: `name`, `tools[]`).
- **instruction_files[]**: `path`, `contents` (full text) — contributed by the image (R3).
- **runtime**: `env_names[]` (names only, never values — FR-015), `mounts[]` (`source`, `target`,
  `mode`), `network`, `memory`, `cpus`, `working_dir`.
- **file_trees**: `workspace[]` and `output[]` at start, each entry `path` + `size` (FR-010).
- **asset?** (asset runs only, FR-011): `asset_key`, `partition_key?`, `variant?`,
  `upstream_inputs?`, `attempt`.
- **completeness**: `complete` (bool), `undisclosed[]` (e.g. `"vendor base system prompt"`),
  `statement` (human-readable) (FR-012).
- **Rules**: env values MUST NOT appear anywhere; every string field passes redaction (FR-013/14).

## 4. Run report  (`report.json` — reuses spec-007 `run-report.schema.json`)

Unchanged shape: `status` (ok|failed|timeout), `tokens_in?`, `tokens_out?`, `turns?`, `cost_usd?`
(null for subscription harnesses), `files_written`, `transcript_path`, `error?`, `notes?`. This
feature only **co-locates** it in the run directory (spec Assumptions); it does not redefine it.

## 5. Retention policy  (`config/settings.yaml` — `contracts/settings.md`)

- `retention.mode`: `keep_forever` (default) | `prune_after_days`.
- `retention.days`: int ≥ 1 (required when `mode == prune_after_days`).
- **Rules**: persisted to instance config; enforced nightly; pruning removes only
  `events.jsonl` + `transcript.jsonl`; `report.json`, `context.json`, and `/output` always kept
  (FR-027).
- **State transition**: a run directory moves *conversation-present → conversation-pruned* when
  the prune job runs against it past its horizon; there is no reverse transition.

## 6. Run (viewer model — derived, not stored)

The list-level row assembled by `runs_store.list_runs`: `run_id`, `agent`, `started`
(from stamp/date), `status`, `model`, `cost_usd`, `attempts`, `run_dir`, and
`conversation_available` (whether `events.jsonl` exists). Filterable by **agent**, **status**,
and **date range** (clarification). Built from `report.json` + `context.json` headers only — never
by parsing `events.jsonl`.

## Redaction (cross-cutting — `contracts/redaction.md`)

Applies to entities 2, 3, and `transcript.jsonl`. Matches replaced with `[REDACTED:<kind>]`;
env values never written (entity 3). Post-capture, a search of the whole run directory for any
secret value present in the run finds no cleartext (`SC-004`).
