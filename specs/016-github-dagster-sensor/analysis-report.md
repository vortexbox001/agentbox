# Specification Analysis Report — 016-github-dagster-sensor

**Feature**: GitHub Project Status Trigger — Board-Driven Agent Launches
**Date**: 2026-09-17
**Command**: `/speckit-analyze` (read-only cross-artifact consistency check)
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `research.md`,
`contracts/{agent-model,orchestrator-model,github-projects-query,ui-automation-and-runs}.md`,
`.specify/memory/constitution.md`
**Prerequisite check**: `check-prerequisites.sh --json --require-spec --require-tasks
--include-tasks` → `FEATURE_DIR` resolved, all required files present. `.specify/extensions.yml`
registers no `before_analyze` / `after_analyze` hooks (empty `hooks: {}`), so none were run.

> **Scope of this run**: This is an **independent re-analysis**, not a re-print of the prior report.
> The seven findings from the earlier pass (F1–F7) were re-checked and are **confirmed resolved**
> (see §A), including spot-verification of the code-reality claims against the actual repository.
> This pass then ran fresh detection over all artifacts and surfaced **two new findings** (N1, N2)
> that the prior report did not catch — one MEDIUM (touching the MVP launch path) and one LOW.
> Because this command is **read-only**, no artifact was edited; §Next Actions lists the recommended
> remediation for a follow-up `/speckit-specify` / `/speckit-tasks` edit.

## Summary verdict

The artifact set is strongly aligned: all 26 functional requirements map to at least one task,
terminology is consistent, the plan/contracts/data-model reinforce the spec, and the constitution
check is accurate. **No CRITICAL or constitution-violating issues were found.**

However, one **MEDIUM** ambiguity remains in how the sensor's **first tick** is discriminated
(`empty cursor` vs `no seen`). The natural `not seen` reading regresses the primary MVP flow — the
US1 independent test turns the sensor on against an *empty* column and *then* moves an issue in — so
it is worth pinning before `/speckit-implement`. One additional **LOW** inconsistency exists around
the cursor `version` field.

---

## New Findings (this run)

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| N1 | Ambiguity / Coverage Gap | **MEDIUM** | contracts/orchestrator-model.md §2 step 1 ("`cursor_state` empty / no `seen`"); data-model.md:81; spec.md FR-007/US1 Independent Test; tasks.md T014/T015 | The "first tick" discriminator is stated two ways: **"empty cursor"** (data-model, tasks) vs **"cursor_state empty / no `seen`"** (orchestrator-model §2.1). These diverge for a sensor **started against an empty column**: on the true first tick `S = {}`, so `next_cursor.seen = {}`; if first-tick detection keys off `not seen` (empty dict is falsy), the *next* populated tick is misclassified as another "first tick" and seeds the genuine arrival `eligible: false` — so it **never launches**. This is exactly the US1 Independent Test path ("turn the sensor on … move an issue into the target status"), which is **not** covered by any task (T014 only tests a first tick with items *already present*). | Pin the discriminator to **presence of the cursor string** (`context.cursor` falsy / `cursor_state == {}`), never to `seen` being empty; ensure `plan_tick` always returns a non-empty `next_cursor` (e.g. carrying `version`, see N2) so a later empty-board tick is unambiguous. Add a `plan_tick` test: **first tick with an empty board seeds nothing; the next tick's new arrival is `eligible: true` and launches** (extend T014). |
| N2 | Inconsistency | LOW | data-model.md:73 (`{"version": 1, "seen": {…}}`) vs contracts/orchestrator-model.md §1–§2 (`plan_tick` / `next_cursor` described only in terms of `seen`) | The persisted cursor shape in `data-model.md` includes a top-level `"version": 1` field, but the orchestrator contract's `plan_tick` / `next_cursor` description never mentions `version` — leaving it unspecified whether `plan_tick` must emit and round-trip it. (A stable `version` marker also makes the N1 first-tick discriminator robust, since a seeded-but-empty board would still persist `{"version":1,"seen":{}}` → non-empty.) | State in orchestrator-model §2 that `next_cursor` always carries `{"version": 1, "seen": {…}}` and that `plan_tick` preserves/sets `version`; optionally assert it in a T014/T015 test. |

---

## §A Prior findings (F1–F7) — re-verified RESOLVED

Re-checked against the current artifacts and the repository. All remain resolved:

| ID | Prior severity | Re-check result |
|----|----------------|-----------------|
| F1 | HIGH | **Resolved.** The three-field cursor (`entered_at, launched, eligible`) is applied consistently in data-model.md (cursor shape + rows), orchestrator-model §1–§2 (seed/new/carried/admit), and tasks.md T014/T015/T017; the decision is recorded in spec.md Clarifications ("Session 2026-09-17 (analysis remediation)"). Admission = `launched:false && eligible:true`, so a pre-existing (seeded) item cannot launch by being carried. |
| F2 | MEDIUM | **Resolved.** T019 implements the `Unresolvable("status option '<status>'")` raise in `filter_items` (owning the T024 expectation); orchestrator-model §1 and github-projects-query §4 state it. |
| F3 | MEDIUM | **Resolved.** T046 verifies FR-018 (`is_automated_run` true, `governor_gate` applies, `derive_chain_depth == 1`). |
| F4 | LOW | **Resolved + code-verified.** Contract and T038 use `set_instigation(kind, name, running)`; confirmed the real signature is `async def set_instigation(kind: str, name: str, running: bool)` at `ui/dagster.py:632`, called at `ui/main.py:735`. |
| F5 | LOW | **Resolved.** Defensive skip of an issue with absent/blank `repository.nameWithOwner` is in T019, asserted by T018, and stated in data-model.md, orchestrator-model §1, and github-projects-query §4. |
| F6 | LOW | **Resolved.** `label` = **exact membership** (not substring), pinned in FR-001, data-model.md, both contracts, and T018/T019. |
| F7 | LOW | **Resolved.** `label` matched **case-insensitively**, consistent with `status`/`repo`; stated in FR-001 + Clarifications and applied across contracts and tasks. |

**Code-reality spot-checks** (Constitution VI): `SCHEMA_VERSION == 7` today with migrations through
`migrate_6_to_7` in `ui/schema.py` — so the 7→8 bump + identity `migrate_7_to_8` is correct and
consistent; `_prepare_upstream_handoff`, `STAGING_ROOT`, and `_launch_mounts(cfg, ws, handoff_dir)`
exist in `orchestrator/factory.py` (the issue handoff twin is a faithful mirror); `orchestrator/redact.py`
masks `ghp_` / `github_pat_` / `gho_` prefixes and a `TOKEN`/`AUTH` name rule, so FR-017's
"passes through existing redaction" holds without new code.

---

## Coverage Summary Table (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 trigger fields | ✅ | T003, T029, T034, T035, T037 | schema + emitter + orchestrator cfg; `label` exact-membership/case-insensitive (F6/F7) |
| FR-002 both kinds / composes | ✅ | T006, T007, T012, T013 | per-kind RunRequest (`asset_selection` / `job_name`) |
| FR-003 dedicated polling sensor | ✅ | T012 | `project_status_<name>`, STOPPED |
| FR-004 filter issues/status/label/repo | ✅ | T008, T018, T019 | excluded items never reach `plan_tick` (never hold slot) |
| FR-005 once-per-entry cursor | ✅ | T009, T014, T015 | three-field cursor w/ `eligible` (F1); **see N1** |
| FR-006 run key | ✅ | T009, T014, T015 | `<item_id>:<entered_at>` |
| FR-007 first-tick suppression | ✅ | T014, T015, T017 | seeded ids `eligible:false`; **N1: empty-board first tick under-covered** |
| FR-008 one-feature slot | ✅ | T016, T017 | per-agent |
| FR-009 held reported | ✅ | T016, T017 | holder named |
| FR-010 oldest-first release | ✅ | T016, T017 | held = `eligible:true` |
| FR-011 feature key | ✅ | T004, T020 | grammar/cap pinned |
| FR-012 run tags | ✅ | T005, T009 | five `agentbox/issue_*` |
| FR-013 env values | ✅ | T006, T010, T011 | five `AGENTBOX_ISSUE_*` |
| FR-014 body `:ro` file | ✅ | T010, T011 | reuses spec-013 handoff |
| FR-015 title/body data + sanitize | ✅ | T004, T010, T020 | 256-cap, control-stripped |
| FR-016 token only from GITHUB_PROJECT_TOKEN | ✅ | T021, T023 | no fallback |
| FR-017 token isolation | ✅ | T021, T022, T023 | redaction verified present |
| FR-018 automated run / governor / depth 1 | ✅ | T046 | verification task (F3) |
| FR-019 transient error → skip, cursor untouched | ✅ | T024, T027 | |
| FR-020 unresolvable → skip naming it | ✅ | T019, T024, T026, T027 | status-option raise in T019 (F2) |
| FR-021 pagination + shared query | ✅ | T024, T025, T026, T027 | |
| FR-022 re-homable observation/admission | ✅ | T003, T009 | hard module seam |
| FR-023 load-time validation | ✅ | T028, T029 | per-agent reject (note: T029 also validates `repo` shape, which is stricter than FR-023's listed fields — additive, benign) |
| FR-024 schema group + comment + migration | ✅ | T030, T034, T036, T037, T043 | 7→8 identity |
| FR-025 automation view (toggle/desc/held) | ✅ | T032, T038, T039, T040, T041 | `set_instigation` signature correct (F4) |
| FR-026 run page issue link | ✅ | T032, T039, T042 | |

**Success Criteria (buildable):** SC-001…SC-009 map to their user-story test tasks (T005–T029);
SC-010 (full behaviour unit-tested, GitHub faked, no network call) maps to T002 + T047. **N1** notes
that SC-001/SC-002's implied empty-board-start path (turn sensor on, then move an issue in) lacks a
dedicated test. No post-launch/outcome KPIs are present (nothing to exclude).

---

## Constitution Alignment Issues

**None.** The plan's Constitution Check (plan.md:167-209) is accurate against all seven principles:

- **I. Agent Isolation** — board token is daemon-only; the only run additions are issue-identity env
  values and a **read-only** `:ro` body mount. ✅
- **II. Configuration over Code** — `on_project_status` is declarative agent YAML, discovered at
  reload; the sensor code is generic over the block. ✅
- **III. Secrets Never in the Open** — `GITHUB_PROJECT_TOKEN` passthrough-by-name, no CLI/log/tag/file
  exposure; `orchestrator/redact.py` masks the token shapes (verified). ✅
- **IV. Uniform Interface** — the handoff is harness-agnostic; no per-harness code path added. ✅
- **V. Ephemeral Runs, Immutable Outputs** — body delivered read-only. ✅
- **VI. Docs Track Reality** — schema 7→8 + golden regen (T043); README + `.env.example` updates
  (T044/T045); the F4 `set_instigation` drift is corrected and matches `ui/dagster.py:632`. ✅
- **VII. One Design System** — new UI composed from shared macros + tokens, pinned by
  `test_conformance.py` (T033). ✅

---

## Unmapped Tasks

**None.** Every task T001–T047 maps to Setup, Foundational, a user story (US1–US9), or Polish. No
task references a file or component absent from the plan/spec.

---

## Metrics

- **Total Functional Requirements**: 26 (FR-001…FR-026)
- **Total Success Criteria**: 10 (SC-001…SC-010; all buildable/testable, no KPI exclusions)
- **Total Tasks**: 47 (T001…T047)
- **Requirement coverage**: 26/26 FRs have ≥1 task = **100%** mapped
- **Ambiguity count**: 1 open (N1 — first-tick discriminator)
- **Inconsistency count**: 1 open (N2 — cursor `version` field)
- **Duplication count**: 0 defects — the three cross-package duplications in plan.md Complexity
  Tracking are deliberate, documented, and pinned by tests
- **Critical issues count**: **0**
- **High issues count**: **0**
- **Medium issues count**: **1** (N1)
- **Low issues count**: **1** (N2)
- **Prior findings (F1–F7)**: all re-verified **resolved**

---

## Next Actions

No CRITICAL or constitution issues block `/speckit-implement`. Two items are worth closing first;
because `/speckit-analyze` is read-only, none were applied here.

1. **N1 (MEDIUM, recommended before implement)** — Pin the first-tick discriminator to the
   **absence of the cursor** (`context.cursor` falsy / `cursor_state == {}`), *not* to `seen` being
   empty, in `contracts/orchestrator-model.md §2 step 1` (align its "empty cursor / no `seen`"
   wording with data-model.md/tasks.md "empty cursor"). Add a `plan_tick` test in **T014** for the
   empty-board start: first tick with `S = {}` seeds nothing; the next tick's new arrival is
   `eligible: true` and launches. This protects the US1 MVP path.
2. **N2 (LOW)** — State in `orchestrator-model.md §2` that `plan_tick` always returns
   `next_cursor = {"version": 1, "seen": {…}}` and preserves `version`, matching `data-model.md:73`;
   optionally assert it in T014/T015.

Suggested commands: `/speckit-specify` (or a manual edit of `contracts/orchestrator-model.md` +
`tasks.md` T014) to close N1/N2, then re-run `/speckit-analyze` to confirm zero open findings before
`/speckit-implement`.

## Offer to remediate

Would you like concrete remediation edits drafted for N1 and N2 (the orchestrator-model wording +
the new T014 empty-board test)? They are **not** applied automatically. *(Running unattended: no
edits were made; this report is the durable record of the read-only analysis.)*
