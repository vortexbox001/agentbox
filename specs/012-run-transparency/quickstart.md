# Quickstart: Validating Run Transparency

Runnable validation scenarios that prove the feature works end-to-end, one per user story plus
the cross-cutting redaction guarantee. Assumes the stack is built and running
(`docker compose up -d`) unless a step says otherwise. UI tests run from the repo root with the
project venv: `cd ui && ../.venv/bin/python -m pytest -q`.

References: `contracts/*` for shapes; `data-model.md` for entities; `research.md` for decisions.

## Prerequisites

- `docker compose build` after image/orchestrator/UI changes; `docker compose up -d`.
- Dagster UI at http://10.0.0.100:3000; management UI at http://10.0.0.100:8080.
- The ui service must mount `$AGENTBOX_DATA` read-only (new mount — see `docker-compose.yml`).

---

## Scenario 1 — Read a run's conversation, every harness (US1, P1)

1. Materialize/run one agent on each harness: an `api`/`pi` agent, a `claude-code` agent, a
   `codex` agent (the `hello-*` agents already exist).
2. For each, confirm the run directory now has all four files:
   ```bash
   ls "$AGENTBOX_DATA"/runs/<agent>/<date>/<run-id>/
   # -> context.json  events.jsonl  report.json  transcript.jsonl
   ```
3. Open each run at `/runs/<run-id>` → **Conversation** tab. Expect the **same threaded shape**
   for every harness: turns in order, collapsible tool calls with args + results, per-turn tokens
   and cost, and in-page search (SC-002).
4. For the claude-code run: every tool call present in `transcript.jsonl` appears in the
   Conversation view, each with its result, and a file edit renders **as a diff** (SC-003, FR-020).
5. Force a missing tool result (a harness event with no faithful result) → the turn is marked
   **missing**, not hidden or reconstructed (FR-021/FR-008).

**Automated**: `images/tests` — per-harness `to_events()` fixture tests assert kinds/order/diff
for each native stream; `ui/tests/test_runs.py` asserts the detail page renders the same
components for a fixture run of each harness.

---

## Scenario 2 — Inspect the starting context (US2, P1)

1. Open a `claude-code` run → **Context** tab. Expect: tools, MCP servers + their exposed tools,
   model, and the **full contents** of every loaded instruction file (e.g. `CLAUDE.md`), plus a
   completeness statement naming the **vendor base system prompt** as undisclosed (SC-008).
2. Open a `pi`/`api` run → Context tab. Completeness states the snapshot is **complete** (SC-008).
3. Any run: environment variables appear as **names only** — no values in the tab or on disk:
   ```bash
   python3 -c "import json;print(json.load(open('.../context.json'))['runtime']['env_names'])"
   grep -R "<a real secret value>" .../context.json   # -> no match
   ```
4. An asset run's Context shows asset key, partition, variant, upstream inputs, attempt (FR-011).

**Automated**: `orchestrator/tests` — context builder produces every FR-009 field; env values
never present; completeness per harness. `ui/tests` — Context tab renders instruction-file
contents + completeness.

---

## Scenario 3 — Browse and open runs with the orchestrator stopped (US3, P2 / SC-007)

1. Stop the orchestrator: `docker compose stop dagster-webserver dagster-daemon`.
2. Open `/runs`. Expect the list to render **from disk**: agent, time, status, model, cost,
   attempts (FR-017).
3. Apply filters — by agent, by status, by date range — and confirm the list narrows
   (clarification).
4. Click a run → its detail page opens with Conversation / Context / Report / Files tabs, all
   rendering from disk (FR-019).
5. Restart the orchestrator; confirm list rows now also carry live status enrichment.

**Automated**: `ui/tests` — `runs_store.list_runs`/`read_run` against a temp run tree (no Dagster
stub reachable) returns rows and detail; route tests use the `client` fixture.

---

## Scenario 4 — Compare two runs (US4, P3 / SC-005)

1. Run an agent; rerun it changing **only** its effort.
2. Open `/runs/compare?a=<run1>&b=<run2>`. Expect the field-by-field context diff to show
   **exactly one** difference (effort) and no spurious differences (SC-005).
3. Compare two different-harness runs → differences shown field by field without implying false
   equivalence for harness-specific fields (edge case).

**Automated**: `ui/tests` — compare over two fixture `context.json` files differing by one field
asserts a single diff row.

---

## Scenario 5 — Control run retention (US5, P3 / SC-006)

1. On the Settings page, set Retention → "prune after 1 day"; confirm it persists to
   `config/settings.yaml`:
   ```bash
   grep -A2 retention "$AGENTBOX_CONFIG"/settings.yaml
   ```
2. Back-date a run directory (`touch -d '3 days ago'` its day dir) and run the prune job (trigger
   `sched_prune_runs` or call `orchestrator/prune.py`).
3. Confirm `events.jsonl` and `transcript.jsonl` are **gone** while `report.json`,
   `context.json`, and the run's `/output` artifacts **remain** (FR-027).
4. Open the pruned run: Context and Report render; the Conversation tab shows a **"conversation
   pruned"** note (FR-028 / SC-006).
5. With retention at the default (`keep_forever`), the job is a no-op and nothing is pruned
   (FR-025 default).

**Automated**: `orchestrator/tests/test_prune.py` — back-dated fixture run: prune removes only the
two files, keeps the rest; `keep_forever` is a no-op. `ui/tests` — pruned run renders the note.

---

## Cross-cutting — Redaction guarantee (SC-004 / FR-013..016)

1. Run an agent whose prompt/instruction file/tool result contains a fake API key
   (e.g. `sk-ant-<fake>`).
2. After the run:
   ```bash
   grep -R "sk-ant-<fake>" "$AGENTBOX_DATA"/runs/<agent>/<date>/<run-id>/   # -> NO match
   ```
   The value appears in the viewer only as `[REDACTED:api_key]` (SC-004), across transcript,
   events, and context (FR-014). Env values appear nowhere at all (FR-015).

**Automated**: `orchestrator/tests/test_redact.py` — `redact()` covers each kind and is
idempotent; a parity test pins `redact.py` against `ui/secret_scan.py`; a capture test greps a
written fixture run directory for the seeded secret and expects no hit.

---

## Design-system & regression gates

- `cd ui && ../.venv/bin/python -m pytest -q` — includes `test_conformance.py`,
  `test_ui_consistency.py`, `test_design_system_sync.py`: no literal colors/pixels/inline styles;
  new viewer CSS in `ui/static/app.css` is byte-equal to the design-system master; every control
  composes a macro.
- `cd orchestrator && python -m pytest -q` and `cd images && python -m pytest -q` — capture,
  redaction, prune, and per-harness event tests.
