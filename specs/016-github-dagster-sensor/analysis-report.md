# Specification Analysis Report — 016-github-dagster-sensor

**Feature**: GitHub Project Status Trigger — Board-Driven Agent Launches
**Date**: 2026-09-17
**Command**: `/speckit-analyze` (read-only cross-artifact consistency check) + remediation pass
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `research.md`,
`contracts/{agent-model,orchestrator-model,github-projects-query,ui-automation-and-runs}.md`,
`.specify/memory/constitution.md`
**Prerequisite check**: `check-prerequisites.sh --json --require-spec --require-tasks
--include-tasks` → `FEATURE_DIR` resolved, all required files present. `.specify/extensions.yml`
registers no `before_analyze` / `after_analyze` hooks (empty `hooks: {}`), so none were run.

> **Scope of this run**: This report records the **post-remediation** state. A prior read-only pass
> surfaced two findings (N1 MEDIUM, N2 LOW) on top of the earlier F1–F7 (all previously resolved).
> N1 and N2 have now been **acted on** by editing the artifacts (spec/plan/tasks/contracts are the
> only things touched — no feature code), and a re-analysis confirms **zero open findings**. §A
> records the F1–F7 re-verification; §B records the N1/N2 remediation.

## Summary verdict

The artifact set is fully aligned: all 26 functional requirements map to at least one task,
terminology is consistent, the plan/contracts/data-model reinforce the spec, and the constitution
check is accurate. **No CRITICAL, HIGH, MEDIUM, or LOW open issues remain, and no constitution
violation was found.** The MVP launch path (US1: turn the sensor on against an empty column, then
move an issue in) is now explicitly pinned and covered by a task.

---

## Open Findings (this run)

**None.** N1 and N2 are resolved (see §B).

---

## §B N1–N2 — remediation applied (this pass)

| ID | Category | Prior severity | Resolution |
|----|----------|----------------|------------|
| N1 | Ambiguity / Coverage Gap | MEDIUM | **Resolved.** The first-tick discriminator is pinned to the **presence of the cursor string** (`context.cursor` falsy ⇒ `plan_tick` receives `cursor_state == {}`), **never** to `seen` being empty. `contracts/orchestrator-model.md §2` step 1 was reworded from "`cursor_state` empty / no `seen`" to "`cursor_state == {}` — no persisted cursor", and now explicitly handles the empty-board first start (`S = {}` still persists `{"version":1,"seen":{}}`, so the next tick is a normal tick and a genuine arrival is `eligible: true`). `data-model.md` first-tick row and `tasks.md` T015 align on the same discriminator. **Coverage gap closed**: `tasks.md` T014 now adds the empty-board start test (first tick with `S={}` seeds nothing; next tick's new arrival is `eligible:true` and launches — the US1 turn-on-then-move-in path). Decision recorded in `spec.md` Clarifications (Session 2026-09-17, analysis remediation). Consistent with FR-007's existing "first tick with no cursor" wording. |
| N2 | Inconsistency | LOW | **Resolved.** `contracts/orchestrator-model.md §2` now states (new step 3) that `plan_tick` **always** returns `next_cursor = {"version": 1, "seen": {…}}`, setting `version:1` when seeding and preserving a carried `version` — matching the persisted shape at `data-model.md`. A `version` row was added to the cursor table in `data-model.md`, and T014/T015 assert/emit it. This also hardens the N1 discriminator (a seeded-but-empty board persists a non-empty cursor). Decision recorded in `spec.md` Clarifications. |

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
| FR-005 once-per-entry cursor | ✅ | T009, T014, T015 | three-field cursor w/ `eligible` (F1) |
| FR-006 run key | ✅ | T009, T014, T015 | `<item_id>:<entered_at>` |
| FR-007 first-tick suppression | ✅ | T014, T015, T017 | seeded ids `eligible:false`; discriminator = cursor presence; empty-board start covered (N1) |
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
SC-010 (full behaviour unit-tested, GitHub faked, no network call) maps to T002 + T047. The
SC-001/SC-002 empty-board-start path (turn sensor on, then move an issue in) is now covered by the
extended T014 (N1 remediation).

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
- **Ambiguity count**: 0 open (N1 resolved)
- **Inconsistency count**: 0 open (N2 resolved)
- **Duplication count**: 0 defects — the three cross-package duplications in plan.md Complexity
  Tracking are deliberate, documented, and pinned by tests
- **Critical issues count**: **0**
- **High issues count**: **0**
- **Medium issues count**: **0** (N1 resolved)
- **Low issues count**: **0** (N2 resolved)
- **Prior findings (F1–F7)**: all re-verified **resolved**; **N1–N2**: **resolved this pass**

---

## Next Actions

**No open findings.** No CRITICAL or constitution issues block `/speckit-implement`; the previously
open N1 (MEDIUM) and N2 (LOW) are resolved and recorded in `spec.md` Clarifications. The artifact set
is ready for `/speckit-implement`.
