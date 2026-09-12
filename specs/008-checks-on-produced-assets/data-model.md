# Phase 1 Data Model: Checks on Produced Assets

There is no database: `agents/*.yaml` plus `ui/schema.py` is the data model (spec 001). This feature
adds one nested list under the existing `produces:` block and two runtime records derived from it.

---

## Entity: Check (declared, in `agents/<name>.yaml` under `produces.checks`)

A named, generic pass/fail command. agentbox attaches no meaning to what the command does.

| Field | Type | Required | Default | Rules |
|-------|------|----------|---------|-------|
| `name` | string | **yes** | — | Unique within the agent. Kebab-case, `^[a-z0-9]+(-[a-z0-9]+)*$` (becomes the asset-check name). |
| `command` | string | **yes** | — | Shell command line, run as `sh -c "<command>"`. Non-empty. |
| `image` | string | no | producing agent's harness image (R6) | Any resolvable Docker image ref. |
| `blocking` | bool | no | `true` | `true` → `AssetCheckSpec(blocking=True)` + `ERROR` severity; `false` → `blocking=False` + `WARN`. |
| `timeout_seconds` | int | no | (per check; suggested default 300) | `1..86400`. Independent per check (FR-017). |
| `network` | enum | no | *none* (no network) | One of `agentnet-isolated`, `agentnet`, `bridge` (FR-016). Omitted ⇒ `--network none`. |

**Placement rule (FR-010)**: `checks` may appear **only** under a `produces:` block that names a
valid `asset`. `checks` on an agent with no `produces.asset` is rejected at load (orchestrator) and
at save (UI), the message naming the file/field.

**Uniqueness rule (edge case)**: two checks sharing a `name` in one agent are rejected (asset-check
names must be unique on an asset).

**Example** (`produces` block):

```yaml
produces:
  asset: repo-review/agentbox
  partition: none
  checks:
    - name: has-output
      command: test -n "$(ls /output)"          # blocking (default), harness image, no network
    - name: advisory-wordcount
      command: 'test "$(cat /output/*.md | wc -w)" -gt 50'
      blocking: false                            # red-but-advisory
    - name: schema-lint
      command: python3 -c "import json,sys; json.load(open('/report.json'))"
      image: agentbox/agent-python:latest
      timeout_seconds: 30
      network: agentnet                          # opt-in network
```

## Entity: Check result (runtime → Dagster asset check)

The outcome of running one check, surfaced as a Dagster `AssetCheckResult` on the produced asset.

| Attribute | Source | Notes |
|-----------|--------|-------|
| `check_name` | `Check.name` | Names the asset check on the asset. |
| `passed` | check container exit code | `exit == 0` ⇒ `True`; else `False`. |
| `severity` | `Check.blocking` | `blocking` ⇒ `AssetCheckSeverity.ERROR`; else `WARN`. |
| `metadata.output` | combined stdout/stderr | Last **4 KB**, tail-truncated (FR-007/SC-006). |
| `metadata.exit_code` | check container | Integer exit status. |
| `metadata.timed_out` | timeout kill | `true` when the check exceeded its `timeout_seconds` (FR-008). |
| `metadata.blocking` | `Check.blocking` | Recorded for legibility. |
| `metadata.partition` | run partition key | Present when the producing run is partitioned (FR-014/R10). |
| `metadata.image` | resolved image | The image the check ran in (or the resolution error on FR-015). |

**Blocking spec**: declared via `AssetCheckSpec(name=Check.name, asset=<key>,
blocking=Check.blocking)`. A failing blocking check fails the run (materialization still recorded);
a failing non-blocking check does not (R3).

## Entity: Check container (ephemeral)

The fresh, short-lived container one check runs in. Distinct from the producing agent's container.

| Aspect | Value |
|--------|-------|
| Name | `check-<agent>-<check-name>-<runid[:8]>`, launched `--rm` |
| Command | `sh -c "<Check.command>"` |
| Image | `Check.image` or the harness default (R6) |
| Network | `Check.network` or `none` (R9) |
| Mounts | `-v <output_dir>:/output:ro`, `-v <workspace>:/workspace:ro` (only if the agent has one), `-v <report file>:/report.json:ro` (R5) |
| Env / creds | none |
| Timeout | `Check.timeout_seconds`; on expiry `docker kill` + reported failed with `timed_out` (R8) |

## Schema evolution

`SCHEMA_VERSION` 4 → 5. `migrate_4_to_5` is the **identity** function (checks are additive; a
schema-4 file simply has no `checks`). Files re-stamp to 5 only when next saved from the UI.

## Relationships & invariants

- A Check belongs to exactly one asset agent's `produces.checks`; it has no meaning without an asset
  (FR-010) and never applies to a job-only agent.
- Checks run **after** the producing container and **always** run, independent of the producer's
  `status` (R2/R4). They run **sequentially in declared order**, each bounded by its own timeout,
  and every declared check runs and reports (FR-017 — a failing blocking check does not
  short-circuit the rest).
- A check can only **read** `/output` and `/workspace`; it can never modify a produced file
  (Constitution V, US3).
- An asset agent with **no** `checks` is byte-for-byte unchanged from before this feature (FR-013).
