**Intent.** An agent can declare that its asset depends on other assets and be triggered when they change. Upstream outputs are handed to the container. This replaces "watch a folder" with an explicit graph.

**What changes.**
- `produces.depends_on:` list of asset keys (other agents' assets, or external assets from 017).
- `triggers:` gains two asset-kind keys alongside `asset_schedule`: `on_upstream: true` (materialize when any upstream materializes and passes its blocking checks) and `on_missing: true` (materialize when the partition has never been produced). Both become automation conditions on the asset, behind the same `autocond_<name>` sensor.
- For partitioned assets, upstream/downstream partitions map one-to-one (daily → daily) by default.
- At launch, for each upstream asset the container receives an env var `AGENTBOX_UPSTREAM_<KEY>` (key upper-snaked) pointing at a small read-only JSON file listing that upstream's latest materialization for the matching partition: output file paths, report metadata, materialization time. The prompt can be told to read it.
- Governors in `config/settings.yaml` (012): `max_runs_per_hour` (default 12), enforced before launching any automated run — a refused run is logged and skipped; every automated run carries a `chain_depth` tag, and a run exceeding `max_chain_depth` (default 5) is refused. Manual runs bypass both. Both editable on the Settings page.
- Schema (Depends-on card; Automation view gains the two new trigger kinds), README updated. `depends_on` cycles are rejected at load naming the assets.

**What I'd check.**
- A produces `notes/daily` (daily). B has `depends_on: [notes/daily]`, `on_upstream: true`. Materialize A's partition for today; B materializes without anyone clicking, and B's container has `AGENTBOX_UPSTREAM_NOTES_DAILY` pointing at a file listing A's output.
- Give A a blocking check that fails; B does not fire. Fix it; B fires.
- Make B depend on itself through C; reload fails naming the cycle.
- Set `max_runs_per_hour: 2`, trigger three automated materializations within an hour; the third is refused, visibly in the daemon log.
- Chain A → B → C → D → E → F; F is refused for exceeding `max_chain_depth: 5`.

**Out of scope.** Fan-in of many partitions to one. Non-identity partition mappings. Sensors on external systems (017).

**Null action.** If `on_upstream` misbehaves on partitioned assets with the daily mapping, restrict it to unpartitioned assets in this release and say so.