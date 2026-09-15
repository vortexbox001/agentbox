# Phase 0 Research: Run Transparency

Decisions that resolve the plan's unknowns. Each: **Decision / Rationale / Alternatives**.
No `NEEDS CLARIFICATION` remain — the spec's five clarifications (redact transcript too; Files =
output artifacts; prune keeps outputs; filter by agent/status/date; Compare any two runs) are
already resolved and are treated as fixed inputs here.

---

## R1 — Run directory layout & migration

**Decision.** A run is a **directory**, `$AGENTBOX_DATA/runs/<agent>/<YYYY-MM-DD>/<run-id>/`,
containing exactly:
- `transcript.jsonl` — the native harness stream, byte-identical to today's capture (redacted).
- `events.jsonl` — the normalized event stream (one JSON object per line).
- `context.json` — the frozen launch snapshot.
- `report.json` — the spec-007 run report (same shape; now co-located, not only in metadata).

Today's flat `runs/<agent>/<date>/<run-id>.jsonl` becomes `.../<run-id>/transcript.jsonl`. The
viewer reads the new directory form; a legacy flat `.jsonl` still on disk is surfaced as a
**transcript-only** run (no events/context/report), rendered with the same "conversation only"
degradation the pruned case uses. No bulk migration job — old runs age out under retention.

**Rationale.** FR-001 mandates one per-run home holding all four artifacts, and it is the unit of
retention (FR-027) and the viewer's source of truth (FR-018). A directory makes pruning a
per-file delete and makes partial-write tolerance (edge case) a simple "render the files that
exist." Reusing the existing `<agent>/<date>/` prefix keeps the README compat symlink
(`agent-logs -> runs`) and the debugging runbook paths meaningful.

**Alternatives.** (a) Keep a flat file per artifact (`<run-id>.events.jsonl`, …) — rejected:
pruning and per-run enumeration get fiddly and the "one home" invariant blurs. (b) A migration
job to rewrite old runs — rejected as unnecessary work for data that ages out; graceful
degradation covers it.

---

## R2 — Who produces normalized events (FR-003)

**Decision.** Each harness **image** owns the native→normalized translation, exactly like the
spec-007 report. Add `images/lib/agent_events.py` (the `NormalizedEvent` dataclass, the JSONL
writer, the OUTPUT/timestamp helpers) and give each wrapper a `to_events(lines)` beside its
existing `parse(lines)`:
- `agent-claude`: map `system`(init) → system, each `assistant` block → assistant / tool_call,
  each `user` `tool_result` → tool_result, final `result` → final.
- `agent-codex`: `turn.*`/`item.*` (reasoning, agent_message, tool items) → assistant/tool_*,
  `error` → error, terminal message → final.
- `agent-pi`: the `message` events and the `agent_end` `messages[]` (content blocks incl. tool
  use) → the stream; usage per assistant message.
- `agent-python`: no CLI stream — synthesise system + user(prompt) + assistant(text) + final
  from the single LiteLLM request/response.

`run_wrapper` (in `agent_report.py`) is extended so the CLI harnesses call both `parse` and
`to_events` from the teed lines; the api runner calls `to_events` inline. The image writes
`events.jsonl` to the ephemeral staging mount (R4); the orchestrator redacts + moves it.

**Rationale.** FR-003 and Constitution IV: no per-harness parsing in the orchestrator. The
image already holds the native-event knowledge (its `parse`), so the events translator is a
sibling. A future harness gains the Conversation view by shipping `to_events` in its image.

**Alternatives.** (a) Orchestrator parses each native stream into events — rejected, violates
FR-003/SC-002 and re-introduces the coupling spec 007 removed. (b) Emit events over Dagster
Pipes like the report — rejected: an event stream is transcript-scale, unsuited to the messages
channel; a file on the staging mount is cheaper and is what the redaction pass consumes.

---

## R3 — Context-snapshot authorship (FR-009..012)

**Decision.** Split by who knows the fact, merged by the orchestrator:
- **Orchestrator-authored** (it builds the `docker run` argv, so it knows these first-hand):
  effective prompt text as sent; appended system-prompt text; model / effort / fallback; harness
  + version; image identity (digest, R10); tool allow/deny + permission mode; MCP server config;
  env var **names** only; mounts + modes; network; memory/CPU caps; working dir; and — for asset
  runs — asset key, partition, variant, upstream handoff inputs, attempt number. Plus the
  workspace/output **file trees** at start (paths + sizes), snapshot before launch.
- **Image-contributed fragment** (`context-harness.json` on the staging mount): the instruction
  files the harness actually loaded, each with path + full contents (claude-code: the `CLAUDE.md`
  hierarchy reachable from `/workspace` and `CLAUDE_CONFIG_DIR`; codex: `AGENTS.md`; pi: its
  instruction files; api: none); the tools each MCP server exposed; and the **completeness
  statement** (claude-code/codex: vendor base system prompt undisclosed; pi/api: complete).

The orchestrator merges the fragment into `context.json`, runs the redaction pass, and writes it
into the run directory at launch (before, or concurrently with, the container running).

**Rationale.** FR-012's completeness statement and "every instruction file the harness loaded"
are harness-specific and belong with the image (same principle as R2/FR-003). Everything else is
already computed in `_build_agent_cmd`/`make_run_op` and is authoritative there. Splitting avoids
the orchestrator guessing at instruction files and avoids the image duplicating launch config it
never sees.

**Alternatives.** (a) Container writes the whole snapshot — rejected: it does not know the host
mount sources, image digest, or resource caps as launched. (b) Orchestrator infers loaded
instruction files by re-implementing each CLI's discovery rules — rejected: fragile and re-adds
per-harness logic to the orchestrator.

---

## R4 — Redaction: single pass, shared heuristic (FR-013..016)

**Decision.** One redaction function, `redact(text) -> text`, that finds secret-like tokens with
the **same heuristic as `ui/secret_scan.py`** (name/prefix/high-entropy rules) and replaces each
match with `[REDACTED:<kind>]` (kinds: `api_key`, `token`, `password`, `private_key`,
`credential`, `secret`, `high_entropy`). It lives in `orchestrator/redact.py`, built on the
detection primitives shared with `secret_scan.py`; the UI keeps `secret_scan.py` and gains a thin
redact twin for defense-in-depth display. The **orchestrator owns the single pass**: it redacts
each `transcript.jsonl` line as it streams (and before forwarding to the Dagster log), and
redacts `events.jsonl` and `context.json` as it moves/writes them into the run directory. The
container never writes into the run directory (Constitution V) and never emits env **values**, so
nothing secret reaches the run directory unredacted, and env values never reach disk at all
(FR-015).

**Rationale.** FR-013 says all three files "pass through a shared secret heuristic before being
written." A single orchestrator-owned pass is the literal reading and the simplest place to
guarantee `SC-004` (grep the whole directory → nothing). Reusing the existing heuristic is an
explicit spec assumption.

**Cross-container duplication (accepted, precedented).** The detection heuristic exists in the UI
(`secret_scan.py`, mirrored in `agent-form.js`) and now in the orchestrator (`redact.py`). The
two run in separate containers with no shared import; pin them with a shared-fixture parity test,
exactly as `paths.py`↔`config.py` and `ASSET_KEY_RE` are pinned today.

**Alternatives.** (a) Each writer redacts its own file (image redacts events, orchestrator
redacts transcript) — rejected: puts the heuristic in the images too and risks divergence; the
single-pass reading of FR-013 is cleaner. (b) Redact only on display in the UI — rejected:
violates FR-016/SC-004 (secret would remain on disk).

---

## R5 — Normalized event schema (FR-004..008)

**Decision.** One line-delimited JSON schema, kinds: `system`, `user`, `assistant`, `tool_call`,
`tool_result`, `final`, `error`. Every event carries `kind`, `ts` (ISO-8601), `turn` (int), and
optional `tokens_in`/`tokens_out`/`cost_usd` where the harness reports them — **`null` means "not
reported", kept distinct from a real `0`** (same rule as the spec-007 report numerics). Kind
specifics: `assistant`/`user`/`system`/`final` carry `text`; `tool_call` carries `tool` + `args`
(object); `tool_result` carries `result` (string) and, for a file edit, `diff` (unified-diff
text), and may set `"missing": true` (FR-008) when the harness cannot produce a faithful result.
Order is preserved and content is never summarized (FR-007). Full schema in
`contracts/normalized-event.schema.json`.

**Rationale.** This is the uniform surface (`SC-002`) the Conversation view renders identically
for every harness. Unified-diff-as-text lets the UI render diffs client-side without a
server-side differ. The null-vs-zero rule matches the operator's existing mental model from the
report metadata.

**Alternatives.** A richer typed AST per block — rejected as over-engineered; the seven kinds
cover every harness's native stream and keep the images' `to_events` small.

---

## R6 — Viewer reads run directories from disk (FR-017/018)

**Decision.** Add `ui/runs_store.py`, a pure disk reader: `list_runs(filters)` scans
`runs/<agent>/<date>/<run-id>/` and reads only `report.json` + `context.json` headers to build
list rows (agent, time, status, model, cost, attempts); `read_run(id)` loads the four files for
the detail page, tolerating any missing file. The UI mounts `$AGENTBOX_DATA` **read-only** (a new
mount — today the ui service has none; see `docker-compose.yml:99`). Run directories are
root-owned `0755`/files `0644` (world-readable), so the ui service (uid 1000) can read them. The
list and run pages never call Dagster, so they render with the orchestrator stopped (`SC-007`);
Dagster is still used, best-effort, only to *enrich* rows with live status when reachable. FR-002
adds a `run_dir` link to the run/materialization metadata in `build_metadata`.

**Rationale.** FR-018/SC-007 require disk-only operation precisely when the orchestrator is down.
A dedicated store keeps the disk-read contract in one testable module, mirroring how
`agents_store.py` isolates YAML access.

**Alternatives.** Read runs from Dagster's GraphQL/SQLite — rejected: unavailable when the
orchestrator is stopped, and the SQLite is WAL-locked (per the debugging runbook).

---

## R7 — Retention & the nightly prune job (FR-025..029)

**Decision.** `settings.yaml` gains a `retention` block: `{ mode: keep_forever | prune_after_days,
days: N }`, default `keep_forever`. `ui/settings_store.py` reads/writes it; the Settings page
edits it. The orchestrator registers a **nightly Dagster schedule** running `prune.py`, which for
each run directory older than N days removes **only** `events.jsonl` and `transcript.jsonl` and
leaves `report.json`, `context.json`, and the run's `/output` artifacts (FR-027). A run whose
`events.jsonl`/`transcript.jsonl` are gone still opens; the Conversation tab shows a "conversation
pruned" note (FR-028). Output artifacts are never pruned by this policy (clarification).

**Rationale.** Config-over-code (Constitution II): the policy is declarative and the job is
generic. Registering the schedule in the job factory matches how every other schedule/sensor is
wired. Keeping report+context+outputs preserves the audit record and the Files tab after pruning.

**Alternatives.** A host cron/systemd timer — rejected: the orchestrator already owns scheduling,
and a Dagster schedule is visible/toggleable alongside agent schedules. Pruning whole directories
— rejected: violates FR-027 (report/context/outputs must survive).

---

## R8 — Compare (FR-023)

**Decision.** `GET /runs/compare?a=<id>&b=<id>` loads both `context.json` files and renders a
field-by-field diff (added/removed/changed), any two runs allowed; same-agent reruns are the
primary case and render cleanly (a single changed field shows exactly one difference, `SC-005`).
Harness-specific fields present in only one snapshot are shown as present-on-one-side, never
implied equivalent (edge case). Comparison is over the snapshots only, not events.

**Rationale.** The snapshot is already the frozen, normalized record; a structural diff over it
is deterministic and needs no orchestrator. Reuses the disk reader from R6.

**Alternatives.** Diffing transcripts/events — rejected: out of scope (spec scopes Compare to
context) and noisy.

---

## R9 — Design-system additions (Constitution VII)

**Decision.** Follow the established four-step promotion for each new piece, in order: (1) add/extend
the specimen under `ui/design-system/templates/run-detail/` (the specimen already prototypes the
timeline, tool-call cards, `ax-diff-add/del`, context rows, env pills, checks, and the
`ax-btn--dagster` variant — reuse its markup as the design source); (2) put the CSS in the
design-system master `ui/design-system/static/app.css`; (3) copy it byte-for-byte into
`ui/static/app.css` (enforced by `test_design_system_sync.py`); (4) add shared Jinja macros in
`ui/templates/components/macros.html` and consume them from the page templates. New macros:
`run_stat_strip`, `timeline` + `timeline_entry`, `tool_call` (collapsible), `diff_block`,
`context_kv` / `context_section`, `env_pill`, `file_row`, and a tab-panel behaviour (the existing
`tabs` macro emits only the tablist; panel switching is net-new JS in `run-detail.js`). Finish the
half-landed `ax-btn--dagster` variant (add to served CSS + a `button` macro intent).

**Rationale.** Principle VII requires design-system-first, macro-second; the hygiene tests
(`test_conformance.py`, `test_ui_consistency.py`) will fail otherwise. The specimen gives the
visual target and most of the CSS already.

**Alternatives.** Inline styles / bespoke markup in the page templates — rejected: forbidden by
Principle VII and the conformance gate.

---

## R10 — Container image identity (digest) for the snapshot (FR-009)

**Decision.** The orchestrator resolves the launched image's digest with
`docker image inspect --format '{{index .RepoDigests 0}}' <ref>` (falling back to `.Id` when the
image was built locally and has no repo digest), captured once per launch into `context.json`.

**Rationale.** FR-009 requires "container image identity (digest)". The orchestrator already
shells out to `docker`; one inspect at launch is cheap and authoritative. Local `latest` builds
have no RepoDigest, so `.Id` (the local image ID) is the honest fallback.

**Alternatives.** Record only the `:latest` tag — rejected: a tag is not an identity and defeats
the audit purpose. Read from the running container — rejected: `--rm` and timeouts make it racy;
inspect the image ref instead.
