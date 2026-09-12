# Quickstart & Verification: Checks on Produced Assets

Runnable validation of every user story and success criterion. Prerequisites: the stack is up
(`docker compose up -d`), the orchestrator image rebuilt after the `factory.py`/`definitions.py`
changes (`docker compose build && docker compose up -d`), and the UI venv present for the UI suite
(see `CLAUDE.local.md`). References: [spec.md](./spec.md), [contracts/](./contracts/).

## 0. Automated tests (fastest)

```bash
# Orchestrator: construction, check argv, outcomes, emission paths, load rejection
cd orchestrator && python -m pytest -q
# UI: produces.checks schema field, validation, YAML round-trip, form gating
cd ui && ../.venv/bin/python -m pytest -q
```

Orchestrator tests to expect (new `tests/test_checks.py` + additions):
- Check argv: `/output` & `/workspace` mounted `:ro`, `/report.json` mounted `:ro`, `--network none`
  by default (and the chosen network when set), `sh -c "<command>"`.
- Outcomes: exit 0 ⇒ passed; non-zero ⇒ failed; timeout ⇒ failed + `timed_out` in metadata; missing
  image ⇒ failed with resolution error (FR-015), other checks still run.
- Severity: `blocking: true` ⇒ `ERROR`; `blocking: false` ⇒ `WARN`; absent ⇒ blocking (default).
- **Failed-producer path**: assert against `instance.event_log_storage.get_logs_for_run(run_id)`
  (not `result.all_events`) that there is **no** `ASSET_MATERIALIZATION`, one `ASSET_OBSERVATION`,
  and one `ASSET_CHECK_EVALUATION` per check.
- Partition: check metadata records the partition key on a partitioned materialize (FR-014).
- FR-013: a checkless asset agent still builds via `from_op` and records one materialization,
  unchanged metadata, no checks.

## 1. The verification fixture agent

This feature provisions `agents/verify-checks.yaml` (spec Assumptions) — a fast asset agent whose
`produces.checks` exercise every path:

```yaml
produces:
  asset: verify/checks
  checks:
    - name: has-output
      command: test -n "$(ls /output)"            # US1: passes when a file was written
    - name: advisory-fail
      command: 'false'                            # US2: non-blocking red
      blocking: false
    - name: readonly-guard
      command: touch /output/x                    # US3: fails, read-only /output
    - name: slow
      command: sleep 60                           # US4: trips its timeout
      timeout_seconds: 2
```

## 2. US1 — a check gates an asset (P1) / SC-001

Materialize `verify/checks` from the Dagster UI (http://10.0.0.100:3000, Assets → Materialize).
- **Expect**: the asset shows an asset check `has-output` that is **green** (the run wrote a file),
  with its captured output attached as metadata.
- Negative: point the agent at an empty output run (or a check `test -z "$(ls /output)"`) and
  confirm `has-output` goes **red**.

## 3. US2 — blocking vs non-blocking (P1) / SC-002, SC-003

On the same materialization:
- `advisory-fail` (`false`, `blocking: false`) shows **red** but the asset still **materialized**
  and nothing downstream is blocked (SC-002).
- Add/point at a **blocking** failing check and confirm the run is marked failed while the
  materialization is still recorded, and no downstream automation fires on that materialization
  (SC-003 — observe no downstream run triggered).
- A check with **no** `blocking` field is treated as blocking (US2 scenario 3).

## 4. US3 — read-only isolation (P2) / SC-005

- `readonly-guard` (`touch /output/x`) shows **red**; its captured output contains a
  read-only / permission error.
- Confirm the output directory is **byte-for-byte unchanged** (no `x` file) after the run.

## 5. US4 — timeout (P2) / SC-004

- `slow` (`sleep 60`, `timeout_seconds: 2`) shows **red** with `timed_out` recorded in metadata.
- `docker ps -a | grep check-verify-checks` shows **no** surviving check container from that run.

## 6. US5 — checks require an asset (P2) / SC-007

- **UI**: open a **job-only** agent (e.g. `hello-cc-opus.yaml`) and confirm **no Checks card** is
  shown; open an asset agent and confirm the Checks card appears inside the asset area.
- **Load rejection**: hand the orchestrator a file declaring `checks` with no `produces.asset`
  (e.g. add `checks:` to a job-only agent by hand), reload, and confirm in the Dagster/daemon logs
  that **that file is rejected by name** while every other agent still loads:
  ```bash
  docker compose logs orchestrator 2>&1 | grep -i "skipping agents/"
  ```
- Duplicate check names in one agent are likewise rejected by name.

## 7. Output tail / SC-006

For any failing check, confirm its attached metadata output is **at most the last 4 KB** of the
check's combined stdout/stderr (tail-truncated).

## 8. Regression / FR-013

Materialize an existing checkless asset agent (e.g. a `repo-librarian-*` asset) and confirm it
behaves exactly as before: one materialization, the spec-007 metadata union, and **no** asset
checks attached.

## 9. Debugging a check

A check's verdict and output tail are on the **asset check** in the Dagster UI (Asset → Checks). The
producing run's report is unchanged (spec-007 metadata / `notes`). Compute logs and the transcript
are located as in `CLAUDE.local.md` §1/§1b. A failed/timed-out **producer** still shows its checks
(they ran) plus the red observation carrying the report.
