---
description: "Task list for the Shared Agent Base Image refactor (014)"
---

# Tasks: Shared Agent Base Image

**Input**: Design documents from `/specs/014-base-image-refactor/`

**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md,
contracts/agent-base-image.md, quickstart.md

**Tests**: No new automated tests are written by this feature. Behavioral parity is proven by the
**existing** `images/tests` suite passing *unchanged* (FR-008/SC-002); build-time behavior is proven
by the scripted checks in `quickstart.md`. Per the tasks template, test tasks are only authored when
new tests are requested — they are not here, so this list contains **verification** tasks (run the
unchanged suite / quickstart checks) rather than test-authoring tasks.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1–US4); Setup/Foundational/Polish carry none

## Path Conventions

This feature touches only the `images/` package plus two build entry points, per plan.md:

- Shared base (new): `images/agent-base/Dockerfile`
- Shell-based harness images: `images/agent-claude/Dockerfile`, `images/agent-pi/Dockerfile`,
  `images/agent-codex/Dockerfile`
- Standalone harness image: `images/agent-python/Dockerfile`
- Shared, unchanged: `images/lib/`, `images/tests/`
- Build entry points: `README.md` (build steps), `scripts/bootstrap.sh`
- All `docker build` commands run with the `images/` directory as context so `COPY lib/` resolves
  (research.md R4). No `docker-compose.yml`, orchestrator, UI, schema, or agent-YAML change.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the new base's home and capture the "before" baseline the footprint story needs.

- [ ] T001 Create the `images/agent-base/` directory as the home of the new shared base Dockerfile,
  per plan.md → Project Structure.
- [ ] T002 [P] Record the pre-refactor "before" state (quickstart.md §1): with the harness images as
  they exist today, capture `docker system df -v | grep -E 'agent-claude|agent-pi|agent-codex'` and
  note how the common OS/tool/runtime install is stored today (once if Docker already dedups the
  byte-identical layers, or up to three times otherwise) as context for the T016 single-storage
  check. This is a baseline snapshot, not a numeric target to beat (SC-005 is a structural claim —
  see spec Clarifications 2026-09-16).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Author and build the single shared base every shell-based harness depends on. This is
the single source of truth for the common tool set and the shared Python/`dagster-pipes` runtime.

**⚠️ CRITICAL**: US1, US2, and US3 cannot begin until `agentbox/agent-base` exists and builds.

- [ ] T003 Create `images/agent-base/Dockerfile` as the single source of truth (FR-001/002/003/013,
  research.md R1/R2/R3, data-model.md "Shared base image", contracts/agent-base-image.md):
  - `FROM node:20-slim` (Debian bookworm-slim, arm64; provides Node 20 + the uid-1000 `node` user).
  - One `apt-get update && apt-get install -y --no-install-recommends` line with the common tool set:
    `git curl ca-certificates ripgrep jq unzip build-essential python3 python3-pip`, then
    `rm -rf /var/lib/apt/lists/*`.
  - Add the official GitHub CLI apt repository (download the keyring to
    `/usr/share/keyrings/githubcli-archive-keyring.gpg`, write the `signed-by` source list to
    `/etc/apt/sources.list.d/github-cli.list` using `arch=$(dpkg --print-architecture)` so it matches
    the arm64 Pi target), then `apt-get update && apt-get install -y gh` (R2).
  - `RUN pip3 install --no-cache-dir --break-system-packages dagster-pipes==1.13.21` (identical pin to
    the current harnesses; FR-013/R3).
  - `WORKDIR /workspace`.
  - Leave the final `USER` as the image default (root) so downstream harnesses can `npm install -g`;
    the uid-1000 `node` user is inherited and available, and each thin harness switches to it
    (`USER node`) as its own last step — preserving today's behavior (data-model.md).
  - A header comment marking this file as the **one place** the common tool set and shared runtime
    live (FR-003/SC-001).
- [ ] T004 Build and smoke-test the base (contracts/agent-base-image.md guarantees, quickstart.md §2–§3):
  from the `images/` context run `docker build -f agent-base/Dockerfile -t agentbox/agent-base .`,
  then confirm `git curl rg jq gh unzip cc python3` all resolve and
  `python3 -c "import dagster_pipes"` succeeds. (Depends on T003.)

**Checkpoint**: `agentbox/agent-base` builds and exposes the full common surface — shell-based
harnesses can now build on it.

---

## Phase 3: User Story 1 - Rebuild every harness on one shared base with identical behavior (Priority: P1) 🎯 MVP

**Goal**: Rebuild `agent-claude`, `agent-pi`, and `agent-codex` as thin `FROM agentbox/agent-base`
layers that add only their harness, with behavior functionally/format-identical to before and no
agent YAML changed.

**Independent Test**: Build `agent-base`, then the four harness images; run one existing agent of
each harness end to end and confirm its report/output match a pre-refactor run; confirm no agent YAML
changed (approximated hermetically by `images/tests` passing unchanged, per FR-008/SC-002).

### Implementation for User Story 1

- [ ] T005 [P] [US1] Rewrite `images/agent-claude/Dockerfile` as a thin layer (FR-004/005/006,
  data-model.md): `FROM agentbox/agent-base`; a one-line comment stating the common tooling comes from
  `agent-base`; keep `RUN npm install -g @anthropic-ai/claude-code`, `COPY lib/ /app/lib/`,
  `COPY agent-claude/wrapper.py /app/wrapper.py`, a final `USER node`, and the unchanged
  `ENTRYPOINT ["python3", "/app/wrapper.py"]`; **remove** the `apt-get` install, the `python3`/`pip`
  install, the `dagster-pipes` install, and the `WORKDIR` line (all inherited from the base).
- [ ] T006 [P] [US1] Rewrite `images/agent-pi/Dockerfile` as a thin layer (FR-004/005/006): `FROM
  agentbox/agent-base`; one-line base pointer comment; keep
  `RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent`, `COPY lib/ /app/lib/`,
  `COPY agent-pi/wrapper.py /app/wrapper.py`, `COPY agent-pi/entrypoint.sh /app/entrypoint.sh` +
  `RUN chmod 755 /app/entrypoint.sh`, a final `USER node`, and the unchanged
  `ENTRYPOINT ["/app/entrypoint.sh"]`; **remove** the shared `apt-get`/`python3`/`pip`/`dagster-pipes`
  and `WORKDIR` lines.
- [ ] T007 [P] [US1] Rewrite `images/agent-codex/Dockerfile` as a thin layer (FR-004/005/006): `FROM
  agentbox/agent-base`; one-line base pointer comment; keep `RUN npm install -g @openai/codex`,
  `ENV CODEX_HOME=/creds` (harness-specific env), `COPY lib/ /app/lib/`,
  `COPY agent-codex/wrapper.py /app/wrapper.py`, a final `USER node`, and the unchanged
  `ENTRYPOINT ["python3", "/app/wrapper.py"]`; **remove** the shared
  `apt-get`/`python3`/`pip`/`dagster-pipes` and `WORKDIR` lines.
- [ ] T008 [P] [US1] Update `README.md` step 4 "Build the agent images" (FR-012, research.md R4):
  build `agentbox/agent-base` **first**, then the four harness images, and correct every `docker build`
  to use `-f images/<image>/Dockerfile … .` with the `images/` directory as context (fixing the
  pre-existing build-context bug where `images/agent-*` was passed as context but the Dockerfiles
  `COPY lib/`).
- [ ] T009 [P] [US1] Update `scripts/bootstrap.sh` to build `agentbox/agent-base` first and then the
  four harness images from the `images/` context (base-first build order; FR-012). Today the script
  does host setup only and builds no images — add the base-first image build step.
- [ ] T010 [US1] Build the three thin harness images on the base from the `images/` context
  (`docker build -f agent-claude/Dockerfile -t agentbox/agent-claude .`, and likewise for
  `agent-pi`/`agent-codex`) and confirm each build resolves `FROM agentbox/agent-base`. (Depends on
  T004, T005, T006, T007.)
- [ ] T011 [P] [US1] Verify the common tools are present and runnable in every shell-based harness
  (FR-007/SC-004, quickstart.md §3): for `agent-claude`, `agent-pi`, `agent-codex` confirm
  `git curl rg jq gh unzip cc python3` resolve and `python3 -c "import dagster_pipes"` prints OK, with
  no `MISSING:` line. (Depends on T010.)
- [ ] T012 [P] [US1] Verify behavioral parity (FR-008/SC-002, quickstart.md §6): run
  `.venv/bin/python -m pytest -q images/tests` and confirm the suite passes **unchanged** — same
  wrapper/runner and report code, so report format and output semantics are unchanged. This is the
  **hermetic approximation** of US1's Independent Test ("run one agent of each harness end to end"):
  because the wrapper/runner and report code are untouched and the parser suite passes unchanged,
  functional/format equivalence is proven without a live run (FR-008 defines parity as
  functional/format equivalence, not a byte-identical rerun). *Optional, non-blocking*: an operator
  may additionally run one agent per harness end to end and compare its report/output to a
  pre-refactor run for extra confidence; this manual check is not required for the gate (analysis
  finding G1).
- [ ] T013 [P] [US1] Verify no agent YAML changed (FR-009/SC-006, quickstart.md §7):
  `git diff --name-only | grep -E '/agents/.*\.ya?ml$'` returns nothing.

**Checkpoint**: The three shell-based harnesses run on the shared base, tools resolve, `images/tests`
passes unchanged, and no agent YAML changed — MVP is complete and independently demonstrable.

---

## Phase 4: User Story 2 - Add a tool for all agents by changing one place (Priority: P1)

**Goal**: Prove that a tool shared by every shell-based agent is added in exactly one place, with zero
edits to any harness image definition.

**Independent Test**: Add `yq` to the shared common tool list, rebuild the base and one harness, and
confirm `yq` is present in that harness with no change to the harness Dockerfile.

### Implementation for User Story 2

- [ ] T014 [US2] Verify single-source-of-truth (SC-001/US2, quickstart.md §5): temporarily append
  `yq` to the one `apt-get install` line in `images/agent-base/Dockerfile`, rebuild `agent-base` and
  `agent-claude` from the `images/` context **without editing** `images/agent-claude/Dockerfile`,
  confirm `command -v yq` resolves in `agent-claude` and `git diff --stat images/agent-claude/Dockerfile`
  shows no change, then **revert** the temporary `yq` edit. (Depends on T010.)
- [ ] T015 [P] [US2] Verify no shell-based harness re-declares the shared install (FR-003/SC-003/US2,
  quickstart.md §4): for `images/agent-claude/Dockerfile`, `images/agent-pi/Dockerfile`, and
  `images/agent-codex/Dockerfile` confirm none matches
  `apt-get|^WORKDIR|python3-pip|dagster-pipes|useradd|adduser`, that each inherits the base's uid-1000 `node` user
  rather than creating one (no `useradd`/`adduser` line — none existed before the refactor either, so
  this grep guards against a regression rather than removing an existing line), that each has
  `FROM agentbox/agent-base`, and that each carries the one-line base pointer (FR-006). (Depends on
  T005–T007.)

**Checkpoint**: Adding a tool for all shell-based agents is proven to be a one-line, one-place change.

---

## Phase 5: User Story 3 - Common work built and stored once, faster rebuilds (Priority: P2)

**Goal**: Confirm the common OS+tool+runtime install is stored once — the three shell-based harnesses
share a single `agent-base` layer (deduplicated, counted once) instead of each carrying its own copy.

**Independent Test**: Inspect deduplicated on-disk usage and confirm the three harnesses share one
`agent-base` layer (common install stored once, not three times) — a structural check, not a raw
"smaller than before" comparison, since the base standardizes net-new tools.

### Implementation for User Story 3

- [ ] T016 [US3] Confirm the shared install is stored once, not three times (FR-011/SC-005,
  quickstart.md §9): `docker system df -v | grep -E 'agent-base|agent-claude|agent-pi|agent-codex'`
  and confirm the three shell-based harnesses share the single `agent-base` layer (the common
  OS+tool+runtime install counted once in deduplicated usage) rather than each carrying its own copy —
  do **not** sum per-image `docker images` SIZE, which counts the base three times (research.md R5).
  This is a structural single-storage check, not a raw "smaller than the T002 baseline" comparison:
  the base standardizes net-new tools (`ripgrep`/`jq`/`gh`/`unzip`/`build-essential`), so the raw
  total need not shrink (spec Clarifications 2026-09-16). (Depends on T002, T010.)

**Checkpoint**: The shared OS+tool+runtime install is stored once instead of three times — the three
shell-based harnesses share the single `agent-base` layer (structural single-storage win; the raw
total need not shrink, since the base standardizes net-new tools).

---

## Phase 6: User Story 4 - Keep a harness on its own base when it can't share (Priority: P3)

**Goal**: Leave `agent-python` on its own base with a documented reason, without adding shell tools it
does not need (the null-action safeguard).

**Independent Test**: Confirm `agent-python` still uses `python:3.12-slim`, records why it stays off
the shared base, and did not gain the common shell tool set.

### Implementation for User Story 4

- [ ] T017 [US4] Edit `images/agent-python/Dockerfile` (comment only; FR-010/US4, data-model.md
  "Standalone harness image"): keep `FROM python:3.12-slim` and its own
  `dagster-pipes==1.13.21` pin, and add a one-line comment recording why it stays off `agent-base`
  (it needs the Python runtime, not the Node-bearing base, and no shell tools). Add no shared shell
  tools.
- [ ] T018 [P] [US4] Verify the standalone exception (FR-010/US4, quickstart.md §8): confirm
  `images/agent-python/Dockerfile` still has `FROM python:3.12-slim`, the reason is documented, and it
  did not gain the common shell tool set. (Depends on T017.)

**Checkpoint**: `agent-python` stays correctly standalone with its reason recorded.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and a final scope check.

- [ ] T019 [P] Run the full `specs/014-base-image-refactor/quickstart.md` verification end to end
  (§1–§9) and confirm every step reports its Expected result.
- [ ] T020 [P] Confirm the refactor stayed within scope (plan.md → Scale/Scope): the only changed
  files are under `images/`, plus `README.md` and `scripts/bootstrap.sh` — no orchestrator, UI,
  schema, `docker-compose.yml`, or agent-YAML change.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS US1, US2, US3** (they build on `agent-base`).
- **US1 (Phase 3)**: Depends on Foundational. The MVP.
- **US2 (Phase 4)**: Depends on Foundational + the thin harness Dockerfiles (T005–T007) and one built
  harness (T010).
- **US3 (Phase 5)**: Depends on the T002 baseline and the rebuilt harnesses (T010).
- **US4 (Phase 6)**: Depends only on Setup — `agent-python` is standalone and has **no** dependency on
  `agent-base`; it can be done in parallel with Phases 2–5.
- **Polish (Phase 7)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only. Independently testable (tools resolve, tests pass, no YAML change).
- **US2 (P1)**: Builds on US1's thin harnesses but is independently demonstrable (the yq experiment).
- **US3 (P2)**: Builds on US1's rebuilt images; independently measurable.
- **US4 (P3)**: Fully independent of the shared base (touches only `agent-python`).

### Within Each User Story

- Author Dockerfiles before building; build before verifying.
- Verification tasks (`images/tests`, tool resolution, footprint, greps) run after their images exist.

### Parallel Opportunities

- **Setup**: T002 can run alongside T001.
- **US1**: T005, T006, T007 (three different harness Dockerfiles), and T008, T009 (README +
  bootstrap) are all independent — do them in parallel. After T010, the verifications T011/T012/T013
  run in parallel.
- **US2**: T015 (static grep) is independent of T014.
- **US4**: T017/T018 are independent of Phases 2–5 and can proceed in parallel from the start.
- **Polish**: T019 and T020 are independent.

---

## Parallel Example: User Story 1

```bash
# Author all three thin harness Dockerfiles + the two build entry points together:
Task: "Rewrite images/agent-claude/Dockerfile as FROM agentbox/agent-base thin layer"
Task: "Rewrite images/agent-pi/Dockerfile as FROM agentbox/agent-base thin layer"
Task: "Rewrite images/agent-codex/Dockerfile as FROM agentbox/agent-base thin layer"
Task: "Update README.md build steps (base first, images/ context)"
Task: "Update scripts/bootstrap.sh (build base first, then harnesses)"

# After building the harnesses (T010), run the verifications together:
Task: "Verify common tools resolve in each harness"
Task: "Run images/tests unchanged (parity)"
Task: "Verify no agent YAML changed"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (create `images/agent-base/`, record before-footprint).
2. Phase 2: Foundational (author + build `agent-base`) — **CRITICAL, blocks US1–US3**.
3. Phase 3: User Story 1 (thin harnesses + build-order docs + parity verification).
4. **STOP and VALIDATE**: `images/tests` passes unchanged, tools resolve, no agent YAML changed.

### Incremental Delivery

1. Setup + Foundational → shared base ready.
2. US1 → the three harnesses run on the base, parity verified → **MVP**.
3. US2 → prove the one-place tool addition (yq experiment).
4. US3 → confirm the shared install is stored once (deduplicated), not three times.
5. US4 → `agent-python` standalone reason (independent; can land any time after Setup).
6. Polish → full quickstart run + scope check.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- No new automated tests are authored: parity is the **existing** `images/tests` passing unchanged
  (FR-008/SC-002); build behavior is the scripted `quickstart.md` checks.
- All `docker build` commands run from the `images/` context (research.md R4).
- Commit after each logical group; the temporary `yq` edit in T014 must be reverted before commit.
- Avoid: adding OS-package installs, user creation, `WORKDIR`, or a `python3`/`dagster-pipes` line to
  any thin harness (that breaks the single-source-of-truth requirement, SC-003).
