# Specification Analysis Report — 016-github-dagster-sensor

**Feature**: GitHub Project Status Trigger — Board-Driven Agent Launches
**Date**: 2026-09-17
**Command**: `/speckit-analyze` (read-only cross-artifact consistency check)
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `research.md`,
`contracts/{agent-model,orchestrator-model,github-projects-query,ui-automation-and-runs}.md`,
`.specify/memory/constitution.md`
**Prerequisite check**: `check-prerequisites.sh --json --require-spec --require-tasks
--include-tasks` → FEATURE_DIR resolved, all required files present.

> **Remediation status (this revision)**: All 7 findings from the prior run (F1–F7) have been acted
> on by editing the artifacts that were actually wrong. A re-analysis after the edits found **zero
> open findings**. The "Findings" table below is retained as an audit trail with each row marked
> **RESOLVED** and the edits that closed it; the sections after it describe the current (post-fix)
> state. The three judgment calls (the F1 cursor design and the F6/F7 `label` semantics) are recorded
> in `spec.md` → `## Clarifications` → **Session 2026-09-17 (analysis remediation)**.

## Summary verdict

The three core artifacts are aligned: every functional requirement maps to at least one task,
terminology is consistent, and the plan/contracts/data-model reinforce the spec. **No CRITICAL or
constitution-violating issues were found**, and the one HIGH design-consistency defect (F1) has been
resolved by adding a third cursor state.

The F1 fix: the sensor cursor entry gained an explicit `eligible` field, so a **held** item
(`launched: false, eligible: true` — must launch when the slot frees, FR-010) is now distinct from a
**first-tick-seeded / pre-existing** item (`launched: false, eligible: false` — must never launch,
FR-007). Admission considers only `launched: false && eligible: true` ids, so a pre-existing item can
never be launched by being carried forward, restoring the P1 exactly-once guarantee. This is applied
consistently in `data-model.md`, `contracts/orchestrator-model.md`, `research.md`, and pinned by a new
"second tick after first-tick seeding launches nothing" test in `tasks.md` T014.

---

## Findings (all RESOLVED — audit trail)

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| F1 | Inconsistency / Underspecification | **HIGH** | contracts/orchestrator-model.md §1–§2; data-model.md cursor; spec.md FR-005/FR-007/FR-010 | The two-field cursor `{entered_at, launched}` made a **held** item and a **first-tick-seeded** item indistinguishable (both `launched: false`), so pre-existing items seeded on the first tick would launch on the **second** tick — violating FR-007/SC-005. | **RESOLVED.** Added a third cursor field `eligible`. First-tick seeds `{…, launched: false, eligible: false}` (never a candidate); genuine arrivals get `eligible: true`. Admission = `launched: false && eligible: true`. Updated data-model.md (cursor shape + rows), orchestrator-model.md §1/§2 (seed/new/carried/admit rules), research.md, and tasks.md T014 (new second-tick test), T015, T017. Decision recorded in spec.md Clarifications. |
| F2 | Coverage Gap | MEDIUM | contracts/orchestrator-model.md §1; tasks.md T019/T024 | The "configured status matches no option ⇒ `Unresolvable`" behaviour was **tested** (T024) but had no **implementation** task. | **RESOLVED.** T019 now explicitly implements the status-option resolution and `Unresolvable("status option '<status>'")` raise in `filter_items` (owning T024's expectation). |
| F3 | Coverage Gap | MEDIUM | spec.md FR-018; contracts/orchestrator-model.md §7; tasks.md | FR-018 (automated run: `dagster/sensor_name`, governor, depth 1) was asserted to need "no new code" but **no task verified it**. | **RESOLVED.** Added task T046: an `orchestrator/tests/test_factory.py` assertion that a sensor `RunRequest` yields an automated run (`is_automated_run` true, `governor_gate` applies, `derive_chain_depth` == 1). Renumbered the full-suite run to T047. |
| F4 | Inconsistency (doc vs. code) | LOW | contracts/ui-automation-and-runs.md; tasks.md T038; actual `ui/dagster.py:632` / `ui/main.py:735` | The contract and T038 gave the toggle helper the wrong argument order/keyword; the real signature is `set_instigation(kind, name, running)`. | **RESOLVED.** Corrected both to `set_instigation(kind="sensor", name=…, running=…)` and cited the real `ui/dagster.py:632` signature and `ui/main.py:735` call site. |
| F5 | Coverage Gap | LOW | spec.md CHK005; data-model.md; tasks.md | CHK005 (absent `repository.nameWithOwner` ⇒ item skipped defensively) had no implementing or testing task. | **RESOLVED.** T019 now defensively skips issues with an absent/blank repo in `filter_items`; T018 asserts it; noted in data-model.md, orchestrator-model.md §1, and github-projects-query.md. |
| F6 | Ambiguity | LOW | tasks.md T019; spec.md FR-001/US4 | "`label` … contains it" was ambiguous — list membership vs. substring. | **RESOLVED.** Pinned as **exact membership** of the label-name list (not substring) in spec.md FR-001, data-model.md, contracts (orchestrator-model §1, github-projects-query §4), and tasks.md T018/T019. |
| F7 | Ambiguity | LOW | spec.md FR-001 | The `label` filter's case sensitivity was unspecified while `status`/`repo` are case-insensitive. | **RESOLVED (decision).** `label` is matched **case-insensitively**, consistent with `status` and `repo`. Stated in spec.md FR-001 + Clarifications and applied across data-model.md, contracts, and tasks.md T018/T019. |

*(7 findings, all resolved. No new findings surfaced by the post-remediation re-analysis.)*

---

## Coverage Summary Table (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 trigger fields | ✅ | T003, T029, T034, T037 | schema + emitter + orchestrator cfg; `label` semantics/case now pinned (F6/F7) |
| FR-002 both kinds / composes | ✅ | T006, T007, T012, T013 | per-kind RunRequest |
| FR-003 dedicated polling sensor | ✅ | T012 | `project_status_<name>` |
| FR-004 filter issues/status/label/repo | ✅ | T008, T018, T019 | label = exact membership, case-insensitive (F6/F7); defensive repo-skip (F5) |
| FR-005 once-per-entry cursor | ✅ | T009, T014, T015 | three-field cursor w/ `eligible` (F1) |
| FR-006 run key | ✅ | T009, T014, T015 | `<item_id>:<entered_at>` |
| FR-007 first-tick suppression | ✅ | T014, T015, T017 | seeded ids are `eligible:false`, never candidates (F1); T014 second-tick test |
| FR-008 one-feature slot | ✅ | T016, T017 | per-agent |
| FR-009 held reported | ✅ | T016, T017 | holder named |
| FR-010 oldest-first release | ✅ | T016, T017 | held = `eligible:true`; launches oldest-first when slot frees (F1) |
| FR-011 feature key | ✅ | T004, T020 | grammar/cap pinned |
| FR-012 run tags | ✅ | T005, T009 | five `agentbox/issue_*` |
| FR-013 env values | ✅ | T006, T010, T011 | five `AGENTBOX_ISSUE_*` |
| FR-014 body `:ro` file | ✅ | T010, T011 | reuses spec-013 handoff |
| FR-015 title/body data + sanitize | ✅ | T004, T010, T020 | 256-cap, control-stripped |
| FR-016 token only from GITHUB_PROJECT_TOKEN | ✅ | T021, T023 | no fallback |
| FR-017 token isolation | ✅ | T021, T022, T023 | redaction verified present |
| FR-018 automated run / governor / depth 1 | ✅ | T046 | verification task added (F3) |
| FR-019 transient error → skip, cursor untouched | ✅ | T024, T027 | |
| FR-020 unresolvable → skip naming it | ✅ | T019, T024, T026, T027 | status-option raise now implemented in T019 (F2) |
| FR-021 pagination + shared query | ✅ | T024, T025, T026, T027 | |
| FR-022 re-homable observation/admission | ✅ | T003, T009 | hard module seam |
| FR-023 load-time validation | ✅ | T028, T029 | per-agent reject |
| FR-024 schema group + comment + migration | ✅ | T034, T036, T037, T043 | 7→8 identity |
| FR-025 automation view (toggle/desc/held) | ✅ | T032, T038, T039, T040, T041 | `set_instigation` signature corrected (F4) |
| FR-026 run page issue link | ✅ | T032, T039, T042 | |

**Success Criteria (buildable):** SC-001…SC-009 map to their user-story test tasks (T005–T029);
SC-010 (full behaviour unit-tested, GitHub faked, no network call) maps to T002 + T047. SC-002/SC-005
are now soundly covered by the F1 cursor fix and the new second-tick test (T014). Post-launch/outcome
KPIs: none present (nothing to exclude).

---

## Constitution Alignment Issues

**None.** The plan's Constitution Check (plan.md:167-209) is accurate against the seven principles:

- **I. Agent Isolation** — the board token is daemon-only; the only run additions are issue-identity
  env values and a **read-only** `:ro` body mount. ✅
- **II. Configuration over Code** — `on_project_status` is declarative agent YAML, discovered at
  reload; the sensor code is generic over the block. ✅
- **III. Secrets Never in the Open** — `GITHUB_PROJECT_TOKEN` passthrough-by-name, no CLI/log/tag/file
  exposure; `orchestrator/redact.py` already masks `ghp_`/`github_pat_`/`gho_` and `*TOKEN*`. ✅
- **IV. Uniform Interface** — the handoff is harness-agnostic; no per-harness code path added. ✅
- **V. Ephemeral Runs, Immutable Outputs** — body delivered read-only. ✅
- **VI. Docs Track Reality** — the one live drift (F4, `set_instigation` signature) is now corrected
  in the contract and T038 to match `ui/dagster.py:632`. ✅
- **VII. One Design System** — new UI composed from shared macros + tokens, pinned by
  `test_conformance.py` (T033). ✅

---

## Unmapped Tasks

**None.** Every task T001–T047 maps to Setup, Foundational, a user story (US1–US9), or Polish
(T046 FR-018 verification, T047 full-suite run). No task references a file or component absent from
the plan/spec.

---

## Metrics

- **Total Functional Requirements**: 26 (FR-001…FR-026)
- **Total Success Criteria**: 10 (SC-001…SC-010; all buildable/testable, no KPI exclusions)
- **Total Tasks**: 47 (T001…T047) — one added this revision (T046, FR-018 verification)
- **Requirement coverage**: 26/26 FRs have ≥1 task = **100%** mapped; **0 flagged** after remediation
  (FR-007/FR-010 resolved by F1's cursor fix; FR-018 covered by T046).
- **Ambiguity count**: 0 open (F6 label semantics and F7 label case both resolved)
- **Duplication count**: 0 defects — the three cross-package duplications in plan.md Complexity
  Tracking are deliberate, documented, and pinned by tests.
- **Critical issues count**: **0**
- **High issues count**: **0** (F1 resolved)
- **Medium/Low open**: **0** (F2–F7 resolved)

---

## Next Actions

**No open findings.** All 7 prior findings (F1 HIGH, F2/F3 MEDIUM, F4–F7 LOW) have been resolved by
editing the artifact that was wrong, and the two design decisions (F1 cursor `eligible` state; F6/F7
`label` = exact membership, case-insensitive) are recorded in `spec.md` → `## Clarifications`. The
artifact set is consistent, fully mapped, and constitution-compliant. This feature is ready for
`/speckit-implement`.
