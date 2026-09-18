# Specification Analysis Report — 016-github-dagster-sensor

**Feature**: GitHub Project Status Trigger — Board-Driven Agent Launches
**Date**: 2026-09-17
**Command**: `/speckit-analyze` (read-only cross-artifact consistency check)
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`,
`contracts/{agent-model,orchestrator-model,github-projects-query,ui-automation-and-runs}.md`,
`.specify/memory/constitution.md`
**Prerequisite check**: `check-prerequisites.sh --json --require-spec --require-tasks
--include-tasks` → FEATURE_DIR resolved, all required files present.

> This run was unattended. Where the skill would normally pause to offer remediation, no edits were
> applied — this report is the durable artifact and the source files (`spec.md`, `plan.md`,
> `tasks.md`) were left untouched.

## Summary verdict

The three core artifacts are unusually well aligned: every functional requirement maps to at least
one task, terminology is consistent, and the plan/contracts/data-model reinforce the spec rather than
drift from it. **No CRITICAL or constitution-violating issues were found.**

One **HIGH** design-consistency defect stands out: the cursor shape and the admission algorithm
(`plan_tick` §2) cannot simultaneously satisfy first-tick suppression (FR-007) and oldest-first held
release (FR-010) because both "held" and "pre-existing/seeded" items are represented identically as
`{entered_at, launched: false}`. As written, the algorithm would launch pre-existing items on the
**second** tick, violating a P1 exactly-once guarantee. This should be resolved before
`/speckit-implement`. The remaining findings are MEDIUM/LOW coverage gaps and doc-vs-code drift.

---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency / Underspecification | **HIGH** | contracts/orchestrator-model.md:49-72 (§2 "Admit: candidates = ids with `launched: false` (new + carried-unlaunched)"); data-model.md:72-82; spec.md FR-005/FR-007/FR-010 | The cursor stores only `{entered_at, launched}`, so a **held** item (entered while slot busy — must launch when the slot frees, FR-010) and a **first-tick-seeded/pre-existing** item (must never launch, FR-007/SC-005/US2 #4) are indistinguishable — both are carried with `launched:false`. Because `plan_tick` admits every carried-unlaunched id as a candidate, the three pre-existing items seeded on the first tick become candidates on the **second** tick and the oldest launches — directly contradicting FR-007/SC-005. FR-005 defines eligibility as edge-triggered ("appeared and was not present on the previous tick"), which the two-field cursor cannot express for a carried item. | Add a third state to the cursor (e.g. an explicit `eligible`/`admitted` flag, or seed first-tick items so they are never candidates while distinguishing genuinely-held items). Update data-model.md's cursor shape and orchestrator-model.md §2's "Admit" rule so "candidate" ≠ "any carried-unlaunched id". Add a `plan_tick` test: first tick seeds 3 items → second tick still launches **none** (currently only US2 T014 tests the first tick, not the tick after). |
| F2 | Coverage Gap | MEDIUM | contracts/orchestrator-model.md:24-29 (§1 `filter_items` "Raises `Unresolvable("status option '<status>'")`"); tasks.md T019/T024/T026 | The "configured status matches no option anywhere on the board ⇒ `Unresolvable`" behaviour is **tested** (T024, US7) but has no **implementation** task. T008 implements the case-insensitive match only; T019 (US4) extends `filter_items` with label/repo and does not mention raising; T026 (US7) implements error mapping in `fetch_board`, not `filter_items`. | Add the status-option-resolution/raise to an explicit implementation task (extend T019 or add to T026's scope for `filter_items`) so T024's expectation has an owner. |
| F3 | Coverage Gap | MEDIUM | spec.md FR-018; contracts/orchestrator-model.md:191-196 (§7 "No new code"); tasks.md (no matching task) | FR-018 (sensor-launched run is automated: carries `dagster/sensor_name`, counts toward the launch-rate governor, starts a chain at depth 1) is asserted to need "no new code," but **no task verifies it**. No orchestrator test confirms `is_automated_run` is true, `governor_gate` applies, or `derive_chain_depth` returns 1 for a `project_status` RunRequest. | Add a small verification task (in `orchestrator/tests/test_factory.py`) asserting a sensor RunRequest yields an automated run subject to the governor at depth 1 — otherwise a future refactor could silently regress FR-018. |
| F4 | Inconsistency (doc vs. code) | LOW | contracts/ui-automation-and-runs.md:35 (`set_instigation(name, kind="sensor", running)`); tasks.md T038 (same); actual `ui/dagster.py:632` = `set_instigation(kind, name, running)` and `ui/main.py:735` calls it positionally as `(kind, name, running)` | The contract and T038 describe the toggle helper with the wrong argument order/keyword; the real signature is `set_instigation(kind, name, running)`. Harmless to intent but will mislead the implementer and violates "Docs Track Reality" (Constitution VI). | Correct the signature reference in the contract and T038 to `set_instigation(kind="sensor", name=…, running=…)` (matching the existing call site). |
| F5 | Coverage Gap | LOW | spec.md:30 (CHK005) & Edge Cases; data-model.md:57; tasks.md (no matching task) | CHK005 ("if `repository.nameWithOwner` is ever absent the item is **skipped defensively** rather than launched with a blank repo") has no task explicitly implementing or testing the defensive skip. Low likelihood (issues always resolve a repo), but the clarification is unverified. | Fold a one-line defensive-skip assertion into T008/T018 (`fetch_board`/`filter_items`) so the clarified behaviour is pinned. |
| F6 | Ambiguity | LOW | tasks.md T019 ("`label` (issue `labels.nodes[].name` **contains** it)"); spec.md FR-001/US4 ("only issues **carrying** that label") | "contains it" is ambiguous — membership of the label-name list vs. substring match. FR-001's "carrying that label" implies exact membership; the task wording could be read as substring. | Reword T019 to "the issue's label names **include** `label` (exact, case-sensitive unless otherwise specified)" to remove the ambiguity, and pin it with a test vector. |
| F7 | Ambiguity | LOW | spec.md FR-001 (`status` matched case-insensitively) vs `label` (no case rule stated) | `status` and `repo` are explicitly case-insensitive; the `label` filter's case sensitivity is left unspecified across spec/plan/contracts/tasks. | State the `label` match's case rule once (spec Assumption or FR-001) so the implementation and its test agree. |

*(No overflow — 7 findings total, well under the 50-row cap.)*

---

## Coverage Summary Table (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 trigger fields | ✅ | T003, T029, T034, T037 | schema + emitter + orchestrator cfg |
| FR-002 both kinds / composes | ✅ | T006, T007, T012, T013 | per-kind RunRequest |
| FR-003 dedicated polling sensor | ✅ | T012 | `project_status_<name>` |
| FR-004 filter issues/status/label/repo | ✅ | T008, T018, T019 | see F6/F7 (label case/semantics) |
| FR-005 once-per-entry cursor | ✅ | T009, T014, T015 | **see F1** (eligibility ambiguity) |
| FR-006 run key | ✅ | T009, T014, T015 | `<item_id>:<entered_at>` |
| FR-007 first-tick suppression | ⚠️ | T014, T015 | **see F1** — algorithm conflicts with FR-010 |
| FR-008 one-feature slot | ✅ | T016, T017 | per-agent |
| FR-009 held reported | ✅ | T016, T017 | holder named |
| FR-010 oldest-first release | ⚠️ | T016, T017 | **see F1** — conflicts with FR-007 under 2-field cursor |
| FR-011 feature key | ✅ | T004, T020 | grammar/cap pinned |
| FR-012 run tags | ✅ | T005, T009 | five `agentbox/issue_*` |
| FR-013 env values | ✅ | T006, T010, T011 | five `AGENTBOX_ISSUE_*` |
| FR-014 body `:ro` file | ✅ | T010, T011 | reuses spec-013 handoff |
| FR-015 title/body data + sanitize | ✅ | T004, T010, T020 | 256-cap, control-stripped |
| FR-016 token only from GITHUB_PROJECT_TOKEN | ✅ | T021, T023 | no fallback |
| FR-017 token isolation | ✅ | T021, T022, T023 | redaction verified present |
| FR-018 automated run / governor / depth 1 | ⚠️ | (none) | **see F3** — no verification task |
| FR-019 transient error → skip, cursor untouched | ✅ | T024, T027 | |
| FR-020 unresolvable → skip naming it | ✅ | T024, T026, T027 | **see F2** (status-option impl gap) |
| FR-021 pagination + shared query | ✅ | T024, T025, T026, T027 | |
| FR-022 re-homable observation/admission | ✅ | T003, T009 | hard module seam |
| FR-023 load-time validation | ✅ | T028, T029 | per-agent reject |
| FR-024 schema group + comment + migration | ✅ | T034, T036, T037, T043 | 7→8 identity |
| FR-025 automation view (toggle/desc/held) | ✅ | T032, T038, T039, T040, T041 | see F4 (signature) |
| FR-026 run page issue link | ✅ | T032, T039, T042 | |

**Success Criteria (buildable):** SC-001…SC-009 map to their user-story test tasks (T005–T029);
SC-010 (full behaviour unit-tested, GitHub faked, no network call) maps to T002 + T046. SC-002/SC-005
depend on the FR-007/FR-010 resolution in **F1**. Post-launch/outcome KPIs: none present (nothing to
exclude).

---

## Constitution Alignment Issues

**None.** The plan's Constitution Check (plan.md:167-209) is accurate against the seven principles:

- **I. Agent Isolation** — the board token is daemon-only; the only run additions are issue-identity
  env values and a **read-only** `:ro` body mount. ✅
- **II. Configuration over Code** — `on_project_status` is declarative agent YAML, discovered at
  reload; the sensor code is generic over the block. ✅
- **III. Secrets Never in the Open** — `GITHUB_PROJECT_TOKEN` passthrough-by-name, no CLI/log/tag/file
  exposure; `orchestrator/redact.py` already masks `ghp_`/`github_pat_`/`gho_` and `*TOKEN*` (verified
  in-repo), so T023's "add the rule if a gap is found" is a no-op safety net. ✅
- **IV. Uniform Interface** — the handoff is harness-agnostic; no per-harness code path added. ✅
- **V. Ephemeral Runs, Immutable Outputs** — body delivered read-only. ✅
- **VI. Docs Track Reality** — README/`.env.example`/templates/golden updates are tasked (T043–T045);
  the one live drift is **F4** (`set_instigation` signature in a contract/task). ⚠️ (LOW)
- **VII. One Design System** — new UI composed from shared macros + tokens, pinned by
  `test_conformance.py` (T033). ✅

---

## Unmapped Tasks

**None.** Every task T001–T046 maps to Setup, Foundational, a user story (US1–US9), or Polish. No
task references a file or component absent from the plan/spec; all named product-tree files
(`orchestrator/github_projects.py`, `factory.py`, `definitions.py`, `ui/schema.py`, `agents_store.py`,
`main.py`, `dagster.py`, `static/*`, `templates/*`, `examples/config/agents/_template-*.yaml`,
`.env.example`, `README.md`) are real or newly-created-by-this-feature.

---

## Metrics

- **Total Functional Requirements**: 26 (FR-001…FR-026)
- **Total Success Criteria**: 10 (SC-001…SC-010; all buildable/testable, no KPI exclusions)
- **Total Tasks**: 46 (T001…T046)
- **Requirement coverage**: 26/26 FRs have ≥1 task = **100%** mapped; 3 flagged (FR-007, FR-010,
  FR-018) for a design conflict (F1) or missing verification (F3), not for zero coverage.
- **Ambiguity count**: 2 (F6 label semantics, F7 label case)
- **Duplication count**: 0 defects — the three cross-package duplications in plan.md Complexity
  Tracking are deliberate, documented, and pinned by tests (continuing the 004–013 discipline).
- **Critical issues count**: **0**
- **High issues count**: **1** (F1)
- **Medium/Low**: 2 MEDIUM (F2, F3) + 4 LOW (F4–F7)

---

## Next Actions

No CRITICAL or constitution issues block progress, but **one HIGH design conflict (F1) should be
resolved before `/speckit-implement`** — it undermines a P1 exactly-once guarantee.

1. **Resolve F1 (HIGH)** — extend the cursor with an explicit eligibility/admission state so held
   items (launch when slot frees) are distinguishable from first-tick-seeded items (never launch).
   Update `data-model.md` (cursor shape), `contracts/orchestrator-model.md` §2 (the "Admit" rule),
   and add a "second tick after first-tick seeding launches nothing" test in T014/T015.
   Suggested command: `/speckit-plan` refinement of the admission algorithm, then re-run
   `/speckit-analyze`.
2. **Close F2 & F3 (MEDIUM)** — assign the status-option `Unresolvable` implementation to a task
   (extend T019/T026) and add an FR-018 verification task. Manual edit of `tasks.md`.
3. **Fix F4–F7 (LOW)** — correct the `set_instigation` signature in the contract/T038; add the
   defensive repo-skip assertion (F5); disambiguate the `label` filter semantics and case rule
   (F6/F7) in the spec and T019.

Nothing else requires action: the artifact set is otherwise consistent, fully mapped, and
constitution-compliant. Once F1 is addressed and F2/F3 are tasked, this feature is ready for
`/speckit-implement`.
