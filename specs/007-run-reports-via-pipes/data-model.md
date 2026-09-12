# Phase 1 Data Model: Structured Run Reports via Dagster Pipes

The feature introduces no persisted database entities. The "data" is three in-flight structures:
the **run report** (produced by the image, or the orchestrator as fallback), the **injected Pipes
context** (orchestrator → container), and the **attached metadata** (the union surfaced in
Dagster). Types below are the contract; the JSON Schema for the report is in
`contracts/run-report.schema.json`.

---

## Entity: Run report

The single structured record a run hands back. One JSON object; the canonical answer to "what
happened in this run."

| Field | Type | Author | Validation / notes |
|-------|------|--------|--------------------|
| `status` | enum `ok` \| `failed` \| `timeout` | image (fallback: orchestrator) | required; drives materialize-vs-fail (FR-007) |
| `tokens_in` | integer \| null | image | `null` only when unmeasurable (e.g. timeout); never negative |
| `tokens_out` | integer \| null | image | as above |
| `turns` | integer \| null | image | as above; ≥ 0 when present |
| `cost_usd` | number \| null | image | `null` for subscription harnesses (claude-code, codex); non-null for api, pi (SC-001) |
| `files_written` | integer | image | count of files the run wrote to `/output`; ≥ 0 (not the path list) |
| `transcript_path` | string \| null | **orchestrator** | host path of the `.jsonl`; container leaves it null, orchestrator fills it |
| `error` | string \| null | image (fallback: orchestrator) | non-null iff `status != ok`, explaining the failure/timeout |
| `notes` | string \| null | image | the run's final assistant message text; no new prompt convention |

**State transitions**: a report is authored exactly once per run. Normal path: the image writes it
before the container exits. Fallback path: the orchestrator authors it when the container could not
(`timeout`, or a missing/malformed report on a normal exit). There is no mutation after authoring;
the orchestrator only *fills* `transcript_path` when merging into metadata.

**Relationships**: one report per run. For an **asset** agent it becomes materialization metadata;
for a **job-only** agent it becomes run/output metadata. It is transported over the Dagster Pipes
messages file (asset → `report_asset_materialization`; job → `report_custom_message`).

---

## Entity: Injected Pipes context (orchestrator → container)

What the orchestrator injects so the image can report correctly. Carried in two env vars produced
by `PipesEnvContextInjector` / `PipesFileMessageReader` and passed on the `docker run -e` list.

| Env var | Content | Notes |
|---------|---------|-------|
| `DAGSTER_PIPES_CONTEXT` | inline base64 JSON: run id, step key, asset keys (if any), partition key (if any), extras | path-independent; passed as-is. Presence of an asset key tells the wrapper to use `report_asset_materialization` vs `report_custom_message`. |
| `DAGSTER_PIPES_MESSAGES` | base64 JSON `{path: /pipes/messages}` | orchestrator **rewrites** the path from the host path to the container mount `/pipes/messages` before adding it. |

Carries **no secrets** (Constitution III). The `/pipes` mount is a per-run host temp dir, bound
read-write, distinct from `/output` (Constitution V).

---

## Entity: Attached metadata (the union surfaced in Dagster)

The set of fields Dagster displays for a run or materialized partition — the union of the report
fields and the existing run-context fields (FR-004/FR-005).

| Key | Source | Kind |
|-----|--------|------|
| `status`, `tokens_in`, `tokens_out`, `turns`, `cost_usd`, `files_written`, `error`, `notes` | run report | report fields (FR-002) |
| `transcript` / `transcript_path` | orchestrator | existing (FR-005) — same host path |
| `output_files` | orchestrator (`/output` before/after diff) | existing (FR-005) — the path list |
| `run_stamp`, `session_id`, `harness`, `model` | orchestrator | existing (FR-005) |
| `partition` | orchestrator (when `context.has_partition_key`) | existing (FR-005) |

`notes` must render inline in the Dagster UI (FR-010) — attached as text/markdown metadata, not a
file reference. `files_written` (count) and `output_files` (list) intentionally coexist.
