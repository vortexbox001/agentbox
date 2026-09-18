# Specification Analysis Report — Run Detail Page

**Feature**: Run Detail Page
**Feature directory**: `specs/017-ui-run-detail-page/`
**Git branch**: `207-ui-run-detail-page`
**Analysis date**: 2026-09-18 (post-remediation refresh)
**Command**: `/speckit-analyze` (read-only cross-artifact consistency check) + remediation pass
**Artifacts analysed**: `spec.md`, `plan.md`, `tasks.md` (plus `data-model.md`, `research.md`,
`quickstart.md`, `contracts/`, and the constitution as supporting context)
**Constitution**: v1.3.0

> **Directory/branch note.** `check-prerequisites.sh --require-spec --require-tasks` resolves
> `FEATURE_DIR` to `specs/017-ui-run-detail-page/`; there is **no** `specs/207-ui-run-detail-page/`
> directory. The `207-…` branch and the `017-…` directory both refer to this one feature (`207` is a
> transposition of `017`); the spec, plan, and tasks all reconcile this (see finding N1). This report
> lives in the resolved feature directory (`017`) so it sits next to the artifacts it analyses.

---

## Executive summary

This artifact set is in **implementation-ready shape**, and the four LOW residual findings from the
prior fresh pass have now been **remediated** unattended per the run instructions. The decisions are
recorded in the spec under *Clarifications → Session 2026-09-18 (analysis remediation — residual
findings)* so they are visible and reviewable.

- **Coverage remains complete** — every one of the 37 functional requirements (FR-001…FR-037) maps to
  at least one task, and all 10 success criteria (SC-001…SC-010) are covered. No requirement has zero
  coverage; no task is unmapped to a requirement, story, or explicit setup/polish purpose.
- **No CRITICAL, HIGH, or MEDIUM findings, and no open LOW findings.** No constitution MUST is
  violated; no conflicting or duplicated requirements; no unresolved placeholders (TODO/TKTK/???); no
  vague unmeasurable adjectives.
- **Citations still track reality** (spot-checked against the repo in the prior pass and unchanged by
  this text-only remediation): `ui/dagster.py:_check_status` returns exactly `pass / warn /
  fail-blocking / not-run`; `ui/templates/runs/list.html:21` defines the `not-run` mark; the reused
  macros and read-path helpers all exist as cited.

---

## Findings — all resolved

| ID | Category | Severity | Status | Resolution |
|----|----------|----------|--------|------------|
| I1 | Inconsistency (terminology) | LOW | **RESOLVED** | The overloaded term "run foot line" is disambiguated into the **Summary foot line** (three fields: status · turns · files written — FR-008) and the **Transcript foot line** (four fields: … · tool calls — FR-033). Every occurrence in `spec.md`, `plan.md`, `data-model.md`, `tasks.md`, `quickstart.md`, and `research.md` now uses the specific name; FR-033 and both data-model entries cross-note that the Summary variant omits `· tool calls`. The underlying rule was never in conflict, so no values changed. Decision recorded in Clarifications. |
| A1 | Ambiguity (stale rationale) | LOW | **RESOLVED** | Plan decision R7's justifying clause is rewritten from the superseded conditional ("because diff colouring cannot survive the clamp cleanly") to the unconditional design choice — diff OUT rows always render expanded so colouring is never clamped — matching the spec's unconditional FR-026 rule and the earlier A1 clarification. Behaviour unchanged. |
| C1 | Coverage (test surface) | LOW | **RESOLVED** | T058 is now labelled a **required acceptance gate** and named the sole sign-off for the client-only criteria SC-002, SC-005 (runtime half), and SC-007 (which have no automated coverage — no JS test harness). T057 now states that a green `pytest` run is not by itself sufficient acceptance and depends on the T058 manual walk-through. |
| N1 | Inconsistency (naming) | LOW | **ACCEPTED / DEFERRED** | Feature directory `017-…` vs git branch `207-…`. No artifact edit is possible or warranted pre-merge — the mismatch is already documented and cross-referenced in `spec.md`, `plan.md`, and `tasks.md`, and `207` is a transposition of `017`. Reconciling the branch/directory names is post-merge housekeeping, out of scope for the spec artifacts. Recorded as an accepted residual in Clarifications. |

**Open findings after remediation: 0.** Total = 4 (all LOW): 3 resolved by edit, 1 accepted/deferred
(not artifact-actionable pre-merge).

---

## Coverage summary

### Functional requirements → tasks (all 37 covered)

| Requirement | Has task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 five sections, fixed order | ✅ | T009, T010, T012 | |
| FR-002 open/closed defaults | ✅ | T009, T012, T047 | Context collapsed verified in T047/T049 |
| FR-003 bordered card / keyboard disclosure | ✅ | T004, T006, T011, T012 | |
| FR-004 per-browser shared persistence | ✅ | T011 | Runtime behaviour manual (C1) |
| FR-005 header + six-stat strip unchanged | ✅ | T010, T012 | |
| FR-006 rail order; only notes+output leave | ✅ | T026, T035, T049 | Removals owned by US3/US4; order asserted by US6 |
| FR-007 Summary markdown subset, no raw HTML | ✅ | T021, T022, T028 | Structural safety via `ui/markdown.py` |
| FR-008 Summary fallback ladder | ✅ | T025, T028 | Now names the **Summary foot line** (I1) |
| FR-009 Summary closed-state note | ✅ | T008, T025 | |
| FR-010 Output file rows | ✅ | T034, T035 | Reuses `file_row` macro |
| FR-011 produced-elsewhere (no-artifacts case) | ✅ | T029, T034, T035 | |
| FR-012 produced row kind/id/action, grouping | ✅ | T029, T031, T033 | |
| FR-013 unminable → file list alone | ✅ | T029, T034 | |
| FR-014 Output note count | ✅ | T030, T034, T037 | |
| FR-015 Checks visual language | ✅ | T038, T040, T042, T043, T044 | Reuses `ax-result` + `CHECK_META` |
| FR-016 check source, no new types | ✅ | T038, T040 | `dagster.run_status([run_id])` |
| FR-017 empty-checks state + "—" | ✅ | T043, T044, T046 | |
| FR-018 Checks note across full vocabulary | ✅ | T039, T046 | `fail-blocking`→failed; `not-run` counts |
| FR-019 Context card verbatim | ✅ | T047 | Reuses `_context_card.html` |
| FR-020 Context note | ✅ | T008, T048 | |
| FR-021 tool card head + IN/OUT | ✅ | T013, T015, T016, T017 | |
| FR-022 `exit N` / `failed` marker | ✅ | T016, T020 | Derived best-effort (R6) |
| FR-023 description fallback | ✅ | T016 | |
| FR-024 clamp 3 lines + fade | ✅ | T016, T019, T020 | Server-detected overflow |
| FR-025 click/keyboard expand-collapse | ✅ | T018 | Runtime manual (C1) |
| FR-026 diff colouring; diff OUT expanded | ✅ | T013, T016, T019 | Unconditional rule; plan R7 aligned (A1) |
| FR-027 missing/failed OUT intent | ✅ | T016, T019 | |
| FR-028 expand-all/collapse-all (view-only) | ✅ | T017, T018 | Non-persistent, resets on reload |
| FR-029 search matches IN/OUT + auto-expand | ✅ | T051, T053 | Runtime manual (C1) |
| FR-030 Readable/Raw-log control relocated | ✅ | T050, T051 | |
| FR-031 turn entries unchanged | ✅ | T050, T053 | |
| FR-032 dedup last message + final event | ✅ | T050, T052, T053 | |
| FR-033 Transcript foot line (4 fields) | ✅ | T050, T052, T053 | Now named the **Transcript foot line** (I1) |
| FR-034 Transcript closed-state note | ✅ | T008 | |
| FR-035 read-path only, no schema/dep change | ✅ | T059 | Explicit guard test (was G1) |
| FR-036 design-system conformance | ✅ | T007, T019, T027, T036, T045, T056 | |
| FR-037 design-system-first, macros second | ✅ | T005, T014, T023, T032, T041, T055 | |

### Success criteria → tasks (all 10 covered)

| Criterion | Has task? | Task IDs | Notes |
|-----------|-----------|----------|-------|
| SC-001 five sections + defaults on reference run | ✅ | T012 | |
| SC-002 collapse/reload persists; fresh profile → defaults | ✅ | T011, **T058** | Manual gate now required (C1) |
| SC-003 Summary reads as formatted text, no raw markup | ✅ | T028 | |
| SC-004 no-files run lists PR+commit; note "0 files · 1 pull request" | ✅ | T037 | |
| SC-005 clamp overflow affordance; click expand | ✅ | T020, **T058** | Runtime half is manual gate (C1) |
| SC-006 refused write → `failed` + failed-colour OUT | ✅ | T020 | |
| SC-007 search on IN/OUT keeps matches, reports count | ✅ | T051, **T058** | Manual gate now required (C1) |
| SC-008 empty checks/final-message fallbacks | ✅ | T028, T046 | |
| SC-009 light/dark/Indigo theme correctness | ✅ | T045, T056, T058 | |
| SC-010 full UI suite + DS conformance + golden fixture | ✅ | T055, T057 | |

**Coverage: 37/37 FR (100%), 10/10 SC (100%).**

---

## Constitution alignment

No violations. Constitution v1.3.0; only the presentation/read-path principles gate this feature.

| Principle | Verdict | Evidence in artifacts |
|-----------|---------|------------------------|
| VII. One Design System | **PASS** | Six new components land in the design system first (T004/T013/T022/T031/T040), then as shared macros (T006/T015/T024/T033/T042), then on the page; tokens-only styling (T007/T019/T027/T036/T045); conformance/sync/docs gates (T055/T056); FR-036/FR-037, SC-009/SC-010. |
| V. Ephemeral Runs, Immutable Outputs | **PASS** | Read-path only; the additive Dagster check-field selection is a read; no `/output` write; `SCHEMA_VERSION` untouched (FR-035). Made verifiable by the T059 guard test. |
| VI. Docs Track Reality | **PASS** | README run-detail refresh (T054) and design-system readme updates (T005/T014/T023/T032/T041); docs/conformance tests keep them honest. |
| I–IV (isolation, config-over-code, secrets, uniform harness) | **N/A** | No orchestrator, agent-schema, harness, container, or secret surface is touched. |

---

## Unmapped tasks

None problematic. Tasks without a `[US#]` label are legitimate Setup/Foundational/Polish work:

- **T001, T002** — Setup (venv, green baseline).
- **T003** — Foundational golden fixture (blocks all story tests; supports SC-010).
- **T004–T007** — Foundational Disclosure component/macro/styling shared by all sections.
- **T054–T059** — Polish: README (Principle VI), DS sync/docs (SC-010, FR-037), conformance
  (FR-036/SC-009), full-suite gate (SC-010), the required manual quickstart+theme walk (SC-009 +
  the client-only SC-002/SC-005/SC-007 sign-off per C1), and the FR-035 read-path guard (was G1).

---

## Metrics

- **Total functional requirements**: 37 (FR-001…FR-037)
- **Total success criteria**: 10 (SC-001…SC-010)
- **Total tasks**: 59 (T001…T059)
- **Requirement coverage**: 37/37 = **100%**
- **Success-criteria coverage**: 10/10 = **100%**
- **Ambiguity count**: 0 (I1 resolved); 0 unresolved placeholders
- **Duplication count**: 0
- **Terminology-drift count**: 0 (I1 resolved)
- **CRITICAL issues**: 0
- **HIGH issues**: 0
- **MEDIUM issues**: 0
- **LOW issues (open)**: 0 — 3 remediated by edit (I1, A1, C1), 1 accepted/deferred (N1, not
  artifact-actionable pre-merge)

---

## Remediation applied

Acting on the run instructions (unattended), the three artifact-actionable LOW findings were fixed and
the decisions recorded in `spec.md` → *Clarifications → Session 2026-09-18 (analysis remediation —
residual findings)*:

1. **I1** — "run foot line" disambiguated into **Summary foot line** (3 fields, FR-008) and
   **Transcript foot line** (4 fields, FR-033) across `spec.md`, `plan.md`, `data-model.md`,
   `tasks.md`, `quickstart.md`, and `research.md`; FR-033 and both data-model rows cross-note the
   field difference.
2. **A1** — plan decision R7's rationale rewritten to the unconditional "diff OUT always renders
   expanded" design choice, matching FR-026 and the earlier A1 clarification.
3. **C1** — T057/T058 updated so the quickstart US1–US7 manual walk-through is a required acceptance
   gate and the sole sign-off for SC-002/SC-005/SC-007.
4. **N1** — no artifact edit (already documented; a post-merge branch/directory rename is the correct
   fix); recorded as an accepted residual.

**Next action:** the feature is cleared to proceed to `/speckit-implement`, starting at Phase 1
(Setup) → Phase 2 (Foundational) → US1, exactly as `tasks.md` sequences.

*Extension hooks: `.specify/extensions.yml` defines `hooks: {}` (no `before_analyze` / `after_analyze`
hooks), so no hook execution applies.*
