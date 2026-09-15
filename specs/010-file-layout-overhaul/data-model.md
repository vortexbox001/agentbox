# Phase 1 Data Model: File Layout Overhaul — Three Roots

This feature's "data" is the on-disk layout: roots, their subpaths, and the two derived
artifacts (rendered LiteLLM config, migration plan). There is no database. Entities below map
directly to the spec's Key Entities and Requirements.

## Roots (the three kinds)

| Entity | Env var | Default | Mount / access | Contents |
|---|---|---|---|---|
| **Product tree** | *(the checkout path)* | repo checkout | read-only in all services | code + product-owned catalogs |
| **Instance-configuration root** | `AGENTBOX_CONFIG` | `<product>/config` | writable by UI | this box's config |
| **Instance-state root** | `AGENTBOX_DATA` | `/data/agentbox` | writable (runtime user) | backed-up state |
| **Dagster-storage root** | `DAGSTER_HOME` | `/data/dagster` | orchestrator/daemon only | Dagster's own storage |

**Resolution rule (FR-002, SC-009)**: the three vars are read in exactly two places —
`orchestrator/paths.py` and `ui/config.py`. Every other path is derived from a root. No literal
state/config path appears elsewhere.

**Unset-vars invariant (FR-003)**: with none of the vars set, all three resolve to their
defaults and the stack starts.

## Instance-configuration tree (`$AGENTBOX_CONFIG`)

| Subpath | Holds | Owner brief |
|---|---|---|
| `agents/` | agent definition YAMLs | this feature |
| `prompts/` | prompt markdown files | this feature |
| `projects/` | project definitions | other brief (reserved subpath) |
| `external-assets/` | external-asset registrations | other brief (reserved subpath) |
| `settings.yaml` | instance settings file | this feature (minimal; new — see research R5) |
| `litellm.overlay.yaml` | instance LiteLLM overlay (providers, key names, bindings) | this feature |
| `litellm.rendered.yaml` | **generated** file LiteLLM loads; gitignored in the config repo | this feature |

- Gitignored in the **product** repo via `/config/` in `.gitignore` (FR-006) so a config git
  repo can be checked out here without polluting the product's git status.
- UI reads/writes `agents/` and `prompts/` here; those writes never touch the product tree
  (FR-007).
- No `_template-*.yaml` files live here — templates are product samples in the examples tree
  (FR-008, R7).

## Instance-state tree (`$AGENTBOX_DATA`)

| Subpath | Holds | Notes / access |
|---|---|---|
| `runs/` | per-run records (the old `agent-logs` transcripts) | new runs write here, not under `$DAGSTER_HOME` (FR-010) |
| `outputs/` | run output files (`/output`) | runtime-user owned; default `output_dir` = `outputs/<name>` |
| `workspaces/` | run scratch (`/workspace`) | runtime-user owned; default `workspace` = `workspaces/<name>` |
| `repo-mirrors/` | repo mirrors | other brief (reserved) |
| `provenance/` | provenance records | other brief (reserved) |
| `credentials/` | claude/codex creds | **owner-only (700)** (FR-011) |
| `keys/` | box keys | **owner-only (700)** (FR-011); other brief (reserved) |

- Backed up as a unit (spec Overview). Bootstrap creates the tree with correct ownership
  (FR-022): runtime user for workspaces/outputs; owner-only for credentials/keys.

## Dagster-storage tree (`$DAGSTER_HOME`)

| Subpath | Holds |
|---|---|
| `storage/` `history/` `compute_logs/` | Dagster's own run storage, DB, compute logs |
| `pipes/` | transient PIPES messages dir (`PIPES_ROOT`), wiped per run — stays here (FR-010/FR-012, R4) |

- Contains **only** Dagster's own storage + the transient PIPES transport; everything else
  agentbox-owned lives under the state root (FR-012).
- Migration leaves everything here in place **except** `agent-logs/`, which moves to
  `$AGENTBOX_DATA/runs/` with a back-symlink for migrated history (R3).

## Product-owned catalogs (stay in the product tree, read-only — FR-013)

`images/` (container image defs + `images/lib` invariants library + `images/tests`),
`ui/design-system/` (the design system), the schema (`ui/schema.py`),
`litellm/config.template.yaml` (alias-tier template), and `examples/`.

## Examples tree (`examples/config/` — product-owned samples, FR-015)

Mirrors the config-root shape sufficiently to seed a working box by copying to `$AGENTBOX_CONFIG`:
`agents/` (the moved `_template-*.yaml` starters), `prompts/` (a sample prompt), `projects/` (a
sample project), `settings.yaml` (minimal), `litellm.overlay.yaml` (minimal overlay).

## Derived artifact: LiteLLM alias-tier template + overlay → rendered config

- **Template** (`litellm/config.template.yaml`, product): the alias tiers features depend on
  (`cheap`, `smart`, `opus`, `kimi`, `kimi-k3`).
- **Overlay** (`config/litellm.overlay.yaml`, instance): providers, `api_key` env-var **names**,
  `api_base`, alias→model bindings, pricing.
- **Rendered** (`config/litellm.rendered.yaml`, generated): deep-merge of the two; the only
  LiteLLM config file mounted/loaded. Contains `os.environ/<KEY>` references, never key values.
- **Validation at render (FR-017)**: every referenced `os.environ/<NAME>` must be present in the
  environment, else the generator fails naming the missing `<NAME>`.

## Derived artifact: Migration plan (FR-018/FR-020)

The ordered set of operations the migration would apply, printed in dry-run:

- **Moves**: `agents/`→`config/agents/`, `prompts/`→`config/prompts/`,
  `orchestrator/settings.yaml`→`config/settings.yaml` (if present), `/data/<x>`→`$AGENTBOX_DATA/<x>`
  for each recognized state dir, `/data/dagster/agent-logs`→`$AGENTBOX_DATA/runs`.
- **Symlink**: `/data/dagster/agent-logs -> $AGENTBOX_DATA/runs` (migrated history only, FR-021).
- **YAML rewrites**: `output_dir`/`workspace`/`env_file` values beginning with an old root,
  remapped to the new root (FR-019).
- **Product-repo deletions**: `agents/`, `prompts/` removed from the product checkout; `/config/`
  added to `.gitignore` (SC-002).
- **Left untouched**: unrecognized old-root dirs (e.g. `/data/logs`), the PIPES dir, Dagster's
  own storage/DB — each recorded in the plan.
- **Refusal condition**: any destination already has content → refuse, naming the blocker.

## Agent-definition schema changes (FR-025/FR-026)

- `SCHEMA_VERSION`: 5 → **6**; add `migrate_5_to_6` (identity) + migrations-list entry; docstring
  records the root change.
- `output_dir`: `required=True` → **optional**, documented default `$AGENTBOX_DATA/outputs/<name>`.
- New path-validation rule on `output_dir`/`workspace`/`env_file`:

| Path value | Result |
|---|---|
| under the product tree | **reject** — message names the field, states "must fall under the data root" |
| outside the data root (and not a documented default) | **reject** — message names the field, states the rule |
| under the data root | accept |
| omitted / documented default | accept without naming a path |
