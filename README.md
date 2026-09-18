# agentbox

Self-hosted runner for scheduled AI agents, built for a Raspberry Pi (arm64, Debian Bookworm).

[Dagster](https://dagster.io) reads agent definitions from the config root's `agents/*.yaml`
(see [Layout](#layout)) and, on a cron schedule or on demand, launches one short-lived Docker
container per run. Four kinds of agent ("harnesses") are supported:

| Harness | What runs | Image | Talks to |
|---|---|---|---|
| `api` | A ~30-line Python script that sends one prompt and saves the reply | `agentbox/agent-python` | LiteLLM proxy (Haiku / Sonnet via your API key) |
| `claude-code` | The Claude Code CLI in headless mode, with a workspace and tools | `agentbox/agent-claude` | Anthropic directly (your Claude subscription credentials) |
| `pi` | [pi](https://github.com/earendil-works/pi), a minimal coding agent with a full tool loop, in print mode | `agentbox/agent-pi` | LiteLLM proxy (API key) |
| `codex` | OpenAI's [Codex CLI](https://github.com/openai/codex) via `codex exec`, default tools | `agentbox/agent-codex` | OpenAI directly (your ChatGPT login) |

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
                    codex harness ──────────────────────────────────► OpenAI (ChatGPT login)
```

### Networks

| Network | Internet? | Who is on it | Use for |
|---|---|---|---|
| `agentnet-isolated` | No (`internal: true`, no gateway) | LiteLLM only | `api` agents — they can reach LiteLLM and nothing else |
| `agentnet` | Yes | LiteLLM, both Dagster services | `pi` agents. Also the default if an agent omits `network`, so an `api` agent that wants isolation must say `agentnet-isolated` explicitly |
| `bridge` | Yes | Docker default | `claude-code` and `codex` agents, which reach their vendor directly |

The "Who is on it" column lists the always-on services. Each agent container additionally joins its
configured network for the duration of its run.

## Layout

agentbox keeps three **kinds** of file strictly apart, so the product can be updated without
touching your box's config, your config can live in its own git repo, and your state can be backed
up as a unit. Every path any service uses is derived from one of **three roots**, each with an
environment variable and a default:

| Kind | Env var | Default | Access | Holds |
|---|---|---|---|---|
| **Product tree** | *(the checkout path)* | this repo | read-only in every service | code and product-owned catalogs — identical on every box |
| **Instance-configuration root** | `AGENTBOX_CONFIG` | `<checkout>/config` | writable by the UI | this box's agents, prompts, and LiteLLM overlay |
| **Instance-state root** | `AGENTBOX_DATA` | `/data/agentbox` | writable (runtime user) | runs, outputs, workspaces, credentials, keys — backed up as a unit |
| **Dagster-storage root** | `DAGSTER_HOME` | `/data/dagster` | orchestrator + daemon only | Dagster's own run DB, compute logs, and PIPES transport — nothing agentbox-owned |

The three vars are read in exactly two places — `orchestrator/paths.py` and `ui/config.py` — and
every other path is derived from a root; no state or config path is hard-coded elsewhere. Leave all
three unset and the stack comes up on the defaults above; set any of them to relocate that root to
another disk (`docker compose` follows them, and `scripts/bootstrap.sh` creates whatever they name).

### Instance-configuration root (`$AGENTBOX_CONFIG`)

This box's configuration — the only tree the management UI writes to. It is **gitignored in the
product repo** (via `/config/`), so you can `git init` it as its own repository without polluting
this repo's `git status`. A fresh install seeds it by copying `examples/config/` here.

| Subpath | Holds |
|---|---|
| `agents/` | agent definition YAMLs (no `_template-*.yaml` — those are product samples in `examples/`) |
| `prompts/` | prompt markdown referenced by agents |
| `projects/`, `external-assets/` | reserved for their owning features |
| `settings.yaml` | instance settings |
| `litellm.overlay.yaml` | this box's LiteLLM providers, key names, and alias→model bindings |
| `litellm.rendered.yaml` | **generated** config the proxy loads (template + overlay); gitignored within the config repo — see [Models and LiteLLM](#models-and-litellm) |

### Instance-state root (`$AGENTBOX_DATA`)

Everything a run reads or writes. `bootstrap.sh` creates this subtree owned by
`${AGENTBOX_UID}:${AGENTBOX_GID}` (default `1000:1000`), with `credentials/` and `keys/` locked to
owner-only (`chmod 700`).

| Subpath | Holds |
|---|---|
| `runs/<agent>/<YYYY-MM-DD>/<run-id>/` | One directory per run (spec 012), holding `transcript.jsonl` (native container stdout — the full Claude Code event stream, a one-line JSON status for `api`), `events.jsonl` (the harness-agnostic normalized event stream the viewer's Conversation tab renders), `context.json` (the frozen launch snapshot), and `report.json` (the spec-007 run report). Secrets are redacted from all three captured files; env values never touch disk. A pre-012 flat `<run-id>.jsonl` is still read as a transcript-only run |
| `outputs/<agent>/` | Files agents write (mounted as `/output`), named `<YYYY-MM-DD_HH-MM>_<descriptive_name>_<session_id>.md`; the default `output_dir`. Never pruned by retention |
| `workspaces/<agent>/` | Persistent scratch dir for `claude-code`, `pi`, and `codex` agents (mounted as `/workspace`); the default `workspace` |
| `credentials/claude/` | Optional `.claude.json` (CLI settings) and, only without `CLAUDE_CODE_OAUTH_TOKEN`, a copied `.credentials.json` |
| `credentials/codex/` | `CODEX_HOME` for the `codex` harness: `auth.json` from a dedicated ChatGPT login, plus codex config and sessions. Mounted read-write |
| `repo-mirrors/`, `provenance/`, `keys/` | reserved for their owning features (`keys/` is owner-only) |

### Dagster-storage root (`$DAGSTER_HOME`)

Dagster's own `storage/`, `history/` (run DB), and `compute_logs/`, plus the transient `pipes/`
transport wiped per run. It holds **nothing** agentbox-owned — run transcripts live under
`$AGENTBOX_DATA/runs/`. A migrated box keeps a `agent-logs -> $AGENTBOX_DATA/runs` compatibility
symlink here so historical transcript links still resolve.

### Migrating an existing box

`scripts/migrate-layout.py` relocates an old single-root box (`agents/`, `prompts/`, and `/data/*`)
into the three roots. It is **dry-run by default** — it prints the full plan (moves, in-YAML path
rewrites, the compatibility symlink, and what it leaves untouched) and changes nothing; add
`--apply` to perform it. Run it on a copy of the box first. See the fresh-install and migration
walkthroughs in `specs/010-file-layout-overhaul/quickstart.md`.

## Setup

1. **Prepare the host** (installs Docker, creates the three roots, adds you to the `docker` group):
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
   it to bind-mount prompt files into agent containers, so a wrong value breaks every run. To put a
   root on another disk, set `AGENTBOX_CONFIG`, `AGENTBOX_DATA`, or `DAGSTER_HOME` here too (see
   [Layout](#layout)); leave them unset for the defaults.

3. **Seed the config root** (fresh install). A new checkout's config root is empty; copy the
   product samples into it, then edit through the UI or by hand:
   ```bash
   cp -r examples/config config          # or into $AGENTBOX_CONFIG if you relocated it
   ```
   Skip this if you migrated an existing box with `scripts/migrate-layout.py` (see above), which
   populates the config root for you.

4. **Build the agent images.** Compose does not build these; do it once and again after editing
   `images/`:
   The three shell-based harnesses (`agent-claude`, `agent-pi`, `agent-codex`) share
   `agentbox/agent-base` — the single source of truth for the common OS/tool set and the
   `python3`/`dagster-pipes` runtime — so build the base **first**. Every build uses the `images/`
   directory as context (the trailing `.`) so each Dockerfile's `COPY lib/` resolves:
   ```bash
   docker build -f images/agent-base/Dockerfile   -t agentbox/agent-base   images
   docker build -f images/agent-claude/Dockerfile -t agentbox/agent-claude images
   docker build -f images/agent-pi/Dockerfile     -t agentbox/agent-pi     images
   docker build -f images/agent-codex/Dockerfile  -t agentbox/agent-codex  images
   docker build -f images/agent-python/Dockerfile -t agentbox/agent-python images
   ```
   (`agent-python` is standalone — it does not build on the base — so its order does not matter.)

5. **Provide Claude credentials for the `claude-code` harness.** Run `claude setup-token` on any
   machine with a browser, and put the long-lived token it prints into `.env` as
   `CLAUDE_CODE_OAUTH_TOKEN`. The orchestrator forwards it into each agent container by name, so it
   never appears in a command line. Skip this step if you only use `api` agents.

   Without the token, the orchestrator falls back to a copied interactive login: copy
   `~/.claude/.credentials.json` into `$AGENTBOX_DATA/credentials/claude/`. This is fragile. The copy
   holds an access token good for about eight hours, and its refresh token dies as soon as the login
   it was copied from refreshes itself, after which every run fails with a 401 until you copy again.

   Either way, `$AGENTBOX_DATA/credentials/claude/.claude.json` (copied from
   `~/.claude/.claude.json`) is mounted if present. It carries CLI settings and onboarding state,
   not secrets.

6. **Provide Codex credentials for the `codex` harness.** Log in *from inside the agent image* into a
   dedicated directory, so the agents own their login and nothing else ever refreshes its tokens:
   ```bash
   mkdir -p "$AGENTBOX_DATA"/credentials/codex
   docker run -it --rm -v "$AGENTBOX_DATA"/credentials/codex:/creds agentbox/agent-codex login --device-auth
   ```
   Open the link it prints on any device, enter the code, and sign in with the ChatGPT account whose
   plan includes Codex. Verify with `docker run --rm -v "$AGENTBOX_DATA"/credentials/codex:/creds agentbox/agent-codex login status`.
   Codex refreshes the tokens itself during runs and writes them back to that directory, which is
   why it is mounted read-write. Do not copy your interactive `~/.codex/auth.json` there instead:
   the two logins would refresh the same token and invalidate each other, exactly the failure the
   `claude-code` fallback has. Skip this step if you do not use `codex` agents.

7. **Start the stack:**
   ```bash
   docker compose up -d
   ```
   A one-shot `litellm-generate` step renders `$AGENTBOX_CONFIG/litellm.rendered.yaml` from the
   product template plus your overlay before the proxy loads it (see
   [Models and LiteLLM](#models-and-litellm)); a missing provider key fails here, not at first
   request. Open the Dagster UI at `http://<host>:3000`. Each enabled agent appears according to its
   declared nature — an **asset**, a **job** `agent_<name>`, or both — plus a schedule
   `sched_<name>` or an `autocond_<name>` sensor if its `triggers:` block carries a cron
   (see [Automation](#automation)). New triggers start paused — turn them on from the UI, or run a
   job / materialize an asset by hand.

Rebuild the orchestrator image (`docker compose build`) only when `orchestrator/Dockerfile`
changes. The product tree (read-only) and the config root (`agents/`, `prompts/`) are bind-mounted,
so code and config edits need at most a restart.

## Asset, job, or both

An agent's **nature** is explicit and operator-chosen (there is no inference from the file's
shape). Two independent flags on the agent decide what Dagster builds; at least one must be set:

- **asset** — a `produces:` block ⇒ the agent is a tracked Dagster **asset** with a
  materialization history. Materialize it by hand or on its `asset_schedule`.
- **job** — `job: true` ⇒ the agent has a launchable Dagster **job** `agent_<name>`. Launch it by
  hand or on its `job_schedule`.

| Kind | `produces` | `job` | Dagster result |
|---|:---:|:---:|---|
| Asset-only | ✓ | ✗ | An asset; no `agent_<name>` job. |
| Job-only | ✗ | ✓ | A plain op job `agent_<name>`; no asset. |
| Both | ✓ | ✓ | An asset **plus** `agent_<name>` as its *materializing* job — every run (manual, auto-condition, or scheduled) records against the one asset. |

Saving an agent that is neither is rejected: *"the agent must be an asset, a job, or both."*

### Asset checks

An asset agent can declare **checks** on its produced asset — pass/fail probes that run *after*
the producer and surface as Dagster **asset checks** on the asset. Each check runs as its own
`--rm` container, in declared order, with `/output` (and `/workspace`, when the harness has one)
and the run's `/report.json` mounted **read-only** and no network, env, or credentials — a check
observes the output, it can never change it. A check is **green** when its command exits 0, **red**
otherwise, with the last 4 KB of its combined output attached as metadata. Every declared check
runs even if the producer failed or an earlier check failed (no short-circuit).

```yaml
produces:
  asset: repo-review/agentbox
  checks:
    - name: has-output                       # required, kebab-case, unique within the agent
      command: test -n "$(ls /output)"       # required; run as sh -c. Exit 0 passes.
    - name: advisory-lint
      command: 'false'
      blocking: false                        # advisory (WARN); does not gate automation
    - name: slow-scan
      command: ./scan.sh
      timeout_seconds: 120                    # killed + failed after this long (default 300)
      image: agentbox/agent-python:latest     # default: the agent's own harness image
      network: agentnet                        # default: no network
```

| Field | Default | Meaning |
|---|---|---|
| `name` | required | Kebab-case, unique within the agent. Names the asset check. |
| `command` | required | Shell command line run as `sh -c`. Exit 0 passes; anything else fails. |
| `image` | the agent's harness image | Docker image the check runs in. |
| `blocking` | `true` | `true` gates downstream automation on failure (severity ERROR); `false` is advisory (WARN). |
| `timeout_seconds` | `300` | Killed and failed after this many seconds (1 to 86400). |
| `network` | none | Docker network for the check: `agentnet-isolated`, `agentnet`, or `bridge`. |

A **blocking** check that fails marks the run failed while still recording the materialization, so
downstream automation is gated but the asset still counts as materialized; a **non-blocking** check
is advisory only. Checks require an asset — a `checks:` list without a `produces.asset` is rejected
at load (and hidden in the UI for job-only agents).

## Automation

*When* an agent runs lives **on the agent**, in its own `triggers:` block — two optional
five-field crons, each applying to one kind:

```yaml
# --- Triggers ---
triggers:
  asset_schedule: "20 17 * * *"   # materialize the asset on this cron (asset kind only)
  job_schedule:   "30 2 * * *"    # launch agent_<name> on this cron (job kind only)
```

- **`asset_schedule`** becomes an `AutomationCondition.on_cron` on the asset, toggled by a paused
  `autocond_<name>` sensor. On a `daily`-partitioned asset it targets the current-day partition.
- **`job_schedule`** becomes a Dagster schedule `sched_<name>` on the agent's job (the plain job,
  or the materializing job for a both-kind agent).
- A blank/absent schedule means no trigger of that kind — the agent stays runnable by hand.

Crons run in the box's timezone — the `TZ` set in `.env` (e.g. `America/New_York`), falling back to
UTC if unset — so `7 17 * * *` fires at 17:07 local, the way ordinary cron does. Set `TZ=UTC` to
schedule in UTC. This applies to both job schedules and asset automation conditions.

New triggers start **paused** — turn them on from the management UI's agents list (flip the
schedule/sensor pill in the **Schedules / Sensors** column) or from the Dagster UI. The
`sched_<name>` / `autocond_<name>` names are stable, so Dagster preserves each trigger's on/off
state across a reload.

Edit the cron itself on the agent's own `triggers:` block via the create/edit form; the on/off
state is a live toggle from the agents list (see [The management UI](#the-management-ui)). If you
are upgrading from a version that kept triggers in a standalone `automation/` directory, run the
one-off
`python3 scripts/migrate-automation-to-triggers.py` once: it folds each cron onto the right
agent's `triggers:` block (setting `job: true` for job-mode agents) and removes the directory
(idempotent).

### Event-driven triggers — the asset dependency graph

Beyond schedules, an asset can fire on **events** by declaring an explicit dependency graph. Under
`produces:`, list the upstream asset keys this asset depends on; under `triggers:`, opt into the two
event triggers (both default off, both asset-kind, both behind the same paused `autocond_<name>`
sensor as `asset_schedule`):

```yaml
produces:
  asset: refined/daily
  partition: daily
  depends_on:          # upstream asset keys this asset depends on (explicit graph edges)
    - notes/daily
    - extras/daily
triggers:
  on_upstream: true    # materialize when any declared upstream materializes & passes blocking checks
  on_missing: true     # materialize the current/latest partition when it has never been produced
```

- **`depends_on`** declares real Dagster deps (visible in the asset lineage). There is no folder- or
  change-watching — the graph is only what you declare. Cycles and references to a non-existent asset
  key are **rejected at load**, naming the offending assets/keys; the offending assets (and anything
  that transitively depends on them) are skipped while every unrelated agent still loads. The
  create/edit form also blocks saving a cycle or dangling reference.
- **`on_upstream`** fires the downstream when any declared upstream materializes and passes its
  **blocking** checks (a failed blocking check records an observation, not a materialization, so it
  never fires the downstream). Partitioned upstream→downstream map one-to-one by kind (daily→daily).
  On a Dagster where that mapping is unreliable, set `AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY=1`: a
  daily asset's `on_upstream` condition is then dropped and the restriction is logged at load.
- **`on_missing`** fills the current/latest expected partition (today for daily; the single
  partition when unpartitioned) when it has never been produced. It never backfills history and never
  re-fires once the partition exists.

When a downstream fires, its container is handed **what each upstream produced**. For every declared
upstream it receives an env var `AGENTBOX_UPSTREAM_<KEY>` pointing at a **read-only** JSON file
(mounted at `/upstreams`) listing that upstream's latest matching-partition output paths, spec-007
report metadata, and materialization time — or a `materialized: false` file when there is none. The
`<KEY>` is the asset key upper-snaked (`/` and `-` → `_`, uppercased): `notes/daily` →
`AGENTBOX_UPSTREAM_NOTES_DAILY`, `repo-review/list-commits` →
`AGENTBOX_UPSTREAM_REPO_REVIEW_LIST_COMMITS`.

### GitHub Projects status trigger — board-driven launches

An agent can also launch when an **issue enters a status column** on a GitHub Projects (v2) board.
Under `triggers:`, add an `on_project_status:` block (valid for both asset- and job-kind agents; it
composes with the other triggers rather than replacing them):

```yaml
triggers:
  on_project_status:
    owner: vortexbox001         # board owner (org or user login)   — required
    project: 1                  # the Projects board number         — required (positive integer)
    status: In progress         # the Status option name            — required (matched case-insensitively)
    label: brief                # optional — only issues carrying this label launch
    repo: vortexbox001/agentbox # optional — only issues from this owner/repo launch (case-insensitive)
    interval_seconds: 60        # optional — poll cadence in seconds (default 60, minimum 30)
```

A paused `project_status_<name>` sensor polls the board on `interval_seconds`; turn it on from the
Automation view like any schedule (it starts **stopped**). Moving a matching **issue** into `status`
launches the agent **exactly once per entry** — PRs, drafts, wrong-status, and filtered-out issues
never launch, and issues already in the status at first start are recorded but not launched. Only
**one feature is in flight at a time per agent**: while a launched issue is still in the status,
other eligible issues are **held** (surfaced with the holder's number on the Automation view) and
launch — oldest first — once the active issue leaves the status. A GitHub outage, rate-limit, or an
unresolvable board/status degrades to a skip-with-reason that leaves the cursor untouched (nothing
re-fires). Agents watching the same board share one query per tick.

Each launched run is handed the issue's identity as env values and a read-only body file:

| Env value | Meaning |
|-----------|---------|
| `AGENTBOX_ISSUE_NUMBER` | the issue number |
| `AGENTBOX_ISSUE_REPO` | the full `owner/repo` |
| `AGENTBOX_ISSUE_URL` | the issue URL (linked from the run page) |
| `AGENTBOX_ISSUE_TITLE` | the title, control-stripped and capped at 256 chars |
| `AGENTBOX_FEATURE_KEY` | a stable key `NNN-slug` (see below) |
| `AGENTBOX_ISSUE_BODY_FILE` | `/issue/body.md` — the body, delivered **only** as a read-only file (never on the command line or in an env value) |

The same identity rides on the run as tags — `agentbox/issue_number`, `agentbox/issue_repo`,
`agentbox/issue_url`, `agentbox/project_item_id`, `agentbox/feature_key` (title and body are never
tags) — and a sensor-launched run is **automated**: it counts toward `max_runs_per_hour` and starts
a chain at depth 1.

The **feature key** is a pure function of the issue: the number zero-padded to three digits, then a
slug of the title (lowercased, only `a-z0-9` kept — non-ASCII letters and emoji are dropped, not
transliterated — with other runs collapsed to single hyphens), the whole key capped at 48 characters
with any trailing hyphen stripped. Grammar `^[0-9]{3}(-[a-z0-9]+)*$`; e.g. issue 38 *"UI: update
runs overview page"* → `038-ui-update-runs-overview-page`, and an all-punctuation/emoji title → `038`.

The sensor reads its token **only** from `GITHUB_PROJECT_TOKEN` — a board-read token, isolated to the
daemon process, with **no** fallback to `GITHUB_TOKEN`. It needs board read scope: a classic PAT with
`read:project` + repo read, or a fine-grained token with Projects: read plus Contents/Issues: read.
The token is never forwarded to a container, tagged, logged, or filed. Set it in `.env` (see
`.env.example`). A malformed `on_project_status` block rejects **only that agent** at load, naming
the offending field, while every other agent still loads.

**Run governors.** Two instance-level limits in `settings.yaml` (edited on the Settings page) bound
automated chaining: `max_runs_per_hour` (default 12, a rolling 60-minute window) and
`max_chain_depth` (default 5; every automated run carries a `chain_depth` — a root is 1, each
automated downstream is its upstream's depth + 1). A run that would breach either limit is refused,
logged, and skipped **without** consuming a per-hour slot; **manual runs bypass both**.

## Adding an agent

The quickest path is the **management UI** at `http://<host>:8080` (the `ui` service; see
[The management UI](#the-management-ui)). Click **New agent**, optionally start from a template,
fill in the schema-driven form, and save. The UI writes `<config>/agents/<name>.yaml`, can create the
prompt file for you, and reloads the Dagster workspace so the new job appears without a manual
restart. Saves regenerate the file from the schema with the standard section comments and one
comment per field; any keys the UI does not manage are preserved verbatim in an "unmanaged" block,
so a hand-added key survives an edit.

To do it by hand instead (paths below are under the config root, `$AGENTBOX_CONFIG`):

1. Copy a template from the product samples in `examples/config/agents/`: `_template-api.yaml`,
   `_template-claude-code.yaml`, `_template-pi.yaml`, or `_template-codex.yaml` into your config
   root's `agents/`. `_template-repo-librarian.yaml` is a specialised starting point for a
   `claude-code` agent that clones and reviews a GitHub repo (see the filled-in
   `repo-librarian-agentbox.yaml`). Files with `enabled: false` (including the templates) are
   ignored — and templates now live only in `examples/`, so they never appear as instance agents.
2. Write the prompt in `<config>/prompts/<name>.md`.
3. Leave `output_dir` unset to take the default (`$AGENTBOX_DATA/outputs/<name>`), or set it to
   another path under the data root; `bootstrap.sh` already created the state subtree. (`claude-code`,
   `pi`, and `codex` agents get a default `workspace` under the data root the same way.)
4. Restart Dagster so it re-scans the config root's `agents/`:
   ```bash
   docker compose restart dagster-webserver dagster-daemon
   ```
   Prompt edits do not need a restart. They are read fresh at each launch.

### The management UI

The `ui` service is a FastAPI app that renders the agent list and a schema-driven create/edit form,
served on port 8080. It runs as `${AGENTBOX_UID}:${AGENTBOX_GID}` (see `.env`, default `1000:1000`)
so files it writes into the config root's `agents/` and `prompts/` stay owned by you rather than
root. It bind-mounts the config root read-write (it edits and creates agents and prompts there) and
the rendered LiteLLM config (`litellm.rendered.yaml`) read-only (the source of the model aliases the
form offers). Every field on the form carries the same explanation the YAML comments and this
README's key table come from — they all read `ui/schema.py`. The form flags env values that look like secrets and asks for confirmation before
writing them, and never logs env values.

The UI is built on the **AgentBox design system**, which lives in the repo at
[`ui/design-system/`](ui/design-system/) and is the single source of truth for how the management
UI looks — `ui/design-system/readme.md` is the authoritative guide, and the token stylesheets under
`ui/design-system/tokens/` are the machine-readable source. The design system makes AgentBox a
**sibling of Dagster**: same layout, fonts, and surfaces, only the brand differs. Three rules follow
from it and are enforced by the UI test suite — style only through design-system **tokens**
(`var(--…)`; no literal colours, fonts, or pixel values in `ui/templates/` or `ui/static/`), keep
all app **CSS in stylesheets** (`ui/static/app.css` and the token files — no inline `style=` or
`<style>` blocks in templates; the `ui/design-system/` reference pages are the sole exception), and
build every screen from the shared component **macros** in `ui/templates/components/macros.html`
rather than bespoke markup. A served developer reference of the whole system lives at
[`/design-system`](http://localhost:8080/design-system) (a developer aid, not linked from the app
navigation).

#### The agents list

The home page is a full-bleed, tabbed table of every enabled agent, sorted by name, that answers
four glance questions per agent: what it is (Name, Harness, Model, Kind badges), when it runs
(Schedules / Sensors — a pill per cron with a clock icon for a `job_schedule`, a sensor icon for
an `asset_schedule`, the cron rendered in plain words in the box timezone, and a live on/off
toggle), how it last did (Latest run — a status dot, relative time, and a link into Dagster), and
whether it is healthy (Checks and a Run-history sparkline of the last ten runs).

- **Tabs** — All / Assets / Jobs / Scheduled / Disabled, each with a live count. The active tab is
  reflected in the URL (`?tab=scheduled`) so a view is shareable and survives reload.
- **Toolbar** — a filter box (matches name, harness, model), a *Show disabled* checkbox (remembered
  per browser), and the primary **New agent** button.
- Columns 1–5 render server-side and never depend on Dagster; the Dagster-derived columns (Latest
  run, Checks, Run history) and the toggle states fill after first paint from a single
  `/api/agents/activity` read. If Dagster is unreachable those columns show em-dashes and the
  toggles disable with an explanatory title — the page still renders.
- Flip a schedule/sensor pill to start or stop it in Dagster (`POST /api/schedules/toggle`). The
  toggle disables (with a title) when the agent is disabled, Dagster is down, or the state is
  unknown.

#### The runs overview

`/runs` is a full-bleed, tabbed table of runs that reads the same as the agents overview. It is
built from disk first — so it renders with the orchestrator stopped — then enriched best-effort
from a single batched Dagster read for each render (capped at the most recent 500 runs of the
filtered set; older rows keep their last-known status and a note says so).

- **Truthful status** — each row shows the real Dagster outcome (succeeded / failed / timed out /
  cancelled / queued / in progress). When Dagster is unreachable or has no record for a run, the
  row falls back to the local report status and is marked **last-known**.
- **Tabs** — All / In progress / Succeeded / Failed, each with a count over the whole filtered set
  (an `unknown`-status run counts only under All, so the sub-tabs need not sum to All).
- **Filter** — a ghost **Filter** control reveals a text box (matches agent, model, target, run id)
  plus the retained agent and date-range filters. Tab, filter, and page all live in the URL, so a
  view is shareable and survives reload; changing any of them returns to page 1.
- **Columns** — Run, Status, Agent, Model, Target, Launched by, Checks, Created, Duration, Cost.
  Agent and Model are mono (the agent links to its page); Created reads in the operator's local
  time (`Sep 17, 1:15 PM`) with the full timestamp on hover; Cost shows `—` for an unknown cost
  (distinct from a real `$0`). Target, Launched by, and Checks come from enrichment and show `—`
  when unobtainable.
- **Dagster link** — a right-justified indigo link icon in the Run column opens that run in Dagster
  in a new tab; it is omitted (no dead link) when Dagster is not configured. The run id itself
  links to the AgentBox run page.
- **Pagination** — 30 runs per page, newest first, via the shared **Pagination** design-system
  component; Prev/Next are real `?page=` links that work without JS.

#### Shell, foot, and settings

Every page shares the sidebar shell. The primary nav leads with **Runs**, then a keyline, then
**Agents**; the brand lockup links home (in both the expanded and collapsed rail). **Settings** is
no longer a nav destination — the single Settings entry is the foot button that opens the modal.
Below a keyline the **foot** carries a Dagster connection-status block, a **Hide navigation**
control that collapses the sidebar to 68px (its accessible name flips to *Show navigation* when
collapsed), and the **Settings** button. The collapse choice persists per browser.

**Settings** opens a *User settings* modal (`role="dialog"`) with a Preferences section and a
**Theme** dropdown — Light, Dark, or *Use system setting*. Choosing an option applies immediately
(no reload) and persists across reloads; *Use system setting* follows the OS light/dark flip. There
is no Save button — the choice takes effect on selection, and **Done** or Escape closes the modal.
The modal also links to the **Settings page** for the server-backed Retention and Run-governors
controls (kept as a route, reachable only through this link, not the nav).

#### The indigo Dagster accent

Points where the UI reaches into Dagster — the foot connection-status block, the Latest-run and
Run-history links, and the checked track of a schedule/sensor toggle — are rendered in a dedicated
**indigo** accent (Dagster's colour), distinct from the theme accent used everywhere else, so a
Dagster-backed control reads as such at a glance. Indigo is a theme-independent token defined in
`ui/design-system/tokens/`, AA-legible in both light and dark.

### Agent YAML reference

Keys marked *api*, *claude-code*, *pi*, or *codex* apply only to that harness. Everything else is common.

This table is descriptive. The authoritative per-key wording, valid values, defaults, and harness applicability live in `ui/schema.py` (the same text the management UI shows and writes as YAML comments); if this table and the schema disagree, the schema is correct and this table should be updated to match (Constitution VI).

| Key | Default | Meaning |
|---|---|---|
| `name` | required | Kebab-case id. Becomes job `agent_<name>` (hyphens become underscores). |
| `enabled` | `true` | `false` skips the file entirely. |
| `harness` | required | `api`, `claude-code`, `pi`, or `codex`. |
| `prompt_file` | required | File in `prompts/`. |
| `output_dir` | required | Host path mounted at `/output`. |
| `timeout_seconds` | `900` | The run is killed after this long. |
| `network` | `agentnet` | `agentnet-isolated`, `agentnet`, or `bridge` (see Networks). |
| `memory` | `1g` | Container memory limit (`docker run --memory`). Only enforced if the host kernel has cgroup memory accounting on; `bootstrap.sh` enables it on Raspberry Pi OS (reboot required). |
| `cpus` | `1.5` | Container CPU limit (`docker run --cpus`). |
| `env` | none | Map of environment variables. A value of the form `${VAR}` forwards the named variable from the Dagster process (which loads `.env`) without writing the secret into the command line. Any other value is passed literally. |
| `env_file` | none | Host path to an env file passed via `--env-file`. |
| `model` | `cheap` (api) / `smart` (pi) / CLI default (claude-code) | *api*: a LiteLLM alias from `litellm/config.yaml`. *pi*: a LiteLLM alias, or `provider/model`. *codex*: a codex model id, passed to `codex exec -m`. *claude-code*: passed to `claude --model`, e.g. `sonnet`, `opus`, `haiku`, `fable`, or a full model id; a `[1m]` suffix on a full id (e.g. `claude-opus-4-8[1m]`) selects the 1M-token context variant. |
| `max_tokens` | `1024` | *api*: response token cap. |
| `workspace` | `/data/workspaces/<name>` | *claude-code*, *pi*, *codex*: host path mounted at `/workspace`. |
| `wipe_workspace` | `false` | *claude-code*, *pi*, *codex*: empty the workspace before every run, so each run starts from a clean directory (e.g. a fresh clone). Ignored for `api`, which has no workspace. |
| `effort` | CLI default | *claude-code*: `low`, `medium`, `high`, `xhigh`, or `max`. *pi*: passed as `--thinking` (`off`, `minimal`, `low`, `medium`, `high`, `xhigh`); `max` is accepted too and mapped to the model's highest level by the image entrypoint. *codex*: passed as `model_reasoning_effort`. |
| `fallback_model` | none | *claude-code*: model to use if the primary is overloaded. |
| `permission_mode` | CLI default | *claude-code*: `default`, `acceptEdits`, `auto`, `bypassPermissions`, `dontAsk`, or `plan` (passed to `claude --permission-mode`). |
| `allowed_tools` | unrestricted | *claude-code*: tool allowlist, e.g. `[Read, Write, Bash]`. *pi*: allowlist of `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls`. |
| `disallowed_tools` | none | *claude-code*: tool denylist. Ignored by *pi* (no such flag). |
| `max_turns` | `10` | *claude-code*: cap on agentic turns. *pi* has no equivalent; `timeout_seconds` is its only cap. |
| `mcp_config` | none | *claude-code*: path to an MCP config JSON inside the container. |
| `append_system_prompt` | none | *claude-code*, *pi*: extra text appended to the system prompt. *codex*: appended to the prompt message instead, since `codex exec` has no system-prompt flag. |
| `produces.asset` | none | Asset key this agent materializes, e.g. `repo-review/agentbox`. Kebab segments joined by `/` for grouping. Declaring a `produces:` block makes the agent a Dagster **asset** (with a materialization history). Combine with `job: true` to also get a materializing `agent_<name>` job. |
| `produces.partition` | `none` | Partition set for the asset: `none` (single) or `daily`. A tracking label only — it does not change the run or output. Default `none`. |
| `produces.checks` | none | Optional list of pass/fail **asset checks** on the produced asset (asset kind only). Each check runs after the producer in a fresh, read-only container and surfaces as a Dagster asset check. See **Asset checks** below for the per-check fields. |
| `produces.depends_on` | none | Optional list of upstream asset keys this asset depends on (explicit graph edges). Each is handed to the container as `AGENTBOX_UPSTREAM_<KEY>` (a read-only handoff file). Cycles/dangling refs are rejected at load. See [Event-driven triggers](#event-driven-triggers--the-asset-dependency-graph). |
| `job` | `false` | `true` makes the agent a launchable Dagster job `agent_<name>`. An agent must be an asset (`produces`), a job (`job: true`), or both. |
| `triggers.asset_schedule` | none | Five-field cron (no `@`-macros) that materializes the asset on a schedule (an `on_cron` auto-condition). Applies only when the agent is an asset. |
| `triggers.on_upstream` | `false` | Materialize this asset when any declared `depends_on` upstream materializes and passes its blocking checks. Asset kind only; starts paused behind `autocond_<name>`. |
| `triggers.on_missing` | `false` | Materialize the current/latest partition when it has never been produced (no history backfill). Asset kind only; starts paused behind `autocond_<name>`. |
| `triggers.job_schedule` | none | Five-field cron (no `@`-macros) that launches `agent_<name>` on a schedule (`sched_<name>`). Applies only when the agent has a job. |
| `triggers.on_project_status` | none | Nested block launching the agent when a GitHub Projects issue enters a status: `owner`/`project`/`status` (required), `label`/`repo`/`interval_seconds` (optional, default 60, minimum 30). Builds a paused `project_status_<name>` sensor read via `GITHUB_PROJECT_TOKEN`. Valid for both agent kinds. See [GitHub Projects status trigger](#github-projects-status-trigger--board-driven-launches). |

### Output files

For every run the orchestrator mints a timestamp (`YYYY-MM-DD_HH-MM`, in the `TZ` from `.env`) and a
session id (a UUID, also used as the Claude Code `--session-id`). Every output file is named
`<timestamp>_<descriptive_name>_<session_id>.md`, for example
`2026-09-05_20-15_documentation_review_3f2a9c1e-….md`. Both values are logged in the Dagster run
log and passed into the container as `AGENTBOX_RUN_STAMP` and `AGENTBOX_SESSION_ID`. `TZ` from `.env`
is forwarded too, so `date` inside the container agrees with the stamp.

- `api` agents: the runner writes one file, `<timestamp>_response_<session_id>.md`.
- `codex` agents: the same text is appended to the prompt message rather than the system prompt.
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

The config the proxy loads is **generated**, not hand-edited, from two sources:

- **Template** (product-owned) — `litellm/config.template.yaml` defines only the *alias tiers* that
  agents and the UI depend on: `cheap` (light/default), `smart` (a step up), `opus` (top tier),
  `kimi` and `kimi-k3` (coding/flagship, via a custom OpenAI-compatible endpoint). Identical on every
  box; you should not need to edit it.
- **Overlay** (instance-owned) — `$AGENTBOX_CONFIG/litellm.overlay.yaml` binds each tier to a
  concrete model, `api_base`, `api_key` env-var **name** (never a value), and pricing. This is where
  you choose which model each alias resolves to. Copied from `examples/config/litellm.overlay.yaml`.

`litellm/generate.py` deep-merges the overlay over the template (overlay wins) into
`$AGENTBOX_CONFIG/litellm.rendered.yaml` — the only config the proxy mounts and loads, and the list
the management UI reads. It keeps `os.environ/<KEY>` references unexpanded and, **before writing**,
asserts every referenced key is present in the environment — a missing key fails generation naming
the key, so the proxy never starts against a broken config. It runs automatically as the
`litellm-generate` step on `docker compose up`; run it by hand (`python3 litellm/generate.py`) after
editing the overlay.

The example overlay ships these bindings:

| Alias | Model |
|---|---|
| `cheap` | Claude Haiku 4.5 (`anthropic/claude-haiku-4-5-20251001`) |
| `smart` | Claude Sonnet 5 (`anthropic/claude-sonnet-5`) |
| `opus` | Claude Opus 4.8 (`anthropic/claude-opus-4-8`), top tier |
| `kimi` | Kimi K2.7 Code (`openai/kimi-k2.7-code`), 256k context |
| `kimi-k3` | Kimi K3 (`openai/kimi-k3`), thinking-only, 1M context |

`LITELLM_MASTER_KEY` is both the proxy's admin key and the bearer token every `api` and `pi` agent
presents. The pi image registers the proxy as a provider named `litellm` at startup. `claude-code` agents
bypass LiteLLM entirely.

## Debugging a run

Given a Dagster run id:

- **Compute logs** (stdout/stderr, including the stack trace on failure). This is Dagster's default
  location under `$DAGSTER_HOME`; `orchestrator/dagster.yaml` does not override it:
  ```bash
  cat "$DAGSTER_HOME"/storage/<run-id>/compute_logs/*.err
  ```
- **Full transcript** for `claude-code` runs, one JSON event per line (`system`, `assistant`, `user`,
  final `result`; for `pi` runs the events are pi's own, ending in `agent_end`; for `codex` runs they are
  codex's `thread.*`, `turn.*`, and `item.*` events). Each run is a **directory** under the data
  root's `runs/` (spec 012); the transcript is the `transcript.jsonl` inside it, alongside
  `events.jsonl`, `context.json`, and `report.json` (a migrated box also keeps a
  `$DAGSTER_HOME/agent-logs` symlink pointing at `runs/`):
  ```bash
  # whole transcript
  cat "$AGENTBOX_DATA"/runs/<agent>/<YYYY-MM-DD>/<run-id>/transcript.jsonl
  # just the final event, pretty-printed
  tail -n 1 "$AGENTBOX_DATA"/runs/<agent>/<YYYY-MM-DD>/<run-id>/transcript.jsonl | python3 -m json.tool
  ```
  The Dagster log itself streams every stdout line live and logs a one-line result summary.
- **GraphQL** at `http://<host>:3000/graphql` for status and events, or the run page in the UI
  (`/runs` lists runs from disk; `/runs/<run-id>` opens the run detail page — see Run retention
  below). The detail page (spec 017) presents each run as **five collapsible sections** in the
  order an operator asks the questions — **Summary, Output, Checks, Context, Transcript** (Summary/
  Output/Checks/Transcript open by default, Context collapsed; each section's open/closed state is
  remembered per browser). **Summary** renders the agent's final message as a small safe markdown
  subset; **Output** lists `/output` artifacts and, when there are none, a best-effort **Produced
  elsewhere** list (pull requests, commits, workspace files) mined from the run's own event stream;
  **Checks** surfaces the recorded checks in the Agents-overview mark language (degrading to an
  empty state when Dagster is unreachable); **Context** reuses the context card; **Transcript**
  renders each tool call as a compact **IN/OUT card** (clamped to 3 lines, expand-on-click) and
  keeps search (now also matching tool IN/OUT content) and the Readable/Raw-log toggle in its
  header. The page is presentation and read-path only — it writes nothing to the run record.
- **Run retention.** By default every run is kept forever. The **Settings** page has a Retention
  section (keep forever / prune after N days) persisted to `$AGENTBOX_CONFIG/settings.yaml`; a
  nightly Dagster schedule (`sched_prune_runs`) then removes only `events.jsonl` +
  `transcript.jsonl` from run directories past the horizon. `report.json`, `context.json`, and the
  run's `/output` artifacts are **always kept**, so a pruned run still opens (its Conversation tab
  shows a "conversation pruned" note).
- **Run governors.** The **Settings** page also has a Run governors section (persisted to the same
  `settings.yaml`) that bounds automated trigger chains: `max_runs_per_hour` (default 12, a rolling
  60-minute window) and `max_chain_depth` (default 5). A run that would breach either limit is
  refused, logged, and skipped without consuming a slot; **manual runs bypass both**. See
  [Event-driven triggers](#event-driven-triggers--the-asset-dependency-graph).

## Repository layout

This is the **product tree** — code and product-owned catalogs, identical on every box and mounted
read-only. Your box's agents and prompts are **not** here; they live under the config root (see
[Layout](#layout)). The product tree holds no instance config or state.

```
images/          agent images: agent-python/ (Dockerfile + runner.py), agent-claude/ (Dockerfile),
                 agent-pi/ (Dockerfile + entrypoint.sh), agent-codex/ (Dockerfile), lib/ (shared
                 report/invariants library), tests/
orchestrator/    Dagster code: paths.py (the single path-resolution point — reads the three roots),
                 factory.py (YAML -> job), definitions.py (discovery from the config root),
                 dagster.yaml, workspace.yaml (code location), Dockerfile, tests/
ui/              management UI (FastAPI + Jinja2): main.py (routes), config.py (the UI's path
                 resolution point — mirrors orchestrator/paths.py), schema.py (the field/harness
                 model that drives the form, YAML comments, and this README's key table),
                 agents_store.py / prompts_store.py (read + atomic write, under the config root),
                 dagster.py (workspace reload), secret_scan.py (secret heuristic), templates/,
                 static/, tests/, design-system/ (the AgentBox design system — source of truth in
                 design-system/readme.md; developer reference served at /design-system)
litellm/         LiteLLM alias-tier template (config.template.yaml) + generate.py (renders the
                 template + instance overlay into the config root's litellm.rendered.yaml), tests/
examples/        product samples that seed a new box: examples/config/ mirrors the config-root shape
                 (agents/ with _template-*.yaml, prompts/, projects/, settings.yaml,
                 litellm.overlay.yaml) — copied to the config root on a fresh install
scripts/         bootstrap.sh (idempotent host setup — creates the three roots) and
                 migrate-layout.py (relocate an old single-root box into the three roots)
config/          the default config root ($AGENTBOX_CONFIG); gitignored — your instance config,
                 not part of the product. Seeded from examples/config/
docker-compose.yml
.env.example     every variable the stack reads, incl. the three roots; copy to .env
```
