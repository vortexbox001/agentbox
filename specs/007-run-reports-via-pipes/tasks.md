---

description: "Task list for Structured Run Reports via Dagster Pipes"
---

# Tasks: Structured Run Reports via Dagster Pipes

**Input**: Design documents from `/specs/007-run-reports-via-pipes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED — the design explicitly calls for them (research R9, quickstart "Unit tests"):
launch-stubbed in-process orchestrator tests plus fixture-driven per-harness parser tests.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1; US3 is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1, US2, or US3 (Setup/Foundational/Polish carry no story label)
- Exact file paths are included in every task

## Path Conventions

Single project (Dagster code location + agent images). Orchestrator at `orchestrator/`,
harness images at `images/`, shared image lib at `images/lib/`, tests at `orchestrator/tests/`
and `images/tests/`. Contracts referenced live under `specs/007-run-reports-via-pipes/contracts/`.

**Key file-conflict note**: `orchestrator/factory.py` (`make_run_op`) is edited by tasks in the
Foundational, US1, US2, and US3 phases. Those tasks touch the **same function** and therefore
run **sequentially** (never `[P]` with each other). Same for shared test files.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Directory scaffolding and test-environment prerequisites for the new shared lib and
image-side tests.

- [X] T001 [P] Create the shared-lib and image-test scaffolding: `images/lib/__init__.py`, `images/tests/__init__.py`, an empty `images/tests/fixtures/` directory (add a `.gitkeep`), and a minimal `images/tests/conftest.py` that puts `images/` on `sys.path` so parser tests can `import lib.agent_report`.
- [X] T002 [P] Install `dagster-pipes` into the project test venv (`.venv`) so image parser tests can import `dagster_pipes`/`lib.agent_report`, using `uv pip install --python .venv/bin/python dagster-pipes` (pin the version compatible with Dagster 1.13.21 per plan.md), and note the same pin in a comment for the image Dockerfiles.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared report helper (needed by every harness) and the orchestrator-side Pipes
launch scaffolding + isolation guarantee (needed by every story that reads a report back).

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T003 Create the shared report helper `images/lib/agent_report.py`: a report dataclass/serialiser matching `specs/007-run-reports-via-pipes/contracts/run-report.schema.json` (fields `status`, `tokens_in`, `tokens_out`, `turns`, `cost_usd`, `files_written`, `transcript_path`, `error`, `notes`), a `files_written` counter (before/after snapshot of `/output`; this is the harness's own in-container count and is intentionally independent of — and may differ from — the orchestrator's `output_files` list diff, per spec Assumptions), and `emit(report, is_asset)` that calls `dagster_pipes.open_dagster_pipes()` and routes to `report_asset_materialization(metadata=...)` (asset step) or `report_custom_message({"report": ...})` (job step), leaving `transcript_path=null`. Blocks all harness wrappers.
- [X] T004 In `orchestrator/factory.py` `make_run_op`, wrap the existing `docker run` launch in `open_pipes_session(context, context_injector=PipesEnvContextInjector(), message_reader=PipesFileMessageReader(path=<host pipes file>))`: create a per-run host temp `/pipes` dir, add `-v <host-pipes-dir>:/pipes` plus `-e DAGSTER_PIPES_CONTEXT=<blob>` and `-e DAGSTER_PIPES_MESSAGES=<blob>` (rewriting the messages `path` from the host path to `/pipes/messages`), and preserve every existing isolation flag verbatim (`--network`, `--memory`, `--cpus`, `--tmpfs`, credential mounts, `--env-file`, passthrough `-e VAR`, `-v .../output`, `--name`, `--rm`). Keep `subprocess.run` for now (streaming is US3). Per contract `contracts/pipes-transport.md` §1.
- [X] T005 In `orchestrator/tests/conftest.py`, replace/augment the launch stub so report tests run in-process via `materialize()` with no `docker run`: the stub yields a canned returncode and lets a test drop a canned report into the Pipes messages file / `get_reported_results()` / `get_custom_messages()`, while still capturing the launched `docker run` argv for the isolation assertion.
- [X] T006 Create `orchestrator/tests/test_reports.py` with the isolation-invariant test (SC-007/FR-011, `contracts/pipes-transport.md` §4): assert the launched `docker run` argv equals the pre-feature argv except for exactly the `-v <pipes>:/pipes` mount and the two `-e DAGSTER_PIPES_*` env vars.

**Checkpoint**: Shared report shape exists, the launch runs under Pipes with isolation proven — user-story work can begin.

---

## Phase 3: User Story 1 - Every run reports itself in a single structured shape (Priority: P1) 🎯 MVP

**Goal**: Every harness (api, claude-code, pi, codex) emits the one common report; the orchestrator
reads it back and attaches it as the metadata union (report fields + existing context fields), with
`notes` legible inline and per-harness stdout parsing removed from the orchestrator.

**Independent Test**: Run one agent of each harness to completion; every materialization/run shows
all report fields in the same shape, `cost_usd` real for api/pi and null for claude-code/codex,
`notes` readable in the UI without opening the transcript.

### Implementation for User Story 1

- [X] T007 [P] [US1] `images/agent-python/runner.py` + `images/agent-python/Dockerfile`: build and emit the report via `lib.agent_report` — tokens from the LiteLLM response `usage`, `cost_usd` from the `x-litellm-response-cost` header (non-null, SC-001), `turns=1`, `notes`=model message text, `files_written` from the `/output` count; Dockerfile installs `dagster-pipes` and copies `images/lib/`. **The runner MUST still print its native event stream to stdout unchanged (as it does today) — the Pipes report is emitted over `/pipes/messages`, NOT in place of stdout — so the orchestrator's transcript `.jsonl` for api runs is byte-for-byte what it is today (FR-006). Matches the "tee native events to stdout unchanged" requirement of T008-T010.**
- [X] T008 [P] [US1] `images/agent-claude/wrapper.py` (NEW) + `images/agent-claude/Dockerfile`: wrapper spawns `claude`, tees native `stream-json` events to stdout unchanged (FR-006), parses the final `result` event for `num_turns`, usage, `is_error`, and final text (`notes`), sets `cost_usd=null` (subscription), and emits via `lib.agent_report`; Dockerfile adds `python3-minimal` + `dagster-pipes`, copies `images/lib/`, sets the wrapper as entrypoint.
- [X] T009 [P] [US1] `images/agent-codex/wrapper.py` (NEW) + `images/agent-codex/Dockerfile`: wrapper spawns `codex`, tees native events to stdout, aggregates `turn.completed` usage, takes the last `item.completed` `agent_message` text as `notes`, collects `error` events, sets `cost_usd=null`, emits via `lib.agent_report`; Dockerfile adds `python3-minimal` + `dagster-pipes`, copies `images/lib/`, sets the wrapper entrypoint.
- [X] T010 [P] [US1] `images/agent-pi/wrapper.py` (NEW) + `images/agent-pi/Dockerfile` + `images/agent-pi/entrypoint.sh`: wrapper spawns `pi`, tees native events to stdout, parses the `agent_end` event (sum assistant `usage.cost.total` → non-null `cost_usd` SC-001, count assistant messages → `turns`, last assistant text → `notes`, `stopReason == "error"` → `error`), emits via `lib.agent_report`; Dockerfile adds `python3-minimal` + `dagster-pipes`, copies `images/lib/`, and `entrypoint.sh` invokes the wrapper.
- [X] T011 [US1] In `orchestrator/factory.py` `make_run_op`, after the container exits read the report back — `session.get_reported_results()` (asset) and `session.get_custom_messages()` (job) — **used strictly as a data channel to recover the report *fields*, NOT to emit a second materialization**: on the success asset path the op returns normally so `from_op` records exactly ONE materialization, whose metadata is the union set via `context.add_output_metadata(metadata)` (do not also `yield`/`log_event` the reported `AssetMaterialization`). Set the report's `transcript_path` to the host `.jsonl` path; build the metadata union per `contracts/metadata.md` (report fields + existing `output_files`, `transcript`, `run_stamp`, `session_id`, `harness`, `model`, `partition`) — the report field `transcript_path` maps onto the existing `transcript` key (same host path), not a separate key; attach `notes` as `MetadataValue.md` when present (FR-010) — when `notes` is `null` (e.g. timeout/crash), omit the key or use a text placeholder rather than calling `MetadataValue.md(None)`, mirroring the null-numeric rule — and surface null numerics distinctly from `0`. (Edits `make_run_op`; sequential after T004.)
- [X] T012 [US1] In `orchestrator/factory.py`, delete the per-harness stdout parsing now owned by the images (the `turn.completed` aggregation, the `agent_end` summariser, the claude `result`/`num_turns` extraction, `item.completed`) so the orchestrator holds zero per-harness parsing (SC-002). (Edits `make_run_op`; sequential after T011.)
- [X] T013 [P] [US1] Add per-harness parser tests with recorded fixtures under `images/tests/`: `images/tests/fixtures/<harness>.jsonl` (one recorded native-event stream each for api, claude-code, codex, pi) and `images/tests/test_<harness>_report.py` asserting the produced report conforms to `run-report.schema.json` and has the expected values — `cost_usd` non-null for api/pi, null for claude-code/codex (SC-001).
- [X] T014 [US1] In `orchestrator/tests/test_reports.py`, add the metadata-union test (FR-004/FR-005, `contracts/metadata.md`): a completed run attaches all report fields plus the existing context keys (`set(md) >= {existing keys}`), `notes` is markdown metadata, and a null numeric renders distinct from `0`. **Also assert the success asset path records exactly ONE materialization (I1): the reported result from `get_reported_results()` is consumed for its fields only and does not produce a second `AssetMaterialization` alongside the `from_op` output.** (Same file as T006; sequential.)

**Checkpoint**: US1 fully functional — every harness reports one uniform shape, attached and legible; orchestrator has no per-harness parsing. This is the MVP.

---

## Phase 4: User Story 2 - Failed asset runs are recorded, not thrown away (Priority: P1)

**Goal**: A non-`ok` asset run produces a materialization carrying `status: failed` (or `timeout`)
with the full report and marks the run failed; job-only agents keep today's raise-on-nonzero
behavior; the orchestrator authors a fallback report on timeout or missing/malformed report.

**Independent Test**: Cap a claude-code asset agent so it cannot finish → its partition shows red
with `status: failed`, an explanatory `error`, and a present `transcript_path`, and the run is
marked failed. Set a short `timeout_seconds` → `status: timeout` recorded and no container remains.

### Implementation for User Story 2

- [X] T015 [US2] In `orchestrator/factory.py` `make_run_op`, implement failure recording (FR-007/FR-008, `contracts/pipes-transport.md` §3): for an **asset** agent with `status != ok`, emit `context.log_event(AssetMaterialization(asset_key=<key from cfg.produces>, partition=<key or None>, metadata=<same union as success>))` **then** `raise` so the partition shows red with the report; for a **job-only** agent, attach the report as run/output metadata and `raise` on non-zero container exit (behavior unchanged). (Edits `make_run_op`; sequential after T012.)
- [X] T016 [US2] In `orchestrator/factory.py` `make_run_op`, add fallback report authoring (FR-009, R8): enforce `timeout_seconds` on the launch, on timeout `docker kill` the named `agent-<name>-<run_id[:8]>` container and author `status: "timeout"` with numeric fields null and an `error` naming the timeout; on a normal exit with no readable/well-formed report author `status: "failed"` with an `error` saying the report was missing/malformed; rely on `--rm` so no container survives (SC-004). (Edits `make_run_op`; sequential after T015.)
- [X] T017 [US2] In `orchestrator/tests/test_reports.py`, add failure-path tests: materialize-on-failure for an asset (SC-003 — `AssetMaterialization` recorded with `status: failed` and the run raises), job-only routing raises on non-zero with the report attached (FR-008), timeout fallback authors `status: timeout` with null numerics (SC-004), and a missing/malformed report authors `status: failed`. (Same file as T014; sequential.)

**Checkpoint**: US1 + US2 both work — successful runs report uniformly and failed/timed-out asset runs are recorded as materializations rather than lost.

---

## Phase 5: User Story 3 - Logs stream live while the run is in flight (Priority: P2)

**Goal**: The orchestrator forwards each run's stdout into the Dagster run log line-by-line while
the container is still running, without changing the transcript byte stream.

**Independent Test**: Start a claude-code run and watch its Dagster run page; tool-call events
appear during execution, not only after the container exits.

### Implementation for User Story 3

- [X] T018 [US3] In `orchestrator/factory.py` `make_run_op`, replace `subprocess.run(capture_output=True)` with `subprocess.Popen(stdout=PIPE, stderr=PIPE, text=True)` and drain stdout **line by line** (R5/FR-003): each line is written to the transcript `.jsonl` handle (byte stream unchanged, FR-006) **and** forwarded to `context.log.info`; drain stderr on a second thread to avoid pipe-buffer deadlock. Integrate with the timeout wait from T016. (Edits `make_run_op`; sequential after T016.)
- [X] T019 [US3] In `orchestrator/tests/test_reports.py`, add a streaming test: the Popen stub yields multiple stdout lines during the run and the test asserts each line is forwarded to the Dagster log as it arrives (not buffered to the end) and the full stream is still written to the transcript. (Same file as T017; sequential.)

**Checkpoint**: All three stories functional — uniform reports, recorded failures, live streaming.

---

## Phase 6: Polish & Cross-Cutting Concerns

### Verification fixture agents (prerequisites for the end-to-end quickstart, T022)

The spec's Assumptions say "one agent per harness … is available" and that `max_turns` /
`timeout_seconds` "can be set on an agent to force the failure and timeout paths." Today only
`agents/_template-api.yaml` exists for the **api** harness (a template, not a runnable enabled
agent), and no capped or short-timeout agent exists. These tasks provision the missing fixtures so
SC-001 (api leg), SC-003, and SC-004 can be exercised end-to-end in T022. They are pure agent
YAML + prompt files (no orchestrator code), so both are `[P]`.

- [X] T024 [P] Create an enabled **api**-harness verification agent so SC-001's api leg and the US1 Independent Test can run: add `agents/verify-api.yaml` (`harness: api`, a trivial `job`-nature task) copied from `agents/_template-api.yaml` and `prompts/verify-api.md`, and confirm it is enabled (auto-discovered by `definitions.py`). Needed by T022 Scenario 1 (one agent per harness) — the existing enabled agents already cover claude-code, pi, and codex.
- [X] T025 [P] Create the failure/timeout verification agents T022 Scenarios rely on (SC-003/SC-004): `agents/verify-fail.yaml` — a **claude-code asset** agent capped (e.g. `max_turns`) so it cannot finish, to force `status: failed` on a partition — and `agents/verify-timeout.yaml` — any-harness agent with `timeout_seconds` short enough to trip — plus their `prompts/*.md`. Both enabled. (Alternatively these may be expressed as run-config overrides on an existing agent; if so, document the exact run config in T022 instead of new files.)

- [X] T020 [P] Update the debugging docs to reality (Constitution VI): revise `CLAUDE.local.md` and `README` so the "Debugging failed Dagster runs" narrative describes the structured report as metadata instead of the removed orchestrator stdout-summarisation.
- [X] T021 [P] Add a schema-conformance assertion shared by the image parser tests: validate each produced report against `specs/007-run-reports-via-pipes/contracts/run-report.schema.json` (e.g. a helper in `images/tests/conftest.py` used by every `test_<harness>_report.py`).
- [ ] T022 Run the quickstart validation end-to-end on the box (`docker compose build && docker compose up -d`, then quickstart Scenarios 1–6) **using the verification fixture agents from T024 (api leg of SC-001) and T025 (SC-003 forced-failure, SC-004 timeout)**, confirming SC-001..SC-007 including `grep -nE "turn\.completed|agent_end|num_turns|item\.completed" orchestrator/factory.py` prints nothing (SC-002) and no `agent-` container survives a timeout (SC-004).
- [X] T023 Run the full test suites and confirm green: `cd orchestrator && ../.venv/bin/python -m pytest -q` and `./.venv/bin/python -m pytest -q images/tests`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: after Setup — BLOCKS all user stories. T003 (shared lib) blocks all harness wrappers; T004 (launch scaffolding) blocks all orchestrator read-back; T005 (stub) blocks all orchestrator tests.
- **US1 (Phase 3)**: after Foundational. MVP.
- **US2 (Phase 4)**: after US1 (shares `make_run_op` and `test_reports.py`).
- **US3 (Phase 5)**: after US2 (shares `make_run_op`; integrates with the timeout wait from T016).
- **Polish (Phase 6)**: after the desired stories are complete. The verification fixture agents (T024, T025) have no code dependency and MAY be created any time, but they BLOCK the end-to-end quickstart (T022).

### Critical same-file chain (must be sequential, never `[P]`)

`orchestrator/factory.py` `make_run_op`: **T004 → T011 → T012 → T015 → T016 → T018**.
`orchestrator/tests/test_reports.py`: **T006 → T014 → T017 → T019**.

### User Story Dependencies

- **US1 (P1)**: independent once Foundational is done — it is the MVP.
- **US2 (P1)**: layers failure branches onto the same op; test after US1's happy path exists.
- **US3 (P2)**: layers streaming onto the same op; sequenced last because it integrates with the
  timeout handling added in US2 (T016).

### Parallel Opportunities

- Setup: T001 and T002 in parallel.
- US1 harness implementations **T007, T008, T009, T010** are fully parallel (four different image
  dirs, all depending only on T003). T013 (parser tests/fixtures) can proceed alongside them.
- Polish T020, T021, T024, and T025 in parallel (docs, schema helper, and the verification fixture agents are all independent files).
- T024/T025 (fixture agents) block only T022 (the end-to-end quickstart), nothing else.

---

## Parallel Example: User Story 1 harness implementations

```bash
# After T003 (shared lib) lands, build all four harness reporters in parallel:
Task: "agent-python runner.py + Dockerfile emit report (T007)"
Task: "agent-claude wrapper.py + Dockerfile parse stream-json (T008)"
Task: "agent-codex wrapper.py + Dockerfile aggregate turn.completed (T009)"
Task: "agent-pi wrapper.py + Dockerfile/entrypoint parse agent_end (T010)"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup (T001–T002).
2. Phase 2: Foundational (T003–T006) — shared report shape + Pipes launch + isolation proof.
3. Phase 3: US1 (T007–T014) — all four harnesses report uniformly; orchestrator attaches the union
   and drops per-harness parsing.
4. **STOP and VALIDATE**: run one agent per harness; confirm uniform reports (SC-001, SC-006, SC-002).

### Incremental Delivery

1. Setup + Foundational → launch reports under Pipes with isolation intact.
2. US1 → uniform reports attached (MVP; SC-001/SC-002/SC-006).
3. US2 → failed/timed-out asset runs recorded (SC-003/SC-004).
4. US3 → live log streaming (SC-005).
5. Polish → docs, schema validation, full quickstart + suites.

---

## Notes

- [P] = different files, no dependencies; the `make_run_op` and `test_reports.py` chains above are
  deliberately **not** [P].
- Tests are included by design (research R9); parser tests are fixture-driven and schema-validated.
- Constitution I/V: never drop an isolation flag and never write the messages file to `/output`;
  T004 and T006 enforce and prove this.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
</content>
</invoke>
