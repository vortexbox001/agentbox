# Phase 0 Research: File Layout Overhaul — Three Roots

All Technical Context unknowns are resolved below. The spec's Clarifications session
(2026-09-14) already settled the three questions that would otherwise be NEEDS
CLARIFICATION (PIPES location, generated-LiteLLM location, `/data/logs` handling); those
are restated here as confirmed decisions with rationale grounded in the current code.

## R1 — Root env-var names and defaults

**Decision**: Three env vars, each with a documented default:
- `AGENTBOX_CONFIG` — instance configuration root. Default: `<product-checkout>/config`
  (resolved against the repo, so a bare clone works with zero env).
- `AGENTBOX_DATA` — instance state root. Default: `/data/agentbox`.
- `DAGSTER_HOME` — Dagster storage root. Default: `/data/dagster` (**unchanged** — Dagster's
  run DB, `storage/`, `history/`, `compute_logs/` stay put; only `agent-logs/` moves out).

**Rationale**: FR-001 mandates exactly three env vars with defaults. Keeping `DAGSTER_HOME`
at its current value (per the Assumptions section) means the migration never touches Dagster's
own run history/DB — the risky part — and only relocates the `agent-logs/` subtree. `DAGSTER_HOME`
is already the env var Dagster itself reads and is already set in `docker-compose.yml`, so we
reuse it rather than inventing a fourth name.

**Alternatives considered**: A single `AGENTBOX_ROOT` with config/data/dagster as subdirs —
rejected because the whole point (spec Overview) is that the three kinds are backed up and
redeployed independently, so they must be independently relocatable (US3).

## R2 — Single resolution point per process

**Decision**: Two resolution modules, one per process:
- `orchestrator/paths.py` (NEW) — reads the three env vars once and exposes derived path
  constants/helpers (config agents/prompts globs, `RUNS_ROOT`, `OUTPUTS_ROOT`,
  `WORKSPACES_ROOT`, `CREDENTIALS_ROOT`, `PIPES_ROOT`, default `output_dir`/`workspace`
  builders, and the host-path equivalents for `docker run -v`).
- `ui/config.py` (existing) — extended from its current three ad-hoc dir vars to derive from
  the config/data roots the same way.

Today's hard-coded literals to eliminate: in `orchestrator/factory.py` —
`HOST_REPO`/`CONTAINER_REPO`, `AGENT_LOG_ROOT = "/data/dagster/agent-logs"`,
`PIPES_ROOT = "/data/dagster/pipes"`, `"/data/workspaces/" + name`,
`"/data/credentials/claude/..."`, `"/data/credentials/codex"`, and the `output_dir` uses; in
`ui/config.py` — `AGENTS_DIR`/`PROMPTS_DIR`/`LITELLM_CONFIG` defaults under `/opt/agentbox`.

**Rationale**: FR-002 / SC-009 require every path to derive from one of the three roots with no
hard-coding outside the two resolution points. The orchestrator and UI run in **separate
containers with no shared import** (established pattern — see the deliberately-duplicated
`ASSET_KEY_RE`/`is_valid_cron` twins in `factory.py` and `ui/schema.py`), so one shared module
is impossible; two mirrored resolution points, pinned by a shared-fixture test, is the
in-repo idiom.

**Alternatives considered**: A shared `agentbox_common` package installed into both images —
rejected as heavier than the established duplication idiom and out of scope for a layout change.

## R3 — agent-logs relocation and the compatibility symlink

**Decision**: New runs write per-run records under `$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>.jsonl`
(orchestrator `RUNS_ROOT` replaces `AGENT_LOG_ROOT`). Migration `git mv`-equivalent-moves the
existing `/data/dagster/agent-logs/` subtree to `$AGENTBOX_DATA/runs/`. Because Dagster
materialization metadata records the *absolute transcript path* of past runs, migration leaves a
**symlink** `/data/dagster/agent-logs -> $AGENTBOX_DATA/runs` for the migrated history only
(FR-021), recorded in the printed plan. New runs never write under `$DAGSTER_HOME`.

**Rationale**: The transcript path is stored as metadata on completed materializations; moving
the files without a back-link would 404 the "transcript" link for historical runs. A symlink at
the *old* location is the minimal fix and costs nothing for new runs (which resolve `RUNS_ROOT`
directly). Confirmed against the CLAUDE.local.md debugging doc, which documents the
`/data/dagster/agent-logs/...` path as the transcript location.

**Alternatives considered**: Rewriting stored metadata paths in the Dagster run DB — rejected;
the DB is SQLite in WAL mode and usually locked by running processes ([[dagster-materialization-greens-partition]]
neighbourhood), and rewriting historical metadata is riskier than a read-only symlink.

## R4 — PIPES messages directory stays under $DAGSTER_HOME

**Decision**: `PIPES_ROOT` derives from `$DAGSTER_HOME` (`$DAGSTER_HOME/pipes`), **not** the
state root. Migration leaves it untouched.

**Rationale**: Clarification A (2026-09-14) plus [[pipes-dir-must-be-under-data]]: the PIPES
messages dir is the agent→Dagster transport, resolved by the **host** daemon on `docker run -v`
and read by Dagster, and it must sit under a path bind-mounted host==container. `$DAGSTER_HOME`
is already mounted host==container (`/data/dagster:/data/dagster`); `$AGENTBOX_DATA` will be too,
but the transport is *Dagster's* transient scratch (wiped per run), not backed-up agentbox state,
so it belongs with Dagster storage per FR-010/FR-012. Keeping it there also means the migration
does not have to move a live transport.

## R5 — The instance settings file (does not exist yet)

**Decision**: There is **no `orchestrator/settings.yaml` in the repo today** (verified). The
"instance settings file" (FR-005) is a *new* artifact whose canonical home is
`config/settings.yaml`. The migration (FR-018) moves `orchestrator/settings.yaml` into
`config/` **only if it exists**; on the current box it does not, so the migration records "no
settings file to move" in its plan and the fresh-install path seeds `config/settings.yaml` from
`examples/config/settings.yaml`. Its schema/contents are deliberately minimal here (a reserved,
mostly-empty file); richer settings are owned by later briefs.

**Rationale**: Avoids a NEEDS CLARIFICATION by treating the move as idempotent/conditional,
consistent with FR-020's "refuse if destination has content" and the general
partial-migration handling. Nothing in the current stack reads a settings file, so introducing
an empty one is non-breaking.

## R6 — LiteLLM template/overlay split and the generator

**Decision**:
- Rename product `litellm/config.yaml` → `litellm/config.template.yaml`: keep the **alias tiers**
  features depend on (`cheap`, `smart`, `opus`, `kimi`, `kimi-k3`) as named tiers, but express
  each tier's concrete `model`/`api_base`/pricing as overlay-fillable.
- Instance **overlay** (`config/litellm.overlay.yaml`, seeded from `examples/`) supplies
  providers, `api_key` **env-var names**, `api_base`, alias→model bindings, and any pricing.
- `litellm/generate.py` (NEW) deep-merges template + overlay → `config/litellm.rendered.yaml`
  (the file LiteLLM's container mounts and loads, FR-014). It runs **on demand** (CLI) and **at
  stack start** (a compose init step / entrypoint before LiteLLM boots, FR-016).
- Missing-key check: for every `api_key: os.environ/<NAME>` the merged config references, the
  generator asserts `<NAME>` is present in the environment; if not, it **fails at generation
  time naming the missing key** and does not emit a config (FR-017). It never expands the value —
  the rendered file keeps the `os.environ/<NAME>` reference (Constitution III).

**Rationale**: FR-006/FR-014/FR-016/FR-017 and US6. Splitting keeps the product upgradeable
(tier names are the contract features depend on) while each box binds its own providers.
Failing at render turns a silent first-request outage into an obvious setup error. Deep-merge
(not replace) lets the overlay add providers/pricing without restating the whole tier list.
The Kimi pricing note in the current `config.yaml` (must be declared or `cost_usd=None`)
becomes overlay data, since providers are instance-owned.

**Alternatives considered**: Have LiteLLM read template + overlay directly — rejected; LiteLLM
loads a single config file, and the env-presence pre-check has to happen *before* LiteLLM boots.

## R7 — Templates move to examples; picker source changes

**Decision**: Move `agents/_template-*.yaml` → `examples/config/agents/` and the picker
(`ui/main.py` create form, `?from=<template>`) reads templates from the **examples tree**, not
from the instance agents dir (FR-008). Add an `EXAMPLES_DIR`/`TEMPLATES_DIR` resolution (product
tree, read-only) to `ui/config.py`. The `is_template = stem.startswith("_")` convention in
`agents_store.py`/`automation_store.py` no longer matches instance agents (none start with `_`
after the move); the template-listing code sources from the examples dir instead.

**Rationale**: FR-008 + FR-015. Templates are product-owned samples, so they belong with the
examples the fresh install copies, not inside the instance's live agents directory (where they'd
otherwise appear as fake agents and get copied into every operator's config repo).

**Alternatives considered**: Keep templates in `config/agents/` and filter by prefix — rejected;
that re-mixes product samples into instance config, defeating the separation.

## R8 — Schema: path validation, version bump, output_dir default

**Decision**:
- Bump `SCHEMA_VERSION` 5 → 6; add `migrate_5_to_6` (identity — no field shape changes) and a
  migrations-list entry, and record the root change in the migration docstring (FR-026).
- Add path validation to `ui/schema.validate`: reject `output_dir`/`workspace`/`env_file`
  that (a) fall under the product tree, or (b) fall outside the data root — **unless** the value
  is the documented default. Rejection message **names the field and states the rule**
  (FR-025, US5, SC-006).
- Make `output_dir` **optional with a documented default** (`$AGENTBOX_DATA/outputs/<name>`) —
  today it is `required=True`. `workspace` already defaults to `/data/workspaces/<name>` (→
  `$AGENTBOX_DATA/workspaces/<name>`). An omitted path passes validation without naming a path
  (spec edge case "documented-default paths").
- Validation must know the roots. Since `ui/config.py` resolves them, `schema.validate`
  reads the roots from config (or takes them as params, matching its existing
  `prompt_exists` injection style) — keeping the single-resolution-point rule.

**Rationale**: FR-025/FR-026 and the "documented-default paths" / "env vars unset" edge cases.
Duplicated structural backstop already exists in `orchestrator/factory.py:validate_checks`; the
authoring guard is the UI copy. Path validation is an *authoring* guard, so it lives in the UI
schema; the orchestrator continues to trust validated files (no per-run path re-validation added).

**Alternatives considered**: Enforce path rules in the orchestrator at load — rejected as
redundant with the UI authoring guard and against the established "UI validates, orchestrator
trusts" split; the load-time backstop stays limited to the existing structural checks.

## R9 — docker-compose mounts and bootstrap ownership

**Decision**:
- Compose mounts become exactly (FR-023): product tree **read-only**
  (`.:/opt/agentbox:ro` or the specific product subdirs RO), the config root writable for the
  UI (`${AGENTBOX_CONFIG}:...`), the state root (`${AGENTBOX_DATA}:...`), the Dagster home for
  orchestrator+daemon only (`${DAGSTER_HOME}:...`), and the Docker socket. LiteLLM mounts **only**
  `config/litellm.rendered.yaml` (a path under the config root). No mount outside the three roots +
  product + socket.
- `bootstrap.sh` creates the `$AGENTBOX_DATA` subtree (`runs outputs workspaces repo-mirrors
  provenance credentials keys`) owned by the runtime user (`AGENTBOX_UID:AGENTBOX_GID`, default
  1000), with `credentials/` (and `keys/`) `chmod 700` (FR-011/FR-022), plus `$DAGSTER_HOME` and
  the `config/` dir. `/data/logs` (empty, unlisted) is **left untouched** (Clarification C).
- Agent-container internal mount contract unchanged (`/workspace`, `/output`, `/config/prompt.md`);
  only host sources change (FR-024). The orchestrator's host-side path builders (currently
  keyed off `AGENTBOX_HOST_REPO`) extend to the config/data roots' host paths.

**Rationale**: FR-011/FR-022/FR-023/FR-024 and the ownership edge case. The current
`docker-compose.yml` mounts `./agents`, `./prompts`, `./litellm/config.yaml`, `/data/dagster`,
`/data/workspaces`, `/data/outputs`; each maps cleanly onto a root. The `ui` service already runs
as `${AGENTBOX_UID}:${AGENTBOX_GID}` so its writes into the config root stay operator-owned.

## R10 — Migration tool shape

**Decision**: `scripts/migrate-layout.py` (Python 3.12, stdlib + pyyaml). Dry-run by default;
`--apply` performs moves. Refuses to run if **any** destination already has content, naming the
blocking destination (FR-020, partial-migration edge case). Moves: `agents/`→`config/agents/`,
`prompts/`→`config/prompts/`, `orchestrator/settings.yaml`→`config/settings.yaml` (if present),
each old `/data/<x>` dir → `$AGENTBOX_DATA/<x>`, `/data/dagster/agent-logs`→`$AGENTBOX_DATA/runs`
(+ symlink, R3). Rewrites `output_dir`/`workspace`/`env_file` in agent YAMLs that begin with an
old root, mapping to the new root (FR-019). Leaves unrecognized dirs (e.g. `/data/logs`) in place
and records it (FR-018, edge case). Prints the full plan; changes nothing without `--apply`.
Also removes the moved `agents/`/`prompts/` from the product repo (a `git rm`-style deletion,
surfaced as the expected git-status delta, SC-002) and adds `/config/` to `.gitignore`.

**Rationale**: US1 is the P1 that must work first. A print-plan/`--apply` split with a
clobber-refusal is the standard safe-migration shape and matches the acceptance scenarios exactly.
Python (not bash) because it must parse+rewrite YAML values (FR-019) and pyyaml is already present.

**Alternatives considered**: A bash `rsync`/`mv` script — rejected because FR-019's in-YAML path
rewrite needs a YAML parser; mixing bash moves with a Python rewrite step is more fragile than one
Python tool that owns the whole plan.
