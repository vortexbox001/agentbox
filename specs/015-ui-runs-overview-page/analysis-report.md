# Specification Analysis Report — Runs Overview Page (015)

**Command**: `/speckit-analyze` (non-destructive cross-artifact consistency check) + remediation pass
**Date**: 2026-09-17
**Branch**: `015-ui-runs-overview-page`
**Feature dir**: `specs/015-ui-runs-overview-page/`
**Artifacts analysed**: `spec.md`, `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`,
`contracts/runs-overview.md`, `contracts/pagination-component.md`, `checklists/*`) against
`.specify/memory/constitution.md` (v1.3.0).

> **Status**: The five findings from the prior read-only re-analysis (C1, C2, I1, A1, I2) have now
> been **remediated** — see spec.md → *Clarifications → Session 2026-09-17 (analysis remediation,
> pass 2)*. All edits were applied consistently across spec / plan / tasks / research / contracts.
> A post-remediation re-scan finds **no CRITICAL or HIGH findings and no remaining
> MEDIUM/LOW findings**. Coverage is 100% of functional requirements. The feature is ready for
> `/speckit-implement`.

---

## Findings

*(0 open findings. All prior findings resolved — see the remediation table below.)*

---

## Remediation of the prior findings (this pass)

| ID | Category | Severity | Resolution | Where fixed |
|----|----------|----------|------------|-------------|
| C1 | Inconsistency (task ordering) | MEDIUM | **Resolved** — T045 (FR-035 enrichment-cap note) moved out of Phase 2 (Foundational) into **Phase 5 (US3)**, the phase that owns the table render it depends on (T014/T019). Stable ID `T045` retained to avoid renumbering churn (a deliberate, documented choice — it sits between T024 and T025 by phase, not by numeric order). | `tasks.md` (T045 relocated; Phase-2 checkpoint restored) |
| C2 | Inconsistency (mislabel) | LOW | **Resolved** — T045 re-tagged `[US1]` → `[US3]`; task text now notes FR-035 is a cross-cutting enrichment-bound requirement with no dedicated user story, tagged to US3 because it renders on the US3 table. | `tasks.md` (T045) |
| I1 | Inconsistency (terminology drift) | LOW | **Resolved** — `unknown` added to research R8's presented-status enumeration, with the "All only" partition rule (`all ≥ in_progress + succeeded + failed`) so R8 matches contract §D, the data-model, and FR-005. | `research.md` (R8) |
| A1 | Ambiguity | LOW | **Resolved (decision recorded)** — the shared `run_status_tag` macro *does* expose a distinct `queued` status value that renders the neutral gray **idle** dot. Pinned once: contract §D now reads "queued (gray idle dot)" and research R8 states the `queued` status → gray idle dot. Decision recorded in the spec's Clarifications (pass 2). | `contracts/runs-overview.md` (§D), `research.md` (R8), `spec.md` (Clarifications) |
| I2 | Inconsistency (docs vs tasks) | LOW | **Resolved** — plan.md's `ui/tests/` structure tree extended with `test_design_system_docs.py`, `test_ui_consistency.py`, and `test_api.py` (all present in the repo; exercised by T037/T040/T042). | `plan.md` (Project Structure) |

*(5 prior findings, all resolved; 0 open.)*

---

## Re-verification of the first remediation pass (A1–A8)

Each item the spec's first "analysis remediation" session claims to have fixed remains consistent in
the current artifacts:

| Prior ID | Concern | Status now |
|----------|---------|-----------|
| A1 (prior) | `timed out` cannot come from Dagster (no TIMEOUT RunStatus) | **Resolved** — FR-001, US1, SC-001, contract §D, research R8 all state `timed_out` derives only from the local record and appears only on a last-known row. Consistent. |
| A2 (prior) | `unknown` status missing from data-model / FR-005 partition | **Resolved** — FR-005 adds the All-only rule; data-model Run & Tab entities carry it; contract §D has an `unknown` row; **and research R8 now enumerates it too** (was finding I1, now fixed). |
| A3 (prior) | N=500 cap promised "never silently truncated" but nothing rendered a note | **Resolved** — FR-035 added; T045 renders the note (now correctly placed in US3 — was finding C1, now fixed). |
| A5 (prior) | SC-007 light/dark parity had no automatable task | **Resolved** — by-construction + manual verification note on T025; consistent with FR-033/`test_conformance.py`. |
| A6 (prior) | a11y unspecified for tabs/filter/pagination | **Resolved** — accessibility note under FR-032/FR-033; the `pagination` macro carries `aria-label="Pagination"`/`aria-disabled` (contract §B; T032). |
| A8 (prior) | server first-paint has no browser tz but SC-005 asserts a literal | **Resolved** — research R7 documents the epoch/ISO + server label + client re-localise approach; data-model adds `created_iso`; T023 implements it. |

---

## Coverage Summary (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 true status | ✅ | T003, T007, T010 | normalisation + pipeline + render |
| FR-002 last-known fallback | ✅ | T007, T011, T012 | unreachable + no-record both covered |
| FR-003 Dagster wins while reachable | ✅ | T007, T012 | merge precedence |
| FR-004 status tag intents | ✅ | T003, T010 | `_status_intent` → `run_status_tag`; `queued` → gray idle dot (A1) |
| FR-005 tabbed partition (+`unknown` All-only) | ✅ | T003, T007, T014 | |
| FR-006 count badges over filtered set | ✅ | T007, T014, T018 | before partition, page-independent |
| FR-007 remove Status dropdown | ✅ | T007, T014, T018 | |
| FR-008 ghost Filter control | ✅ | T015 | |
| FR-009 text filter agent/model/target/run id | ✅ | T006, T016 | server + client |
| FR-010 agent + date filters retained | ✅ | T015, T016 | |
| FR-011 URL state | ✅ | T007, T016 | |
| FR-012 ten-column order | ✅ | T019 | |
| FR-013 remove Date/Time/Attempts | ✅ | T005, T019 | |
| FR-014 Target | ✅ | T004, T021 | |
| FR-015 Launched by | ✅ | T004, T021 | |
| FR-016 Checks (as Agents overview) | ✅ | T004, T022 | |
| FR-017 Created `Sep 17, 1:15 PM` + hover | ✅ | T023, T025 | |
| FR-018 Duration elapsed / in-progress | ✅ | T005, T023 | |
| FR-019 Cost `—` not `0` | ✅ | T024 | reuses `_fmt_cost` |
| FR-020 mono Agent/Model + agent link | ✅ | T020 | |
| FR-021 `—` when unobtainable | ✅ | T021 | |
| FR-022 Dagster link icon | ✅ | T026, T027 | |
| FR-023 run id → AgentBox page | ✅ | T019, T026 | |
| FR-024 no icon when Dagster unconfigured | ✅ | T026, T028 | |
| FR-025 30/page, newest first | ✅ | T007, T034 | |
| FR-026 filters before pagination | ✅ | T007 | |
| FR-027 tab/filter change → page 1 | ✅ | T007, T017 | client + server clamp |
| FR-028 page in URL | ✅ | T034, T035 | |
| FR-029 nav order Runs·rule·Agents | ✅ | T038 | |
| FR-030 single Settings entry | ✅ | T038, T040 | |
| FR-031 settings reachable from modal (staged) | ✅ | T038 | research R4 |
| FR-032 logo → home + focus state | ✅ | T039, T040 | |
| FR-033 design-system conformance | ✅ | T027, T033, T043 | + conformance suite |
| FR-034 pagination in DS first | ✅ | T029–T033 | design-system-first |
| FR-035 enrichment-cap note | ✅ | T045 | now in Phase 5 / US3 (C1/C2 resolved) |

**Success Criteria (buildable) → Tasks**: SC-001/002 → T013; SC-003/004 → T018; SC-005 → T023/T025;
SC-006 → T036; SC-008 → T040; SC-009 → T037/T043. SC-007 (cross-overview light/dark parity) is
**by-construction + manual** (documented note on T025; enforced indirectly by `test_conformance.py`),
not a discrete automated task — accepted per the A5 remediation.

**Coverage**: 35/35 functional requirements have ≥ 1 task (**100%**). No requirement has zero
coverage.

---

## Constitution Alignment (v1.3.0)

| Principle | Verdict | Evidence |
|-----------|---------|----------|
| VII. One Design System | **PASS** | Pagination lands in the design system first (T029–T031) before the macro (T032) and page use (T034); FR-033/FR-034; conformance enforced by `test_conformance.py`/`test_design_system_sync.py`/`test_design_system_docs.py` (SC-009). No inline styles / literal colours / hand-rolled controls planned. |
| V. Ephemeral Runs, Immutable Outputs | **PASS** | Read-path only; `SCHEMA_VERSION` untouched; no run-record writes (plan Summary, data-model header, tasks Notes). |
| VI. Docs Track Reality | **PASS** | README (T041) and design-system readme (T031/T042) updated; docs tests keep them honest. |
| I–IV | **N/A** | No orchestrator, agent-schema, harness, or secret surface changes. |

**No constitution violations. No CRITICAL findings.**

---

## Unmapped Tasks

None that are orphaned. Non-requirement tasks map cleanly to plan/constitution obligations:
T001–T002 (Setup — baseline suite + reusable-asset verification), T041–T044 (Polish — docs per
Principle VI, full-gate run per SC-009, quickstart walk-through).

---

## Metrics

- **Total functional requirements**: 35 (FR-001 … FR-035)
- **Total success criteria**: 9 (SC-001 … SC-009)
- **Total tasks**: 45 (T001 … T045)
- **Requirement coverage**: 100% (35/35 with ≥ 1 task)
- **Open findings**: 0 (0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW)
- **Findings resolved this pass**: 5 (1 MEDIUM, 4 LOW)
- **Duplication count**: 0
- **Ambiguity count**: 0 (A1 `queued`/`idle` naming pinned)
- **Terminology-drift count**: 0 (I1 `unknown` propagated to research R8)
- **Task-ordering issues**: 0 (C1 T045 re-slotted into US3)
- **Constitution violations**: 0

---

## Next Actions

- **No open issues** — the feature is cleared to proceed to `/speckit-implement`.
- Note for implementers: T045 keeps its stable ID while living in Phase 5 (US3) by phase, not by
  numeric position; this is intentional (avoids renumbering the whole list for one late-added,
  cross-cutting task).

## Remediation

This pass **modified artifact files** to close the five prior findings: `tasks.md` (T045 relocation
+ retag), `research.md` (R8 `unknown` enumeration + `queued` intent), `contracts/runs-overview.md`
(§D `queued` intent), `plan.md` (test-file tree), and `spec.md` (a *Clarifications → Session
2026-09-17 (analysis remediation, pass 2)* subsection recording the A1 decision and the C1/C2/I1/I2
fixes). The run was unattended, so the one judgment finding (A1) was decided from the repo (the
`run_status_tag` macro's actual `queued` handling) and recorded in the spec rather than left open. No
feature code was changed — this is a spec/plan/tasks reconciliation only.
