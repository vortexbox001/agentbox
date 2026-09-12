# Contract: The metadata union attached to runs and materializations

The metadata the orchestrator attaches (FR-004/FR-005) is the union of the run-report fields and
the run-context fields recorded today. Verified by `test_reports.py`
(`test_materialization_records_expected_metadata` extended, plus new report-field assertions).

## Keys and their Dagster metadata kinds

| Key | Type in report/context | Dagster MetadataValue | Notes |
|-----|------------------------|-----------------------|-------|
| `status` | enum | text | one of ok/failed/timeout |
| `tokens_in` | int \| null | int, or text `"—"` when null | null must stay distinguishable from 0 |
| `tokens_out` | int \| null | int / text when null | " |
| `turns` | int \| null | int / text when null | " |
| `cost_usd` | number \| null | float, or text when null | null for claude-code/codex |
| `files_written` | int | int | the count (not the list) |
| `error` | string \| null | text / markdown, or omitted/`"—"` when null | present when status != ok |
| `notes` | string \| null | **md** (markdown text), or omitted/`"—"` when null | MUST render inline in the UI (FR-010); when null (timeout/crash) omit the key or use a text placeholder — never `MetadataValue.md(None)` |
| `output_files` | list[str] | json | existing; the `/output` before/after diff (path list) |
| `transcript` | host path | path | existing; same host path as report `transcript_path` |
| `run_stamp` | string | text | existing |
| `session_id` | string | text | existing |
| `harness` | string | text | existing |
| `model` | string | text | existing |
| `partition` | string | text | existing; present only when `context.has_partition_key` |

## Rules

- **Superset of today.** Every key the run records today (`output_files`, `transcript`,
  `run_stamp`, `session_id`, `harness`, `model`, `partition`) is still present, so the assertion
  `set(md) >= {those keys}` in the existing test continues to hold; the report keys are added.
- **Null is not zero.** A null numeric field (timeout/unmeasured) is surfaced distinctly from a
  genuine `0` — e.g. as a text placeholder — never coerced to `0`. The same applies to a null
  `notes`: omit the key or attach a text placeholder rather than a markdown value built from `None`.
- **`notes` is inline.** Attached as markdown text metadata so an operator reads it in the Dagster
  UI without opening the transcript file (FR-010/SC-006).
- **`transcript_path` maps to the existing `transcript` key.** The report field `transcript_path`
  (filled by the orchestrator) is surfaced through the existing `transcript` metadata key — the same
  host path — not as a second key. This satisfies FR-004 ("attach every report field") without
  duplicating the path under two names.
- **`files_written` (count) and `output_files` (list) coexist by design.** They are produced by
  different actors — `files_written` is the harness's own in-container `/output` count (report
  field), `output_files` is the orchestrator's `/output` before/after diff — and MAY differ; neither
  is derived from the other.
- **Same on success and failure.** For asset agents, the identical metadata union is attached
  whether it rides the normal output path's materialization (`status == ok`) or the explicit
  `AssetObservation` event on failure (`status != ok`). (A failure records an observation, not a
  materialization: a materialization event greens the partition, so emitting one on failure made a
  failed partition render MATERIALIZED — bug `failed-asset-shows-materialized`. The observation
  attaches the report while the failed run leaves the partition red.)
