# Quickstart: Validating structured run reports via Dagster Pipes

Runnable validation for each user story and success criterion. Assumes the box at `10.0.0.100`
with the stack up (`docker compose up -d`) and one verification agent per harness (api, claude-code,
pi, codex) available (spec Assumptions). Host paths follow `CLAUDE.local.md`.

## Prerequisites

```bash
cd /home/vortex/GitHub/agentbox
docker compose build            # rebuild orchestrator + all four agent images with the wrappers
docker compose up -d
# UI: http://10.0.0.100:3000
```

## Scenario 1 — Uniform report for every harness (US1 / SC-001)

Materialize (or run) one agent of each harness, then inspect the materialization/run metadata.

```bash
# from the Dagster UI: Materialize each harness's asset agent, or launch its agent_<name> job.
# Then read the report fields straight off the compute log's result summary, or the UI metadata.
```

**Expected**: every run's metadata shows all report fields — `status`, `tokens_in`, `tokens_out`,
`turns`, `cost_usd`, `files_written`, `transcript_path`, `error`, `notes` — in the same shape.
`cost_usd` is a real number for **api** and **pi**, and `null` for **claude-code** and **codex**.
The `notes` field is legible in the UI without opening the transcript (SC-006).

## Scenario 2 — Failed asset run is recorded, not thrown away (US2 / SC-003)

Force a claude-code **asset** agent to fail — cap it so it cannot finish (e.g. `max_turns: 1` on a
task that needs more, or a deliberately impossible instruction).

```bash
# Materialize the capped asset agent's partition from the UI.
```

**Expected**: the partition shows **red with a materialization attached** — `status: failed`, an
`error` explaining the failure, and a present `transcript_path` — and the run itself is marked
failed. (Before this feature: no materialization at all.)

## Scenario 3 — Timeout leaves a report and no surviving container (SC-004 / FR-009)

Set `timeout_seconds` short enough to trip on any agent, and run it.

```bash
# after the run ends:
docker ps -a | grep agent-        # expect: no container from this run remains (--rm)
```

**Expected**: the run records `status: timeout`, `error` naming the timeout, and `null` for
`tokens_in`/`tokens_out`/`turns`/`cost_usd`. No `agent-<name>-<runid>` container remains.

## Scenario 4 — Live log streaming (US3 / SC-005)

Start a claude-code run and open its Dagster run page while it is still running.

**Expected**: tool calls and output appear in the run log **during** execution, not only after the
container exits.

## Scenario 5 — Orchestrator holds zero per-harness parsing (SC-002)

```bash
# the codex turn.completed aggregation, the pi agent_end summariser, and the claude result
# extraction must all be GONE from the orchestrator:
grep -n -E "turn\.completed|agent_end|num_turns|item\.completed" orchestrator/factory.py || echo "OK: no per-harness parsing in the orchestrator"
```

**Expected**: `OK: no per-harness parsing in the orchestrator`. The parsing now lives in
`images/<harness>/wrapper.py` (or `runner.py` for api).

## Scenario 6 — Isolation preserved (SC-007 / FR-011)

```bash
cd orchestrator && ../.venv/bin/python -m pytest -q tests/test_reports.py -k isolation
```

**Expected**: the test comparing the launched `docker run` argv to the pre-feature argv passes —
identical except for the `-v <pipes>:/pipes` mount and the two `-e DAGSTER_PIPES_*` env vars.

## Unit tests

```bash
# orchestrator: report routing, metadata union, materialize-on-failure, timeout fallback
cd /home/vortex/GitHub/agentbox/orchestrator && ../.venv/bin/python -m pytest -q

# per-harness parsers against recorded native-event fixtures
cd /home/vortex/GitHub/agentbox && ./.venv/bin/python -m pytest -q images/tests
```

**Expected**: all pass, including a parser test per harness asserting the produced report matches
`contracts/run-report.schema.json` and the expected `cost_usd` nullness per harness (SC-001).

## References

- Report shape: [`contracts/run-report.schema.json`](./contracts/run-report.schema.json)
- Transport boundary: [`contracts/pipes-transport.md`](./contracts/pipes-transport.md)
- Metadata union: [`contracts/metadata.md`](./contracts/metadata.md)
- Design decisions: [`research.md`](./research.md) · Entities: [`data-model.md`](./data-model.md)

## Running it on the box (T022 runbook)

The concrete command sequence for the end-to-end validation above, run on the Pi
(`10.0.0.100`). Nothing here is automated — it rebuilds and restarts the live stack and
launches real agent runs (which spend tokens and need live credentials).

### 1. Build the four agent images (build context = `images/`)

The agent images are **not** built by docker-compose, and since spec 007 they build from the
`images/` directory so they can `COPY lib/` (the shared report helper):

```bash
cd /home/vortex/GitHub/agentbox
docker build -f images/agent-python/Dockerfile -t agentbox/agent-python:latest images/
docker build -f images/agent-claude/Dockerfile -t agentbox/agent-claude:latest images/
docker build -f images/agent-codex/Dockerfile  -t agentbox/agent-codex:latest  images/
docker build -f images/agent-pi/Dockerfile     -t agentbox/agent-pi:latest     images/
```

Watch for `dagster-pipes==1.13.21` installing, and — on the node images — `python3` /
`pip3 --break-system-packages` succeeding on arm64.

### 2. Rebuild the orchestrator and restart the stack

```bash
docker compose build          # orchestrator
docker compose up -d          # restarts; auto-discovers agents/verify-*.yaml
```

Confirm in the UI (http://10.0.0.100:3000) that the fixture agents registered: job
**`agent_verify_api`** and assets **`verify/fail`** and **`verify/timeout`**.

### 3. Scenario 1 — uniform report per harness (SC-001, SC-006)

Run one of each harness: launch job **`agent_verify_api`** (api), and materialize an existing
**claude-code** (`repo-review/agentbox`), **codex** (`repo-librarian-codex`), and **pi**
(`repo-librarian-pi-sonnet`) agent.

**Expect:** every run's metadata shows all report fields in the same shape; `notes` renders
inline; `cost_usd` is a real number for **api**/**pi** and `null` for **claude-code**/**codex**.

### 4. Scenario 2 — failed asset recorded (SC-003)

Materialize the **`verify/fail`** asset (claude-code capped at `max_turns: 1`).

**Expect:** the partition goes **red with a materialization attached** — `status: failed`, an
explanatory `error`, and a present `transcript` path.

### 5. Scenario 3 — timeout (SC-004)

Materialize the **`verify/timeout`** asset (`timeout_seconds: 5`), then:

```bash
docker ps -a | grep agent-      # expect: no verify-timeout container remains
```

**Expect:** `status: timeout`, numeric fields null; no surviving `agent-verify-timeout-*`
container.

### 6. Scenario 4 — live streaming (SC-005)

Start a claude-code run and open its run page **while it is still running**.

**Expect:** stdout events appear line-by-line during execution, not only after the container exits.

### 7. Scenario 5 — no per-harness parsing in the orchestrator (SC-002)

```bash
grep -nE "turn\.completed|agent_end|num_turns|item\.completed" orchestrator/factory.py \
  || echo "OK: no per-harness parsing in the orchestrator"
```

**Expect:** `OK: no per-harness parsing in the orchestrator`.

### 8. Scenario 6 + full suites (SC-007, all)

```bash
cd /home/vortex/GitHub/agentbox/orchestrator && ../.venv/bin/python -m pytest -q tests/test_reports.py -k isolation
cd /home/vortex/GitHub/agentbox/orchestrator && ../.venv/bin/python -m pytest -q
cd /home/vortex/GitHub/agentbox && ./.venv/bin/python -m pytest -q images/tests
```

### Notes / gotchas

- **Credentials:** `verify-api`/pi need `LITELLM_MASTER_KEY` (already in `.env`);
  `verify-fail`/`verify-timeout` use claude-code, so its OAuth token must be set as for the
  other claude agents.
- **If the code location errors on reload:** `docker compose logs -f dagster-webserver`.
- **Inspect a report from the shell:** the report is on the run/materialization metadata; the
  transcript stays at `/data/dagster/agent-logs/<agent>/<date>/<run-id>.jsonl`.
