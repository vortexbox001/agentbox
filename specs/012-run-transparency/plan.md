# Implementation Plan: Run Transparency — Conversation View and Context Snapshot

**Branch**: `012-run-transparency` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/012-run-transparency/spec.md`

## Summary

Turn every run into something an operator can read and audit entirely from the management
UI. Three capture additions land around the run, and one viewer surface reads them back:

1. **Run directory** — every run writes to `$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`
   holding four files: the native `transcript.jsonl`, a harness-agnostic `events.jsonl`, a
   `context.json` snapshot frozen at launch, and the spec-007 `report.json`. (Today a run is a
   single flat `<run-id>.jsonl`.)
2. **Normalized events** — each harness *image* translates its own native stream into one
   uniform event schema (`images/lib/agent_events.py` + a `to_events()` per wrapper/runner);
   the orchestrator keeps zero per-harness parsing, exactly as with the spec-007 report.
3. **Context snapshot** — the orchestrator writes the launch-known context (prompt, model,
   tools, mounts, env *names*, caps, image digest, asset details, file trees); each image
   contributes a small harness-known fragment (loaded instruction-file contents, MCP tools
   exposed, completeness statement). A single **redaction** pass owned by the orchestrator runs
   the shared secret heuristic over transcript + events + context before they land in the run
   directory, so the whole directory is secret-free and env values never touch disk.

The **viewer** is a new disk-backed area in the FastAPI UI: a filterable Runs list and a run
page with Conversation / Context / Report / Files tabs, a Compare action over two context
snapshots, and a Settings page whose Retention section drives a nightly prune job. The list and
run pages read run directories directly, so they work while the orchestrator is stopped.

## Technical Context

**Language/Version**: Python 3.12 (UI, orchestrator, harness images — matches `ui/Dockerfile`);
Jinja2 templates; vanilla ES-module JavaScript over design-system CSS tokens; Bash for scripts.

**Primary Dependencies**: FastAPI + Jinja2 + httpx (UI); Dagster 1.13.21 + `dagster-pipes`
(orchestrator, pinned); PyYAML. Harness CLIs unchanged (claude-code, codex, pi, python runner).
No new runtime service. Diff and markdown rendering are done client-side from strings the
capture layer already produced (unified-diff text; report/notes markdown) — no new server dep.

**Storage**: Filesystem only. Run directories under `$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`;
instance settings in `$AGENTBOX_CONFIG/settings.yaml`. No database; Dagster's own SQLite is
untouched and is **not** a source for the viewer.

**Testing**: pytest across three suites — `ui/tests` (FastAPI `TestClient`, run via
`../.venv/bin/python -m pytest -q`), `orchestrator/tests`, `images/tests` (per-harness
event/report fixtures). Design-system hygiene gates in `ui/tests` (`test_conformance.py`,
`test_ui_consistency.py`, `test_design_system_sync.py`).

**Target Platform**: Linux arm64 (Raspberry Pi, Debian Bookworm/Trixie), Docker Compose;
agent containers launched Docker-outside-of-Docker via the mounted socket.

**Project Type**: Web — FastAPI management UI + Dagster orchestrator, plus four harness
container images. Single project tree with three service roots (`ui/`, `orchestrator/`,
`images/`).

**Performance Goals**: No latency SLA. The Runs list must build from disk in one pass over run
directories (read `report.json`/`context.json` headers only; never parse `events.jsonl` for the
list). The Conversation view must stay navigable for large transcripts via collapsible sections
and in-page search rather than rendering a wall of text.

**Constraints**: Constrained single-board host. The viewer must render with the orchestrator
stopped (disk-only). Docker-outside-of-Docker: every capture mount source must resolve on the
*host* filesystem (under a host==container bind mount), never container-private `/tmp`. Secrets
must never reach disk in cleartext anywhere in the run directory; env values never at all.
PEP-668 host — use the project `.venv` (Python 3.12), never a bare `pip install`.

**Scale/Scope**: Single operator; tens–hundreds of runs per agent; four harnesses today, future
harnesses conform to the same normalized-event contract. Five prioritized user stories (P1–P3).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| **I. Agent Isolation** | PASS. The only new agent-facing surface is one ephemeral, host-shared *staging* mount (reused/adjacent to the existing `/pipes` dir) that the image writes `events.jsonl` + the harness context fragment to. It is not `/output`, is `--rm`-cleaned per run, and grants no new network or credential reach. Checks and launch isolation are unchanged. |
| **II. Configuration over Code** | PASS. Retention is declarative (`settings.yaml`); the prune job is generic orchestrator infrastructure, not per-agent code. Adding an agent still needs only YAML; a new harness gains transparency purely by its *image* emitting the normalized-event contract — no orchestrator edit. |
| **III. Secrets Never in the Open** | PASS (strengthens). A single redaction pass over transcript + events + context; env captured as names only (FR-015); `SC-004` verifies no cleartext secret survives in the run directory. |
| **IV. Uniform Interface, Diverse Runtimes** | PASS (embodies). The normalized-event schema *is* the uniform surface; the viewer has one shape for every harness (`SC-002`). Adding a runtime does not change the schema. |
| **V. Ephemeral Runs, Immutable Outputs** | PASS. The run directory is written once by the orchestrator (capture, not agent output) and is immutable after the run; the container still writes only to `/output` + ephemeral staging; the viewer is strictly read-only (FR-024). Pruning bounds disk but always keeps outputs, report, and context. |
| **VI. Docs Track Reality** | PASS. README Layout + a new Retention section (FR-029); the debugging runbook in `CLAUDE.local.md` reflects the new directory. |
| **VII. One Design System** | PASS, and this is the largest compliance workstream. Every viewer screen composes design-system macros over tokens; no literals, no inline styles. New components (transcript timeline, tool-call card, diff block, context key/value + env pills, file browser, tab-panel behaviour, the `ax-btn--dagster` variant) **land in the design system first**, then the shared macros in `ui/templates/components/macros.html`, then the CSS synced into `ui/static/app.css` (byte-equal, `test_design_system_sync.py`), then the page templates. |

No violations require Complexity Tracking. Two deliberate, precedented duplications are noted in
Phase 0 (R2/R4): the shared secret heuristic and the run-directory-layout constants live in more
than one container image with no shared import, following the existing `paths.py`↔`config.py` and
`ASSET_KEY_RE` parity-test pattern.

## Project Structure

### Documentation (this feature)

```text
specs/012-run-transparency/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions R1–R10
├── data-model.md        # Phase 1 — entities & schemas
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── contracts/           # Phase 1 — the durable contracts
│   ├── run-directory.md              # layout, file set, migration, retention interplay
│   ├── normalized-event.schema.json  # the uniform event schema (FR-004..008)
│   ├── context-snapshot.schema.json  # the frozen launch snapshot (FR-009..012)
│   ├── redaction.md                  # heuristic, kinds, single-pass ownership (FR-013..016)
│   ├── viewer-routes.md              # UI routes + disk-read contract (FR-017..024)
│   └── settings.md                   # settings.yaml retention schema + prune job (FR-025..029)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
images/
├── lib/
│   ├── agent_report.py          # (exists) spec-007 report shape + Pipes emit
│   └── agent_events.py          # NEW: normalized-event dataclass, schema, JSONL writer,
│                                #      instruction-file enumeration helpers
├── agent-claude/wrapper.py      # + to_events(lines) + context fragment
├── agent-codex/wrapper.py       # + to_events(lines) + context fragment
├── agent-pi/wrapper.py          # + to_events(lines) + context fragment
├── agent-python/runner.py       # + synthesised events + context fragment (no CLI stream)
└── tests/                       # + per-harness to_events() fixtures/tests

orchestrator/
├── paths.py                     # + run-directory path helpers (dir, not flat file)
├── factory.py                   # run-dir assembly, context.json authorship, redaction pass,
│                                #   metadata link to run dir; register the nightly prune job
├── redact.py                    # NEW: shared secret redactor (heuristic → [REDACTED:<kind>])
├── run_capture.py               # NEW: context-snapshot builder + run-dir writer (from factory)
├── prune.py                     # NEW: retention prune logic (events+transcript only)
└── tests/                       # + capture/redaction/prune tests

ui/
├── config.py                    # + settings.yaml path + DATA_ROOT runs access
├── runs_store.py                # NEW: disk reader — list runs, read one run's files
├── settings_store.py            # NEW: read/write config/settings.yaml (retention)
├── main.py                      # + /runs, /runs/{id}, /runs/compare, /settings routes + APIs
├── secret_scan.py               # heuristic reused by redact.py (parity-tested twin)
├── templates/
│   ├── base.html                # + Runs + Settings nav items (reserved slots exist)
│   ├── runs/list.html           # NEW (tabbed-list pattern)
│   ├── runs/detail.html         # NEW (Conversation/Context/Report/Files tabs)
│   ├── runs/compare.html        # NEW
│   ├── settings/page.html       # NEW (Retention section)
│   └── components/macros.html   # + new macros (timeline, tool_call, diff, kv, file_row, …)
├── static/
│   ├── app.css                  # + viewer CSS (synced from design-system master)
│   ├── runs-list.js             # NEW
│   ├── run-detail.js            # NEW (tab-panel switching, collapse, search)
│   └── settings.js              # + retention form
└── design-system/               # new components land here FIRST (specimens + tokens + master CSS)

docker-compose.yml               # + read-only $AGENTBOX_DATA mount into the ui service
README.md                        # + Retention section; Layout run-directory update
```

**Structure Decision**: Keep the existing single-tree, three-service layout (`images/`,
`orchestrator/`, `ui/`) and the three-root path discipline. Capture code is split by ownership:
per-harness event/instruction translation lives in the images (FR-003), the run-directory
assembly + redaction + context authorship live in the orchestrator, and the read-only viewer +
settings live in the UI. This mirrors how spec 007 split the run report (shape shared in
`images/lib`, parsing in images, metadata union in the orchestrator).

## Complexity Tracking

No constitution violations. No entries required. The two cross-container duplications (secret
heuristic; run-directory layout constants) are governed by the existing parity-test pattern and
are documented in research R2/R4 rather than tracked as complexity.
