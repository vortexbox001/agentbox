# Agentbox: revised feature briefs 007–030

This is a separate proposed revision of `specs/000-briefs.md`, based on the 007–028 version read on 2026-09-14 (SHA-256 `C4FF4554693DA87744F5E932D20319E8DCD5DE8E5561DB5C1774276D5304C0E8`). It preserves the existing brief numbers and adds 029 and 030. Numbers identify briefs; they no longer prescribe implementation order.

**Status boundary.** 007, 008 and 009 are completed; 010 is in progress, per the operator. Their original brief text is retained verbatim below as historical reference, not as instructions to restart or redesign that work. Adopt 010's delivered layout when it lands. All proposed reporting corrections and check hardening are owned by the new 029 brief, including changes that supersede historical claims in 007–008. The forward contracts below apply to future work and do not rewrite those historical briefs. Nothing in this document authorizes deployment, spending, or changing an existing installation.

## Product intent

Agentbox turns declared repository intent into isolated, checked proposals for human review. Intent has two sources: an operator-approved feature work order (030), or a deterministic observation of maintenance drift (024). Both use the same execution, checking, publication, and evidence mechanisms.

The primary use cases are building bounded features, performing migrations, and maintaining repositories. The existing general-purpose agent jobs and artifact assets remain supported. A feature spec is not treated as a mechanically decidable invariant: executable acceptance criteria, existing regression checks, advisory reviews, and human acceptance are recorded separately.

Dagster owns scheduling, run execution, and asset lineage. Git and the hosting provider own repository and PR state. Agentbox owns the small amount of durable state needed to connect an approved request to attempts, checked artifacts, publication, and subsequent outcomes. Existing formatters, codemods, dependency bots, CI checks, harnesses, and attestation formats are reused wherever they solve the job. A second general-purpose workflow engine is not part of this proposal.

## Delivery order and scope

A/B labels below are release slices of a numbered brief, not new spec numbers. Later slices are optional extensions, with no hidden prerequisite on them from an earlier slice.

| Milestone | Included briefs or slices | Exit evidence |
|---|---|---|
| Established baseline | 007–009 completed; finish 010 in flight | Existing runs and configuration survive the layout migration. |
| Execution foundation | 029; 012A minimal run record and viewer; 014 compatibility/build fixes as needed | Recovery, isolation, report validation, and check identity scenarios pass on the deployment host. |
| Build one useful change | 016A one project/repo; 020A isolated checkout; 021A one PR; 026A basic signed evidence; 030 bounded work order | One real feature spec produces a checked PR, is reviewed and merged by a human, and gets post-merge verification. No variants, fifth harness, or broad rule library required. |
| Maintain one useful condition | 024A one scheduled observer, modes, deduplication and review limits; use 029's scheduler-independent admission service | Drift leads to one useful PR; repeat scans do not duplicate it; merge is re-observed. A deterministic actuator is supported from the start. |
| Operate and extend | 011 when mocks are available; 012B conversation/compare; 013 dependencies; 015 parameters; 016B multiple repos; 019 escalation; 023 panels; 025 selected rules | Operator can explain failures, stop work, and recover without database surgery. Add features in response to demonstrated need. |
| Optional breadth and governance | 017, 018, 022; 026B ledger exports; 027; 028 | Each extension has an observed use case, measured operating cost, and a supported fallback. |

012A includes durable redacted context/report records and a basic run-detail page; 012B adds the full normalized conversation, compare view, and rich file browser. 016A uses explicit agent configuration and one repository alias; defaults and repository partitioning come later. 020A may use an independent clone, with mirror/worktree optimization optional. 021A includes retry-safe branch/PR publication and outcome refresh; labels, reviewer routing, and rich summaries are extensions. 026A signs execution evidence outside the code branch; 026B adds repository exports.

024A can call the 029 admission service from a scheduled Dagster scan without 013, 015, 017, 019, 022, 023, or 025. It uses one repository, one rule, one request at a time, and an existing image. Work orders in 030 do not depend on reconciliation.

**Value gate.** Before expanding beyond these two loops, compare a small, preselected set of representative changes with the current direct-agent-plus-CI workflow. Record setup/operation time, human spec/review/rework minutes, accepted changes, rejected/duplicate proposals, provider usage, and post-merge failures over a declared follow-up window. Missing measurements are unknown, not zero. Agree a minimum useful reduction in human effort before the pilot; if the pilot misses it, reduce scope before adding governance features. No invented productivity percentage is a release criterion.

## Shared contracts

These contracts apply to every future brief. 029 implements the common execution/admission parts; each feature implements its own domain fields.

- **Paths.** `config/` denotes `AGENTBOX_CONFIG_DIR`; state is under `AGENTBOX_DATA`; Dagster's own state remains under `DAGSTER_HOME`, following 010. Containers receive only specific subdirectories and credentials needed for their role, never the whole state or config root.
- **Identity.** An approved request has a stable `request_id`; retries retain it. Each execution has a `run_id` and numbered `attempt_id`. Freeze the repository/base SHA, effective configuration digest, intent/spec digest, check-bundle digest, image digest, and upstream manifest identities. Branch naming uses the request/run identity, not a minute-resolution timestamp.
- **State.** Keep execution status, check verdict, publication status, human decision, and post-merge result separate. A finished model call is not a passed check; a passed check is not human acceptance; a merged PR is not proof of post-merge success.
- **Authority.** The operator approves intent and permissions. Agents can write only their candidate workspace and current output staging area. Check runners have no publish credentials. A publisher can update approved proposal branches and PR metadata but cannot merge or push to protected base branches. Signing keys are available only to the evidence service. Hosting branch protections enforce the remote boundary where supported.
- **Trust limits.** Containers bound ordinary workload access; this is a single trusted operator installation, not a hostile multi-tenant service. The host/control plane, configured check tools, and approved policy authors remain trusted. Evidence describes observations by those parties; signatures do not make the operator independently trustworthy.
- **Immutable evidence.** Final run/attempt records and published output manifests are append-only. Later PR and merge outcomes are new events, not edits to old reports or Dagster materializations. The UI derives current state from those events.
- **Success and missing data.** Null usage is unknown. Check statuses are `pass|fail|error|timeout|unsupported`; only a valid `pass` satisfies a required check. Model statements and critics are advisory. Failed executions produce retained failure evidence, not successful asset materializations.
- **Change ownership.** Acceptance policy and approved spec revisions are protected; candidate implementation tests may be written and changed. Ordinary test additions are not automatically judge tampering. Changes to trusted acceptance tests, their loaders, or policy require a separate human-approved revision.
- **Side effects.** No automatic merge, including provenance-only changes. On uncertain external outcomes, record `unknown` and reconcile before retrying. Do not promise exactly-once remote execution or no partial state.
- **Fallbacks.** Fallbacks may reduce scope or leave work awaiting an operator. They cannot remove isolation, required evidence, or human admission while retaining a success claim.

## Change map

| Concern from review | Revision |
|---|---|
| Runner and UI validation drift; malformed YAML breaks discovery | Shared versioned configuration model and file-local error isolation in 029 |
| Pipes read timing, cancellation, orphan containers | Reporting follow-up, supervised lifecycle and restart reconciliation in 029 |
| Mutable shared outputs and contaminated attempts | Per-attempt staging, sealed manifests, bounded retention in 012/019/029 |
| Credentials visible in argv or shared with agents | Destination-name environment binding in 029; role-specific project credentials in 016/020/021 |
| Too much infrastructure before useful feature work | Two initial delivery loops; new 030 work orders; optional later breadth |
| Git worktrees mistaken for security isolation | Independent agent Git metadata; trusted import and credential-separated publisher in 020 |
| Checks can be influenced through candidate configuration | Check hardening follow-up: trusted bundles, isolated loaders and assurance limits in 029 |
| Duplicate PRs, stale checks, restart ambiguity | Durable admission/outbox state in 029 and current-head verification in 021 |
| More PRs than humans can review | Observe-only default, one active proposal per intent, review capacity and cooldowns in 024 |
| Receipts and levels overstate trust | Standard attestation envelope, separate merge records, evidence dimensions instead of quality levels in 026 |
| Tour/ADR rules conflict with building new code | Role-scoped tour paths; separate acceptance policy; scoped human boundary authorization in 027/028/030 |

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
- Each check becomes a Dagster asset check on the asset. Blocking failures show on the asset and prevent downstream automation (013) from firing; non-blocking ones show but don't block.
- Check stdout/stderr (last 4 KB) attached to the check result as metadata.
- Schema (a Checks card under Job), YAML comments, README updated.

**What I'd check.**
- Add to an asset agent a check `command: test -n "$(ls /output)"` → passes when the agent wrote a file. Add `command: false` with `blocking: false` → shows failed, asset still counts as materialized. Both appear as asset checks with output attached.
- A check exceeding its timeout is reported failed with `timeout` in its metadata.
- A check that writes to `/output` fails with a read-only error.
- An agent without `produces` cannot have `checks`; the UI hides the card and the factory rejects the file naming it.

**Out of scope.** Escalation on failed checks (019). Checks for job-only agents. Built-in check types.

**Null action.** If asset checks can't attach per-partition in this Dagster version, attach them unpartitioned and record the partition key in metadata; note the limitation in the plan.

---

## 009 — Design system migration: Archon → AgentBox (Dagster sibling)

**Intent.** Replace the Archon design system (dark-only, cyan/magenta, Playfair serif, `--ax-*` tokens) with the AgentBox design system delivered in `AgentBox_Design_System.zip`: a Dagster-derived system with light and dark themes, navy/teal/lime brand colours, Inter + Source Code Pro, a 240px collapsible sidebar and no top bar, Lucide outline icons, and a component set matching Dagster's. After this, the management UI looks like a sibling app to Dagster, every page uses the new tokens and components, and the design system lives in the repo where both humans and coding agents can reference it. This is a visual and structural migration only; no feature behaviour changes. It runs before 012 because 012 adds the largest new surface (Runs, Settings) and should be built on the new system, not migrated after.

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

**Out of scope.** New pages or features (012+ build on this). Replacing Inter/Source Code Pro with Geist. A theme setting in `config/settings.yaml` (the Settings page arrives in 012; localStorage suffices now). Porting the React `ui_kits` to Jinja beyond what the pages need. Mobile layout.

**Null action.** If self-hosting the fonts under a licence-compatible path is blocked, keep the system-font fallback stack (`-apple-system … sans-serif`, `ui-monospace … monospace`) as the effective rendering, leave the `@font-face` file in place with a comment, and record in the plan that Inter/Source Code Pro load only when the box has internet — never restore the Google Fonts `@import` in the served CSS.

---

## 010 — Layout: product, instance config, and instance data

**Intent.** Separate the three kinds of files agentbox has today: the product (same on every box), the instance configuration (this box's agents, prompts, projects — versioned in git, edited by the UI), and instance state (run records, outputs, workspaces, Dagster storage — on disk, backed up). Today the first two share the product repo and the third is scattered across seven top-level directories under `/data`. After this, a fresh install is "clone agentbox, copy `examples/config` to `config/`, point `AGENTBOX_DATA` at a disk", and every later brief places its files under one of two roots.

**What changes.**
- **Three roots, three env vars.** `AGENTBOX_CONFIG_DIR` (default `./config`, resolved against the repo) holds instance configuration; `AGENTBOX_DATA` (default `/data/agentbox`) holds instance state; `DAGSTER_HOME` (default `/data/dagster`) stays a sibling, since Dagster may serve other workloads on the same box. All three are read once in `orchestrator/factory.py` and `ui/config.py` and never hard-coded elsewhere; compose mounts exactly these three paths (plus the product tree read-only and the Docker socket). `.env.example` documents all three.
- **Instance config tree** (`config/`, gitignored in the product repo; intended to become its own repo — README describes checking a config repo out at that path):
  ```
  config/
    agents/            # today's agents/*.yaml (templates removed, see examples)
    prompts/           # today's prompts/*.md
    projects/          # 016
    assets/external/   # 017
    settings.yaml      # today's orchestrator/settings.yaml (012 retention, 013 governors, …)
    litellm.yaml       # instance overlay: providers, keys by env name, alias→model bindings
  ```
  `litellm/config.yaml` in the product becomes the alias-tier template; a small generator (`scripts/render-litellm.py`, also run at compose start) merges it with `config/litellm.yaml` into the file LiteLLM actually loads. Product-owned catalogs stay in the product: `images/`, `invariants/` (the 025 library), the schema, the design system.
- **Examples.** `examples/config/` holds the current `_template-*.yaml`, a sample prompt, a sample project, and a minimal `settings.yaml` and `litellm.yaml`. The UI's template picker reads templates from `examples/config/agents/`, not from the instance's agents directory.
- **Instance data tree** (`$AGENTBOX_DATA`):
  ```
  runs/           # per-run directories (today /data/dagster/agent-logs)
  outputs/        # today /data/outputs
  workspaces/     # today /data/workspaces
  repos/          # bare mirrors (020)
  provenance/     # ledgers and completed receipts (026)
  credentials/    # today /data/credentials, mode 700
  keys/           # box keys (026)
  ```
  `DAGSTER_HOME` (`/data/dagster`) holds only Dagster's own storage and compute logs; `agent-logs` moves out of it into `$AGENTBOX_DATA/runs/`. `orchestrator/dagster.yaml` and `workspace.yaml` derive their paths from `DAGSTER_HOME`; everything agentbox-owned derives from `AGENTBOX_DATA`. Backups cover both roots.
- **Migration.** `scripts/migrate-layout.py` moves `agents/` and `prompts/` into `config/`, `orchestrator/settings.yaml` into `config/settings.yaml`, each `/data/<x>` (outputs, workspaces, credentials) into `$AGENTBOX_DATA/<x>`, and `/data/dagster/agent-logs` into `$AGENTBOX_DATA/runs` (leaving `/data/dagster` otherwise untouched), rewriting `output_dir`, `workspace`, and `env_file` values in agent YAML that begin with the old roots. It prints the plan and does nothing without `--apply`; it refuses to run if the destination already has content. `scripts/bootstrap.sh` creates the data tree with correct ownership (uid 1000 for workspaces and outputs, 700 for credentials).
- **Compose and images.** Volume mounts reduce to `./:/opt/agentbox:ro`, `${AGENTBOX_CONFIG_DIR}:/opt/agentbox/config` (writable for the UI), `${AGENTBOX_DATA}:/data/agentbox`, `${DAGSTER_HOME}:/data/dagster` (orchestrator and daemon only), and the Docker socket. Agent containers keep their existing mount contract (`/workspace`, `/output`, `/config/prompt.md`); only the host side of each bind changes.
- **Schema and validation.** `ui/schema.py` validates that `output_dir`, `workspace`, and `env_file` fall under `$AGENTBOX_DATA` (or are the documented defaults) and rejects paths under the product tree. The schema version increments; the migrations list records the root change.
- **Docs.** README gets a "Layout" section with the three-kinds model and both trees, and the file-tree listing is rewritten. `AGENTS.md` states where new file kinds go: product code in the product, instance config under `config/`, state under `$AGENTBOX_DATA`, samples under `examples/config/`.

**What I'd check.**
- On the existing box: run the migration with `--apply`, restart compose, and every agent, prompt, schedule, past run, and output is where the UI and Dagster expect it; `git status` in the product repo shows only deletions of `agents/` and `prompts/` and the new `.gitignore` entry.
- Fresh-install rehearsal in a clean directory on the Pi: clone, `cp -r examples/config config`, set `AGENTBOX_DATA` and `DAGSTER_HOME` to empty directories, run `bootstrap.sh`, `docker compose up`; the UI lists the example agents, one materializes, its run directory appears under `$AGENTBOX_DATA/runs/`, and nothing was written outside the two roots (verify with a filesystem watch); `$DAGSTER_HOME` contains no agentbox run directories.
- Set `AGENTBOX_DATA` and `DAGSTER_HOME` to non-default paths; all services follow them with no residual writes to the defaults.
- An agent YAML with `output_dir: /opt/agentbox/ui` is rejected naming the field and the rule.
- `config/` is a separate git repo checked out at that path; the UI's saves commit-free edits land there and `git status` in the product repo stays clean.
- `render-litellm.py` produces a config with the product's alias tiers bound to the instance's providers; a missing provider key name is reported at render time, not at first request.

**Out of scope.** Multiple config directories or multi-instance on one box. Sharing `DAGSTER_HOME` with a non-agentbox code location (supported by the sibling layout, but not configured here). Moving the design system or images. Git-committing config edits from the UI (a later brief). Backup tooling beyond documenting the single root.

**Null action.** If moving `agent-logs` out of `DAGSTER_HOME` breaks a materialization-metadata link in existing runs, leave a symlink `$DAGSTER_HOME/agent-logs → $AGENTBOX_DATA/runs` for the migrated history only, and record it in the plan; new runs never write under `DAGSTER_HOME`.

---

## 011 — Page rebuild from mocks

**Intent.** Rebuild the existing screens from the operator's supplied mocks, using completed 009 and the layout delivered by 010. Preserve this as presentation work, independent of the execution foundation.

**What changes.**
- Finalize screen-specific acceptance criteria when the mocks are available; do not invent a new visual direction in this revision.
- Use `ui/design-system/readme.md`, its tokens, and the shared macros in `ui/templates/components/macros.html`, following the repository's current AGENTS.md.
- Existing pages retain their actions, validation, keyboard behavior, and error states. Future pages are added when their feature exists; mock placeholders are noninteractive and clearly marked.
- Include light/dark themes, keyboard focus, readable error states, and long-content handling in the screen review.

**What I'd check.** Compare each supplied mock at its viewport; exercise existing create/edit/automation keyboard paths; run the existing design-system conformance checks.

**Out of scope.** New domain fields, rewriting completed 009, and designing absent mocks.

**Null action.** Keep the completed UI when a mock is absent. Backend core work does not wait on this brief.

---

## 012 — Run transparency: evidence records and conversation viewer

**Intent.** Explain what a run received, did, produced, and failed to disclose. Capture enough for diagnosis without promising exact replay or complete vendor internals.

**What changes.**
- **Slice A:** persist a versioned operation summary and per-attempt directory under `$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`. Retain `context.json`, `report.json`, check records, and manifest references, with a minimal readable run page. The orchestrator owns final records; agents supply bounded event/report messages through a separate channel.
- **Slice B:** add normalized `events.jsonl`, redacted native `transcript.jsonl`, conversation search, context comparison, and a file browser. Events carry sequence number, timestamp/source, attempt, turn, event kind, tool-call correlation ID, and usage where actually supplied. Preserve disclosed content/order subject to recorded redaction and size limits; represent missing results explicitly.
- At launch freeze the effective configuration, rendered prompt, instruction-file snapshot available at launch, base SHA, image/harness version, configured tools and permissions, mounts, environment names, and resource caps. Append initialization/runtime disclosures as events; do not rewrite the launch snapshot to imply knowledge obtained later.
- Record each field's source and completeness. A file found on disk is not automatically a file the harness loaded. Vendor prompt internals, nondeterminism, changing model services, and unavailable tool results prevent claims of complete replay.
- Replace the environment-value heuristic with a shared streaming redactor: known injected secret values, recognized credential substrings, multiline private keys, and structured sensitive fields. Apply it before all persistent sinks, including native/normalized transcripts, stderr, reports, prompts, setup logs, Dagster logs, and PR excerpts. Handle secrets crossing stream chunks. Environment values are excluded.
- Unknown secret encodings cannot be guaranteed detectable. Native transcript means redacted native event structure, not an unredacted archive. Bound event size, total log volume, and file-tree traversal; report redaction/truncation counts without storing removed content.
- Retention defaults: conversation data 30 days; final context/report/check/evidence records retained until an explicit administrative purge; unbounded conversation retention is opt-in. Settings include byte budgets and free-space thresholds. Pruning never removes data needed by an active request, unresolved publication, or pending check. Archive/export before destructive administrative purge.
- Compare separates meaningful config changes from inevitable run IDs, timestamps, and image/base changes. HTML and tool results render escaped, and file access is confined to the recorded manifest.

**What I'd check.**
- Fake secrets embedded inside tool results, stderr, prompt text, private-key blocks, and split chunks appear nowhere in persistent outputs or PR summaries.
- A harness withholding tool results shows missing content; a late-loaded instruction appears as a runtime disclosure rather than an invented launch input.
- Retention removes expired conversations but leaves required evidence and a visible pruned marker; disk limits produce a controlled stop.
- Dagster unavailable: finalized runs still open from disk. Comparing two runs shows volatile and effective differences separately.

**Out of scope.** Perfect secret detection, deterministic LLM replay, vendor prompt reconstruction, live interactive sessions.

**Null action.** Ship slice A first. Missing normalization support stays explicit; do not synthesize tool results from assistant prose.

---

## 013 — Asset dependencies and event-driven triggers

**Intent.** Pass identified, checked upstream artifacts to dependent runs without creating uncontrolled fan-out.

**What changes.**
- Preserve `produces.depends_on`, `on_upstream`, and `on_missing`. Resolve keys and reject cycles at configuration load. Declare supported partition mappings explicitly: identity daily/static initially; unsupported mappings fail validation.
- Handoffs contain the exact upstream run, attempt, partition, artifact manifest, hashes, and relevant check results selected at admission. Mount selected artifacts read-only at container-accessible paths; host paths alone are not a handoff.
- Environment references use a collision-checked identifier mapping. Keys whose normalized names collide are rejected; structured handoff metadata preserves original keys.
- An event becomes a request through 029's durable admission service. Deduplicate on downstream target, partition and relevant upstream manifest identities. Check results must apply to those exact inputs.
- Enforce shared launch/hour, concurrency, chain-depth, pending-review and applicable usage budgets at admission. Automated runs never bypass these through escalation or nested triggers. Manual requests bypass only an explicitly authorized scheduling limit, not isolation or hard resource caps.
- A stale/missing/failed upstream record blocks with a reason. New upstream state does not mutate a request already in flight; it creates a pending superseding input subject to coalescing.

**What I'd check.** A → B fires once with readable checked files; failed A checks prevent B; repeat events and restarts do not duplicate B; identical normalized names are rejected; two concurrent admissions cannot both consume the final quota slot.

**Out of scope.** Arbitrary partition fan-in, automatic conflict resolution, autonomous unbounded chains.

**Null action.** Restrict mappings to those demonstrated on the pinned Dagster version; never silently use a different partition.

---

## 014 — Shared images and reproducible builds

**Intent.** Reduce duplicated image maintenance while making the tested runtime recoverable.

**What changes.**
- Introduce a lean shared base only for compatible harnesses. Choose a supported runtime at implementation time and pin the selected image digest, harness versions, and dependency set. Keep the API image independent if that is smaller.
- Pin matching tested Dagster/Pipes versions; centralize the version matrix and update it intentionally. Run images by recorded digest rather than an untracked moving tag.
- Keep publish tooling in a publisher image and check tooling in check images. GitHub CLI availability in an agent image grants no publishing authority.
- Correct README/bootstrap build contexts for `images/lib`; one supported build entry point handles shared-base ordering and smoke tests.
- Measure actual unique-layer disk usage, build time, and per-run memory on arm64. A shared base does not guarantee lower total size.

**What I'd check.** Clean documented build succeeds on the target; all required report/check contracts pass; old and new image digests remain distinguishable; a rebuild uses the recorded dependency set or explicitly reports an unavailable dependency.

**Out of scope.** New language toolchains without a use case; universal base-image uniformity.

**Null action.** Leave incompatible harnesses on independent pinned bases. Fix build correctness without requiring the refactor first.

---

## 015 — Parameterized agents

**Intent.** Remove repetitive configuration after actual multi-target usage establishes which variation is useful.

**What changes.**
- Add static partitions, vars, per-partition schedules, and named variants as in the source brief. Pass `AGENTBOX_PARTITION_KEY` consistently.
- Use restricted value substitution with strict missing-variable errors. No expression execution, arbitrary attribute access, file reads, or shell evaluation.
- Template prompts, appended prompts, declared nonsecret env values, and approved path suffixes. Resolve repository selection only through a project's authorized alias list. Do not template network, credential selectors, images, tool permissions, or arbitrary mount roots.
- Precedence: schema defaults → approved project defaults → base agent → named variant → allowed run variables. Revalidate the fully expanded configuration and resolved paths after substitution.
- Variants cannot override identity, project, asset key/partition/dependency declarations, protected policy, credential scope, or resource ceilings. Null explicitly removes an optional inherited field; lists replace instead of concatenating.
- Migration emits a preview and leaves sibling files intact unless an explicit apply step is requested. Show configuration equivalence separately from expected identity/path changes.

**What I'd check.** Collapsed variants select the same model/harness/options; inherited incompatible fields fail clearly; path traversal via a partition key fails after expansion; a variant cannot widen credentials; a per-partition schedule targets only its declared partition.

**Out of scope.** Variants of variants, general expression languages, mandatory migration of simple agents.

**Null action.** Keep separate agent files until equivalent expansion and scheduling are demonstrated.

---

## 016 — Projects and authority boundaries

**Intent.** Group repositories, defaults, and evidence without implicitly giving every agent every project credential.

**What changes.**
- Slice A adds `config/projects/<name>.yaml` with one repository alias, URL, base ref, allowed proposal branch prefix, and explicit credential references. Slice B adds multiple repositories, defaults, grouping and repository partitions.
- Separate credential roles: repository reader for trusted checkout, publisher for proposal branches/PRs, provider credential for the selected harness, optional narrowly scoped tool secrets. There is no automatic `GITHUB_TOKEN` injection into candidate execution.
- Legacy `credentials_env` migrates to the publisher reference with a visible compatibility warning; explicitly configured agent tool access requires a separate binding. Values are resolved at launch by the trusted process and forwarded under destination names without entering argv.
- Project defaults may select registered harnesses/models/networks within box policy; projects cannot define those global resources or exceed resource/permission ceilings. Resolve the source brief's ambiguous “any field” inheritance by using an explicit allowlist.
- Asset keys are namespaced, defaults remain visible in effective configuration, and cross-project references are rejected unless separately declared by the operator.
- Namespace separation is an application boundary on a trusted single-operator host, not a claim of adversarial tenant isolation.

**What I'd check.** Two projects cannot request each other's secrets or repository aliases; a candidate has no repository publish token; missing credentials fail before dispatch; explicit destination-name binding works without logging values; existing projectless runs retain documented behavior.

**Out of scope.** Hostile multi-tenancy, enterprise IAM, project-owned runtime catalogs.

**Null action.** Start with one repository and explicit agent values; defer inheritance and partition expansion.

---

## 017 — Dynamic partitions and external assets

**Intent.** Expand work from validated external state while keeping resource use bounded.

**What changes.**
- Add dynamic partition sets and external git-ref/path observers. Partition registrations from agent reports are requests validated by the controller, not authority to schedule arbitrary targets.
- Scope sets to project, validate key grammar/length, cap keys per response and total active keys, and require explicit downstream fan-out limits. Registration itself does not bypass admission.
- Git change identity is an observed commit SHA. Path changes use a sorted manifest of approved paths and content hashes or a documented weaker fingerprint that detects deletions; newest mtime alone is insufficient.
- Coalesce rapid changes; store durable event cursors and deduplication keys. External observations request work through the same service as 013.
- External filesystem access is limited to operator-approved read-only roots, with symlink/traversal checks.

**What I'd check.** Repeated registrations are no-ops; deletion is observed; a huge key list is refused before scheduling; three keys produce at most three admitted requests across restart; unauthorized paths/sets fail.

**Out of scope.** Multi-dimensional partition design, unlimited key retention, external source mutation.

**Null action.** Use a bounded explicit target list and scheduled scans; no requirement for dynamic partitions in the first reconciliation loop.

---

## 018 — Optional mini-swe-agent harness

**Intent.** Add another actuator only if its tool loop or metering delivers value on a representative task.

**What changes.**
- Provide the pinned mini-swe-agent image and normal report/event adapter, through the existing launch and check interfaces. Keep step limits and model settings declarative.
- Prefer an isolated network with a scoped proxy credential. Declare the actual enforcement mechanism for cost limits; client-side estimates are not advertised as hard billing caps.
- Record provider-reported usage, pricing version, measured/estimated cost, and unknown values. A configured request cap must account for in-flight calls and possible overshoot.
- Reuse existing trajectory parsing support where possible; do not invent a second harness orchestration layer.

**What I'd check.** The same bounded feature fixture runs under an existing harness and mini; compare accepted result, human review effort, time, and measured usage. Step/cost stops produce failure evidence and no orphan container.

**Out of scope.** Making the fifth harness a prerequisite for feature work or reconciliation.

**Null action.** Keep using a supported existing harness when the adapter or model endpoint cannot meet the contract.

---

## 019 — Bounded escalation and attempt lineage

**Intent.** Retry plausible implementation failures without spending more on broken infrastructure or losing attempt history.

**What changes.**
- Preserve the report object; add an `attempts` array and final summary rather than replacing it with a list. Every attempt has separate output, workspace snapshot, model, context, check results and cost.
- Add an optional same-harness model ladder with at most three attempts. Escalate only a classified implementation/check failure. Missing credentials, observer errors, unsupported checks, disk exhaustion, policy blocks and unknown publication states do not trigger a stronger model.
- Default attempts start from the request's frozen base. An explicit `resume_previous` policy imports the previous candidate snapshot, recording its digest. Failure output is quoted as untrusted diagnostic data, not appended as authoritative instructions.
- Bound aggregate elapsed time, attempts and applicable usage budget for the request. Every attempt consumes the same admission quotas; a larger model is not assumed to be better.
- When an old attempt cannot be confirmed stopped, do not launch its replacement.

**What I'd check.** A controlled fixture fails its first attempt and passes its second with both records intact; an invalid checker causes no escalation; restart neither repeats a completed attempt nor loses its cost; repeated attempts never share mutable output.

**Out of scope.** Cross-harness escalation and learned routing.

**Null action.** Stop after one attempt when a safe context or workspace handoff cannot be established; do not silently retry without required evidence.

---

## 020 — Isolated repository workspaces

**Intent.** Let agents build code on a frozen repository snapshot while protecting the authoritative repository and publication credentials.

**What changes.**
- Preserve the workspace block with repository alias and branch prefix. Resolve `base_ref` to `base_sha` before launch. Proposal branch names include a stable request identity; concurrent requests cannot collide.
- Trusted checkout may maintain a mirror under `$AGENTBOX_DATA/repos/`. Candidate execution gets its own repository and writable Git metadata. It does not receive a writable shared Git common directory, mirror, host hooks/config, credential helper, or publisher token.
- Slice A uses an independent clone or export/import boundary. Host-side worktrees are an optional storage optimization only where their shared metadata is inaccessible to the candidate. Branch names alone do not enforce isolation.
- Trusted Git operations ignore candidate global/local hooks and configuration; disable uncontrolled submodule/LFS fetches and validate those sources when enabled. Use safe argv and validated repository paths.
- After execution, stop all writers and snapshot the candidate. A credential-free import step validates paths, symlinks, size limits, protected-policy changes, base ancestry and diff scope before handing an immutable commit/tree to checks and publisher. Do not run agent-controlled Git hooks in a privileged process.
- Agent commits and any final commit of uncommitted files are identified separately. Preserve failed candidates for bounded diagnosis; remove disposable workspaces only after durable snapshot and ownership checks.
- A persistent path workspace remains available for legacy jobs, with exclusive access and an explicit lower-isolation mode. Automated code proposals use isolated candidates.

**What I'd check.**
- Two runs can create commits without modifying each other's refs or the mirror.
- An agent attempts to push base, rewrite shared refs, install a credential helper, or place a malicious hook: it cannot gain publishing authority or execute code in the trusted publisher.
- Attempting to replace a parent of a protected path or export an escaping symlink is detected.
- Worker loss preserves a discoverable candidate; branch identities remain unique even with the same partition/stamp.

**Out of scope.** Automatic merging, conflict resolution, and a promise that worktrees themselves provide security isolation.

**Null action.** Use independent clones. If isolation cannot be demonstrated, disable automated repository writes for that execution mode.

---

## 021 — Recoverable publication and human admission

**Intent.** Turn a checked immutable candidate into one reviewable PR and recover cleanly from partial publication.

**What changes.**
- A separate publisher consumes an approved request, sealed candidate SHA/tree and check/evidence records. It has no agent tools or writable candidate environment. Only this role receives repository publishing credentials.
- Persist publication intent before side effects. Use a stable proposal branch and request marker in the PR. Push with expected-ref checks; query branch/head and PR identity after timeout or connection loss before deciding to retry.
- States include `not_requested|pending|pushed|pr_open|failed|unknown`; human outcome is separately `open|merged|closed_unmerged`. A push-only outcome is partial publication, not full success. A failed PR request never reruns the agent automatically.
- Initial PR creation, retry-safe recovery of that PR, and outcome refresh are slice A. Arbitrary revisions of an existing PR remain out of scope; refreshing evidence/draft status for its existing head is supported.
- Ready status requires valid checks for the exact current candidate SHA and frozen check policy plus satisfied authorization. Failed checks may produce a draft according to explicit policy. Required-check errors and protected-policy changes cannot produce ready status.
- If remote head changes, old evidence becomes stale. If base moves, show the old tested base and revalidate against current integration state before claiming freshness. Agentbox does not silently rebase or merge; a hosting required check/merge policy must enforce freshness at actual merge time.
- PR text separates trusted check summaries from quoted agent notes; includes spec/intent, acceptance criteria covered, limitations, changed files, usage and evidence references. Private transcripts are not automatically uploaded publicly.
- Basic merge/close polling is here, not deferred to 025. Append outcome events with provider source, observed head/merge SHA and timestamps.
- No automatic merge or direct base push, even for evidence-only changes. Verify installed credential/branch protections; otherwise restrict to draft/export mode and show the limitation.

**What I'd check.**
- Kill the publisher before push, after push, and after remote PR creation but before local acknowledgement: recovery produces one branch and one PR, with no fresh model call.
- A revoked token leaves a recoverable pending/failed publication record. A provider timeout stays unknown until reconciled.
- Changing PR head invalidates evidence. Moving base prevents a stale-green presentation.
- Only a human merge advances the repository; subsequent verification is a separate result.

**Out of scope.** Automatic merges, silent force pushes, arbitrary PR rewrite loops, non-GitHub hosts initially.

**Null action.** Export the checked patch/branch and evidence for manual publication. Clearly distinguish exported, pushed, and PR-open states.

---

## 022 — Optional per-agent runtime tools

**Intent.** Support occasional extra tooling without weakening the tested execution boundary.

**What changes.**
- Prefer pinned prebuilt images for repeated agents and all trusted acceptance checks. Optional `setup` supports validated apt package selections and pinned pip requirements, with recorded resolved versions and hashes where available.
- Installation is code execution, even if package names have no shell metacharacters. Run setup without repository/publisher/signing credentials, with explicit network policy and time/disk limits.
- Root installation, if needed, finishes in the preparation stage before dropping privileges. The agent never retains package-manager root privileges.
- Freeze the prepared runtime identity for check and run evidence. A dynamically prepared runtime without reproducible dependencies records that limitation.
- Reject setup on an isolated network unless its dependencies are already available through an approved local source. No silent network widening.

**What I'd check.** Setup failure starts no agent; a no-setup run incurs no installation; package install logs are redacted; the final harness is non-root; receipts distinguish resolved runtimes.

**Out of scope.** Arbitrary root scripts, claiming package-name validation prevents supply-chain attacks, package caching infrastructure.

**Null action.** Require a prebuilt image when safe preparation cannot be supported.

---

## 023 — Operator views for requests, runs and proposals

**Intent.** Reduce the work required to review proposals and recover failures without duplicating Dagster or GitHub.

**What changes.**
- Use the completed design system. Add agent/project/asset summaries, recent run/check records, and links to the existing Dagster and GitHub surfaces.
- Show intent/spec reference, current stage, execution result, check assurance, current PR head, stale evidence, review age, usage, and unknown states separately.
- Slice-specific minimal panels arrive with 012/021/024/030; this brief consolidates them rather than blocking those workflows.
- Actions are narrow: cancel a request, pause automation, retry a known failed publication, acknowledge an unresolved state, and open the PR. State-changing actions go through the controller; the UI cannot rewrite final evidence files.
- Index finalized records for bounded queries; list pages do not scan every transcript. When a dependency is unavailable, show last-observed state and timestamp.
- Show review capacity, blocked reasons, expired conversations and disk pressure prominently enough to act on.

**What I'd check.** Dagster or GitHub unavailable leaves useful local records with stale markers; an unknown push is not shown as failed execution; retry publication cannot create a new agent run; escaped tool output cannot inject UI markup.

**Out of scope.** Rebuilding GitHub review/merge tools or Dagster's full run explorer; placeholder dashboards without working data.

**Null action.** Ship a compact request table and run details before richer asset graphs and cards.

---

## 024 — Repository reconciliation with bounded review demand

**Intent.** Observe selected repository conditions and propose useful repairs while controlling human review load. A passing observer is evidence about that condition, not proof of general correctness.

**What changes.**
- A project defines invariants with stable ID, description, versioned observer/check-bundle reference, typed parameters, priority, and optional actuator. `mode: off|observe|dispatch` is included from the first release and defaults to `observe`.
- Observers use the common 029 result contract: `pass|fail|error|timeout|unsupported`, stable violation IDs, optional numeric values with units, and tool/data versions. Tool failures, unavailable advisory feeds, invalid JSON and unsupported languages are not violations that automatically dispatch an agent.
- A scheduled Dagster state asset freezes repository SHA, observer bundle and relevant external data. It emits a finalized drift record. No dynamic partitions, broad rule catalog or LLM observer is required for slice A.
- Prefer an existing deterministic actuator for formatting, codemods and dependency updates. The controller can adopt an existing bot PR as an externally managed proposal and avoid competing with it. Agentic actuation is used for repairs that need it.
- Dispatch through 029 with a stable logical intent keyed by project/repo/rule and normalized violation identity. An active proposal suppresses repeat dispatch even when unrelated commits change base SHA. After closure, explicit retry or configured cooldown/policy permits a new request.
- Default one active request or open PR per invariant; all drafts and queued requests count. Default one automated repository request at a time and one dispatch per scan until operator configuration expands it. The project must configure an aggregate open-proposal limit; hitting it or an age threshold pauses new proposals.
- Include per-rule/project attempt, time and usage budgets, refusal threshold (default three consecutive human closures without merge), and cooldown. Closing a PR is meaningful feedback; it does not immediately recreate it.
- After a candidate is checked, record `observed_condition_satisfied` and candidate/base/check identities. After human merge, run the observer again at the merged repository state. Only that observation resolves repository drift.
- Freeze suspected regressions with evidence about the intervening range. Temporal proximity to another agent's merge is correlation, not proven causality. Quarantine repeated ineffective merged repairs after three distinct repair/merge cycles, not three polls of the same unchanged state.
- Persist freezes/refusals/quarantines as operational events, separate from declared configuration. Clearing them is an explicit operator action with a reason.
- A minimal queue shows condition, proposal, reason for suppression, review age, attempted usage and last post-merge result. Rules whose observer is costly can have independent scan intervals.

**What I'd check.**
- Three scans in observe mode spend no model budget; enabling dispatch requests one repair; repeating scans/restarting requests none while that proposal is active.
- An observer infrastructure error produces no repair. A deterministic formatter can complete a repair without an LLM.
- A closed PR is not immediately recreated; every draft counts toward the cap.
- A passing candidate merged into a changed base is re-observed; a later failure is visible without claiming which commit caused it.
- Across the pilot, report accepted repairs, abandoned/rejected proposals, review minutes, usage and rework. No merge was performed by Agentbox.

**Out of scope.** LLM-defined invariant truth, automatic merge, autonomous conflict resolution, mandatory partitioning by invariant.

**Null action.** Stay in observe mode or emit a report when the actuator, observer assurance or review capacity is insufficient.

---

## 025 — Versioned rule library and outcome-based operations

**Intent.** Make useful rules reusable without turning every available metric into mandatory work.

**What changes.**
- Product-owned `invariants/` contains versioned rules: ID, description, observer/check-bundle reference, typed params, supported languages, external data sources, cost/latency expectations and preferred actuator type.
- Projects include explicit rules/revisions; snapshot expanded configuration and hashes at request admission. Updating a rule creates a new baseline/compatibility decision, not a silent reinterpretation of old results.
- Start with a small useful set; reuse existing tools and bot integrations. Clusters are menus with off/observe defaults, never automatic activation of every “universal” rule.
- Modes, refusal handling and PR polling already exist in 024/021. Add authoring, preview, configuration validation and outcome summaries here.
- Adoption summaries include accepted versus closed proposals, review latency, human rework, observation errors, post-merge recurrence and usage. Distinguish estimated cost, measured cost, and subscription run counts.
- Preview uses the exact admission selection logic but consumes no reservations and performs no side effects. Saving a rule does not implicitly enable dispatch.
- Fixture validation includes clean, violating, malformed-result, unsupported and tool-failure cases. Check that known deterministic fixes are suggested before expensive general agents.

**What I'd check.** Required/unknown params fail by rule name; upgrading a rule preserves historical meaning; preview matches subsequent admission if state is unchanged; closed PR outcomes survive restart; no claim of “total spend” when usage is partly unknown.

**Out of scope.** A marketplace, broad preset coverage for every language, automatic metric tuning.

**Null action.** Keep explicit project rules until a second concrete use justifies library extraction.

---

## 026 — Signed process evidence and optional repository ledger

**Intent.** Let a reader verify that a named Agentbox installation attested to specific inputs, outputs, checks and observed review outcomes. Do not claim independence from the installation/operator, comprehensive code attribution, software correctness or human understanding.

**What changes.**
- **Slice A:** sign a versioned execution statement after the candidate is sealed and checked. Use an established in-toto statement/DSSE envelope with an Agentbox-specific predicate rather than inventing signature canonicalization. This is not a SLSA compliance claim.
- The subject identifies the candidate commit/tree and output manifest. The predicate records request/run/attempt IDs, frozen spec or invariant identity, base SHA, effective-config and context hashes, image/check-bundle digests, individual check verdicts/assurance, candidate-authored tests, protected-path findings, attempt lineage and usage provenance.
- The evidence service owns the key; agents/checkers/publisher do not. Record signer/key ID, documented trust boundary, rotation history and revocation handling. Signature validity, signer trust and evidence completeness are separate verifier results.
- The signed candidate statement is stored outside the candidate tree under `$AGENTBOX_DATA/provenance/`, with a hash reference in the PR. This avoids a receipt containing the hash of the commit that contains itself.
- After publication and merge, append separately signed statements referencing the execution statement. Capture provider/source IDs, PR head, merge method, resulting commit/tree, observed actor and timestamp. A signed provider observation means “this installation observed this response”; it is not a provider signature or offline proof of the actor.
- Merge commits, squash and rebase are handled explicitly. Preserve the reviewed candidate identity; compare actual merged content and record the transformation. If equivalence cannot be established, show `unverified_transformation` and run new checks against the resulting tree. Do not require original commit SHAs to survive squash/rebase.
- Capture human rationale only from an explicit recorded review/field with author and source reference. A default merge message or arbitrary last comment is not automatically a rationale.
- **Slice B:** export immutable statements plus a derived ledger into a separate evidence branch, archive, or human-reviewed repository PR. No direct base push. Ledger-only changes do not recursively trigger more ledger PRs; derive them from new substantive outcome-event IDs, and classify evidence-maintenance commits separately.
- Replace Level 1/2/3 with independent dimensions: valid signature/trusted signer, intent linkage, checked candidate identity, protected-policy status, observed human admission, merge-content verification, post-merge check state, available/expired evidence. Optional tour/design signals remain separate.
- Attribution distinguishes known Agentbox proposals, externally managed proposals and unknown changes. Git author strings do not prove human or AI authorship. Scope any completeness claim to registered requests and the declared history interval.
- A standalone verifier accepts an evidence export plus repository snapshot/public keys; it validates signatures, hashes, subjects and claimed relationships that can be established offline. An optional online mode rechecks hosting observations. Report `verified|failed|unknown|not_applicable` per dimension, with missing dependencies stated.

**What I'd check.**
- Alter a signed statement or candidate file: verification fails. Rotate/revoke a key: cryptographic validity remains distinct from trust policy.
- Normal merge, squash and rebase produce appropriate identity relationships; none falsely assumes original SHAs remain on base.
- Adding merge metadata does not modify the original signed execution statement.
- A fresh offline export verifies artifact bindings but explicitly leaves unauthenticated hosting facts dependent on signer trust.
- A ledger PR does not initiate another identical ledger PR. Unknown authorship remains unknown.

**Out of scope.** Independent attestation without independent infrastructure, patent/quality certification, a universal assurance score, and direct writes to base.

**Null action.** Export local signed evidence when repository publication is unavailable. Missing evidence remains visible; never substitute a PR-body summary for a verified original without marking the loss.

---

## 027 — Optional code tours and sampled review

**Intent.** Help maintainers reconstruct the codebase and inspect a declared sample of changes, while avoiding claims that these mechanisms prove understanding.

**What changes.**
- Opt-in tours live at `.agentbox/tour/` plus `TOUR.md`, using CodeTour-compatible files. This subtree is explicitly authorable by documentation agents; `.agentbox/receipts/`, ledger exports and trusted policy remain protected.
- Structural checks validate paths/symbols, spec/ADR links, declared module coverage and staleness. They cannot determine the truth or clarity of prose; a reviewer/critic assessment remains separate.
- Candidate tours are checked against the candidate SHA; scheduled freshness scans use current base. File/line/hash fallback is explicit per language.
- Permit feature PRs to include directly relevant tour updates when the work order allows them. A separate tour-maintenance PR touches documentation only. Do not simultaneously require a tour in the feature PR and forbid mixing it with code.
- Deep review is opt-in with a declared weekly capacity. Freeze and record the eligible merged-request set, sampling algorithm/version, precommitted seed and selected IDs. Reproducibility alone is not proof that selection was unmanipulable; stronger sampling requires an independently sourced randomness commitment.
- Create one issue per selected change using a durable idempotency key. Completion requires a comment/record from a configured reviewer identity and the referenced revision, not merely issue closure.
- Track eligible changes, selected changes, completed sampled reviews and overdue reviews separately. Voluntary reviews are separate. A zero eligible denominator is N/A; a fixed one-review/week budget does not imply a fixed percentage at every throughput.
- Explain-back is optional and advisory. It may identify a contradiction; consistency is not evidence that a human personally understood or authored the explanation. No personnel ranking or certificate level follows from it.

**What I'd check.** Agent can update a tour but not receipts; feature PR tour references resolve on the feature SHA; repeating weekly sampling creates no duplicates; seed/eligibility changes are visible; issue closure without a qualifying review remains incomplete.

**Out of scope.** Proof of comprehension, mandatory quizzes, universal coverage quotas and gates on optional research metrics.

**Null action.** Keep a simple human-maintained tour and publish sample metadata without automated explain-back.

---

## 028 — Optional design fitness and scoped architecture decisions

**Intent.** Test declared architectural constraints and make authorized exceptions visible without mistaking proxy metrics for design quality.

**What changes.**
- Adopt a small set of relevant tools for the project's language: dependency direction/cycles, selected complexity/duplication measures, and API constraints. Each check states its supported scope, metric definition, units, tool version and baseline.
- Architecture declarations, the constitution and acceptance policy are trusted inputs. Agents may propose changes to those in a separate policy request; they cannot approve or use their own proposal as authorization for an implementation run.
- ADRs are accepted through the human workflow. Authorization records bind an accepted ADR revision/hash to permitted boundary paths/edges, request scope and any metric exception. Merely writing `ADR-0007` in a PR cannot authorize an unrelated change.
- Distinguish a declared boundary *change* from an implementation edit within an existing public module. Projects choose which changes require authorization; do not require an ADR for every ordinary file touch by default.
- If implementation encounters an undeclared boundary change, stop at `awaiting_operator` or publish draft evidence. Resume only against a new approved request/policy revision and rerun affected checks.
- Ratchets compare candidate and frozen base with the same tool, configuration and metric definition. Advance baselines only after merged-state verification. A winning unmerged branch never changes the repository baseline. Tool-version changes establish a new comparable series.
- Metric exceptions include scope, reason and permitted bound; one old ADR is not a permanent exemption. Historic churn concentration is a reporting metric unless a meaningful candidate comparison is explicitly defined.
- Diff size is advisory by default with generated/vendor changes separated. Do not encourage artificial PR splitting to satisfy an arbitrary universal threshold.
- Optional design critics store concerns and model/prompt version; cross-model numeric scores are not treated as comparable without calibration. Keep critique alongside deterministic results, not above them.
- Design evidence is an optional dimension in 026. Unsupported language rules display unsupported, not green.

**What I'd check.** A forbidden dependency fails; an unrelated accepted ADR does not authorize it; an appropriately scoped authorization does. A normal implementation edit inside an approved boundary needs no new ADR unless project policy says so. Ratchet baseline remains unchanged until merge and post-merge verification.

**Out of scope.** Certification of good design, autonomous ADR approval, universal metric ceilings and claims of numerical critic objectivity.

**Null action.** Run supported rules in observe mode and record coverage gaps. Do not fabricate layering enforcement.

---

## 029 — Execution foundation: shared contracts, isolation and recovery

**Intent.** Add the minimum reliable control plane needed before automated repository publication. Build on completed 007–009 and the delivered 010 layout; keep Dagster as scheduler/executor.

**What changes.**
- **Module boundary.** Extract a shared versioned configuration/domain package imported by UI and orchestrator. Separate configuration resolution, request admission, process supervision, check execution, artifact finalization and publication adapters. `factory.py` builds Dagster definitions and calls these services; it does not accumulate all new domain behavior.
- **Validation.** Parse each YAML inside a per-file error boundary; reject duplicate YAML keys, non-mappings, unsupported schema versions, invalid crons, duplicate generated identities and missing required values. One malformed file costs only that file; dependent definitions get an explicit unresolved-dependency error. Validate fully expanded configuration and graph before activation; retain the last known-good active generation on an invalid update and show the difference from saved config.
- **Path policy.** Canonicalize host paths after substitutions and verify allowed subroots, ownership and mount mapping. Being somewhere under `AGENTBOX_DATA` is insufficient: an output/workspace cannot target credentials, keys, run evidence, another request, product/config, or the root itself. Reject symlink escapes and unsafe ancestors. Wipes are confined to known disposable workspaces, never operator-computed broad roots.
- **Environment.** `DEST: ${SOURCE}` resolves SOURCE into an allowlisted DEST in the trusted subprocess environment; Docker argv contains `-e DEST`, never the value. Reserved controller variables cannot be overridden by run config. Generic agent env-file mounts cannot expose publisher/signing credentials. All launch and failure logs use the shared redactor.
- **Artifacts.** Give every attempt a new writable staging output directory and isolated candidate area. Stop writers, copy/validate safe files into controller-owned final storage, compute hashes/sizes, and atomically publish a manifest. No agent can mount prior final outputs writable. Legacy filenames may remain inside the unique run directory; readers use manifests, not a before/after shared-folder diff.
- **Supervision.** Persist container identity and request ownership before launch. Use bounded waits for startup, cancellation, timeout, kill and removal, handling all exits. On worker loss, reconcile containers by durable labels; do not launch a replacement while an old writer may exist. If stop cannot be confirmed, record unknown and retain the exclusive resource lease pending reconciliation.
- **Durable request state.** A local transactional store under `$AGENTBOX_DATA/control/` records request IDs, config snapshots, attempts, quota reservations, resource leases, operation intents and append-only outcome events. SQLite on local disk is sufficient for the initial single-host scope; do not depend on network-filesystem locking.
- **Stages.** Record `admitted → preparing → executing → checking → candidate_recorded`, followed by publication and human/post-merge states from 021. Terminal failures/cancellation and `awaiting_operator` are explicit. Committed state transitions use expected-version checks so duplicate Dagster deliveries do not create duplicate attempts.
- **Recovery protocol.** Persist intent, perform the external action, observe actual outcome, then acknowledge it. Restart reconstructs stage from the database plus container/Git/provider evidence. “Unknown” is recoverable state, not permission for a blind retry. Backups include the transactional store, referenced evidence and config; restore begins with reconciliation against external reality.
- **Admission limits.** Reserve request/attempt slots transactionally. Bound concurrent writers, launches/hour, request elapsed time, attempt count, output/log bytes and pending-review capacity. Monetary limits state whether enforced by provider/proxy or estimates; for unmetered subscriptions enforce time/attempt limits and mark money unknown. Manual actions cannot bypass hard isolation/resource limits.
- **Check contract.** A check envelope records schema version, check ID, target SHA/digest, check-bundle digest, verdict, violations with stable IDs, numeric value/units if applicable, timings and diagnostic reference. Explicit adapters map existing tool exit codes to fail versus infrastructure error; plain shell exits are not sufficient to make that distinction universally.
- **Independent checks.** Approved bundles are separately materialized read-only with controlled configuration/plugins/fixtures and fixed tool dependencies. Candidate acceptance-policy changes are detected before evaluation. A restricted credential-free check container can execute candidate code but cannot mutate trusted policy or persistent evidence. State the remaining test-model limitations.
- **Control-plane access.** Default management endpoints to a trusted local/private binding. Require an authenticated access boundary and CSRF protection before permitting remote mutation; the UI itself has no Docker socket, signing key, or publisher token. This is protection for the declared operator workflow, not a multi-tenant IAM project.
- **Integration boundary.** Reuse Dagster run IDs, Git operations, hosting APIs and existing check tools. If single-host restart tests cannot be made reliable with this bounded adapter, record an architecture decision before considering a durable-workflow dependency. Do not quietly grow a second general workflow language.

**Reporting follow-up to completed 007.** These are new requirements owned by 029; the historical 007 brief is not reopened.

- Keep the report object and current fields: status, token counts, nullable cost, turns, files written, transcript reference, error, and notes. Add a report schema version and provenance for measured versus orchestrator-authored fields. Preserve compatibility for existing readers.
- Drain and close the Pipes session before deciding that a final report is absent. Validate field types and required fields before using report values as Dagster metadata; missing or malformed reports become explicit protocol failures.
- The orchestrator owns execution exit status, timeout/cancellation state, artifact manifest, and host record references. A harness cannot convert a nonzero process exit into success by reporting `ok`.
- A failed asset attempt is recorded as an observation/failure event with evidence. Only successful production emits a success materialization. Blocking check outcomes remain separately recorded and gate downstream eligibility for that exact production.
- Logs pass through the redaction boundary before reaching Dagster or persistent storage (012/029). Job-only failures retain the same report even if no op output is emitted.

**Check hardening follow-up to completed 008.** These are new requirements owned by 029, preserving compatible existing declarations.

- Preserve existing check declarations. New checks use explicit `argv`, image digest, timeout, blocking flag, trusted check-bundle reference, and output format (`exit-code` or `violations-json`). Legacy shell commands remain supported only as explicit trusted-shell checks with their assurance limitation recorded; do not silently reinterpret them.
- Checks run in fresh credential-free containers. Candidate files and output manifests are read-only; temporary build/test products go into a separate disposable directory. The harness entrypoint is not implicitly reused as a check runner.
- Results include name, verdict, exit code, timeout/error, redacted bounded output, run/attempt ID, candidate SHA or artifact digest, check-bundle digest, configuration digest, and tool/image versions. JSON-producing checks use the common versioned violations contract defined in this brief.
- Distinguish `independent_acceptance` checks from `candidate_regression` checks that deliberately execute candidate test/config code. Both are useful, but only the former claims independently sourced acceptance policy.
- The trusted bundle pins test/observer code, runner configuration, discovery rules, fixtures, plugin policy, and tool dependencies. Mounting a base test file alone is insufficient. Explicitly disable unapproved candidate test plugins/config discovery; unsupported isolation yields an assurance limitation.
- Deterministic tools may execute candidate code in their sandbox. This is evidence under a declared test model, not a proof against arbitrary adversarial code. An untrusted output string cannot forge the control-plane result.
- Gate downstream use on checks for the exact artifact, partition, and attempt. A historical green check is not transferable to a later materialization.

**What I'd check.**
- Malformed YAML, a list document, invalid cron and duplicate names each leave unrelated agents usable; UI and runner accept/reject the same corpus.
- Simultaneous admissions at a limit accept only the available capacity. Duplicate scheduler delivery creates one logical request.
- Kill workers during launch, execution, finalization and checking; restart finds the existing resources and neither loses finalized evidence nor runs two writers.
- Deny Docker kill temporarily: the operation remains visibly unresolved and blocks replacement; cancellation is not falsely reported complete.
- An output path into keys, a symlink escape, and a wipe aimed at a shared/root directory are rejected.
- Known secrets do not enter argv or persistent logs. Per-attempt artifact identities are stable after finalization.
- A malicious candidate config/plugin cannot replace the approved acceptance runner; unsupported independent checking is explicit.
- Restore a backup after a remote branch was pushed: reconciliation finds the branch and resumes publication instead of producing a new candidate.
- Target-host integration tests use real containers, Pipes and file permissions; stub tests alone do not establish these boundaries.

- A deliberately delayed final Pipes message is retained after process exit; no timing-dependent missing-report classification.
- Missing fields, invalid numeric values, nonzero exit with `status: ok`, timeout, cancellation, and absent reports each produce an identifiable failure record.
- One smoke run per supported harness has real usage or explicit unknowns; subscription usage is not represented as zero dollars.
- A failed partition stays failed, the report remains accessible, and no dependent request treats it as a successful input.
- A check against attempt A cannot approve attempt B. A failed/timeout/malformed observer cannot be treated as a clean repository.
- An agent edits a candidate test to always pass: regression status may change, but protected acceptance results do not.
- A candidate adds a test plugin or loader configuration: the independent check rejects or ignores it according to the declared bundle.
- A build requiring temporary files succeeds without making the source mount writable. Output and stdout limits work.

**Out of scope.** Multi-host scheduling, arbitrary workflow DSLs, perfect exactly-once effects, adversarial tenant isolation, enterprise identity management.

**Null action.** Keep repository automation manual/export-only until the required lifecycle tests pass. Existing simple jobs can continue with clearly documented limitations. Retain the mounted-file Pipes transport when needed to preserve isolation flags; unsupported report protocols keep their failure evidence. If Dagster cannot display per-partition check state, enforce exact-artifact gating using the common check record. If independent checking cannot be established, record `unsupported` for that assurance requirement and require human disposition.

---

## 030 — Feature work orders: building the codebase

**Intent.** Make bounded feature development and migrations first-class alongside maintenance. An approved specification becomes a proposed code change with independent acceptance evidence and an explicit human decision.

**What changes.**
- Add `config/work-orders/<id>.yaml` with stable ID, project/repository alias, spec path or frozen issue snapshot, spec digest, target base ref, implementation agent or deterministic actuator, allowed change scope, acceptance-bundle reference, existing regression checks, human acceptance criteria, documentation obligations, budget/timeout, dependencies and publication policy.
- A work order starts as `draft`. An explicit operator admission records the approved spec, policy and permissions plus resolved base SHA. Editing any of these creates a new revision requiring admission; the agent cannot expand its own scope.
- Large-spec decomposition may generate draft work orders, but children are not automatically approved. Initially run one bounded task at a time; a dependent task becomes eligible only after its prerequisite is human-merged and required post-merge checks pass.
- If independent feature acceptance tests do not yet exist, support a preparation step that proposes them. An operator approves the bundle before implementation admission. Existing tests remain regression evidence; newly agent-authored tests are labeled candidate tests and never promoted into trusted policy automatically.
- Natural-language criteria remain a checklist for human review. An advisory critic can compare the candidate with the spec, identify omitted criteria and raise design concerns, but cannot declare semantic completeness or override a required check.
- Execute through 029/020, check through 029's hardened contract extending completed 008, publish through 021 and attach 026A evidence. No separate “feature agent” orchestration engine. Model escalation (019) is optional.
- The PR maps each acceptance criterion to a check result, demonstration/artifact, advisory finding, or `requires human evaluation`. Include scope deviations, migration/compatibility/rollback evidence where requested, and limitations. Use `checks_passed` rather than claiming the spec is proven.
- Ordinary code and implementation-test changes inside scope are allowed. Acceptance bundles, architecture policy and approved spec revisions remain outside agent authority. Boundary changes pause for the human process in 028 only where that project has enabled it.
- Unclear or conflicting requirements lead to `awaiting_operator` with a focused question and preserved candidate. A failed test whose trusted expectation contradicts the approved spec requests policy correction instead of endless model escalation.
- Human PR merge records admission of the code. Required post-merge CI/acceptance runs bind to the resulting repository SHA. Complete the work order only after those results are known and required conditions pass; otherwise mark `merged_verification_failed` or `merged_verification_unknown` and surface it without automatic rollback.

**What I'd check.**
- A real bounded feature, such as adding an optional output format to an API, starts from an approved spec and produces implementation, candidate tests, independent acceptance results, docs and one PR.
- Candidate code passes automated checks but omits a human criterion: the PR shows that criterion unresolved instead of claiming full acceptance.
- An agent changes its acceptance test or widens the allowed scope: ready status is blocked; ordinary new unit tests remain permitted.
- A migration work order supplies compatibility and rollback evidence; no production migration is executed merely because implementation is approved.
- A second task depends on the first: it starts from the newly observed base after human merge and post-merge success, not from a sibling unmerged branch.
- A publisher restart does not repeat implementation. Closing without merge stops the request; a revision requires a new admitted identity.
- Compare the pilot's total human spec/review/rework time with the direct-agent-plus-CI baseline before expanding task volume.

**Out of scope.** Autonomous product prioritization, unapproved task decomposition, automatic merges, automatic deployments, and treating passing tests as proof of design quality.

**Null action.** Deliver a checked local patch and evidence, or pause for clarification, when publication, trusted acceptance or scope cannot be established.

---

## Cross-brief acceptance scenarios

These scenarios are the integration gate for the proposed core, not a request to implement every optional feature.

1. **Bounded feature.** Approved work order → isolated candidate → independent acceptance plus candidate regression checks → signed candidate evidence → one PR → human merge → verification of resulting SHA.
2. **Maintenance without churn.** Observe-only rule → explicit dispatch enablement → one bounded repair → repeated scans suppress duplicates → human closure triggers cooldown/refusal rather than replacement spam.
3. **Failure recovery.** Interrupt each external stage, including an ambiguous push/PR response. The restored controller reconciles identity, preserves evidence and never launches a duplicate writer.
4. **Judge tampering.** Candidate alters acceptance loader/config/tests or tries to execute a privileged Git hook. It cannot modify the trusted bundle, publisher or signer; the request records the attempted policy change.
5. **Stale success.** Change PR head or base after checks. Old results remain historically valid but cannot be presented as current acceptance; post-merge verification targets the actual resulting tree.
6. **Honest evidence.** Unknown cost, missing tool results, unsupported architecture tools, unverified squash transformation and absent review rationale remain visible as distinct gaps.
7. **Human capacity.** Fill the review queue. New automated proposals pause even if agents and model budget are available. Measure whether the accepted work saved human effort after setup and review costs.

## Migration and compatibility notes

- This proposal is documentation only. Adopt individual briefs through the existing SDD workflow after reconciling them with delivered specs, especially 010; do not rerun completed migrations.
- Preserve existing agent schemas through explicit versioned adapters. Runtime records gain schema versions; immutable historical records remain readable without in-place rewrites.
- Keep existing job-only agents and artifact-only assets usable. Repository publication requires the stronger request/check/publisher contract; do not silently grant that authority to legacy jobs.
- Split configuration authority from UI presentation metadata in the shared package. Existing schema-driven forms remain consumers; extraction is not a reason to replace the UI framework.
- Optional governance cannot become an undeclared prerequisite for building a feature. The core always records its enabled checks and limitations.
- Architectural tradeoffs remain reviewable proposals: independent clones first, a bounded single-host request store, standard attestation envelopes, optional governance, and explicit authority changes. Each can evolve through evidence from the pilot without changing the product's human-admission boundary.
