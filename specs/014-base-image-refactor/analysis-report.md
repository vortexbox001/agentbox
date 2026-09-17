# Specification Analysis Report — 014 Shared Agent Base Image

**Run**: `/speckit-analyze` (read-only cross-artifact consistency check), re-run after remediation
**Date**: 2026-09-16 (post-remediation)
**Branch**: `014-base-image-refactor`
**Artifacts**: `spec.md`, `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`,
`contracts/agent-base-image.md`, `quickstart.md`); constitution `.specify/memory/constitution.md`
(v1.3.0)

The original analysis surfaced 5 findings (1 HIGH, 2 MEDIUM, 2 LOW; 0 CRITICAL). All 5 have been
acted on by editing the spec/plan/tasks (and the supporting design docs that echoed the same wording,
to avoid re-introducing the inconsistency). This report records the post-remediation state; the
"Resolution" column documents what changed. A fresh cross-artifact pass over the edited artifacts
finds **no open findings**.

---

## Findings — all resolved

| ID | Category | Severity | Location(s) | Original summary | Resolution |
|----|----------|----------|-------------|------------------|------------|
| H1 | Inconsistency / Underspecification | HIGH | spec.md FR-011, SC-005, US3; plan.md Summary/R5/Constraints; research.md R5; data-model.md; quickstart.md §9 | FR-011/SC-005 asserted the combined harness footprint MUST be *smaller* after the refactor, but the base **adds** net-new tools (`ripgrep`, `jq`, `gh`, `unzip`, `build-essential` — the last ~150–200 MB) while the five already-shared packages are byte-identical (likely already deduped). The "smaller footprint" MUST may be unachievable, making T016/SC-005 a gate that could legitimately fail. | **RESOLVED (judgment decision, recorded in spec Clarifications 2026-09-16 (analysis remediation)).** Re-scoped FR-011/SC-005/US3 (and plan Summary/R5/Constraints, research.md R5, data-model.md, quickstart.md §9, tasks.md T002/T016 and the Phase 5 goal/test/checkpoint) from "combined total is smaller than before" to the structurally guaranteed claim: the common OS+tool+runtime install is **stored once** as a single shared `agent-base` layer instead of three times. The raw combined total is explicitly *not* asserted to shrink (net-new tools). SC-005/T016 are now a pass/fail single-storage check. |
| C1 | Constitution Alignment | MEDIUM | plan.md Constitution Check §I; spec.md FR-002; T003 | Principle I ("grant the **minimum** each agent needs") vs. installing `build-essential` and `gh` into **every** shell-based agent uniformly — a judgment call worth surfacing (not CRITICAL: no isolation/network/mount change). | **RESOLVED (trade-off surfaced).** Constitution Check §I now records the explicit uniform-tooling-vs-minimum trade-off and the decision to keep the uniform common set (FR-002 fixes it; one auditable place beats per-agent drift), and notes `build-essential` can be dropped later if an audit shows it unused. Also recorded in spec Clarifications 2026-09-16 (analysis remediation). |
| M1 | Inconsistency (doc vs. reality) | MEDIUM | spec.md US1/US3; plan.md Summary | The narrative framed the refactor as removing *duplicated* installs; in reality only 5 packages (`git`, `curl`, `ca-certificates`, `python3`, `python3-pip`) + the `dagster-pipes` pin are already shared, while `ripgrep`/`jq`/`gh`/`unzip`/`build-essential` are net-new. | **RESOLVED.** US3 narrative and plan Summary now distinguish "consolidate the five already-shared packages + the pin" from "*newly standardize* the additional tools", keeping the motivation honest (Principle VI). |
| L1 | Inconsistency (vacuous check) | LOW | spec.md US1-AS2, SC-003; tasks.md T015 | US1-AS2/SC-003/T015 asserted no harness carries "non-root-user creation" and grepped `useradd\|adduser`, but the harnesses never create a user (uid-1000 `node` is inherited from `node:20-slim`) — trivially satisfied, slightly misleading. | **RESOLVED.** US1-AS2, SC-003, and T015 reworded to "inherits the base's uid-1000 `node` user (no user-creation line — none existed before either)"; the `useradd`/`adduser` grep in T015 is reframed as a regression guard, not the removal of an existing line. |
| L2 | Inconsistency (cross-reference) | LOW | tasks.md T004 | T004 (build + smoke-test the base) cited `quickstart.md §3`, but the base build step is §2; §3 is tool resolution. T004 spans both. | **RESOLVED.** T004 now cites `quickstart.md §2–§3`. |

No CRITICAL issues (original or post-remediation). No unresolved placeholders (TODO/TKTK/???), no
conflicting requirements, no terminology drift between artifacts (entity names — `agent-base`,
thin/standalone harness — remain consistent across spec/plan/data-model/contracts/tasks).

---

## Coverage Summary

Every functional requirement and success criterion still maps to at least one task (unchanged by the
remediation — no FR/SC/task was added or removed, only reworded).

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 shared base exists | ✅ | T003 | Authored in Foundational phase. |
| FR-002 common tool set | ✅ | T003, T011 | Set defined once; resolution verified. C1 trade-off now surfaced in plan §I. |
| FR-003 single source of truth | ✅ | T003, T014, T015 | yq experiment + static grep. |
| FR-004 harnesses on base, no re-declare | ✅ | T005, T006, T007, T015 | |
| FR-005 retain harness-specific setup | ✅ | T005, T006, T007 | |
| FR-006 one-line base pointer | ✅ | T005, T006, T007, T015 | |
| FR-007 tools runnable in harnesses | ✅ | T011 | |
| FR-008 behavioral parity | ✅ | T012 | Unchanged `images/tests`. |
| FR-009 no agent YAML change | ✅ | T013, T020 | |
| FR-010 agent-python standalone + reason | ✅ | T017, T018 | |
| FR-011 shared install stored once | ✅ | T002, T016 | Re-scoped per H1 — now a structural single-storage claim (achievable). |
| FR-012 build order (README + bootstrap) | ✅ | T008, T009 | Compose null-action confirmed by T020. |
| FR-013 base provides python3 + dagster-pipes | ✅ | T003 | |
| SC-001 add tool in one place | ✅ | T014 | |
| SC-002 report format/semantics unchanged | ✅ | T012 | |
| SC-003 no OS/user/workdir in harnesses | ✅ | T015 | Reworded per L1 (inherits base user). |
| SC-004 common tools resolve | ✅ | T011 | |
| SC-005 shared install stored once, dedup | ✅ | T002, T016 | Re-scoped per H1 — structural single-storage check. |
| SC-006 no agent YAML change | ✅ | T013 | |

**Constitution Alignment Issues:** None open. The former C1 trade-off (uniform common tooling vs.
strict per-agent minimum) is now recorded explicitly in the plan's Constitution Check §I and the spec
Clarifications, so it is auditable. Constitution Check remains PASS; no CRITICAL conflict.

**Unmapped Tasks:** None. Setup/Polish tasks map cleanly: T001 (create base dir → FR-001), T019
(end-to-end quickstart run), T020 (scope guard → FR-009/FR-012).

**Intentional duplication (not a defect):** `dagster-pipes==1.13.21` is pinned in both
`images/agent-base/Dockerfile` (for shell harnesses) and `images/agent-python/Dockerfile` (standalone
base). Documented in plan.md Complexity Tracking; unavoidable given FR-010.

---

## Metrics

- **Total Functional Requirements**: 13 (FR-001…FR-013)
- **Total Success Criteria**: 6 (SC-001…SC-006)
- **Total Tasks**: 20 (T001…T020)
- **Requirement coverage**: 13/13 FR (100%), 6/6 SC (100%)
- **Ambiguity count (unresolved)**: 0
- **Duplication count**: 1 (intentional `dagster-pipes` pin, tracked in Complexity Tracking)
- **Critical issues**: 0
- **High issues**: 0 open (1 resolved — H1)
- **Medium issues**: 0 open (2 resolved — C1, M1)
- **Low issues**: 0 open (2 resolved — L1, L2)

---

## Next Actions

- **All findings resolved → the feature may proceed to `/speckit-implement`.** The artifacts are
  internally consistent, fully task-covered, and constitution-compliant. The two judgment calls (H1
  footprint re-scope, C1 uniform-tooling trade-off) are recorded in the spec's `## Clarifications`
  (Session 2026-09-16 (analysis remediation)) and the plan's Constitution Check §I, so they are
  visible and reviewable.
- **On implementation**, treat SC-005/T016 as a *single-storage* check (three harnesses share one
  `agent-base` layer in deduplicated usage), not a raw before-vs-after size comparison.

## Remediation Note

Unlike a normal read-only `/speckit-analyze` run, this pass was invoked to **act on** the findings.
The edits above were applied to `spec.md`, `plan.md`, `tasks.md`, and the supporting design docs
(`research.md`, `data-model.md`, `quickstart.md`) that echoed the same wording. No feature/image code
was changed — only the spec-kit artifacts were reconciled.
