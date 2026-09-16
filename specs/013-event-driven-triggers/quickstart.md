# Quickstart: Event-Driven Triggers — Asset Dependency Graph

Runnable validation for the feature. Fast, deterministic checks run as unit tests; the end-to-end
firing/handoff/governor behavior is validated against a live Dagster, matching the 006/008/012
posture. Paths are project-relative; run commands from the repo root.

## Prerequisites

- The stack builds and runs: `docker compose build && docker compose up -d` (orchestrator +
  daemon + UI). Dagster UI at `http://10.0.0.100:3000`, management UI at the `ui` service.
- `pytest` available for `ui/` and `orchestrator/` (`cd ui && pytest`, `cd orchestrator && pytest`).
- Two demo asset agents to wire A → B (unpartitioned first, then daily):
  - `agents/notes.yaml` — `produces.asset: notes/daily`, an `api`/`pi` harness, a trivial prompt.
  - `agents/refined.yaml` — `produces.asset: refined/daily`, `produces.depends_on: [notes/daily]`,
    `triggers.on_upstream: true`, a prompt that reads `AGENTBOX_UPSTREAM_NOTES_DAILY`.

## §0 Static checks (unit tests)

```bash
cd ui && pytest -q                 # schema, agents_store, settings, api, conformance
cd ../orchestrator && pytest -q    # factory, definitions, governors, paths parity
```

Expected: green. Key assertions — see [contracts/](contracts/):
- `depends_on` + `on_upstream`/`on_missing` in `/api/schema`; `migrate_6_to_7` is identity; a
  schema-6 file loads with no noise and re-stamps to 7 on save.
- The emitter writes `depends_on` under `produces:` and the two flags under `triggers:`; round-trip
  is stable.
- Governor read/validate/write; `POST /api/settings/governors` round-trips and 400s on bad input.
- Parity: `orchestrator/governors.DEFAULT_GOVERNORS == ui/settings_store.DEFAULT_GOVERNORS ==
  {"max_runs_per_hour": 12, "max_chain_depth": 5}`; the `AGENTBOX_UPSTREAM_<KEY>` transform matches
  its documented form.

## §1 US1 — fire a downstream when its upstream materializes (P1)

1. In the UI, open `refined`, confirm the **Depends-on** card shows `notes/daily` and the
   **on_upstream** toggle is on. Save.
2. In Dagster, turn **on** `refined`'s `autocond_refined` sensor (new triggers start paused).
3. Materialize `notes/daily` (manually or via its schedule) so it succeeds.
4. **Expected**: within a sensor tick, `refined/daily` materializes for the matching partition with
   **no manual action** against `refined` (SC-001 / Acceptance US1 #1).

Blocking-check gating (SC-003 / US1 #2/#3):
5. Add a **blocking** check to `notes` that fails; materialize `notes`. **Expected**: `refined` does
   **not** fire (the failed blocking check records an observation, not a materialization).
6. Fix the check; materialize `notes` again. **Expected**: `refined` fires.

Paused-by-default (US1 #4): with `autocond_refined` off, materializing `notes` does **not** fire
`refined` until the sensor is turned on.

## §2 US2 — upstream handoff to the container (P1)

1. With `refined` fired by `notes` (§1), open `refined`'s latest run.
2. **Expected**: the container saw `AGENTBOX_UPSTREAM_NOTES_DAILY` set to a path under `/upstreams`,
   and that JSON file lists `notes`'s output paths, report metadata, and materialization time for
   the matching partition (SC-002 / US2 #1), matching
   [contracts/upstream-handoff.schema.json](contracts/upstream-handoff.schema.json).
3. **Read-only** (US2 #2): the `/upstreams` mount is `:ro`; a write from the container fails.
4. **Multiple upstreams** (US2 #3): give `refined` a second `depends_on` (`extras/daily`) with no
   matching materialization. **Expected**: `AGENTBOX_UPSTREAM_EXTRAS_DAILY` is still present and
   points at a file with `materialized: false` and null/empty fields (FR-012a).

Unit-level: `orchestrator/tests/test_factory.py` asserts the handoff builder's env-var naming,
matching-partition selection, latest-of-many, and the "no materialization" file against an ephemeral
instance.

## §3 US3 — materialize a never-produced partition (P2)

1. Give an asset `on_missing: true`, turn on its sensor, for a partition never produced.
2. **Expected**: it materializes that partition on its own (US3 #1). Once it exists, `on_missing`
   does not re-fire for that partition (US3 #2). For a daily asset, only today's partition is
   filled — history is not backfilled.
3. With both `on_upstream` and `on_missing` on, either condition materializes the asset, both behind
   the one `autocond_<name>` sensor (US3 #3).

## §4 US4 — reject cycles & dangling refs at load (P2)

1. Wire `B depends_on C` and `C depends_on B`; reload the code location (or run
   `orchestrator/tests/test_definitions.py`). **Expected**: `B` and `C` are rejected with a
   daemon-log message **naming both assets in the cycle** (SC-004 / US4 #1); unrelated agents still
   load.
2. An acyclic graph loads cleanly (US4 #2).
3. A `depends_on` naming a non-existent asset key ⇒ that agent is rejected, the log **naming the
   missing key** (US4 #3). The form also blocks saving a dangling reference / cycle.

## §5 US5 — governors (P3)

Rate (SC-005 / US5 #1):
1. Settings → set `max_runs_per_hour: 2`. Trigger three automated materializations within one
   rolling 60-minute window.
2. **Expected**: the third is **refused, skipped, and logged** in the daemon log; the refused run
   does **not** consume a slot (only launched runs count).

Depth (SC-005 / US5 #2):
3. Chain `A → B → C → D → E → F` all with `on_upstream`, `max_chain_depth: 5`. Drive `A`.
4. **Expected**: `F` (depth 6) is **refused and logged**; `A..E` run.

Manual bypass (SC-006 / US5 #3):
5. After a governor refuses an automated run, **manually** materialize the same agent.
6. **Expected**: the manual run proceeds — manual runs bypass both governors.

Persist (US5 #4):
7. Edit both governors on the Settings page. **Expected**: values persist to
   `config/settings.yaml` (the `governors:` block, `retention:` untouched) and take effect on the
   next automated run / reload.

Unit-level: `orchestrator/tests/test_factory.py` asserts the refusal path (observation, no
materialization, no `launched` tag) and the rolling-window count against an ephemeral instance;
`ui/tests/test_settings.py` asserts persistence + validation.

## §6 Partitioned on_upstream build-time check (FR-007 / R2)

Switch `notes` and `refined` to `partition: daily`. Materialize `notes`'s **today** partition.
- **Expected (primary path)**: `refined`'s **today** partition materializes (daily→daily identity),
  and the handoff reflects the today partition.
- **Fallback**: set `AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY=1` and reload. **Expected**: `refined`'s
  daily `on_upstream` condition is dropped, a load-warning names the asset, and the README documents
  the restriction. This gates whether partitioned `on_upstream` ships (R2).

## §7 Docs (FR-021)

Confirm the README documents: `produces.depends_on`; `triggers.on_upstream` / `on_missing`; the
`AGENTBOX_UPSTREAM_<KEY>` env var + handoff file (with the key transform); the two governors and
their defaults; and the partitioned-`on_upstream` fallback. The docs-layout test
(`ui/tests/test_docs_layout.py`) stays green.
