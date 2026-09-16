# Contract: Settings & retention

**Requirements**: FR-025–FR-029, SC-006. **File**: `$AGENTBOX_CONFIG/settings.yaml`.
**New modules**: `ui/settings_store.py`, `orchestrator/prune.py`.

## settings.yaml — retention block

```yaml
# config/settings.yaml
retention:
  mode: keep_forever          # keep_forever | prune_after_days
  days: 30                    # required when mode == prune_after_days; int >= 1
```

- Default when absent or `mode: keep_forever`: nothing is pruned, runs kept forever (FR-025,
  FR-028 default case).
- `ui/settings_store.py` reads and writes this block; unknown keys in the file are preserved
  (future settings sections extend the same file — the placeholder already ships in
  `examples/config/settings.yaml`).

## Settings page (FR-025)

`GET /settings` renders `settings/page.html` with a **Retention** section: a choice of "keep
forever" / "prune after N days" and the N field, composed from design-system macros. `POST
/api/settings/retention` validates and persists to `settings.yaml`. (Today "Settings" is only a
localStorage theme modal; this adds the first server-backed Settings page. The theme picker
stays.)

## Nightly prune job (FR-026, FR-027)

- Registered by the orchestrator's job factory as a **Dagster schedule** (`sched_prune_runs` or
  similar), running once nightly in `cron_timezone()`, visible/toggleable alongside agent
  schedules.
- `orchestrator/prune.py` reads the retention policy; for each run directory whose day is older
  than `days`, it removes **only** `events.jsonl` and `transcript.jsonl`.
- It MUST NOT touch `report.json`, `context.json`, or the run's `/output` artifacts (FR-027,
  clarification: output artifacts are never pruned).
- `mode: keep_forever` (or absent) → the job is a no-op.

## Pruned-run rendering (FR-028 / SC-006)

A run whose `events.jsonl`/`transcript.jsonl` are gone still opens: Context and Report tabs
render from the retained files; the Conversation tab shows a "conversation pruned" note in place
of history. The Files tab still lists retained output artifacts.

## Documentation (FR-029)

The retention behaviour (policy, what is/ isn't pruned, the nightly job) is documented in the
README, consistent with Constitution VI.
