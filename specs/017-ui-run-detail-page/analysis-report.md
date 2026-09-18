# Specification Analysis Report — Run Detail Page

**Feature**: Run Detail Page
**Feature directory**: `specs/017-ui-run-detail-page/`
**Git branch**: `207-ui-run-detail-page`
**Analysis date**: 2026-09-18
**Command**: `/speckit-analyze` (read-only, non-destructive cross-artifact consistency check)
**Artifacts analysed**: `spec.md`, `plan.md`, `tasks.md` (plus `data-model.md`, `contracts/`, and the
constitution as supporting context)
**Constitution**: v1.3.0

> **Directory/branch note.** `check-prerequisites.sh --require-spec --require-tasks` resolves
> `FEATURE_DIR` to `specs/017-ui-run-detail-page/`; there is **no** `specs/207-ui-run-detail-page/`
> directory. The `207-…` branch and the `017-…` directory both refer to this one feature (the spec,
> plan, and tasks all reconcile this — see finding N1). This report is therefore written into the
> resolved feature directory (`017`) so it sits next to the artifacts it analyses. This decision was
> made unattended per the run instructions.

---

## Executive summary

This artifact set is in **strong, implementation-ready shape**. It has already been through one
`/speckit-analyze` + remediation cycle (git `87c05ea` "add speckit-analyze cross-artifact analysis
report" and `e232b94` "Reconcile run-detail spec artifacts per speckit-analyze findings"), and the
spec records the remediation decisions explicitly under *Clarifications → Session 2026-09-18 (analysis
remediation)* (findings I1, A1, U1, A2) and the tasks under the *Test-surface note (C1)* and *G1*.

This fresh pass confirms:

- **Coverage is complete** — every one of the 37 functional requirements (FR-001…FR-037) maps to at
  least one task, and all 10 success criteria (SC-001…SC-010) are covered. No requirement has zero
  coverage; no task is left unmapped to a requirement, story, or explicit setup/polish purpose.
- **No CRITICAL or HIGH findings.** No constitution MUST is violated; no conflicting or duplicated
  requirements; no unresolved placeholders (TODO/TKTK/???); no vague unmeasurable adjectives
  (fast/scalable/robust/…).
- **Citations track reality.** The code/line references the plan and data-model rely on were spot-
  checked against the repo and are accurate: `ui/dagster.py:_check_status` returns exactly the
  `pass / warn / fail-blocking / not-run` vocabulary the spec claims; the Agents overview
  (`ui/templates/runs/list.html:21`) does define a `not-run` mark, so the CheckRow "reuse" claim
  holds; `ui/templates/runs/_rail.html:91` is the `report.notes` line; `images/agent-claude/
  wrapper.py` sets `notes=`; the reused macros (`file_row`, `tool_call`, `timeline`, `diff_block`,
  `tool_out`) and read-path helpers (`conversation_entries`, `read_output_files`, `read_transcript`,
  `run_status`, `_ASSET_CHECKS_SUBQUERY`, `_run_checks_by_id`) all exist as cited.

Four **LOW**-severity residual items remain (below). None blocks `/speckit-implement`.

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency (terminology) | LOW | spec.md:170 (FR-008 / US3-AC3), spec.md:458 (FR-033 / US7-AC6); data-model.md:36, data-model.md:131 | "The run foot line" names **two different renderings**: the Summary fallback foot line is **3 fields** — `status · turns · files written` — while the Transcript foot line is **4 fields** — `status · turns · files written · tool calls`. Both are called "the run foot line" with no note that they differ, so an implementer could render one where the other is expected. | Disambiguate the term — e.g. call them the "summary foot line" and the "transcript foot line", or add a one-line note in FR-008/FR-033 that the Summary foot line omits `· tool calls`. The rule itself is consistent; only the shared name is ambiguous. |
| N1 | Inconsistency (naming) | LOW | spec.md:3-6, plan.md:3/7-8, tasks.md:13-14 | Feature directory is `017-ui-run-detail-page` but the git branch is `207-ui-run-detail-page`, and there is no `specs/207-…` directory. This is **documented and reconciled** across all three artifacts (intentional — `207` is a transposition of `017`), but the mismatch is real: `check-prerequisites.sh` resolves `FEATURE_DIR` to `017`, so any tool or reviewer keying off the branch name looks in the wrong place. | Adequately mitigated by the explicit cross-references; no artifact edit needed now. Post-merge, consider renaming the branch (or directory) so they agree, to remove the standing footgun for tooling. |
| A1 | Ambiguity (stale rationale) | LOW | plan.md:180 (decision R7) vs spec.md:434-436 (FR-026) / spec.md:37-41 (clarification A1) | The spec was remediated to state a diff OUT row "MUST render expanded by default" **unconditionally**. Plan R7 still carries the *older conditional rationale* — "Diff OUT rows render expanded by default **because diff colouring cannot survive the clamp cleanly**". The behavioural rule is consistent (always expanded); only the plan's justifying clause retains the superseded conditional phrasing. | Cosmetic. When the plan is next touched, align R7's wording with the spec's unconditional rule so the "why" reads as a design choice, not a conditional trigger. Not edited here (read-only analysis; and spec.md/plan.md/tasks.md are out of scope for this run). |
| C1 | Coverage (test surface) | LOW / INFO | tasks.md:20-25 (Test-surface note), T011/T018/T051; SC-002, SC-005, SC-007 | Three success criteria are gated **only by manual quickstart validation** because there is no JS test harness (plain ES modules, no `package.json`): FR-004/SC-002 per-browser persistence, FR-025/FR-028 clamp + expand-all, and FR-029/SC-007 search-hide + auto-expand (plus the *runtime* half of SC-005). This is explicitly acknowledged in the tasks' Test-surface note and routed to `quickstart.md`; it is a residual **risk**, not a plan gap. | Treat `quickstart.md` US1/US2/US7 as a **required, tracked** artifact of the acceptance run (T058), not optional. Optionally note in T057/T058 that SC-002/SC-005/SC-007 sign-off depends on the manual walk-through, so the automated `pytest` green is not by itself sufficient acceptance. |

**Overflow**: none. Total findings = 4 (all LOW); well under the 50-row cap.

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
| FR-008 Summary fallback ladder | ✅ | T025, T028 | |
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
| FR-026 diff colouring; diff OUT expanded | ✅ | T013, T016, T019 | |
| FR-027 missing/failed OUT intent | ✅ | T016, T019 | |
| FR-028 expand-all/collapse-all (view-only) | ✅ | T017, T018 | Non-persistent, resets on reload |
| FR-029 search matches IN/OUT + auto-expand | ✅ | T051, T053 | Runtime manual (C1) |
| FR-030 Readable/Raw-log control relocated | ✅ | T050, T051 | |
| FR-031 turn entries unchanged | ✅ | T050, T053 | |
| FR-032 dedup last message + final event | ✅ | T050, T052, T053 | |
| FR-033 Transcript foot line (4 fields) | ✅ | T050, T052, T053 | See finding I1 |
| FR-034 Transcript closed-state note | ✅ | T008 | |
| FR-035 read-path only, no schema/dep change | ✅ | T059 | Explicit guard test (was G1) |
| FR-036 design-system conformance | ✅ | T007, T019, T027, T036, T045, T056 | |
| FR-037 design-system-first, macros second | ✅ | T005, T014, T023, T032, T041, T055 | |

### Success criteria → tasks (all 10 covered)

| Criterion | Has task? | Task IDs | Notes |
|-----------|-----------|----------|-------|
| SC-001 five sections + defaults on reference run | ✅ | T012 | |
| SC-002 collapse/reload persists; fresh profile → defaults | ✅ | T011 | Manual (C1) |
| SC-003 Summary reads as formatted text, no raw markup | ✅ | T028 | |
| SC-004 no-files run lists PR+commit; note "0 files · 1 pull request" | ✅ | T037 | |
| SC-005 clamp overflow affordance; click expand | ✅ | T020 | Runtime half manual (C1) |
| SC-006 refused write → `failed` + failed-colour OUT | ✅ | T020 | |
| SC-007 search on IN/OUT keeps matches, reports count | ✅ | T051 | Manual (C1) |
| SC-008 empty checks/final-message fallbacks | ✅ | T028, T046 | |
| SC-009 light/dark/Indigo theme correctness | ✅ | T045, T056, T058 | |
| SC-010 full UI suite + DS conformance + golden fixture | ✅ | T055, T057 | |

**Coverage: 37/37 FR (100%), 10/10 SC (100%).**

---

## Constitution alignment

No violations. Constitution v1.3.0; only the presentation/read-path principles gate this feature.

| Principle | Verdict | Evidence in artifacts |
|-----------|---------|------------------------|
| VII. One Design System | **PASS** | Six new components land in the design system first (T004/T013/T022/T031/T040), then as shared macros (T006/T015/T024/T033/T042), then on the page; tokens-only styling (T007/T019/T027/T036/T045); conformance/sync/docs gates (T055/T056); FR-036/FR-037, SC-009/SC-010. Existing `tool_call`/`timeline` macros left intact for the compare page. |
| V. Ephemeral Runs, Immutable Outputs | **PASS** | Read-path only; the additive Dagster check-field selection is a read; no `/output` write; `SCHEMA_VERSION` untouched (FR-035). Made verifiable by the T059 guard test (analysis finding G1). |
| VI. Docs Track Reality | **PASS** | README run-detail refresh (T054) and design-system readme updates (T005/T014/T023/T032/T041); docs/conformance tests keep them honest. |
| I–IV (isolation, config-over-code, secrets, uniform harness) | **N/A** | No orchestrator, agent-schema, harness, container, or secret surface is touched. |

---

## Unmapped tasks

None problematic. The tasks without a `[US#]` label are legitimate infrastructure/quality tasks per
the tasks.md format (Setup/Foundational/Polish carry no story label):

- **T001, T002** — Setup (venv, green baseline).
- **T003** — Foundational golden fixture (blocks all story tests; supports SC-010).
- **T004–T007** — Foundational Disclosure component/macro/styling shared by all sections.
- **T054–T059** — Polish: README (Principle VI), DS sync/docs (SC-010, FR-037), conformance
  (FR-036/SC-009), full-suite gate (SC-010), manual quickstart+theme walk (SC-009), and the FR-035
  read-path guard (was finding G1).

Each maps to a success criterion or principle rather than a single FR, which is expected for
setup/foundational/polish work.

---

## Metrics

- **Total functional requirements**: 37 (FR-001…FR-037)
- **Total success criteria**: 10 (SC-001…SC-010)
- **Total tasks**: 59 (T001…T059)
- **Requirement coverage**: 37/37 = **100%** (requirements with ≥1 task)
- **Success-criteria coverage**: 10/10 = **100%**
- **Ambiguity count**: 1 (finding I1 — "run foot line" overloaded); 0 unresolved placeholders
- **Duplication count**: 0
- **Terminology-drift count**: 1 (finding I1)
- **CRITICAL issues**: 0
- **HIGH issues**: 0
- **MEDIUM issues**: 0
- **LOW issues**: 4 (I1, N1, A1, C1)

---

## Next actions

No CRITICAL or HIGH issues exist — the feature is **cleared to proceed to `/speckit-implement`**. The
four LOW findings are refinements, not blockers:

1. **I1 (optional, before or during implementation)** — disambiguate "run foot line" so the 3-field
   Summary fallback and the 4-field Transcript foot line are not confused. A single clarifying clause
   in FR-008/FR-033 (or the data-model) suffices. Would be a manual edit to `spec.md`/`data-model.md`.
2. **N1 (post-merge, optional)** — reconcile the `017` directory vs `207` branch name once the branch
   merges, to stop tooling that keys off the branch from looking in a non-existent directory. No
   change needed pre-merge; the cross-references are adequate.
3. **A1 (housekeeping)** — when the plan is next edited, align decision R7's rationale wording with
   the spec's now-unconditional "diff OUT renders expanded by default" rule. Cosmetic.
4. **C1 (process)** — make the `quickstart.md` US1/US2/US7 walk-through (T058) a required acceptance
   gate alongside the `pytest` suite, since SC-002/SC-005/SC-007 have no automated coverage by design
   (no JS test harness). Consider noting this dependency in T057/T058.

**Suggested commands** (all optional; nothing is required to unblock implementation):

- To apply I1/A1 wording refinements: manually edit `spec.md` / `plan.md` / `data-model.md` (a
  targeted edit, not a full `/speckit-specify` re-run).
- Otherwise: proceed with **`/speckit-implement`**, starting at Phase 1 (Setup) → Phase 2
  (Foundational) → US1, exactly as tasks.md sequences.

---

## Remediation offer

Per the skill's step 8: concrete remediation edits for the top findings (I1's foot-line
disambiguation, A1's plan-rationale alignment) are available on request but are **not applied here** —
this analysis is strictly read-only, and this unattended run is additionally scoped to *not* edit
`spec.md`, `plan.md`, or `tasks.md`. The four findings are LOW severity and none blocks
implementation, so the recommended action is to proceed to `/speckit-implement` and fold the wording
refinements in opportunistically.

*Extension hooks: `.specify/extensions.yml` defines `hooks: {}` (no `before_analyze` / `after_analyze`
hooks), so no hook execution applies.*
