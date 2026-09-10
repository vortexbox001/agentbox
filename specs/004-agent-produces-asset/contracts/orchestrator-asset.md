# Contract: Orchestrator asset representation

How `orchestrator/factory.py` and `orchestrator/definitions.py` turn a `produces` block into a
Dagster asset, and how they reject bad declarations. This is the behavioral contract; tests
assert against it.

---

## 1. Mode selection

```
build for agent cfg:
  if "produces" not in cfg  -> build_job_and_schedule(cfg)   # unchanged; job agent_<name>
  else                      -> build_asset(cfg)              # asset per this contract
```

The op is built once via `make_run_op(cfg)` and used by whichever branch applies. The
`docker run` construction MUST NOT be duplicated between the two (Null Action).

## 2. The run op (shared by both modes)

`make_run_op(cfg)` keeps its name `run_{name_with_underscores}` (FR-010) and its existing body,
with these additions:

1. **Before launch**: snapshot `cfg["output_dir"]` as `{path: (mtime, size)}` (empty dict if the
   directory does not yet exist).
2. **After the container exits and the transcript is written**: snapshot again; compute
   `output_files` = paths that are new or whose mtime changed within the run window.
3. Attach metadata via `context.add_output_metadata({...})` with the fields in
   [data-model.md](../data-model.md#entity-materialization-record). `partition` is included only
   when `context.has_partition_key`.
4. The op declares one nominal output (value `None`). In job-mode nothing consumes it; in
   asset-mode `from_op` binds it to the asset key.

The op MUST NOT read the partition key to alter the command, mounts, `output_dir`, or file names
(FR-008b). It records the partition key in metadata only.

## 3. build_asset(cfg)

```
key         = AssetKey(cfg["produces"]["asset"].split("/"))
partition   = cfg["produces"].get("partition", "none")
partitions_def = DailyPartitionsDefinition(start_date="2026-09-09")  if partition == "daily"
                 else None
the_op      = make_run_op(cfg)                       # SAME op object as job-mode would use
asset_def   = AssetsDefinition.from_op(
                 the_op,
                 keys_by_output_name={"result": key},   # bind the op's single output to the key
                 partitions_def=partitions_def,
              )
return asset_def
```

- `start_date` for the daily partition set is fixed (`2026-09-09`, the feature epoch) so the set
  is bounded and identical across reloads (research R5).
- Materializing any partition (including a past date) launches the identical container (FR-008b).

## 4. Validation (orchestrator load, FR-011/FR-012)

A valid asset key matches:
```
^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$
```
On load, for each enabled agent file:
- `produces` present with no `asset` → reject the file.
- `asset` not matching the regex → reject the file.
- `partition` not in {`none`, `daily`} → reject the file.

A **rejection** logs a message that **names the offending file** and skips only that file; every
other agent still loads (per-file try/except). Example message:
`agents/foo.yaml: invalid produces.asset "Bad Key" — must match <regex>`.

## 5. Duplicate asset keys (FR-019)

After per-file validation, collect asset keys from the enabled, valid, asset-producing agents.
For any key declared by two or more files, reject **all** those files with a message naming them,
and load everything else:
`asset key "repo-review/agentbox" declared by agents/a.yaml, agents/b.yaml — all rejected`.

Rationale: Dagster refuses a `Definitions` containing two assets under one key, so the conflict
must be resolved to a file-naming operator message rather than a hard code-location failure.

## 6. Definitions assembly (`definitions.py`)

```
jobs, schedules, assets = [], [], []
for path in sorted(agent yaml):
    cfg = load; skip if disabled/empty
    try:
        if "produces" in cfg: assets.append(build_asset(cfg))
        else:                 job, sched = build_job_and_schedule(cfg); ...
    except RejectAgent as e:
        log e (names the file); continue
# then apply the duplicate-key rule, dropping conflicting assets with a named message
defs = Definitions(jobs=jobs, schedules=schedules, assets=assets)
```

## 7. Scheduling in asset-mode (documented limitation)

This feature does not wire an asset-mode agent's `schedule` to an automatic materialization
(scheduling changes are deferred to feature 005). Job-mode scheduling is unchanged. An
asset-mode agent with a `schedule` still validates and loads; the schedule simply does not drive
materializations yet.

## 8. Compose requirement

Both `dagster-webserver` and `dagster-daemon` MUST mount the outputs root read-only
(`/data/outputs:/data/outputs:ro`) so the op's snapshot (§2) can read `output_dir`
(research R7). Without it, asset materializations would record empty `output_files`.
