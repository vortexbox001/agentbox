# agentbox

Self-hosted runner for scheduled AI agents, built for a Raspberry Pi (arm64, Debian Bookworm).

[Dagster](https://dagster.io) reads agent definitions from `agents/*.yaml` and, on a cron
schedule or on demand, launches one short-lived Docker container per run. Three kinds of
agent ("harnesses") are supported:

| Harness | What runs | Image | Talks to |
|---|---|---|---|
| `api` | A ~30-line Python script that sends one prompt and saves the reply | `agentbox/agent-python` | LiteLLM proxy (Haiku / Sonnet via your API key) |
| `claude-code` | The Claude Code CLI in headless mode, with a workspace and tools | `agentbox/agent-claude` | Anthropic directly (your Claude subscription credentials) |
| `pi` | [pi](https://github.com/earendil-works/pi), a minimal coding agent with a full tool loop, in print mode | `agentbox/agent-pi` | LiteLLM proxy (API key) |

## Architecture

Three long-running services come up with `docker compose up -d`:

- **litellm** — OpenAI-compatible proxy on port 4000. Maps friendly aliases (`cheap`, `smart`) to
  Anthropic models. Attached to both networks below.
- **dagster-webserver** — UI and GraphQL API, published on `DAGSTER_HOST_PORT` (default 3000).
- **dagster-daemon** — runs the cron schedules and the run queue (max 2 concurrent runs).

Both Dagster services mount the host's Docker socket. `orchestrator/factory.py` turns each agent YAML
into a Dagster job whose single op shells out to `docker run` on the host. Agent containers are
therefore siblings of the compose services, not children, and are removed when they exit.

```
cron / UI click
      │
      ▼
dagster-daemon ──► job agent_<name> ──► docker run --rm agentbox/agent-… ──► /output, /workspace
                                                │
                    api / pi harness ───────────┴──► litellm:4000 ──► Anthropic API
                    claude-code harness ────────────────────────────► Anthropic (subscription)
```

### Networks

| Network | Internet? | Who is on it | Use for |
|---|---|---|---|
| `agentnet-isolated` | No (`internal: true`, no gateway) | LiteLLM only | `api` agents — they can reach LiteLLM and nothing else |
| `agentnet` | Yes | LiteLLM, both Dagster services | `pi` agents. Also the default if an agent omits `network`, so an `api` agent that wants isolation must say `agentnet-isolated` explicitly |
| `bridge` | Yes | Docker default | `claude-code` agents, which must reach Anthropic directly |

The "Who is on it" column lists the always-on services. Each agent container additionally joins its
configured network for the duration of its run.

### Host layout (`/data`)

| Path | Purpose |
|---|---|
| `/data/dagster/` | Dagster state (`DAGSTER_HOME`): run history, compute logs |
| `/data/dagster/agent-logs/<agent>/<date>/<run-id>.jsonl` | Container stdout for every run: the full Claude Code event stream for `claude-code` runs, a one-line JSON status for `api` runs (empty if the runner failed before printing it; see compute logs) |
| `/data/outputs/<agent>/` | Files the agents write (mounted as `/output`), named `<YYYY-MM-DD_HH-MM>_<descriptive_name>_<session_id>.md` |
| `/data/workspaces/<agent>/` | Persistent scratch dir for `claude-code` agents (mounted as `/workspace`) |
| `/data/credentials/claude/` | Optional `.claude.json` (CLI settings) and, only without `CLAUDE_CODE_OAUTH_TOKEN`, a copied `.credentials.json` |

## Setup

1. **Prepare the host** (installs Docker, creates `/data`, adds you to the `docker` group):
   ```bash
   scripts/bootstrap.sh
   ```
   Log out and back in so the group change takes effect.

2. **Configure secrets:**
   ```bash
   cp .env.example .env
   ```
   Fill in the secrets and adjust the paths and ports for your host. In particular set
   `AGENTBOX_HOST_REPO` to the absolute path of this checkout on the host. The orchestrator uses
   it to bind-mount prompt files into agent containers, so a wrong value breaks every run.

3. **Build the agent images.** Compose does not build these; do it once and again after editing
   `images/`:
   ```bash
   docker build -t agentbox/agent-python images/agent-python
   docker build -t agentbox/agent-claude  images/agent-claude
   docker build -t agentbox/agent-pi      images/agent-pi
   ```

4. **Provide Claude credentials for the `claude-code` harness.** Run `claude setup-token` on any
   machine with a browser, and put the long-lived token it prints into `.env` as
   `CLAUDE_CODE_OAUTH_TOKEN`. The orchestrator forwards it into each agent container by name, so it
   never appears in a command line. Skip this step if you only use `api` agents.

   Without the token, the orchestrator falls back to a copied interactive login: copy
   `~/.claude/.credentials.json` into `/data/credentials/claude/`. This is fragile. The copy holds
   an access token good for about eight hours, and its refresh token dies as soon as the login it
   was copied from refreshes itself, after which every run fails with a 401 until you copy again.

   Either way, `/data/credentials/claude/.claude.json` (copied from `~/.claude/.claude.json`) is
   mounted if present. It carries CLI settings and onboarding state, not secrets.

5. **Start the stack:**
   ```bash
   docker compose up -d
   ```
   Open the Dagster UI at `http://<host>:3000`. Each enabled agent appears as a job named
   `agent_<name>`, plus a schedule `sched_<name>` if its YAML sets one. Turn schedules on from the UI
   or run a job by hand.

Rebuild the orchestrator image (`docker compose build`) only when `orchestrator/Dockerfile`
changes. The `orchestrator/`, `agents/`, and `prompts/` directories are bind-mounted, so code and
config edits need at most a restart.

## Adding an agent

1. Copy a template: `agents/_template-api.yaml`, `agents/_template-claude-code.yaml`, or
   `agents/_template-pi.yaml`.
   `agents/_template-repo-librarian.yaml` is a specialised starting point for a `claude-code` agent
   that clones and reviews a GitHub repo (see `agents/repo-librarian-agentbox.yaml` for a filled-in
   copy). Files with `enabled: false` (including the templates) are ignored.
2. Write the prompt in `prompts/<name>.md`.
3. Create the output directory (and workspace, for `claude-code`) under `/data`.
4. Restart Dagster so it re-scans `agents/`:
   ```bash
   docker compose restart dagster-webserver dagster-daemon
   ```
   Prompt edits do not need a restart. They are read fresh at each launch.

### Agent YAML reference

Keys marked *api*, *claude-code*, or *pi* apply only to that harness. Everything else is common.

| Key | Default | Meaning |
|---|---|---|
| `name` | required | Kebab-case id. Becomes job `agent_<name>` (hyphens become underscores). |
| `enabled` | `true` | `false` skips the file entirely. |
| `harness` | required | `api`, `claude-code`, or `pi`. |
| `schedule` | none | Cron expression. Omit or leave empty for manual-only runs. |
| `prompt_file` | required | File in `prompts/`. |
| `output_dir` | required | Host path mounted at `/output`. |
| `timeout_seconds` | `900` | The run is killed after this long. |
| `network` | `agentnet` | `agentnet-isolated`, `agentnet`, or `bridge` (see Networks). |
| `memory` | `1g` | Container memory limit (`docker run --memory`). Only enforced if the host kernel has cgroup memory accounting on; `bootstrap.sh` enables it on Raspberry Pi OS (reboot required). |
| `cpus` | `1.5` | Container CPU limit (`docker run --cpus`). |
| `env` | none | Map of environment variables. A value of the form `${VAR}` forwards the named variable from the Dagster process (which loads `.env`) without writing the secret into the command line. Any other value is passed literally. |
| `env_file` | none | Host path to an env file passed via `--env-file`. |
| `model` | `cheap` (api) / `smart` (pi) / CLI default (claude-code) | *api*: a LiteLLM alias from `litellm/config.yaml`. *pi*: a LiteLLM alias, or `provider/model`. *claude-code*: passed to `claude --model`, e.g. `sonnet`, `opus`, `haiku`, `fable`, or a full model id; a `[1m]` suffix on a full id (e.g. `claude-opus-4-8[1m]`) selects the 1M-token context variant. |
| `max_tokens` | `1024` | *api*: response token cap. |
| `workspace` | `/data/workspaces/<name>` | *claude-code*, *pi*: host path mounted at `/workspace`. |
| `wipe_workspace` | `false` | *claude-code*, *pi*: empty the workspace before every run, so each run starts from a clean directory (e.g. a fresh clone). Ignored for `api`, which has no workspace. |
| `effort` | CLI default | *claude-code*: `low`, `medium`, `high`, `xhigh`, or `max`. *pi*: passed as `--thinking` (`off`, `minimal`, `low`, `medium`, `high`, `xhigh`). |
| `fallback_model` | none | *claude-code*: model to use if the primary is overloaded. |
| `permission_mode` | CLI default | *claude-code*: `default`, `acceptEdits`, `auto`, `bypassPermissions`, `dontAsk`, or `plan` (passed to `claude --permission-mode`). |
| `allowed_tools` | unrestricted | *claude-code*: tool allowlist, e.g. `[Read, Write, Bash]`. *pi*: allowlist of `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls`. |
| `disallowed_tools` | none | *claude-code*: tool denylist. Ignored by *pi* (no such flag). |
| `max_turns` | `10` | *claude-code*: cap on agentic turns. *pi* has no equivalent; `timeout_seconds` is its only cap. |
| `mcp_config` | none | *claude-code*: path to an MCP config JSON inside the container. |
| `append_system_prompt` | none | *claude-code*, *pi*: extra text appended to the system prompt. |

### Output files

For every run the orchestrator mints a timestamp (`YYYY-MM-DD_HH-MM`, in the `TZ` from `.env`) and a
session id (a UUID, also used as the Claude Code `--session-id`). Every output file is named
`<timestamp>_<descriptive_name>_<session_id>.md`, for example
`2026-09-05_20-15_documentation_review_3f2a9c1e-….md`. Both values are logged in the Dagster run
log and passed into the container as `AGENTBOX_RUN_STAMP` and `AGENTBOX_SESSION_ID`. `TZ` from `.env`
is forwarded too, so `date` inside the container agrees with the stamp.

- `api` agents: the runner writes one file, `<timestamp>_response_<session_id>.md`.
- `claude-code` and `pi` agents: the same fixed system-prompt addition tells the agent to write to `/output` using this
  exact pattern, to write each file in one go, to keep drafts and scratch files in `/workspace`, and never
  to read or edit existing files in `/output`. Prompts should refer to "the filename convention from your
  system prompt" rather than spelling out a name.

### Runtime overrides

A job can be launched from the UI with extra environment variables via op config, which are passed
into the container as `-e KEY=VALUE`:

```yaml
ops:
  run_my_agent:
    config:
      env:
        TOPIC: "raspberry pi"
```

## Models and LiteLLM

`litellm/config.yaml` defines the aliases `api` agents can request:

| Alias | Model |
|---|---|
| `cheap` | Claude Haiku 4.5 |
| `smart` | Claude Sonnet 5 |

`LITELLM_MASTER_KEY` is both the proxy's admin key and the bearer token every `api` and `pi` agent
presents. The pi image registers the proxy as a provider named `litellm` at startup. `claude-code` agents
bypass LiteLLM entirely.

## Debugging a run

Given a Dagster run id:

- **Compute logs** (stdout/stderr, including the stack trace on failure). This is Dagster's default
  location under `DAGSTER_HOME`; `orchestrator/dagster.yaml` does not override it:
  ```bash
  cat /data/dagster/storage/<run-id>/compute_logs/*.err
  ```
- **Full transcript** for `claude-code` runs, one JSON event per line (`system`, `assistant`, `user`,
  final `result`; for `pi` runs the events are pi's own, ending in `agent_end`):
  ```bash
  # whole transcript
  cat /data/dagster/agent-logs/<agent>/<YYYY-MM-DD>/<run-id>.jsonl
  # just the final event, pretty-printed
  tail -n 1 /data/dagster/agent-logs/<agent>/<YYYY-MM-DD>/<run-id>.jsonl | python3 -m json.tool
  ```
  The Dagster log itself shows only the final event plus the transcript path.
- **GraphQL** at `http://<host>:3000/graphql` for status and events, or the run page in the UI.

## Repository layout

```
agents/          agent definitions (YAML); _template-*.yaml are starting points
prompts/         prompt files referenced by agents
images/          agent images: agent-python/ (Dockerfile + runner.py), agent-claude/ (Dockerfile),
                 agent-pi/ (Dockerfile + entrypoint.sh)
orchestrator/    Dagster code: factory.py (YAML -> job), definitions.py (discovery), dagster.yaml,
                 workspace.yaml (code location), Dockerfile (orchestrator image)
litellm/         LiteLLM proxy config (model aliases)
scripts/         bootstrap.sh — idempotent host setup
docker-compose.yml
.env.example     every variable the stack reads; copy to .env
```
