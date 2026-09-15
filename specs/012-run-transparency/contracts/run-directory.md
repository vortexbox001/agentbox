# Contract: Run directory

**Requirements**: FR-001, FR-002, FR-018, FR-027, FR-028. **Depends on**: `paths.py`
(`RUNS_ROOT`), spec-007 report shape.

## Layout

```
$AGENTBOX_DATA/runs/<agent>/<YYYY-MM-DD>/<run-id>/
├── transcript.jsonl   # native harness stream, redacted           (pruned by retention)
├── events.jsonl       # normalized-event.schema.json, one/line     (pruned by retention)
├── context.json       # context-snapshot.schema.json               (ALWAYS kept)
└── report.json        # spec-007 run-report.schema.json            (ALWAYS kept)
```

- `<agent>` = agent name; `<YYYY-MM-DD>` = run-stamp day; `<run-id>` = Dagster run id.
- Directory `0755`, files `0644`, root-owned — world-readable so the ui service (uid 1000) reads
  them read-only.
- The directory is created and written by the **orchestrator** at launch (context.json first, so
  the audit record exists even for a crash-before-first-event) and completed at run end
  (transcript, events, report). It is immutable thereafter (Constitution V).

## Ownership of writes

| File | Native producer | Written to run dir by | When |
|------|-----------------|-----------------------|------|
| `context.json` | orchestrator (+ image fragment merged) | orchestrator | at launch |
| `transcript.jsonl` | container stdout | orchestrator (streams, redacts per line) | during run |
| `events.jsonl` | image `to_events()` → staging mount | orchestrator (redacts, moves) | at run end |
| `report.json` | image over Dagster Pipes (or orchestrator-authored on timeout) | orchestrator | at run end |

The container writes only `/output` and the ephemeral staging mount; it never writes into the
run directory.

## Metadata link (FR-002)

`build_metadata` adds `run_dir` (a `MetadataValue.path` to the directory) alongside the existing
`transcript` key. `report.transcript_path` continues to point at `.../transcript.jsonl`.

## Backward compatibility & partial writes

- **Legacy flat runs** (`runs/<agent>/<date>/<run-id>.jsonl`) are surfaced as transcript-only
  runs (no events/context/report), rendered with the "conversation only / context unavailable"
  degradation. No bulk migration (R1).
- **Partial write** (crash mid-run): the viewer renders whatever files exist and never fails the
  whole page because one is absent (edge case).

## Retention interplay (FR-027/FR-028)

Pruning removes only `events.jsonl` and `transcript.jsonl`. `context.json`, `report.json`, and
the run's `/output` artifacts are always kept. A pruned run still opens; its Conversation tab
shows a "conversation pruned" note. See `settings.md`.
