# Specification Analysis Report — 014 Shared Agent Base Image

**Run**: `/speckit-analyze` (read-only cross-artifact consistency check)
**Date**: 2026-09-16
**Branch**: `014-base-image-refactor`
**Artifacts**: `spec.md`, `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`,
`contracts/agent-base-image.md`, `quickstart.md`); constitution `.specify/memory/constitution.md`
(v1.3.0)

This is a non-destructive analysis. No spec/plan/tasks file was modified. Findings are prioritized
most-severe first.

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| H1 | Inconsistency / Underspecification | HIGH | spec.md FR-011, SC-005; plan.md R5; research.md R5 | The design **adds** packages the shell harnesses do not carry today (`ripgrep`, `jq`, `gh`, `unzip`, `build-essential`), yet FR-011/SC-005 assert the combined footprint MUST be *smaller* after the refactor. Since all three shell harnesses already `FROM node:20-slim` with **byte-identical** apt/pip layers (see below), Docker's content-addressed store likely already de-duplicates the shared layers today — so the only guaranteed change is the *addition* of new (and large — `build-essential` alone is ~150–200 MB) tools. No document shows the dedup benefit offsets the additions. The "smaller footprint" MUST may be unachievable as specified. | Either (a) re-scope FR-011/SC-005 to "the shared common install is stored once instead of three times" (a structural claim that holds) rather than "combined footprint is smaller"; or (b) add a research note quantifying the added tool size vs. the dedup saving so T016 has a realistic pass condition; or (c) accept T016 may legitimately fail and define the fallback. |
| C1 | Constitution Alignment | MEDIUM | plan.md Constitution Check §I; spec.md FR-002; T003 | Principle I ("grant the **minimum** of each that the agent needs") vs. installing a full compiler toolchain (`build-essential`) and `gh` into **every** shell-based agent uniformly. The plan reasons this is acceptable ("granted uniformly rather than ad hoc"), but broadening every agent's toolset beyond what each needs is a judgment call worth surfacing — not a hard violation (no isolation boundary, network reach, or mount changes), so not CRITICAL. | Keep, but record the explicit trade-off in the Constitution Check (uniform tooling vs. per-agent minimum) so the decision is auditable; consider whether `build-essential` is truly common to all shell agents or could be dropped from the shared set. |
| M1 | Inconsistency (doc vs. reality) | MEDIUM | spec.md Input/US1/US3; plan.md Summary | The narrative frames the refactor as removing *duplicated* tool installs ("instead of each installing the same OS and tools"). The current harness Dockerfiles install only `git curl ca-certificates python3 python3-pip` (+ `dagster-pipes`), not the full common set. The genuine consolidation is those five packages + the pip pin; `ripgrep`/`jq`/`gh`/`unzip`/`build-essential` are net-new. The one-place-to-add-a-tool win (US2/FR-003) is real regardless, but the "de-duplicate the same tools" motivation is partly overstated. | Adjust the US3 / footprint rationale to distinguish "consolidate the 5 already-shared packages" from "newly standardize additional tools"; keeps the spec honest per Principle VI. |
| L1 | Inconsistency (vacuous check) | LOW | spec.md US1 Acceptance Scenario 2; tasks.md T015 | US1-AS2 and T015 assert/verify that no harness carries "non-root-user creation" and grep for `useradd|adduser`. The current harnesses never create a user — the uid-1000 `node` user is inherited from `node:20-slim` — so this check is trivially satisfied and cannot fail. Harmless but slightly misleading (implies user-creation was being removed). | Reword to "inherits the base image's uid-1000 user (no user-creation line)" for accuracy; no functional change needed. |
| L2 | Inconsistency (cross-reference) | LOW | tasks.md T004 | T004 (build + smoke-test the base) cites `quickstart.md §3`, but the base build step is `quickstart.md §2`; §3 is tool resolution. T004 legitimately spans both §2 and §3. | Cite `quickstart.md §2–§3` in T004. |

No CRITICAL issues. No unresolved placeholders (TODO/TKTK/???), no conflicting requirements, no
terminology drift between artifacts (entity names — `agent-base`, thin/standalone harness — are used
consistently across spec/plan/data-model/contracts/tasks).

---

## Coverage Summary

Every functional requirement and success criterion maps to at least one task.

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 shared base exists | ✅ | T003 | Authored in Foundational phase. |
| FR-002 common tool set | ✅ | T003, T011 | Set defined once; resolution verified. |
| FR-003 single source of truth | ✅ | T003, T014, T015 | yq experiment + static grep. |
| FR-004 harnesses on base, no re-declare | ✅ | T005, T006, T007, T015 | |
| FR-005 retain harness-specific setup | ✅ | T005, T006, T007 | |
| FR-006 one-line base pointer | ✅ | T005, T006, T007, T015 | |
| FR-007 tools runnable in harnesses | ✅ | T011 | |
| FR-008 behavioral parity | ✅ | T012 | Unchanged `images/tests`. |
| FR-009 no agent YAML change | ✅ | T013, T020 | |
| FR-010 agent-python standalone + reason | ✅ | T017, T018 | |
| FR-011 smaller footprint | ✅ | T002, T016 | **See H1 — may not hold as specified.** |
| FR-012 build order (README + bootstrap) | ✅ | T008, T009 | Compose null-action confirmed by T020. |
| FR-013 base provides python3 + dagster-pipes | ✅ | T003 | |
| SC-001 add tool in one place | ✅ | T014 | |
| SC-002 report format/semantics unchanged | ✅ | T012 | |
| SC-003 no OS/user/workdir in harnesses | ✅ | T015 | |
| SC-004 common tools resolve | ✅ | T011 | |
| SC-005 smaller dedup footprint | ✅ | T002, T016 | **See H1.** |
| SC-006 no agent YAML change | ✅ | T013 | |

**Constitution Alignment Issues:** One MEDIUM (C1 — "minimum toolset" vs. uniform install). No
CRITICAL constitution conflicts. The plan's Constitution Check is thorough and rated PASS; this
analysis concurs, subject to surfacing the C1 trade-off.

**Unmapped Tasks:** None. Setup/Polish tasks map cleanly: T001 (create base dir → FR-001
infrastructure), T019 (end-to-end quickstart run), T020 (scope guard → FR-009/FR-012). No task lacks
a requirement or story anchor.

**Intentional duplication (not a defect):** `dagster-pipes==1.13.21` is pinned in both
`images/agent-base/Dockerfile` (for shell harnesses) and `images/agent-python/Dockerfile` (standalone
base). Documented in plan.md Complexity Tracking; unavoidable given FR-010. Consistent with the
current `agent-python/Dockerfile`.

---

## Metrics

- **Total Functional Requirements**: 13 (FR-001…FR-013; FR-013 added in the 2026-09-16 clarification)
- **Total Success Criteria**: 6 (SC-001…SC-006)
- **Total Tasks**: 20 (T001…T020)
- **Requirement coverage**: 13/13 FR (100%), 6/6 SC (100%)
- **Ambiguity count (unresolved)**: 0 — "standard build essentials" is resolved to `build-essential`
  in plan.md Assumptions/research; all four clarification questions answered in spec.md.
- **Duplication count**: 1 (intentional `dagster-pipes` pin, tracked in Complexity Tracking)
- **Critical issues**: 0
- **High issues**: 1 (H1)
- **Medium issues**: 2 (C1, M1)
- **Low issues**: 2 (L1, L2)

---

## Next Actions

- **No CRITICAL issues → the feature may proceed to `/speckit-implement`.** The artifacts are
  internally consistent, fully task-covered, and constitution-compliant.
- **Before relying on SC-005 as a pass/fail gate (H1)**: decide the footprint claim's fate. The
  cleanest fix is a one-line spec/plan refinement re-scoping FR-011/SC-005 from "combined footprint is
  smaller" to "the common install is stored once, not three times," which is structurally guaranteed;
  otherwise T016 carries real risk of a legitimate failure once `build-essential`/`gh` are added.
  Suggested: `Run /speckit-specify` (refine FR-011/SC-005 wording) or manually adjust the footprint
  claim + add a sizing note to research.md R5.
- **M1 / L1 wording (Principle VI accuracy)**: optionally tighten the "de-duplicate the same tools"
  narrative and the vacuous user-creation check; low urgency, no blocker.
- **C1**: record the uniform-tooling vs. minimum-per-agent trade-off explicitly in the plan's
  Constitution Check so the decision is auditable.
- **L2**: correct the T004 quickstart cross-reference (§2–§3).

## Remediation Offer

Concrete remediation edits for the top issues (H1 footprint re-scope, M1/L1 wording, C1 trade-off
note, L2 cross-reference) can be drafted on request. Per the read-only contract of `/speckit-analyze`,
none were applied — this report records findings only and makes no change to `spec.md`, `plan.md`, or
`tasks.md`.
