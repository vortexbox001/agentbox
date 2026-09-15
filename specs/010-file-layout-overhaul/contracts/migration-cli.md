# Contract: Migration CLI (`scripts/migrate-layout.py`)

## §1 Invocation

```
python3 scripts/migrate-layout.py            # dry-run: print the plan, change nothing
python3 scripts/migrate-layout.py --apply    # perform the moves/rewrites/symlink
```

Reads the three roots from the same env vars as the running stack (defaults per
path-resolution §1). Old-layout locations are the current hard-coded ones: product `agents/`,
`prompts/`, `orchestrator/settings.yaml`; `/data/dagster`, `/data/outputs`, `/data/workspaces`,
`/data/credentials`, `/data/dagster/agent-logs`.

## §2 Plan operations (FR-018/FR-019/FR-021)

| Kind | Operation |
|---|---|
| move | `agents/`→`$CONFIG/agents/`, `prompts/`→`$CONFIG/prompts/` |
| move (if present) | `orchestrator/settings.yaml`→`$CONFIG/settings.yaml` |
| move | each recognized `/data/<x>`→`$DATA/<x>` (outputs, workspaces, credentials, …) |
| move | `/data/dagster/agent-logs`→`$DATA/runs` |
| symlink | `/data/dagster/agent-logs -> $DATA/runs` (migrated history only, FR-021) |
| rewrite | agent-YAML `output_dir`/`workspace`/`env_file` beginning with an old root → new root (FR-019) |
| product-repo delete | remove `agents/`, `prompts/` from the checkout; add `/config/` to `.gitignore` |
| leave + record | unrecognized old-root dirs (e.g. `/data/logs`), the PIPES dir, Dagster storage/DB |

## §3 Behavioural requirements

- **R-MIG-1 (FR-020, US1-1)**: without `--apply`, print the full plan and change **nothing** on
  disk (verifiable: byte-for-byte-unchanged tree after a dry run).
- **R-MIG-2 (FR-020, edge "partial prior migration")**: if **any** destination already has
  content, refuse to run (with or without `--apply`) and name the blocking destination; make no
  changes.
- **R-MIG-3 (FR-019)**: only values **beginning with an old root** are rewritten; already-migrated
  or unrelated values are left as-is. Rewrite preserves YAML structure/comments as far as the
  writer allows (reuse the UI's atomic-write style where practical).
- **R-MIG-4 (FR-021)**: the symlink is created only if moving `agent-logs` would otherwise break a
  historical transcript link, and is recorded in the printed plan. New runs never depend on it.
- **R-MIG-5 (SC-001/SC-002)**: after `--apply` + restart, all agents/prompts/schedules/past
  runs/outputs are present and functional; the product repo's git status shows only the deletions
  of `agents/`/`prompts/` and the new `.gitignore` entry — nothing else.
- **R-MIG-6 (Clarification C)**: `/data/logs` and any other unrecognized dir are neither moved nor
  deleted, and the plan records them as left untouched.

## §4 Tests

- Unit (planner): synthesize an old-layout fixture tree in a temp dir; assert the computed plan
  lists exactly the expected moves/rewrites/symlink/left-untouched entries (R-MIG-1/3/4/6).
- Unit (clobber): pre-populate one destination → assert refusal names it and nothing changes
  (R-MIG-2).
- Unit (rewrite): agent YAML with old-root and already-new-root and default paths → assert only
  old-root values change (R-MIG-3).
- Integration (quickstart, manual on a box copy): dry-run matches contents; `--apply` + restart →
  R-MIG-5 (covered by quickstart, not CI).
