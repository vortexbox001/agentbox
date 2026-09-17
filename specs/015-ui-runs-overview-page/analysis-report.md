# Specification Analysis Report — Runs Overview Page (015)

**Command**: `/speckit-analyze` (read-only cross-artifact consistency check)
**Date**: 2026-09-17
**Feature dir**: `specs/015-ui-runs-overview-page/`
**Artifacts analysed**: `spec.md`, `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`, `contracts/runs-overview.md`, `contracts/pagination-component.md`, `checklists/`)
**Constitution**: v1.3.0 (`.specify/memory/constitution.md`)

> **Status: post-remediation.** This report was regenerated after the analysis-remediation pass that
> acted on the eight findings below. The original findings are retained with a **Resolution** column
> so the change is reviewable. All eight are now **RESOLVED**; a fresh detection pass over the edited
> artifacts surfaced **no new findings**. The judgment calls made unattended are recorded in
> `spec.md` §Clarifications → *Session 2026-09-17 (analysis remediation)*.

## Summary verdict

The three core artifacts were already unusually well aligned; the remediation pass closed the eight
refinement findings without any architectural change. Every functional requirement (FR-001–**FR-035**)
maps to at least one task, every user story has an implementation + test task pair, and the
constitution gates (VII One Design System, V Ephemeral Runs, VI Docs Track Reality) remain respected
and explicitly tracked. **No CRITICAL issues and no constitution violations — before or after
remediation.**

What changed in remediation:
- The `timed_out` status-vocabulary inconsistency (A1) is reconciled: `timed out` derives only from
  the local record and shows on last-known rows; FR-001, US1, and SC-001 now say this, matching
  contract §D and research R8.
- The `unknown` status set now matches across data-model, contract §D, tasks, and a new FR-005 note
  (A2), including the explicit `all ≥ in_progress + succeeded + failed` count relationship.
- The N=500 enrichment cap is now a real requirement (**FR-035**) with a rendering task (**T045**),
  so the "surfaced, never silently truncated" promise in research R1 is honest (A3).
- The reviewer-owned `spec-quality.md` checklist (CHK001–CHK040) was walked and marked satisfied
  (A4), with the previously-open gaps (CHK003/008/022/031/032) closed by the edits above.
- LOW findings A5 (SC-007 theme-parity verification), A6 (a11y of added controls), A7 (`created_iso`
  field-inventory drift), and A8 (first-paint timezone) are each recorded/reconciled.

An operator may proceed to `/speckit-implement`.

## Findings (all resolved)

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Inconsistency | MEDIUM | spec.md FR-001, US1 (narrative + Independent Test), SC-001; contracts/runs-overview.md §D; research.md R8 | FR-001/US1/SC-001 claimed a **timed-out** status is "the real outcome Dagster records", but Dagster has no TIMEOUT RunStatus (§D marks `timed_out` as "(none; local)"), so it can never present while Dagster is reachable and wins (FR-003). | **RESOLVED.** FR-001, US1 (narrative + Independent Test), and SC-001 now state `timed out` derives **only** from the local record and appears only on a last-known row; while Dagster is reachable a timed-out run shows Dagster's terminal state (failed/cancelled). Now consistent with §D and R8. Decision recorded in Clarifications. |
| A2 | Inconsistency | MEDIUM | spec.md FR-005; data-model.md (Run + Tab entities); contracts/runs-overview.md §D; tasks.md T003 | Presented-status set differed: data-model listed 6 states (no `unknown`); §D + T003 listed 7. `unknown` routes to "All only", so the three sub-tab counts need not sum to `all`, and FR-005 never mentioned it. | **RESOLVED.** `unknown` added to the data-model Run presented set and Tab entity; FR-005 now states an `unknown` run appears under All only and that `all ≥ in_progress + succeeded + failed`. Parity across data-model, §D, tasks, spec. Decision recorded in Clarifications. |
| A3 | Coverage Gap | MEDIUM | research.md R1; spec.md FR-035 (new); tasks.md T045 (new) | R1 promised the N=500 enrichment cap be "surfaced (a note), never silently truncated," but no FR/SC required it and no task rendered it. | **RESOLVED.** Added **FR-035** (visible cap note; rows beyond the cap shown last-known, never truncated) and **T045** to render it in `runs/list.html` (tokens/macros only) with a covering `test_runs.py` case. R1 now cross-references FR-035/T045. Closes CHK031/CHK032. |
| A4 | Underspecification | MEDIUM | checklists/spec-quality.md (CHK001–CHK040) | The feature's reviewer-owned quality checklist was entirely unchecked; `/speckit-implement` reads checkbox state as a gate. | **RESOLVED.** All CHK001–CHK040 walked and marked `[x]` in the remediation pass. Previously-open gaps closed by A1/A2/A3/A5/A6 edits (CHK003 marker form, CHK008 a11y, CHK022 SC-007 parity, CHK031/032 cap). A dated review note was added to the checklist's Notes and to Clarifications. |
| A5 | Coverage Gap | LOW | spec.md SC-007; tasks.md T025 | SC-007 requires light/dark cross-overview parity, but no task can observe rendered themes (T025 uses TestClient). | **RESOLVED.** Recorded that theme parity is guaranteed **by construction** (tokens-only, enforced by `test_conformance.py`) and validated **manually** per quickstart — no pixel/theme assertion is added. Verification note added under T025; decision in Clarifications. |
| A6 | Coverage Gap | LOW | spec.md FR-032/FR-033; checklists/spec-quality.md CHK008 | Accessibility was specified only for the logo focus state; tabs/filter/pagination carried no explicit keyboard/ARIA requirement. | **RESOLVED.** Added an accessibility note under the Design-system-conformance requirements: a11y for the added controls is inherited from the shared macros (covered by FR-033); the new `pagination` macro adds `aria-label`/`aria-disabled`. Closes CHK008; decision in Clarifications. |
| A7 | Inconsistency | LOW | data-model.md (Run entity); contracts/runs-overview.md §B; tasks.md T008 | `created_iso` appeared in the `/api/runs` payload (§B) and T008's row fields but not in the data-model Run entity table. | **RESOLVED.** Added a `created_iso` row to the data-model Run table (companion to `created`: the hover value and the machine-readable value JS re-localises). Field inventory now identical across data-model, §B, and T008. |
| A8 | Ambiguity | LOW | research.md R7; spec.md SC-005; tasks.md T023 | Created/Duration are formatted browser-tz-side, but the server's first paint has no browser tz while SC-005 asserts an exact literal — the first-paint interaction was unstated. | **RESOLVED.** R7 now states each row carries a machine-readable timestamp (epoch/`created_iso`) plus a server-rendered fallback label; `runs-list.js` re-localises to the browser tz on load, and SC-005's exact literal is evaluated in the operator's local tz. Status/ordering never depend on it. Decision in Clarifications. |

_No findings dropped to overflow; all eight are resolved and no new findings were introduced._

## Coverage Summary — Functional Requirements → Tasks

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 true status | ✅ | T003, T007, T010, T013 | A1 reconciled: `timed_out` is local-only / last-known. |
| FR-002 last-known fallback | ✅ | T004, T007, T011, T012, T013 | Covers both unreachable and no-record cases. |
| FR-003 Dagster wins | ✅ | T012, T013 | Merge precedence in T007. |
| FR-004 status tag intents | ✅ | T003, T010 | |
| FR-005 tabbed partition | ✅ | T003, T014 | `unknown` → All only; `all ≥ sub-tabs` (A2 resolved). |
| FR-006 count badges over filtered set | ✅ | T007, T014, T018 | |
| FR-007 remove Status dropdown | ✅ | T007, T014, T018 | Old `status` param ignored. |
| FR-008 ghost Filter | ✅ | T015 | |
| FR-009 text filter substring | ✅ | T006, T016, T018 | Em-dash target never matches. |
| FR-010 agent + date filters retained | ✅ | T015 | |
| FR-011 URL state | ✅ | T016, T018 | |
| FR-012 column order | ✅ | T019, T025 | |
| FR-013 remove Date/Time/Attempts | ✅ | T019, T025 | |
| FR-014 Target | ✅ | T004, T021 | |
| FR-015 Launched by | ✅ | T004, T021 | |
| FR-016 Checks like Agents | ✅ | T004, T022 | Reuses `_check_status`/`_parse_checks`. |
| FR-017 Created format | ✅ | T023, T025 | First-paint tz reconciled (A8). |
| FR-018 Duration | ✅ | T023, T025 | No live ticker. |
| FR-019 Cost `—` not 0 | ✅ | T024, T025 | Reuses `_fmt_cost`. |
| FR-020 mono Agent/Model + agent link | ✅ | T020, T025 | |
| FR-021 `—` when unobtainable | ✅ | T021, T025 | |
| FR-022 Dagster link icon | ✅ | T026, T028 | |
| FR-023 run id link | ✅ | T019, T026, T028 | |
| FR-024 no icon when unconfigured | ✅ | T026, T028 | |
| FR-025 30/page pagination | ✅ | T007, T034, T036 | |
| FR-026 filters before pagination | ✅ | T007 | |
| FR-027 change tab/filter → page 1 | ✅ | T017, T036 | Client + server clamp. |
| FR-028 page in URL | ✅ | T016, T034, T035 | |
| FR-029 nav Runs · rule · Agents | ✅ | T038, T040 | |
| FR-030 single Settings entry | ✅ | T038, T040 | |
| FR-031 settings modal reachable (staged) | ✅ | T038 | `/settings` retained unlinked (R4). |
| FR-032 logo → home + focus | ✅ | T039, T040 | a11y of added controls now noted (A6). |
| FR-033 design-system conformance | ✅ | T027, T033, T037 | |
| FR-034 Pagination design-system-first | ✅ | T029, T030, T031, T032, T037 | |
| **FR-035 enrichment-cap note** | ✅ | **T045**, T007 | New (A3): visible cap note; older rows last-known. |

**FR coverage: 35 / 35 = 100%.**

### Success Criteria → Tasks

| SC | Has Task? | Task IDs | Notes |
|----|-----------|----------|-------|
| SC-001 status truth | ✅ | T013 | Reworded for `timed out` provenance (A1). |
| SC-002 renders with Dagster down | ✅ | T013 | |
| SC-003 single-action find | ✅ | T018 | |
| SC-004 URL round-trip | ✅ | T018, T036 | |
| SC-005 exact Created/Cost literals | ✅ | T023, T025 | First-paint tz reconciled (A8). |
| SC-006 30/page + page-1 reset | ✅ | T036 | |
| SC-007 light/dark cross-overview parity | ✅ | T025 + conformance | Verification method now stated (A5): tokens-only conformance + manual quickstart. |
| SC-008 nav/settings/logo | ✅ | T040 | |
| SC-009 full suite incl. conformance | ✅ | T037, T043 | |

## Constitution Alignment

No violations, before or after remediation. The plan's Constitution Check (plan.md:82–99) remains
accurate against v1.3.0:

- **VII One Design System** — Pagination is design-system-first (component + specimen + manifest +
  bundle + readme, then macro, then use; T029–T034); FR-035's cap note is tokens/macros only (T045);
  enforced by `test_conformance.py` / `test_design_system_docs.py` / `test_design_system_sync.py`.
  **PASS.**
- **V Ephemeral Runs, Immutable Outputs** — read-path/presentation only; `SCHEMA_VERSION` untouched;
  no run-record writes (the remediation added no write path). **PASS.**
- **VI Docs Track Reality** — README + design-system readme updates tracked (T041, T042). **PASS.**
- **I–IV** — not engaged. **N/A.**

No CRITICAL findings arise from the constitution.

## Unmapped Tasks

None orphaned. Non-FR tasks are correctly scoped as infrastructure/quality:
- **T001, T002** — Setup (baseline suite green; confirm reusable assets).
- **T009** — foundational `test_dagster.py` coverage (one-POST guarantee).
- **T041, T042** — docs (constitution VI).
- **T043, T044** — full gate + quickstart walk (SC-009).
- **T045** — maps to the new FR-035 (enrichment-cap note).

## Metrics

- **Total functional requirements**: 35 (FR-001–FR-035)
- **Total success criteria**: 9 (SC-001–SC-009)
- **Total tasks**: 45 (T001–T045)
- **FR coverage**: 100% (35/35 have ≥1 task)
- **SC coverage**: 100% (SC-007 verification method now explicit)
- **Open findings**: 0 (8 resolved)
- **Ambiguity count**: 0
- **Inconsistency count**: 0
- **Coverage-gap count**: 0
- **Duplication count**: 0
- **Critical issues count**: 0
- **Constitution violations**: 0

## Next Actions

No open findings and no CRITICAL issues — implementation is **not blocked**. `/speckit-implement` may
proceed. The eight prior findings are resolved in `spec.md`, `data-model.md`, `research.md`,
`tasks.md`, and `checklists/spec-quality.md`; the unattended judgment calls (A1, A2, A3, A5, A6, A8)
are recorded in `spec.md` §Clarifications → *Session 2026-09-17 (analysis remediation)*. No re-plan or
re-architecture is warranted; `/speckit-plan` need not be rerun.

## Extension hooks

`.specify/extensions.yml` was checked: `hooks:` is empty (`hooks: {}`), so no `before_analyze` or
`after_analyze` hooks are registered — hook execution skipped, as designed.
