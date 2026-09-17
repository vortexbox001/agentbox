# Specification Analysis Report — Runs Overview Page (015)

**Command**: `/speckit-analyze` (non-destructive, read-only cross-artifact consistency check)
**Date**: 2026-09-17
**Branch**: `015-ui-runs-overview-page`
**Feature dir**: `specs/015-ui-runs-overview-page/`
**Artifacts analysed**: `spec.md`, `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`,
`contracts/runs-overview.md`, `contracts/pagination-component.md`, `checklists/*`) against
`.specify/memory/constitution.md` (v1.3.0).

> **Context**: This feature's artifacts have already been through one `/speckit-analyze`
> remediation pass — see spec.md → *Clarifications → Session 2026-09-17 (analysis remediation)*,
> which resolved findings A1, A2, A3, A5, A6, and A8 by editing spec / plan / tasks / data-model /
> research / contracts in lockstep. This report is a **fresh re-analysis** of the current state. The
> earlier remediated items are re-verified below as **resolved**; the findings that remain are the
> residue that the prior pass did not fully propagate, plus one task-ordering issue. **No CRITICAL or
> HIGH findings.** Coverage is 100% of functional requirements. The feature is ready for
> `/speckit-implement`.

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Inconsistency (task ordering) | MEDIUM | tasks.md T045 (Phase 2, lines 97–103); depends on T014 (Phase 4), T019 (Phase 5) | T045 renders the FR-035 enrichment-cap note and sits inside **Phase 2 (Foundational)** — right above the "Checkpoint: Foundation ready" line — yet its own body states it *depends on T014 and T019*, which live in Phase 4 (US2) and Phase 5 (US3). The Foundational phase is declared a blocking prerequisite that "no status/tab/column story can begin until complete," but T045 cannot complete until two later-phase template tasks land. | Move T045 out of Phase 2 into Phase 5 (or a late cross-cutting slot after T019), or split it: keep the server-side cap **flag** in T007 (Phase 2) and render the **note** in a US3-phase task. The dependency is already documented in the task text, so this is a placement fix, not new work. |
| C2 | Inconsistency (mislabel) | LOW | tasks.md T045 line 97 (`[US1]`) | T045 is tagged `[US1]` but implements **FR-035** (enrichment bound / cap note), which the spec places under its own *Enrichment bound* heading and is not part of US1's status-truth narrative (US1 = truthful per-row status). FR-035 has no dedicated user story. | Re-tag T045 to the story that owns the table render it depends on (US3), or leave `[US1]` but note FR-035 is a cross-cutting requirement. Cosmetic; does not affect coverage. |
| I1 | Inconsistency (terminology drift) | LOW | research.md R8 line 166–167 vs data-model.md L16, contracts/runs-overview.md §D L128, spec FR-005, tasks.md T003 | The A2 remediation added the `unknown` presented status to FR-005, the data-model Run/Tab entities, contract §D, and T003 — but **research.md R8's enumerated "presented status set" still lists only six** (succeeded, failed, timed out, cancelled, queued, in progress) and never mentions `unknown`. Every other artifact now carries a seven-member set including `unknown` (→ All-only). | Add `unknown` to R8's presented-status enumeration (and note its "All only" partition) so R8 matches contract §D and the data-model. Read-only report — not applied here. |
| A1 | Ambiguity | LOW | contracts/runs-overview.md §D L127 ("queued/idle") vs research.md R8 L178 ("idle/queued") vs spec FR-004 | The tag **intent** for a `queued` run is not pinned to one name: the contract writes "queued/idle" and research writes "idle/queued", while FR-004 only mandates reusing "the existing run status tag intents." Whether a distinct `queued` intent exists or it reuses `idle` is left to implementation (T003 `_status_intent`). | Confirm during implementation which intent the existing `run_status_tag` macro actually exposes and state it once. Low impact — FR-004's "reuse existing intents" is satisfied either way. |
| I2 | Inconsistency (docs vs tasks) | LOW | plan.md §Project Structure L165–169 vs tasks.md T037, T040, T042 | The plan's `ui/tests/` tree lists `test_runs.py`, `test_dagster.py`, `test_conformance.py`, `test_design_system_sync.py`, but the tasks also exercise `test_design_system_docs.py` (T037/T042), `test_ui_consistency.py` and `test_api.py` (T040). The plan tree is illustrative, but omits three test files the tasks depend on. | Add the three test files to the plan's structure block (or annotate the tree as non-exhaustive). No functional impact; all named files exist in the repo. |

*(5 findings total; no overflow — well under the 50-row cap.)*

---

## Re-verification of the prior remediation pass

Each item the spec's "analysis remediation" session claims to have fixed was re-checked in the
current artifacts and confirmed consistent:

| Prior ID | Concern | Status now |
|----------|---------|-----------|
| A1 (prior) | `timed out` cannot come from Dagster (no TIMEOUT RunStatus) | **Resolved** — FR-001, US1, SC-001, contract §D, research R8 all state `timed_out` derives only from the local record and appears only on a last-known row. Consistent. |
| A2 (prior) | `unknown` status missing from data-model / FR-005 partition | **Resolved in spec/data-model/contract/tasks** — FR-005 adds the All-only rule and `all ≥ in_progress+succeeded+failed`; data-model Run & Tab entities carry it; contract §D has an `unknown` row. **Not propagated to research.md R8** → see finding **I1**. |
| A3 (prior) | N=500 cap promised "never silently truncated" but no requirement/task rendered a note | **Resolved** — FR-035 added; T045 renders the note. (Placement of T045 → finding **C1**.) |
| A5 (prior) | SC-007 light/dark parity had no automatable task | **Resolved** — recorded as a by-construction + manual verification note on T025; no pixel/theme assertion added. Consistent with FR-033/`test_conformance.py`. |
| A6 (prior) | a11y unspecified for tabs/filter/pagination | **Resolved** — accessibility note under FR-032/FR-033; the new `pagination` macro carries `aria-label="Pagination"`/`aria-disabled` (contract §B; T032). |
| A8 (prior) | server first-paint has no browser tz but SC-005 asserts a literal | **Resolved** — research R7 documents the epoch/ISO + server label + client re-localise approach; data-model adds `created_iso`; T023 implements it. |

Findings **A4** and **A7** from the earlier pass are not listed in the spec's remediation session;
their underlying decisions (R4 staged Settings consolidation, R7 timestamp formatting) are present
and internally consistent in the current artifacts, so no residual issue is raised for them.

---

## Coverage Summary (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 true status | ✅ | T003, T007, T010 | normalisation + pipeline + render |
| FR-002 last-known fallback | ✅ | T007, T011, T012 | unreachable + no-record both covered |
| FR-003 Dagster wins while reachable | ✅ | T007, T012 | merge precedence |
| FR-004 status tag intents | ✅ | T003, T010 | `_status_intent` → `run_status_tag` |
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
| FR-035 enrichment-cap note | ✅ | T045 | placement → finding C1 |

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
- **Findings**: 5 (0 CRITICAL, 0 HIGH, 1 MEDIUM, 4 LOW)
- **Duplication count**: 0
- **Ambiguity count**: 2 (A1 queued intent; the `queued`/`idle` naming)
- **Terminology-drift count**: 1 (I1 `unknown` missing from research R8)
- **Task-ordering issues**: 1 (C1)
- **Constitution violations**: 0

---

## Next Actions

- **No CRITICAL/HIGH issues** — the feature is cleared to proceed to `/speckit-implement`.
- Before or during implementation, address the residue (all optional, none blocking):
  1. **C1 (MEDIUM)** — relocate/split T045 so its phase matches its T014/T019 dependency, or move the
     note render into a US3 task and keep only the cap **flag** in Phase-2 T007.
  2. **I1 (LOW)** — add `unknown` to research.md R8's presented-status enumeration to match contract
     §D / data-model / FR-005.
  3. **C2, A1, I2 (LOW)** — retag T045's story, pin the `queued` tag intent once, and extend the
     plan's test-file tree to include `test_design_system_docs.py`, `test_ui_consistency.py`, and
     `test_api.py`.
- Suggested commands to apply the above (manual, not run by this read-only analysis):
  - `/speckit-tasks` to re-slot T045 (finding C1/C2).
  - Manual edit of `research.md` R8 and `plan.md` structure block (findings I1/I2) — outside the
    analyze scope, which does not touch these files.

## Remediation

This is a read-only analysis and **no artifact files were modified** (spec.md, plan.md, tasks.md,
research.md, data-model.md, and contracts are unchanged). Because the run is unattended, no
remediation edits were applied automatically. The residual findings above are all LOW/MEDIUM and
non-blocking; a follow-up remediation session could fold them in the same way the prior pass folded
A1–A8, but doing so is optional and not required to begin implementation.
