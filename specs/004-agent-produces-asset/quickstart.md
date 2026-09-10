# Quickstart: Agent Produces Asset

End-to-end validation that an agent can declare an asset, materialize it, and revert — and that
bad declarations are rejected. Run on the Pi host. References
[contracts/orchestrator-asset.md](contracts/orchestrator-asset.md) and
[contracts/schema-and-yaml.md](contracts/schema-and-yaml.md) for the exact rules.

## Prerequisites

- The stack builds and runs: `docker compose build && docker compose up -d`.
- `docker-compose.yml` mounts the outputs root read-only into `dagster-webserver` and
  `dagster-daemon` (contract §8) — required for the metadata snapshot.
- Dagster UI reachable at `http://10.0.0.100:3000`.
- The UI venv exists for the automated tests: `cd ui && ../.venv/bin/python -m pytest -q`.

## Scenario 1 — Declare an asset (User Story 1, P1)

1. Add to an existing agent file (e.g. `agents/repo-librarian-agentbox.yaml`):
   ```yaml
   produces:
     asset: repo-review/agentbox
     partition: daily
   ```
2. Reload the orchestrator (restart the Dagster services, or reload the code location).
3. **Expect**: an **asset** `repo-review/agentbox` with a daily partition set appears; there is
   no bare job for that agent (AC-1).
4. Materialize today's partition from the Dagster UI.
5. **Expect**: the same container launches (compute step `run_repo_librarian_agentbox`, AC-2);
   the output lands in `/data/outputs/repo-librarian/agentbox/` with no duplicate (AC-4, SC-003).
6. Open the materialization → **Expect** metadata: `output_files`, `transcript`, `run_stamp`,
   `session_id`, `harness`, `model`, and `partition` (AC-3, SC-002).
7. Materialize again → **Expect** a materialization history for the asset (AC-5).

## Scenario 2 — Revert to job-mode (User Story 2, P1)

1. Remove the `produces` block; reload.
2. **Expect**: the agent is a job `agent_repo_librarian_agentbox` again, no longer an asset
   (AC-1); running it behaves exactly as before the asset existed (AC-3, SC-004).
3. Confirm the full current agent set (none declaring `produces`) still loads with **zero**
   warnings/migration noise (SC-005) — check the code-location load log.

## Scenario 3 — Author from the UI (User Story 3, P2)

1. In the management UI, create/edit an agent and fill the **Produces** card (asset key +
   partition) under the Runs column; save.
2. Inspect the written YAML → **Expect** a `produces:` block in the Runs section with one comment
   per field (AC-1).
3. Reopen the agent in the form → **Expect** the same asset key and partition (round-trip, AC-2,
   SC-007).
4. Create an agent leaving Produces empty; save → **Expect** no `produces` block; it stays a job
   (AC-3).

## Scenario 4 — Invalid asset key is rejected with a naming message (User Story 4, P2)

1. In the UI, enter an invalid key (e.g. `Bad Key`) and save → **Expect** rejection before save,
   with a reason on the asset field (AC-1).
2. Hand-write `produces: {asset: "Bad Key"}` into a YAML file and reload the orchestrator →
   **Expect** that file rejected with a message that **names it**, while all other agents still
   load (AC-2, SC-006).
3. (FR-019) Give two enabled agents the same `asset` key and reload → **Expect** both files
   rejected by name; every other agent still loads.

## Automated checks

```bash
cd ui && ../.venv/bin/python -m pytest -q
```

Covers: the `produces` section/fields in the schema and `/api/schema`; asset-key validation
accept/reject (shared fixtures pinning the UI and orchestrator regex agree, research R6); the
nested block round-tripping via regenerated golden files; the form rendering a Produces card.
Orchestrator job-vs-asset selection, op naming, snapshot diff, and conflict/invalid-key handling
are unit-tested over `factory`/`definitions` with a stubbed launch. Live materialization
(Scenario 1) is verified manually against the Dagster UI.
