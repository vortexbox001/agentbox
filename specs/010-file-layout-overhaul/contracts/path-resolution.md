# Contract: Path Resolution (the three-root env-var contract)

The internal contract both long-running processes (orchestrator/daemon, UI) honour. Not an HTTP
API — the "callers" are the two resolution modules and every path derived from them.

## §1 Inputs — the three env vars (FR-001)

| Var | Default | Meaning |
|---|---|---|
| `AGENTBOX_CONFIG` | `<product checkout>/config` | instance-configuration root |
| `AGENTBOX_DATA` | `/data/agentbox` | instance-state root |
| `DAGSTER_HOME` | `/data/dagster` | Dagster-storage root (unchanged) |

Plus the existing host-path bridge for Docker-outside-of-Docker launches
(`AGENTBOX_HOST_REPO` and the host equivalents of the config/data roots), because agent
containers' `-v` sources are resolved by the host daemon.

## §2 Resolution points (FR-002, SC-009)

- `orchestrator/paths.py` — reads §1 vars **once** at import; exposes derived constants:
  `CONFIG_ROOT`, `DATA_ROOT`, `DAGSTER_ROOT`, `AGENTS_GLOB`, `PROMPTS_DIR`, `RUNS_ROOT`,
  `OUTPUTS_ROOT`, `WORKSPACES_ROOT`, `CREDENTIALS_ROOT`, `KEYS_ROOT`, `PIPES_ROOT`
  (`= DAGSTER_ROOT/pipes`), and helpers `default_output_dir(name)`, `default_workspace(name)`,
  plus the host-path forms used when composing `docker run -v`.
- `ui/config.py` — reads the same §1 vars; exposes `AGENTS_DIR`, `PROMPTS_DIR` (both under
  `CONFIG_ROOT`), `EXAMPLES_DIR`/`TEMPLATES_DIR` (product tree, read-only), `LITELLM_RENDERED`,
  and the roots for schema path validation.

**MUST**: no literal state/config path exists outside these two modules.

## §3 Behavioural requirements

- **R-PR-1 (FR-003)**: with none of §1 set, all three resolve to their defaults and both
  processes import/start normally.
- **R-PR-2 (FR-004, SC-005)**: with the roots set to non-default paths, every derived path points
  under the configured root; no derived path falls back to a default location.
- **R-PR-3 (FR-010, R4)**: `RUNS_ROOT` derives from `DATA_ROOT`; `PIPES_ROOT` derives from
  `DAGSTER_ROOT`. New runs write records under `RUNS_ROOT`, never under `DAGSTER_ROOT`.
- **R-PR-4 (FR-024)**: agent-container internal mount points (`/workspace`, `/output`,
  `/config/prompt.md`) are unchanged; only the host source of each bind derives from the new roots.

## §4 Tests (both mirrored copies pinned)

- Unit: monkeypatch each var → assert derived constants; assert unset → defaults (R-PR-1);
  assert non-default roots contain no default-path leakage (R-PR-2).
- Unit: `PIPES_ROOT` under `DAGSTER_ROOT`, `RUNS_ROOT` under `DATA_ROOT` (R-PR-3).
- Shared-fixture parity test: any constant duplicated between `orchestrator/paths.py` and
  `ui/config.py` (root names, default subpaths) agrees across the two, matching the existing
  `ASSET_KEY_RE`/`is_valid_cron` parity-test idiom.
