# Agentbox → Dagster assets: feature briefs 007–027

Paste each brief into `/speckit.specify` in order. Each stands alone; later ones assume earlier ones are merged.

> Numbering: 009 is the design-system migration; 010 is reserved for a brief to be added; feature briefs continue from 011. Cross-references use these brief numbers.


State these briefs build on (schema 4, after specs 004–006): an agent is an asset (`produces: {asset, partition: none|daily}`), a job (`job: true`), or both; triggers live on the agent in `triggers: {asset_schedule, job_schedule}`; the Automation view edits triggers per agent; asset crons become `on_cron` automation conditions behind a paused-by-default `autocond_<name>` sensor, with a documented fallback to a schedule + materializing job for partitioned assets; `ui/schema.py` is the single source of truth for the YAML format, with a migrations list; outputs land in `<output_dir>` as `<stamp>_<name>_<session_id>.md`; transcripts land in `/data/dagster/agent-logs/<agent>/<date>/<run-id>.jsonl`; `env` values of the form `${NAME}` are forwarded by name; the UI reloads Dagster via GraphQL after saving.

Order: 007 Pipes run reports · 008 checks · 009 design system migration · 010 (reserved) · 011 run transparency · 012 dependencies & event triggers · 013 base-image refactor · 014 parameterized agents · 015 projects · 016 dynamic partitions & external assets · 017 mini-swe-agent harness · 018 escalation ladder · 019 git worktree workspaces · 020 publish results · 021 per-agent runtime tools · 022 management UI catch-up · 023 repository reconciliation · 024 rule library & authoring · 025 provenance receipts · 026 codebase tour & deep review · 027 design fitness rules & ADR gate.

---

## 007 — Structured run reports via Dagster Pipes

**Intent.** Stop scraping the container's stdout to guess what happened. Each run hands Dagster a structured report, recorded as materialization metadata (or run metadata for job-only agents). Failed runs of asset agents are recorded, not thrown away.

**What changes.**
- Container launch moves to Dagster Pipes (Docker). Logs stream to the Dagster run log live rather than after exit.
- Every harness image writes a run report before exiting, in one JSON shape: `status` (`ok` | `failed` | `timeout`), `tokens_in`, `tokens_out`, `cost_usd` (null if unknown), `turns`, `files_written`, `transcript_path`, `error` (string or null), `notes` (free text: the agent's end-of-run note to its future self). Each image's entrypoint or runner produces it from that harness's native events — the four per-harness parsers now in `factory.py` move into the images.
- The factory reads the report through Pipes and attaches every field as materialization metadata alongside the existing fields (output files, transcript, stamp, session id, harness, model, partition). The transcript `.jsonl` is still written as today.
- Asset agents: a non-`ok` status produces a materialization with `status: failed` metadata and marks the run failed; the partition shows red with the report attached rather than showing no materialization.
- Job-only agents: behavior unchanged (raise on non-zero exit), report attached to the run as metadata.
- `timeout_seconds` still kills the container; the report then says `timeout` (written by the orchestrator if the container couldn't).

**What I'd check.**
- Run one agent per harness (api, claude-code, pi, codex). Each materialization shows the full report with real numbers; `cost_usd` is null only for claude-code and codex (subscription).
- Watch a claude-code run in the Dagster run page: tool calls appear while it runs, not after.
- Set `max_turns: 1` on a claude-code asset agent so it can't finish; the partition materializes with `status: failed`, `error` explains, the transcript path is present, the run is marked failed.
- Set `timeout_seconds: 5`; the report shows `timeout` and the container is gone.
- The `notes` field is visible in the Dagster UI without opening the transcript.

**Out of scope.** Acting on the report (checks, escalation). Cost aggregation. Output file naming.

**Null action.** If Pipes' Docker client can't express the current `docker run` flags (networks, tmpfs creds, env passthrough by name), keep the `docker run` launch and implement the Pipes protocol over a mounted messages file; drop no isolation flag to make Pipes fit.

---

## 008 — Checks on produced assets

**Intent.** An agent YAML can declare checks that run after the asset is produced, each a command that passes or fails. Results attach to the asset in Dagster. Checks are generic commands — agentbox doesn't know whether they're tests, linters, or a script that counts files.

**What changes.**
- New optional `checks:` list inside `produces:`. Each check: `name`, `command` (run inside a container), optional `image` (default: the agent's harness image), optional `blocking` (default `true`), optional `timeout_seconds`.
- A check runs in a fresh container with the output dir read-only at `/output`, the workspace (if any) read-only at `/workspace`, and the run report (007) at `/report.json`. Exit 0 = pass.
- Each check becomes a Dagster asset check on the asset. Blocking failures show on the asset and prevent downstream automation (012) from firing; non-blocking ones show but don't block.
- Check stdout/stderr (last 4 KB) attached to the check result as metadata.
- Schema (a Checks card under Job), YAML comments, README updated.

**What I'd check.**
- Add to an asset agent a check `command: test -n "$(ls /output)"` → passes when the agent wrote a file. Add `command: false` with `blocking: false` → shows failed, asset still counts as materialized. Both appear as asset checks with output attached.
- A check exceeding its timeout is reported failed with `timeout` in its metadata.
- A check that writes to `/output` fails with a read-only error.
- An agent without `produces` cannot have `checks`; the UI hides the card and the factory rejects the file naming it.

**Out of scope.** Escalation on failed checks (018). Checks for job-only agents. Built-in check types.

**Null action.** If asset checks can't attach per-partition in this Dagster version, attach them unpartitioned and record the partition key in metadata; note the limitation in the plan.

---

## 009 — Design system migration: Archon → AgentBox (Dagster sibling)

**Intent.** Replace the Archon design system (dark-only, cyan/magenta, Playfair serif, `--ax-*` tokens) with the AgentBox design system delivered in `AgentBox_Design_System.zip`: a Dagster-derived system with light and dark themes, navy/teal/lime brand colours, Inter + Source Code Pro, a 240px collapsible sidebar and no top bar, Lucide outline icons, and a component set matching Dagster's. After this, the management UI looks like a sibling app to Dagster, every page uses the new tokens and components, and the design system lives in the repo where both humans and coding agents can reference it. This is a visual and structural migration only; no feature behaviour changes. It runs before 011 because 011 adds the largest new surface (Runs, Settings) and should be built on the new system, not migrated after.

**Where the artifacts live.**
- `ui/design-system/` — the unzipped bundle replaces the Archon files wholesale (`ARCHON-DESIGN-SYSTEM.md`, `archon-tokens.css`, the three `.dc.html` specimens, `support.js` are deleted). Kept as delivered: `readme.md`, `SKILL.md`, `github.md`, `styles.css`, `tokens/`, `components/`, `guidelines/`, `ui_kits/`, `assets/`, `_ds_manifest.json`, `_ds_bundle.js`, `thumbnail.html`. Dropped: `uploads/` (raw logo sources, duplicated in `assets/`), `.thumbnail`, `_adherence.oxlintrc.json` (React/oxlint rules that do not apply to a Jinja app; their intent is enforced by the tests below). The existing mount stays: `config.DESIGN_SYSTEM_DIR` serves the directory at `/design-system/`, and `/design-system/` now opens `ui_kits/agentbox-app/index.html` as the developer reference.
- `ui/design-system/readme.md` is the single human-readable source of truth for the visual language (voice, colour, type, spacing, layout, components). `tokens/*.css` is the machine-readable one. `components/*.jsx` and `*.prompt.md` are **reference specimens**: the UI is server-rendered Jinja, so each component is re-expressed as a Jinja macro + CSS, and the JSX/`.prompt.md` pair is what an implementer reads to get it right.
- `ui/templates/components/` — new: one macro file per design-system component (`button.html`, `text_input.html`, `select.html`, `checkbox.html`, `toggle.html`, `badge.html`, `status_dot.html`, `alert.html`, `spinner.html`, `tabs.html`, `card.html`, `dialog.html`, `table.html`), each macro's parameters mirroring the corresponding `.d.ts`. Pages compose these; no page defines its own button or card styling.
- `ui/static/app.css` — rewritten on the new tokens only (`--color-*`, `--type-*`, `--space-*`, `--radius-*`, `--shadow-*`, `--transition-*`, `--nav-width*`, `--icon-*`). It `@import`s `/design-system/styles.css` first. Class prefix moves from `ax-` to `ab-` (the bundle's own prefix, e.g. `.ab-label`, `ab-fadeIn`).
- `ui/static/fonts/` — Inter and Source Code Pro self-hosted as woff2 with an `@font-face` file; the Google Fonts `@import` in `tokens/typography.css` is replaced by a local `@import` so the UI renders correctly on a box with no internet. `github.md` gains a note recording the substitution.
- `ui/static/icons.svg` — rebuilt as a Lucide sprite (`<symbol>` per icon, `stroke: currentColor`, `stroke-width: 2`, `fill: none`) vendored from the `lucide-static` package at build time; no CDN reference at runtime.
- `.claude/skills/agentbox-design/SKILL.md` — a copy of the bundle's `SKILL.md` with its "Read the README" line pointed at `ui/design-system/readme.md`, so Claude Code (and any harness that reads `.claude/skills/`) picks the skill up when working on the UI. `AGENTS.md` gains one line: "UI work follows `ui/design-system/readme.md`; use the macros in `ui/templates/components/`."
- `.specify/memory/constitution.md` — a "Design" principle: every screen uses the design-system tokens and component macros; no literal colours, fonts, or pixel values in `app.css` or templates; new components are added to `ui/design-system/` first and to `ui/templates/components/` second.

**What changes.**
- **Theme.** `data-theme` on `<html>` defaults from `prefers-color-scheme` via a two-line inline script before first paint, with a theme toggle (Light / Dark / System) in the sidebar foot next to the Dagster link, persisted in `localStorage`. The DS's `[data-theme="dark"]` scope does the rest. Base `.html` no longer hard-codes `dark`.
- **Shell.** The top bar goes away. The sidebar becomes the DS's 240px / 68px collapsible navigation (`--nav-width`, `--nav-width-collapsed`, `inset -1px` keyline, nav items 32px with 8px radius, `--color-background-blue` active fill, collapse toggle at the bottom, collapse state persisted). The brand block uses `assets/logo.svg` with `wordmark.svg` on the dark nav. Page title, breadcrumb, and page actions move into a page header at the top of the content area (Dagster's `Page.module.css` pattern), 24px content padding, 64px bottom scroll clearance. The Dagster status link, status region, toast region, and modal root keep their behaviour with new styling.
- **Tokens and classes.** Every `--ax-*` reference in `app.css`, templates, and JS is replaced per a mapping recorded in the plan (`--ax-bg-root → --color-background-default`, `--ax-bg-card → --color-background-default` with `--color-border-default` border, `--ax-cyan → --color-accent-teal`, `--ax-text-mid → --color-text-light`, `--ax-space-N → --space-N` re-indexed to the 2px scale, `--ax-type-* → --type-*`, and so on). Playfair Display and every serif use is removed; the "thinking is different" italic-serif treatment is dropped in favour of the DS's mono/body split. Magenta has no equivalent and is retired; its two uses (queued status, template identity) become the DS `queued` (gray) and `scheduled` (lime) badge intents.
- **Components.** Existing bespoke controls are replaced by the macros: the custom dropdown from spec 002 becomes the DS `Select` (native select with custom chevron, per the DS), keeping keyboard behaviour; the toggle, checkbox, inputs, buttons (primary / outlined / ghost / danger, 8px radius, inset-shadow border), badges (running / success / error / warning / queued / scheduled / default / primary), status dots, alerts, spinner, tabs (bottom-border indicator with count badges), cards (border, no shadow), dialog (backdrop blur), and the grid table all come from `ui/templates/components/`. The `ax-grid-form` responsive form grid is kept as `ab-grid-form` on the DS spacing tokens.
- **Copy.** UI text is audited against the DS content rules: sentence case, no emoji, lowercase status text, numeric counts in mono, relative timestamps under a day, page titles of one or two words.
- **Tests.** `test_no_literal_colours_or_fonts` extends to forbid literal `px` values outside `tokens/` and `fonts/`, any `--ax-` token, any `googleapis`/`unpkg`/`cdn` URL in served CSS/HTML, and any `font-family` outside the font file. `test_design_system_docs` is repointed from `ARCHON-DESIGN-SYSTEM.md` to `readme.md` and additionally asserts that every component listed in `_ds_manifest.json` has a macro file in `ui/templates/components/`. `test_ui_consistency` asserts every `<select>`, `<button>`, and `<table>` in rendered pages carries the DS class rather than being bare.
- **Docs.** README's design-system paragraph and file-tree entry describe the new location and the "sibling of Dagster" rule; spec 002's guide-accuracy requirement now applies to `readme.md`.

**What I'd check.**
- Open every existing page (agents list, agent create/edit, automation list, 404) in light and dark: no `--ax-` token resolves (grep the served CSS), no serif font loads, the sidebar collapses to 68px and back, and the page header carries title, breadcrumb, and actions where the top bar used to.
- Put the management UI and the Dagster UI side by side in dark mode: same sidebar width, same font, same gray scale for surfaces and borders, same red/yellow/green for status; only the accent differs (teal vs blurple).
- Pull the network cable (or block egress) and reload: fonts and icons still render, no request leaves the box.
- The agent form: every select, toggle, checkbox, input, and button renders from a macro; the spec 002 dropdown keyboard scenarios (open, arrow, select, Escape) still pass; validation error states still show.
- Toggle theme to System, change the OS theme; the UI follows without reload flash.
- Run the test suite: the extended literal-value tests fail on a deliberately inserted `#fff`, a `12px`, and a `--ax-cyan`, and pass on the migrated tree.
- `/design-system/` serves the reference app; a Claude Code session in the repo lists `agentbox-design` under skills and, asked to add a card, produces markup using the `card` macro.

**Out of scope.** New pages or features (011+ build on this). Replacing Inter/Source Code Pro with Geist. A theme setting in `orchestrator/settings.yaml` (the Settings page arrives in 011; localStorage suffices now). Porting the React `ui_kits` to Jinja beyond what the pages need. Mobile layout.

**Null action.** If self-hosting the fonts under a licence-compatible path is blocked, keep the system-font fallback stack (`-apple-system … sans-serif`, `ui-monospace … monospace`) as the effective rendering, leave the `@font-face` file in place with a comment, and record in the plan that Inter/Source Code Pro load only when the box has internet — never restore the Google Fonts `@import` in the served CSS.

---

## 011 — Run transparency: conversation view and context snapshot

**Intent.** Open any run and see exactly what the agent did and exactly what it was given: a full chat-style history like a Claude Code session in VS Code, and a frozen snapshot of the agent's context at start — prompt, model, tools, instruction files, environment, workspace. Same view for every harness.

**What changes.**
- **Run directory.** Every run (and every escalation attempt, later) writes to `/data/dagster/agent-logs/<agent>/<date>/<run-id>/`: `events.jsonl` (normalized), `transcript.jsonl` (native, as today), `context.json`, `report.json` (007). Materialization/run metadata links to the directory.
- **Normalized events.** One schema for all harnesses: `system`, `user`, `assistant`, `tool_call`, `tool_result`, `final`, `error`; each with `ts`, `turn`, `tokens_in`/`tokens_out` where reported, `cost_usd` where known. `tool_call` carries tool name and arguments; `tool_result` carries the result and, for file edits, a unified diff. Each harness image emits `events.jsonl` from its native stream. Faithful order and content; nothing summarized.
- **Context snapshot** (`context.json`), written at launch: effective prompt text as sent; appended system-prompt text; model, effort, fallback model; harness and version; image digest; tool allow/deny lists, permission mode, MCP servers and the tools each exposed (from the harness init event where available); every instruction file the harness loaded (AGENTS.md, CLAUDE.md, nested) with path and full contents; env var **names** only; mounts with modes; network; memory/cpu caps; working directory; file tree of `/workspace` and `/output` at start (paths and sizes); for asset runs: asset key, partition key, variant, upstream handoff files (012), attempt number. A `completeness` field states what the harness does not disclose (vendor base system prompt for claude-code and codex).
- **Redaction.** `events.jsonl` and `context.json` pass through the existing secret heuristic (`ui/secret_scan.py`, moved to a shared module) before writing. Matches become `[REDACTED:<kind>]`. Env values are never written. Applies to tool results too.
- **Viewer (management UI).** New Runs area: run list (agent, time, status, model, cost, attempts) with filters; run page with tabs — **Conversation** (threaded, collapsible tool calls/results, diffs as diffs, per-turn tokens/cost, search), **Context**, **Report**, **Files**. A **Compare** action diffs two runs' `context.json`. Post-run only.
- **Settings page.** New UI page, one section for now: **Retention** — keep forever (default) or prune run directories older than N days, with `report.json` and `context.json` always kept. Stored in `orchestrator/settings.yaml`; enforced by a nightly prune job the factory registers. Documented in README.

**What I'd check.**
- Run one agent per harness. Each run directory has all four files. The Conversation tab has the same shape for all four. For claude-code, every tool call in the native transcript appears with its result, and a file edit shows as a diff.
- The Context tab for a claude-code run lists tools, MCP servers, model, and the full CLAUDE.md contents; `completeness` says the vendor system prompt is unavailable. For pi, `completeness` says complete.
- Prompt an agent to read a file containing a fake API key; the Conversation tab shows `[REDACTED:api_key]`, and grepping the run directory finds nothing.
- Change an agent's `effort` and rerun; Compare shows exactly that one difference.
- Set retention to 1 day, back-date a run directory, run the prune job; events and transcript are gone, report and context remain, the run page renders Context and Report with a "conversation pruned" note.
- With Dagster stopped, the Runs area still lists and opens runs from disk.

**Out of scope.** Live streaming. Editing from the viewer. Aggregated cost dashboards. Capturing vendor base system prompts.

**Null action.** If a harness cannot produce faithful `tool_result` events, record them with `missing: true` and say so in the view rather than reconstructing.

---

## 012 — Assets depend on assets; event-driven triggers

**Intent.** An agent can declare that its asset depends on other assets and be triggered when they change. Upstream outputs are handed to the container. This replaces "watch a folder" with an explicit graph.

**What changes.**
- `produces.depends_on:` list of asset keys (other agents' assets, or external assets from 016).
- `triggers:` gains two asset-kind keys alongside `asset_schedule`: `on_upstream: true` (materialize when any upstream materializes and passes its blocking checks) and `on_missing: true` (materialize when the partition has never been produced). Both become automation conditions on the asset, behind the same `autocond_<name>` sensor.
- For partitioned assets, upstream/downstream partitions map one-to-one (daily → daily) by default.
- At launch, for each upstream asset the container receives an env var `AGENTBOX_UPSTREAM_<KEY>` (key upper-snaked) pointing at a small read-only JSON file listing that upstream's latest materialization for the matching partition: output file paths, report metadata, materialization time. The prompt can be told to read it.
- Governors in `orchestrator/settings.yaml` (011): `max_runs_per_hour` (default 12), enforced before launching any automated run — a refused run is logged and skipped; every automated run carries a `chain_depth` tag, and a run exceeding `max_chain_depth` (default 5) is refused. Manual runs bypass both. Both editable on the Settings page.
- Schema (Depends-on card; Automation view gains the two new trigger kinds), README updated. `depends_on` cycles are rejected at load naming the assets.

**What I'd check.**
- A produces `notes/daily` (daily). B has `depends_on: [notes/daily]`, `on_upstream: true`. Materialize A's partition for today; B materializes without anyone clicking, and B's container has `AGENTBOX_UPSTREAM_NOTES_DAILY` pointing at a file listing A's output.
- Give A a blocking check that fails; B does not fire. Fix it; B fires.
- Make B depend on itself through C; reload fails naming the cycle.
- Set `max_runs_per_hour: 2`, trigger three automated materializations within an hour; the third is refused, visibly in the daemon log.
- Chain A → B → C → D → E → F; F is refused for exceeding `max_chain_depth: 5`.

**Out of scope.** Fan-in of many partitions to one. Non-identity partition mappings. Sensors on external systems (016).

**Null action.** If `on_upstream` misbehaves on partitioned assets with the daily mapping, restrict it to unpartitioned assets in this release and say so.

---

## 013 — Base image refactor: one shared base, thin harness layers

**Intent.** Extract a single `agent-base` image with the OS, non-root user, git, and the common command-line tools every agent tends to need, and rebuild each harness image as a thin layer on top. Adding a tool for all agents becomes a one-line change in one place; Pi builds get smaller and faster. No agent YAML changes.

**What changes.**
- New `images/agent-base/` (Debian slim + Node 20, since three harnesses need Node): installs `git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, the GitHub CLI (`gh`), `unzip`, and standard build essentials; creates the uid-1000 `node` user the harness images already assume; sets `WORKDIR /workspace`. Tagged `agentbox/agent-base`.
- `agent-claude`, `agent-pi`, `agent-codex` change to `FROM agentbox/agent-base` and drop their duplicated `apt-get`/user/workdir lines, keeping only the harness install (`npm install -g …`), entrypoint, and harness-specific env (`CODEX_HOME`). `agent-python` stays on `python:3.12-slim` (the api runner needs no shell tools) unless the plan finds it benefits.
- README build steps and `scripts/bootstrap.sh` build `agent-base` first, then the harness images. Compose notes updated if they reference builds.
- The common tool list lives in exactly one Dockerfile; each harness image carries a one-line comment pointing at the base.

**What I'd check.**
- Build `agent-base`, then the four harness images; none contains its own `apt-get git curl` line. `docker run --rm agentbox/agent-claude which rg jq gh git` prints paths; same for `agent-pi` and `agent-codex`.
- Run an existing agent of each harness end to end; behavior identical (same report, same output).
- Combined harness image size is smaller (shared layer), per `docker image ls`.
- Add `yq` to `agent-base`, rebuild base and one harness; the tool is present with no change to the harness Dockerfile.

**Out of scope.** Per-agent images. Runtime tool installation (021). Changing which harness images exist. Language toolchains beyond the common set.

**Null action.** If a harness genuinely can't use the shared base, leave that one on its own base and document why, rather than forcing a lowest-common-denominator base that bloats the others.

---

## 014 — Parameterized agents: static partitions, per-partition triggers, variants, templating

**Intent.** One agent file can run against many targets, and can exist in several configurations, without copy-pasting files. Today `agents/` holds ten near-identical `repo-librarian-*` files differing only in model or harness; after this, that is one file.

**What changes.**
- **Static partitions.** `produces.partition` accepts a list: `partition: [agentbox, cogni, findhills]`. The asset gets a static partition set; each key is a separate row with its own history and checks. `AGENTBOX_PARTITION_KEY` is passed to every container launched for a partitioned asset (including daily).
- **Templating.** These fields accept `{{ partition }}`, `{{ variant }}`, and `{{ vars.<name> }}`: the prompt file contents, `append_system_prompt`, `workspace`, `output_dir`, and `env` values. Nothing else is templatable — harness, model, network, mounts, and credentials cannot vary by partition.
- **`vars:` block.** A mapping of default values. Any run may override them: manual runs via run config (next to the existing `env` run config), scheduled runs via a `vars` mapping on the trigger entry. Overrides never change non-templatable fields.
- **Per-partition triggers.** `triggers.asset_schedule` accepts either a cron string (as today: fires for the latest/all partitions per the existing rules) or a list of `{partition, cron, vars?}` entries. Each entry becomes a schedule targeting the asset with that fixed partition key (the existing schedule-plus-materializing-job path), named `sched_<name>__<partition>`, paused by default. `on_upstream`/`on_missing` remain asset-wide.
- **Variants.** New optional top-level `variants:` mapping. Each variant name maps to overrides of any field except `name`, `produces.asset`, `produces.partition`, `produces.depends_on`, and `project`. The factory expands each variant into a sibling definition: asset key `<asset>/<variant>`, job `agent_<name>__<variant>`, sensors and schedules suffixed likewise. Each variant's effective config is validated exactly like a standalone agent (harness rules, required fields). A variant may carry its own `triggers`; absent, it inherits the base's. `{{ variant }}` resolves to the variant name; an un-varianted agent resolves it to `default`.
- **Templates and UI.** Templates gain commented `partition: [...]`, `vars:`, and `variants:` examples. Agent form: Partition field accepts a list; a Vars card under Runs; a Variants card (list of variant names, each expanding to an override editor showing only overridden fields, with an "effective config" read-only view). Automation view shows per-partition schedule rows and per-variant rows. README key table updated; a "Parameterizing agents" section explains partition vs variant.
- **Migration.** A one-off script `scripts/collapse-variants.py` takes a base agent file and a list of sibling files, emits one file with a `variants:` block containing only the differences, and prints what it would delete; it does not delete without `--apply`.

**What I'd check.**
- Collapse the ten `repo-librarian-*` files into `repo-librarian.yaml` with variants `claude-opus`, `claude-fable`, `claude-haiku`, `claude-sonnet`, `codex`, `pi-haiku`, `pi-kimi`, `pi-kimi-k3`, `pi-opus`, `pi-sonnet`. After reload, Dagster shows ten assets under `repo-review/…`, each materializable, each launching the same container it did from its old file (verify by comparing `context.json` from 011 before and after: only `variant` differs).
- Make `repo-librarian` partitioned by `[agentbox, cogni]` with `output_dir: /data/outputs/repo-review/{{ partition }}` and `env: {GITHUB_REPONAME: "{{ partition }}"}`. Materialize `cogni`; the container has `GITHUB_REPONAME=cogni` and writes under `/data/outputs/repo-review/cogni/`.
- Give `asset_schedule` two entries: `agentbox` nightly, `cogni` weekly. Dagster shows two paused schedules with the right names and crons; turning on `agentbox`'s materializes only that partition at its cron.
- Set `vars: {focus: "drift"}`, put `{{ vars.focus }}` in the prompt, launch a manual run with `vars: {focus: "security"}`; `context.json` shows the prompt with "security".
- A variant that overrides `harness: pi` but leaves a claude-code-only field set is rejected naming the variant and the field.
- Put `{{ partition }}` in `network:`; the file is rejected naming the field as non-templatable.

**Out of scope.** Multi-dimensional partitions. Dynamic partitions (016). Variants of variants.

**Null action.** If a schedule cannot target a single static partition of an asset in this Dagster version, emit one materializing job per partition entry and schedule that; name the deviation in the plan.

---

## 015 — Projects

**Intent.** A project groups repos, defaults, and agents. An agent attached to a project can reach the project's repos by alias, inherits its defaults and credentials, and has its assets namespaced under the project. Two projects can't see each other's secrets.

**What changes.**
- New directory `projects/` with one YAML per project:
  ```yaml
  name: cogni
  repos:
    app:   { url: https://github.com/leeclemmer/cogni,       base_ref: main }
    infra: { url: https://github.com/leeclemmer/cogni-infra, base_ref: main }
  credentials_env: COGNI_GITHUB_TOKEN     # host env var forwarded by name to this project's agents as GITHUB_TOKEN
  defaults:                                # any agent fields; agent values win
    network: bridge
    timeout_seconds: 1800
  ```
- Agent YAML gains optional `project: <name>`. With it: the agent's `produces.asset` is namespaced to `<project>/<asset>` and its Dagster asset group is the project; `depends_on` keys without a `/` prefix resolve within the project; `output_dir` defaults to `/data/outputs/<project>/<agent>/`; `workspace` defaults to `/data/workspaces/<project>/<agent>/`; the project's `defaults` apply beneath the agent's own values; `credentials_env` is forwarded as `GITHUB_TOKEN` (name-only passthrough, like `${NAME}` today); `{{ project.repos.<alias>.url }}` and `.base_ref` are available in templated fields (014).
- `produces.partition: repos` gives the asset one static partition per project repo alias; `{{ partition }}` resolves to the alias.
- Harness images, model tiers, LiteLLM config, and networks stay box-level; a project cannot declare them.
- Agents without `project:` behave exactly as today.
- UI: a Projects view (list, form: name, repos table, credentials env, defaults); the agent form gains a Project dropdown, and shows inherited defaults greyed with "from project"; the Assets/Automation views group by project. README gains a Projects section and the key table gains `project`.

**What I'd check.**
- Create `projects/agentbox.yaml` with repo `main` → this repo. Set `project: agentbox` on `repo-librarian`, remove its hard-coded `GITHUB_*` env and `output_dir`. After reload, its asset is `agentbox/repo-review`, group `agentbox`, outputs land in `/data/outputs/agentbox/repo-librarian/`, and the container has `GITHUB_TOKEN` set from `AGENTBOX_GITHUB_TOKEN` (the project's `credentials_env`) with no value visible in `context.json`.
- Create a second project `cogni` with a different `credentials_env`; an agent in `cogni` sees only cogni's token.
- Set `partition: repos` on an agent in a two-repo project; Dagster shows two partitions named by alias, and `{{ project.repos[partition].url }}` resolves in the prompt.
- Two projects each with an asset named `code-map` coexist as `agentbox/code-map` and `cogni/code-map`.
- A `project:` naming a non-existent project rejects the agent file naming it; a project file with a duplicate repo alias is rejected naming the alias.

**Out of scope.** One Dagster code location per project (future brief; asset groups only for now). Project-level harness or model settings. Cross-project credential sharing.

**Null action.** If `{{ project.repos[partition].url }}` indexing is awkward in the chosen template engine, provide `{{ repo.url }}` / `{{ repo.base_ref }}` as shorthands bound to the current partition's repo and document that.

---

## 016 — Dynamic partitions and external assets

**Intent.** Partitions that appear at runtime (one per item in a list an agent produced), and assets agentbox doesn't produce but watches (a git branch, a folder outside `/data`).

**What changes.**
- `produces.partition: dynamic` with `partition_set: <name>`. The asset materializes one partition per key.
- A materialization may register new keys for a set: the run report (007) gains optional `register_partitions: {set: <name>, keys: [...]}`. The factory adds those keys after the run. This is how "A produces a list; B runs once per item" works.
- New file kind `assets/external/*.yaml`: `asset` key, `kind` (`git-ref` | `path`), kind-specific fields (`repo` or a project repo alias, `ref` / `path`, `glob`), `poll_seconds` (default 300), optional `project`. The factory creates an observable external asset with a sensor that records a new observation when the ref moves or the path's newest mtime changes. Downstream `depends_on` + `on_upstream` (012) then fire.
- Schema/UI/README updated; the Automation view lists external assets with last observation.

**What I'd check.**
- A's report registers `["t1","t2","t3"]` for set `items`. B has `partition: dynamic, partition_set: items, depends_on: [A], on_upstream: true`. After A runs, B materializes three times, each container seeing a different `AGENTBOX_PARTITION_KEY`.
- Define an external `git-ref` asset on a project repo's `main`. Push a commit; within the poll interval the asset shows a new observation and a downstream `on_upstream` agent fires.
- Define an external `path` asset on `/data/inbox` with glob `*.md`; drop a file; downstream fires.
- Registering an existing key is a no-op.

**Out of scope.** Removing partition keys. Multi-dimensional partitions. Other external kinds.

**Null action.** If observable external assets can't drive `on_upstream` in this Dagster version, have the sensor request the downstream materialization directly and note the deviation.

---

## 017 — mini-swe-agent harness

**Intent.** A fifth harness: a minimal bash-loop coding agent through LiteLLM with hard step and cost caps — the cheap, metered, looped option the existing harnesses don't cover (api has no loop; pi has no cost cap; claude-code and codex bypass LiteLLM).

**What changes.**
- New image `images/agent-mini/` with mini-swe-agent in local-environment mode (the container is the sandbox). Entrypoint writes the run report (007) and events (011) from mini's trajectory JSON, including `cost_usd` from mini's accounting.
- `harness: mini` in the schema. Applicable keys: `model` (LiteLLM alias), `effort` (mapped to the model's reasoning parameter where supported), `workspace`, `wipe_workspace`, `output_dir`, `env`, plus `step_limit` (default 40) and `cost_limit_usd` (default 0.50). `max_turns` does not apply.
- Model access: `openai/<alias>` against `http://litellm:4000/v1` with `LITELLM_MASTER_KEY` passthrough, as `api` does. Default network `agentnet-isolated`.
- `_template-mini.yaml`; README harness table, key table, image build steps; UI harness rules in `schema.py`.

**What I'd check.**
- Build on the Pi (arm64); run an agent with `model: cheap`, a prompt to create a file in `/output`, `step_limit: 15`. The file appears with the naming convention; the report shows steps, tokens, non-null `cost_usd`; LiteLLM's spend log shows the same calls.
- `cost_limit_usd: 0.01`: the run stops early, `status: failed`, `error` mentions the cost limit, partition red if asset.
- `step_limit: 1`: same, mentioning the step limit.
- The form for a `mini` agent shows Step limit and Cost limit under Limits, hides Max turns and Tools & permissions.

**Out of scope.** Structured editing tools. Repo maps. Escalation (018).

**Null action.** If mini's native tool-calling mode fails against a given LiteLLM alias, fall back to its text-based command parsing for that alias and document which aliases need it.

---

## 018 — Escalation ladder

**Intent.** An asset agent can try a cheap model first and re-run on a stronger one only when its blocking checks fail — inside one materialization, so the attempt history stays together.

**What changes.**
- Optional `escalation:` block inside `produces:`: `ladder: [<model>, ...]` (aliases or harness model ids, in order) and `max_attempts` (default = ladder length, capped at 3). When present, `model` is ignored.
- The materialization runs at ladder[0], runs blocking checks (008), and on failure re-runs at ladder[1] with the failed checks' output appended to the system prompt (or prompt, for codex), up to `max_attempts`. Non-blocking checks don't escalate.
- The run report becomes a list of attempt reports; metadata records `attempts`, final model, per-attempt cost, summed cost. The run directory (011) holds one sub-directory per attempt.
- `wipe_workspace` applies only before the first attempt.
- Each attempt counts as one run for `max_runs_per_hour`.
- Schema/UI (Escalation card under Box)/README updated.

**What I'd check.**
- `ladder: [cheap, smart, opus]` with a blocking check requiring a phrase the prompt asks for. With an easy prompt: one attempt, `cheap`. With a prompt only stronger models handle: 2–3 attempts, in order, summed cost, one attempt directory each.
- An always-failing check: three attempts, final `failed`, all reports present.
- Attempt 1's failed check output is visible in attempt 2's context snapshot.
- `escalation` on an agent without `checks` is rejected with a clear message.

**Out of scope.** Cross-harness escalation. Learned model selection.

**Null action.** If a harness can't accept the appended check output, escalate without it and record `context_passed: false`.

---

## 019 — Git worktree workspaces

**Intent.** An agent's workspace can be a checkout of a project repo on a branch created for the run. Commits stay on that branch; nothing an agent does can reach the base branch.

**What changes.**
- `workspace` accepts a host path (as today) or a block: `repo: <project repo alias>` (or a bare `url` for project-less agents), `branch_prefix` (default `agent/<name>/`), `push` (default `false`). The factory keeps a bare mirror under `/data/repos/<project>/<alias>/`, fetches, creates a worktree at `/data/workspaces/<project>/<agent>/<run-id>` on branch `<branch_prefix><partition-or-stamp>` from the repo's `base_ref`, mounts it at `/workspace`, and removes the worktree after the run, keeping the branch.
- Credentials: the project's `credentials_env` (015), forwarded by name.
- Post-run: uncommitted changes are committed by the orchestrator as `agentbox: end of run <run-id>`; the report gains `git: {branch, head_sha, base_sha, commits, files_changed}`; the branch is pushed only if `push: true`.
- The factory refuses a `branch_prefix` resolving to `base_ref`, `main`, or `master`, and never pushes to `base_ref`. The remote configured inside the mirror is push-restricted to the branch prefix where the hosting supports it.
- Checks (008) run against the worktree at `head_sha`.
- Schema/UI (Directories card gains repo alias, branch prefix, push)/README updated.

**What I'd check.**
- Agent in project `cogni` with `workspace: {repo: app}` and a prompt to add a file. After the run: branch `agent/<name>/<stamp>` exists in the mirror with commits, the report lists `head_sha` and the file, the worktree dir is gone, `main` untouched.
- `push: true` with a token; the branch is on the remote; remote `main` untouched.
- A prompt that tries `git push origin main` fails inside the container.
- Two parallel runs on the same repo get separate worktrees and branches without interference.
- A `partition: repos` agent with `workspace: {repo: "{{ partition }}"}` checks out the right repo per partition.

**Out of scope.** Merging. Conflict resolution. Pull request creation.

**Null action.** If bare-mirror-plus-worktree doesn't work with the harness images' git versions, fall back to a full clone per run and record the cost in the plan.

---

## 020 — Publish results: push branches and open pull requests

**Intent.** After a worktree run (019), take the branch the rest of the way to a reviewable artifact: push it and, optionally, open a pull request whose body is assembled from the run report. This turns "the factory produced a branch" into "the factory produced work you can review and merge," keeping the rule that only you merge.

**What changes.**
- The worktree block (019) gains `pull_request:` with `enabled` (default `false`), `draft` (default `auto` — ready when blocking checks pass, draft when they don't), `title` (templatable), `base` (default the repo's `base_ref`), `labels` (optional), `reviewers` (optional).
- After a run whose branch has commits beyond `base_ref`, the orchestrator pushes the branch (implying `push: true`) and opens a PR via `gh` (from the base image, 013) using the project's `credentials_env` token. The PR body is generated from the run report and run directory: `files_changed` summary, the agent's `notes`, per-attempt models and summed cost (018), a link to the transcript, and the check results table.
- The run report (007) gains `pull_request: {url, number, state}` (null if none); materialization metadata surfaces the PR URL.
- Escalation (018): the PR reflects the final attempt; the body notes attempt count and succeeding model.
- Guardrails: the token and remote branch rules must forbid pushing to or merging `base`; the orchestrator never merges, only opens the PR. A run configured for a PR where the token lacks PR scope fails with a clear message rather than silently skipping.
- Schema/UI (a Pull request card under Directories, gated on the worktree block)/README updated.

**What I'd check.**
- Agent with `workspace: {repo: app, pull_request: {enabled: true}}` and passing checks; after the run a ready PR exists whose body lists changed files, notes, and cost, and the materialization shows the PR URL.
- Same agent with a failing blocking check and `draft: auto`; the PR opens as draft (or not, if configured), body showing the failing check.
- A run producing no commits opens no PR and records `pull_request: null`.
- A token lacking PR permission fails the run naming the missing scope, no partial state.
- After the PR exists, `base` on the remote is unchanged.

**Out of scope.** Merging (always the human). Conflict resolution. Updating an existing PR in place. Non-GitHub hosts.

**Null action.** If `gh` PR creation is unreliable, push the branch and record `pull_request: {state: "push-only"}` with the branch name in metadata so the operator opens the PR by hand; do not fail the whole run when the code push succeeded.

---

## 021 — Per-agent runtime tools via `setup:`

**Intent.** Let a single agent install the few extra tools it needs at container start, without a new image and without bloating the shared base (013). Most agents need nothing beyond the base; the rare one that needs, say, `duckdb` or a specific linter declares it in its YAML and the entrypoint installs it before the harness runs.

**What changes.**
- New optional `setup:` block with two lists: `apt:` (Debian package names) and `pip:` (Python package specs). Before launching the harness, the entrypoint runs `apt-get install -y --no-install-recommends <apt...>` and/or `pip install <pip...>`. Empty/absent means no setup step.
- Runs inside the agent container as part of normal launch; packages exist only for that run. Docs note that a frequently-needed tool should be promoted into `agent-base` (013) rather than installed every run.
- `setup:` is captured in the context snapshot (011) so a run records exactly what was installed.
- Guardrails: `setup` runs no arbitrary shell — only package names for the two managers, validated against a name pattern (no shell metacharacters, no URLs); anything else is rejected naming the field. `apt` needs the install step to run as root then drop to the agent user for the harness (the base entrypoint supports this); if a harness image is non-root only, `apt` is rejected and only `pip --user` is allowed — the plan decides and documents which.
- Network note: `setup:` needs a network reaching the package index (`agentnet` or `bridge`, not `agentnet-isolated`); the factory warns (or fails, per the plan) if `setup:` is set on an isolated-network agent.
- Schema/UI (a Setup card under Job, two tag-style lists)/README updated; templates gain a commented example.

**What I'd check.**
- An agent with `setup: {apt: [duckdb], pip: [pytest]}` on `agentnet`: tools install, the harness uses them, the context snapshot lists them.
- The same agent on `agentnet-isolated`: warning logged (or run fails, per plan) because the index is unreachable.
- `setup: {apt: ["duckdb; rm -rf /"]}` is rejected naming the field before any container launches.
- An agent with no `setup:` launches exactly as today, no extra step, no slowdown.
- A heavy package shows up as run time; docs point to promoting it into `agent-base`.

**Out of scope.** Arbitrary setup scripts. Caching installs across runs. Non-apt/pip managers. Auto-promotion.

**Null action.** If install-as-root-then-drop-privileges can't be made clean in a harness, restrict `setup:` to `pip --user` for that harness and document the limitation rather than running the harness as root.

---

## 022 — Management UI catches up

**Intent.** The management UI shows the asset side of an agent — what it produces, recent materializations with status and cost, check results, triggers, project — so day-to-day operation doesn't need the Dagster UI.

**What changes.**
- Agent list gains columns: project, produces (asset key or —), variants/partitions count, last run (time, status, cost), trigger summary.
- Agent form's Runs column gains a read-only Recent runs card (last 5 materializations/runs: time, status, model, cost, attempts, link to the 011 run page and to Dagster) and a Check results card (last result per check).
- New Assets view: asset, agent, project, partition scheme, upstream, downstream, last materialization, last observation for external assets.
- All read through the existing GraphQL client in `ui/dagster.py` and the run directories from 011; the UI stays read-only for run data and writable only for `agents/`, `prompts/`, `projects/`, `assets/external/`, `orchestrator/settings.yaml`.
- Design-system compliance per spec 002.

**What I'd check.**
- Materialize an asset agent twice (once failing); the Recent runs card shows both with correct status and cost; clicking one opens the run page.
- The Assets view shows the 012 A → B chain and the 016 external asset with its last observation.
- With Dagster stopped, the UI still renders agents, forms, and run history from disk, with Dagster-backed panels showing "Dagster unreachable" rather than an error page.

**Out of scope.** Triggering runs from the UI. Editing check results. Cost reports.

**Null action.** If a panel's GraphQL query can't return in under two seconds on the Pi, render it lazily after page load.

---

## 023 — Repository reconciliation: invariants, drift, human-gated convergence

**Intent.** Declare what state a project's repository should be in, and have agentbox continuously observe drift from that state and dispatch agents to close it — never merging, only proposing. This turns the box from "produce an artifact on a schedule" into a reconciliation controller: invariants are the desired state, a deterministic scan is the observation, agents are the actuators, checks are the proof of convergence, and you are the admission controller. Builds directly on checks (008), handoffs and governors (012), escalation (018), worktrees (019), and pull requests (020).

**What changes.**
- A project (015) gains an optional `invariants:` map (in `projects/<name>.yaml` or an adjacent `projects/<name>.invariants.yaml`). Each invariant has `observe` (a command run in a fresh worktree at `base_ref` that exits 0 when satisfied and, on failure, prints a JSON list of violations on stdout), `describe` (one line, for the UI and PR bodies), `actuator` (the name of an agent in the project), `priority` (`low|normal|high`, default `normal`), optional `escalation` (018 ladder override for the actuator), optional `partition_by_violation` (default `false`). `observe` accepts package-style arguments only — a command name and flags, no shell metacharacters — and runs in a container, never on the host. Observers and agent output checks (008) are one primitive: the same runner, the same result format (exit code plus a JSON violations list on stdout), the same `blocking` semantics; 023 points that primitive at the repository at `base_ref` instead of at an agent's output. The scan asset accepts a `setup:` block (021) so observer toolchains (`pip-audit`, `trivy`, `lychee`, `gitleaks`) can be installed without bloating `agent-base`; the project may instead name an `observer_image`. Each observer receives the previous drift report for its invariant at `AGENTBOX_PREVIOUS_STATE` so ratchet rules (coverage high-water mark, "no dependency more than N versions behind", "no TODO older than N days") can compare against last time; the drift report records an optional numeric `value` alongside `satisfied` so ratchets have history.
- A deterministic, LLM-free asset `<project>/state` is added per project with invariants. It materializes on `triggers.asset_schedule` (project default) or on external git-ref change (016), checks out `base_ref` in a throwaway worktree (019 machinery), runs every `observe`, and records a drift report as materialization metadata: per invariant `satisfied`, `violations`, `observed_sha`, `duration`. The drift report is also written to `/data/outputs/<project>/state/<stamp>.json`.
- A per-project `reconcile_<project>` sensor (paused by default, like the autocond sensors) reads each new drift report. For every unsatisfied invariant it requests a materialization of the actuator's asset, partitioned by invariant name (or by `<invariant>/<violation-id>` when `partition_by_violation` is set), passing the violation list through the existing upstream handoff file mechanism (012) as `AGENTBOX_UPSTREAM_STATE`. Actuators are ordinary worktree agents (019) with `pull_request.enabled: true` (020); the brief adds nothing to what an actuator is.
- The judge is immutable to the judged. Observers, checks, and the test files they invoke are always executed from `base_ref`'s copy, never from the actuator's branch; the scan asset checks out `base_ref` for the observer code and the branch only for the code under observation. Any actuator PR whose diff touches a file matched by the project's `protected_paths` (default: the observer commands' scripts, test directories, CI config, and the invariants file itself) is marked `touches_judge: true` in the run report, opens as draft regardless of `converged`, and is labelled for human review; the sensor never counts such a PR as progress.
- Convergence check: after an actuator run produces a branch, the orchestrator re-runs that invariant's `observe` on the branch before opening the PR and records `converged: true|false` in the run report (007). `converged: true` opens a ready PR whose body begins with the invariant's `describe` and the before/after violation counts; `converged: false` is a failed blocking check that drives escalation (018) and, if the ladder is exhausted, opens a draft PR or none per the actuator's `draft` setting.
- Governors, all in the project block with defaults: `max_open_prs_per_invariant` (default 3 — no new dispatch while that many unmerged actuator PRs exist for the invariant), `max_dispatches_per_scan` (default 5, highest priority first), `regression_freeze` (default `true` — if a scan shows an invariant that was satisfied at the previous scan now unsatisfied and the intervening merged commits came from another invariant's actuator, both invariants are frozen and surfaced), `quarantine_after` (default 3 — an invariant whose actuator PR was merged by the human but whose `observe` still fails on the next scan `quarantine_after` times in a row is disabled and surfaced, on the assumption the observer is wrong before the human is). Frozen and quarantined invariants appear in the drift report with their state and are skipped by the sensor until the operator clears them in the UI.
- Reconciliation queue in the UI (022): one row per unsatisfied invariant showing priority, violation count, open actuator PRs with `converged` state and cost, and freeze/quarantine flags with a clear action. This is the review surface; merging happens on GitHub.
- Schema migration adds the fields; `ui/schema.py` validates that every `actuator` names an agent in the same project that has a worktree block and a pull request block; README gains a "Reconciliation" section stating the principle: reconcile the mechanical, materialize the judgment-based on demand — an invariant whose `observe` needs a model is not an invariant.

**What I'd check.**
- Project with two invariants (`docstrings` via a script, `vuln-deps` via `pip-audit`) and a repo violating both; materializing `<project>/state` records both unsatisfied with violation lists and touches no LLM (LiteLLM spend unchanged, no agent container launched).
- Unpause the sensor; two actuator runs are requested with the violation lists in their handoff files; each opens a PR; the `docstrings` PR is `converged: true` and ready, the `vuln-deps` PR fails `observe` on its branch, escalates once, and lands as draft with `converged: false` in the body.
- With `max_open_prs_per_invariant: 1` and the docstrings PR unmerged, the next scan dispatches nothing for `docstrings` and the queue says why.
- Merge the docstrings PR by hand; the next scan shows it satisfied; the reconciliation queue drops the row.
- Simulate a regression: a merged actuator PR for invariant A causes invariant B to fail on the next scan; both are frozen, neither dispatches, the UI shows the freeze with the offending SHA.
- An `observe` containing shell metacharacters is rejected at YAML validation.
- An actuator that "fixes" a failing `docstrings` invariant by deleting the docstring-check script: the observer, run from `base_ref`'s copy, still fails on the branch; the PR opens as draft with `touches_judge: true` and the review label, and does not count against `max_open_prs_per_invariant` as converged work.
- A `coverage` ratchet invariant: with the previous drift report recording 81%, a branch at 80% fails and one at 82% passes; the new high-water mark is recorded in the next drift report.
- The scan asset with `setup: {pip: [pip-audit]}` runs the observer without `pip-audit` being in `agent-base`, and the tool appears in the scan's context snapshot (011).
- Full cycle with the sensor unpaused for 24 hours against a real repo: no merge to `base_ref` occurred that a human didn't perform, and total spend equals the sum of actuator run reports.

**Out of scope.** LLM-based observers. Auto-merge under any condition. Cross-project invariants. Reusable rule library, per-rule modes, PR outcome tracking, and rule authoring UI (024). Invariants over non-git targets. Learned prioritization. Conflict resolution between concurrent actuator branches.

**Null action.** If per-invariant partitioning of the actuator asset conflicts with an actuator that already uses `partition: repos` (014/015), dispatch the actuator unpartitioned with the invariant name in the handoff file and a `reconcile.invariant` tag on the run; record in the plan that a second partition dimension is the real fix and belongs with multi-dimensional partitions.

---

## 024 — Rule library, per-rule modes, PR outcome tracking, and rule authoring

**Intent.** Turn "a project can declare an invariant" (023) into "an operator manages rules." Universal rules (vulnerable dependencies, secrets, lint, dead code, docstring coverage, stale TODOs, broken doc links) are written once at box level and included by name; rules can be watched before they are allowed to spend money; the system notices when a human keeps refusing a rule's PRs; and rules are edited in the UI rather than by hand.

**What changes.**
- A box-level rule library at `invariants/*.yaml`. Each library rule has the 023 fields plus `params:` with typed defaults (thresholds, allowlists, file globs, day counts), a `cluster` tag (`universal`, `library`, `service`, `cli`, `data`, `infra`, `ml`, `monorepo`), a `setup:` for its toolchain, and a `default_actuator` naming a box-level agent template that projects can accept or override. Library rules are templated with `{{ params.* }}` in the same engine as 014.
- A project's `invariants:` may contain `include:` entries — a library rule name plus `params` overrides and an optional `actuator` override — alongside inline rules. Includes expand at load time into ordinary 023 invariants; the schema validates that every required param is set and every param name exists. The repo ships the universal cluster and one preset per other cluster as starting points, with README guidance that a preset is a menu, not a mandate.
- Per-rule `mode:` with values `off` (defined, not scanned), `observe` (scanned and reported, never dispatched), and `dispatch` (023 behaviour). Default `observe`. A rule moves to `dispatch` only by explicit operator action; the sensor ignores anything else. The scan asset always runs `observe`- and `dispatch`-mode rules so the drift history exists before spending begins.
- PR outcome tracking. The scan asset refreshes the state of every actuator PR opened for the project (`gh pr view` on each recorded URL, using the project token) and records per invariant: `merged`, `closed_unmerged`, `open`, with ages. The run report (007/020) `pull_request.state` is updated in materialization metadata rather than being frozen at creation. A new governor `refusal_threshold` (default 3): when the last N actuator PRs for a rule were all closed unmerged by a human, the rule drops to `observe` mode and is surfaced with "rule refused" — the same treatment as quarantine (023), for the opposite signal: the observer may be right but the fixes are unwanted.
- Rules page in the UI (022) per project: list of rules with cluster, mode, last drift (satisfied / count / ratchet value), open PRs, and merged / refused counts over the last 30 days; add a rule by picking from the library and filling params; edit params, mode, priority, actuator; clear a freeze, quarantine, or refusal; a "what would dispatch now" preview that runs the sensor's selection logic without requesting anything. Saving writes the project YAML and reloads Dagster as elsewhere.
- Cost attribution: LiteLLM spend and flat-rail run counts are tagged with `project` and `invariant` so the Rules page can show spend per rule, and `max_spend_per_rule_per_day` (default unset) can stop a runaway rule.
- Schema migration, README "Rules" section, and a `scripts/lint-invariants.py` that runs every library rule's `observe` against a fixture repo in CI so the library can't rot.

**What I'd check.**
- A project including `universal/vuln-deps` with `params: {allowlist: [CVE-2026-0001]}`; the expanded invariant carries the allowlist, the scan flags other CVEs and not that one, and a missing required param fails validation naming the rule and the param.
- A rule added in default `observe` mode shows drift in the Rules page for three scans and dispatches nothing; switching it to `dispatch` in the UI causes the next scan to dispatch.
- Three consecutive actuator PRs for a rule closed unmerged on GitHub; the next scan records them as `closed_unmerged`, the rule drops to `observe`, and the Rules page shows "refused" with the three PR links.
- A merged actuator PR shows `merged` in the next scan's metadata and in the Rules page counts.
- The "what would dispatch now" preview lists exactly the rules the sensor would request, respecting mode, priority, and the 023 governors, and requests nothing.
- `scripts/lint-invariants.py` fails CI when a library rule's observer errors against the fixture repo.
- Spend per rule on the Rules page equals the sum of tagged LiteLLM spend plus flat-rail runs for that rule over the window.

**Out of scope.** Sharing rule libraries between boxes. Rule versioning and upgrade migration. Learned parameter tuning. Suggesting rules from repo contents.

**Null action.** If tagging LiteLLM spend per invariant is not possible for a given harness (the flat rail carries no per-request tags), attribute by run: sum the run reports for that rule and show "estimated" on the Rules page rather than omitting the number.

---

## 025 — Provenance receipts

**Intent.** Make the trust claim auditable from inside the repository. Every change agentbox lands leaves a receipt: which spec it served, which checks it passed and from whose copy, whether the judge was touched, how many attempts and which models, what it cost, who merged it, and where the full run record lives. A third party reading the repo can verify the process without trusting agentbox or its operator. This is the difference between "built carefully" and "here is the proof": provenance, not quality, is what is certified.

**What changes.**
- Per-run receipt. Every worktree run (019) that produces commits writes `receipt.json` into the run directory (011) alongside `report.json`, containing: `spec` (the brief/spec path or ticket reference from the agent YAML or handoff, null if none), `invariant` (023, if dispatched by reconciliation), `commits` (SHAs on the branch), `checks` (name, verdict, `ran_from: base_ref`, observer command, blocking), `touches_judge` (023), `attempts` (per attempt: model, harness, cost, verdict; 018), `context_snapshot` (hash of `context.json`, 011), `harness_image` (image digest), `agentbox_version`, and `run_id`. The receipt is signed with a box-level key (`/data/keys/receipt.ed25519`, generated at setup) so it can be checked against a published public key.
- Receipt in the PR (020). The PR body gains a collapsed "Provenance" section rendering the receipt, and the receipt file is committed on the branch under `.agentbox/receipts/<run-id>.json` in a final commit made by the orchestrator, not the agent, after the agent's commits. The agent's worktree is read-only to `.agentbox/` (a `protected_paths` entry, 023).
- Merge record. The scan asset's PR outcome refresh (024) records, for each merged PR, `merged_by` and `merged_at` from GitHub and appends them to the receipt as a `merge` block, writing the completed receipt to `/data/provenance/<project>/<run-id>.json`. A `merge_rationale` is read from the PR's merge commit message or the last review comment by the merger, if present; the project may set `require_merge_rationale: true`, in which case the scan marks a merge without one as `rationale: missing` in the ledger and the Rules page.
- Repository ledger. A deterministic asset `<project>/provenance` (LLM-free, like `<project>/state`) regenerates `.agentbox/PROVENANCE.md` and `.agentbox/provenance.jsonl` on `base_ref` after each merge, opening its own orchestrator-authored PR when the files change (or pushing directly if the project sets `provenance_push: true` — the one place the orchestrator may push to base, limited to `.agentbox/` by a path-scoped check). The ledger lists every agentbox-authored commit with its receipt summary, plus a level assessment (below), and names commits on `base_ref` that are not agentbox-authored so the reader can see the human share of the history.
- Levels, computed from the ledger and shown at its top and in the UI: **Level 1** — every agentbox commit is spec-linked and human-merged; **Level 2** — plus every agentbox commit passed at least one blocking deterministic check run from `base_ref`'s copy with `touches_judge: false`; **Level 3** — plus the project runs the universal rule cluster (024) in `dispatch` or `observe` mode, has a coverage ratchet, has no quarantined or refused rules older than 30 days, every merge carries a rationale, the codebase tour rules are green and the deep-review sample rate is above its floor (026), and the `design` rule cluster is active with the ADR gate on declared boundaries (027). Until 026 and 027 are merged, Level 3 is computed without their conditions and the ledger says so. The level is a statement about the repository's history, recomputed each time; a single unreceipted agentbox commit drops it and the ledger says which.
- Verifier. `scripts/verify-provenance.py <repo-path> --pubkey <key>` runs anywhere with no agentbox install: checks receipt signatures, confirms each receipted commit exists on `base_ref`, confirms the receipt's commit list matches the PR's merged commits, and prints the level and any discrepancies. This is the artifact you hand to a skeptic.
- UI (022): a Provenance card per project with the level, counts of receipted vs unreceipted agentbox commits, missing rationales, and a link to the ledger; the run viewer (011) shows the receipt next to the report.
- Schema/README: `.agentbox/` documented as orchestrator-owned; README "Provenance" section stating the boundary — receipts certify process, not design quality.

**What I'd check.**
- A worktree run with two blocking checks passing and one escalation: the run directory holds a signed `receipt.json` listing both checks with `ran_from: base_ref`, two attempts with models and cost, and the context snapshot hash; the PR body's Provenance section matches; the branch's last commit is the orchestrator's receipt commit.
- An agent attempting to write into `.agentbox/` on its branch: the write is rejected or reverted, the run reports `touches_judge: true`, and the PR opens as draft.
- Merge the PR on GitHub; the next scan appends `merged_by` and `merged_at`; `<project>/provenance` regenerates `PROVENANCE.md` with the new row; with `provenance_push: true` the file lands on `base_ref` with no other path touched.
- `verify-provenance.py` on a fresh clone with the public key reports Level 2 and zero discrepancies; alter one byte of a receipt and it reports a signature failure and drops the level.
- A hand-made commit to `base_ref` appears in the ledger as non-agentbox and does not affect the level; an agentbox commit merged without a receipt (simulated by deleting one) drops the level to "unrated" and names the SHA.
- With `require_merge_rationale: true`, a merge with an empty merge message shows `rationale: missing` on the Provenance card, and the project cannot reach Level 3 until it is annotated.

**Out of scope.** Certifying design quality or correctness beyond the checks. Third-party attestation services or transparency logs. Cross-repository provenance. Receipts for job-only agents with no commits.

**Null action.** If committing receipts on the branch conflicts with a harness that force-pushes or rewrites the branch, keep receipts out of the branch and rely on the PR body plus `/data/provenance/`; the ledger then links to the PR rather than to an in-repo receipt, and the verifier checks the PR body via the GitHub API instead. Note the reduced offline verifiability in the plan.

---

## 026 — Codebase tour and sampled deep review

**Intent.** Make human understanding reconstructable and sampled, since it cannot be proved. Reconstructable: every project carries a maintained, ordered walkthrough of its own code that a person can follow to understand what is there and why, kept truthful by deterministic rules rather than good intentions. Sampled: the ledger records that randomly chosen agentbox commits received a full human read, so the claim "a human understands this" becomes "N% of changes were deep-reviewed, sampled at random" — a number a skeptic can check.

**What changes.**
- The tour is a maintained asset `<project>/tour`, produced by a doc-writer agent (the librarian split from the documentation guide: writer → critic → deterministic gate) and stored in the repo as `.agentbox/tour/*.tour` in the VS Code CodeTour JSON format, plus a rendered `TOUR.md`. Each stop names a file, a symbol or line range, an explanation of what it does and why it exists, and a link to the spec or ADR that motivated it. Tours are ordered: an entry tour for the whole codebase, then one per top-level module. The writer is fed the PR explanation sections (020) since the last tour update, so the tour grows with the code.
- Tour rules, shipped in the rule library (024) as a `understanding` cluster and deterministic throughout: every source module has at least one stop; every stop's file and symbol resolve on `base_ref` (via `ctags`/tree-sitter symbol lookup); every stop links to a spec or ADR that exists; no stop is older than N merged changes to its file (default 20) without being revisited; any PR adding a public module adds or updates a stop, checked from the diff. Violations dispatch the doc-writer as actuator; the tour PR is orchestrator-labelled `tour` and never mixes with code changes.
- Deep review. The project sets `deep_review: {per_week: N, seed: <string>}` (default 1). Each week the scan asset (023) deterministically samples N receipted commits merged in the prior period (seeded PRNG over receipt hashes, so the selection is reproducible and provably not chosen by hand) and opens a review issue per commit via `gh issue create` with the diff summary, the receipt, and the relevant tour stops. A human closes the issue with a written explanation of the change in their own words. The scan records per commit `deep_review: {reviewer, date, explanation_hash, sampled: true}` in the ledger (025); reviews of unsampled commits are also recorded with `sampled: false` and count separately.
- Explain-back check (advisory only). When a deep review or a merge rationale (025) is recorded, a critic agent compares the human's explanation to the diff and flags contradictions or explanations that describe something the diff does not do. The result is stored beside the review as `explain_back: {consistent: bool, notes}`; it never blocks, never changes a level, and is shown on the Provenance card as a hint that a review may have been a rubber stamp.
- Understanding metrics on the Provenance card (025) and in the ledger: tour coverage (modules with a stop / modules), tour freshness (stops within their revisit window), deep-review sample rate over 90 days, open deep-review issues and their ages, and explain-back inconsistency count. Level 3 (025) requires tour rules green and a sample rate at or above `deep_review.floor` (default 10%).
- Schema, README ("Understanding" section stating the boundary: the tour makes understanding possible, sampling makes it measurable, neither proves it), and UI: a Tour view that renders the entry tour with links into the repo, and a Deep review card listing sampled commits and their status.

**What I'd check.**
- A project with four modules and no tour: the `understanding` rules report four missing stops; the doc-writer's PR adds an entry tour and per-module tours whose stops all resolve; the rules go green after merge.
- Rename a symbol referenced by a stop and merge: the next scan flags the stop; the doc-writer's fix PR touches only `.agentbox/tour/` and `TOUR.md`.
- A code PR that adds a new public module without a tour stop opens as draft with the `understanding/new-module-stop` check failing in the body.
- With `per_week: 2` and eight receipted commits merged last week, the scan opens exactly two review issues; re-running the scan with the same seed and inputs selects the same two.
- Close a review issue with an explanation; the ledger records the review, the sample rate updates, and `verify-provenance.py` (025) reports it.
- Close a review issue with an explanation that describes the wrong function; `explain_back.consistent` is false on the Provenance card, the level is unaffected.
- A project below the deep-review floor cannot reach Level 3, and the ledger names the shortfall.

**Out of scope.** Interactive quizzes or comprehension tests. Tracking who read the tour. Tours for non-code assets. Enforcing deep reviews (a missed week lowers the rate; it does not block anything).

**Null action.** If CodeTour symbol references cannot be resolved reliably for a language, fall back to file-plus-line-range stops with a content hash of the range, and treat a hash mismatch as "stop stale" rather than "stop broken"; note the language in the plan.

---

## 027 — Design fitness rules, ADR gate, and non-degradation ratchets

**Intent.** Design quality cannot be certified, but three things about it can: that the structure the architect declared is the structure that exists, that only humans move architectural boundaries, and that design metrics do not get worse without a recorded human decision. This brief encodes design principles as executable fitness functions in the rule library, gates boundary changes on architecture decision records, and ratchets the measurable proxies. What remains unmeasurable goes to the constitution the agents are prompted with and to the code critic's recorded, advisory review.

**What changes.**
- A `design` cluster in the rule library (024), all deterministic: dependency direction and layering (`import-linter` for Python, `dependency-cruiser` for JS/TS, ArchUnit-style tooling per language) against a human-authored `architecture.yaml` in the repo declaring layers, allowed edges, and the public API surface; no circular imports; module, file, and function size ceilings; cyclomatic complexity ceiling; duplication threshold (`jscpd`); public API surface size; "no package imports another package's `internal`"; dependency count per package; maximum diff size per PR (default 400 changed lines, since design erodes through large unreviewed changes). Each has params and a `default_actuator` (usually a refactor agent scoped to the violation).
- Architecture decision records. `docs/adr/` in the MADR format is human-authored and orchestrator-protected (`protected_paths`, 023): agents may not create or edit ADRs. The ADR gate is a rule: any PR whose diff touches a declared boundary — `architecture.yaml`, files matched by the project's `boundary_paths` (public API modules, schema definitions, the module map, CI config), or any change that alters the layering graph as computed by the layering tool — must reference an accepted ADR by id in its body or commit message, checked mechanically; without one the PR opens as draft, `touches_boundary: true` is recorded in the receipt (025), and the actuator is not re-dispatched for that violation until an ADR exists. Agents implement inside boundaries; only humans move them.
- Ratchets. Complexity, coupling (afferent/efferent per package), duplication, API surface, dependency count, and churn concentration (share of changes in the top 5% of files) are recorded per scan (023's `value`) and may not regress on a branch unless the PR references an ADR that names the metric it is allowed to worsen. The rule library ships these as `design/ratchet-*` with `mode: observe` by default so a project accumulates baselines before enforcing.
- Constitution in context. The project's `constitution.md` (Spec Kit) is mounted into every agent run and its hash recorded in the context snapshot (011) and the receipt (025), so the ledger can state which principles each change was made under. Changing the constitution is itself a boundary change and needs an ADR.
- Critic as evidence. The code-critic agent's design review of each PR (the existing critic role, prompted with the constitution and the diff) is stored in the run directory and summarized in the receipt as `design_review: {score, concerns}`; it is advisory, never a gate, and the Provenance card trends it so a slow decline is visible even when every ratchet is green.
- Provenance (025) gains a design section in the ledger: fitness rules active and green, boundary changes and their ADRs, ratchet baselines and every permitted regression with its ADR, and critic trend. Level 3 requires the `design` cluster active with the ADR gate on and no unlinked boundary change in the ledger.
- Schema (`architecture.yaml`, `boundary_paths`, ADR directory config), README ("Design" section stating the boundary: fitness rules certify declared structure and non-degradation, not good design), and UI: an Architecture card showing the layering graph, boundary changes awaiting ADRs, and ratchet trends.

**What I'd check.**
- A repo with `architecture.yaml` declaring `api → service → data` and a branch where `data` imports `api`: the layering rule fails on the branch, the PR opens as draft naming the forbidden edge, and the refactor actuator's fix PR converges.
- A PR that edits a public API module without an ADR reference opens as draft with `touches_boundary: true`; adding `ADR-0007` to the PR body and re-running the check lets it open as ready (or converged per 023); the receipt records the ADR id.
- An agent PR that creates a file under `docs/adr/`: rejected as a protected path, `touches_judge: true`.
- Ratchet: with a baseline complexity of 12.4, a branch at 12.9 fails; the same branch with a PR body referencing an ADR that names `complexity` passes and the ledger records the permitted regression; a branch at 12.1 passes and lowers the baseline.
- A 900-line diff opens as draft on the diff-size rule; splitting it into three PRs under the cap passes.
- Edit `constitution.md` without an ADR: draft with `touches_boundary: true`; every subsequent run's receipt shows the new constitution hash once merged.
- The critic's `design_review.score` trends down over ten PRs while all ratchets stay green: the Architecture card shows the trend; no level changes, no PR is blocked.

**Out of scope.** Certifying design quality. Automated ADR authoring. Cross-repository architecture rules. Language support beyond what the chosen layering tools cover (others fall back to size, duplication, and diff-size rules only).

**Null action.** If no layering tool exists for a project's language, run the `design` cluster without the dependency-direction rule, compute boundary changes from `boundary_paths` alone, and record in the ledger that layering is unenforced for that project so the level reflects it.
