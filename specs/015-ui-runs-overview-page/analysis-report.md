# Specification Analysis Report — Runs Overview Page (015)

**Command**: `/speckit-analyze` (read-only cross-artifact consistency check)
**Date**: 2026-09-17
**Feature dir**: `specs/015-ui-runs-overview-page/`
**Artifacts analysed**: `spec.md`, `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`, `contracts/runs-overview.md`, `contracts/pagination-component.md`, `checklists/`)
**Constitution**: v1.3.0 (`.specify/memory/constitution.md`)

> Run unattended: no clarifying questions were asked. Where a judgement call was needed it is stated inline and resolved to the most reasonable reading of the spec + repo. This report writes no changes to `spec.md`, `plan.md`, or `tasks.md`.

## Summary verdict

The three core artifacts are unusually well aligned. Every functional requirement (FR-001–FR-034) maps to at least one task, every user story has an implementation + test task pair, and the constitution gates (VII One Design System, V Ephemeral Runs, VI Docs Track Reality) are respected and explicitly tracked. **No CRITICAL issues and no constitution violations were found.**

The findings below are refinements, not blockers: one genuine status-vocabulary inconsistency (`timed_out` has no Dagster source), a `unknown`-status modelling gap that ripples into tab-count math, a research decision (the N=500 enrichment cap "surfaced as a note") that no task implements, and a few measurability/coverage gaps already flagged by the feature's own quality checklist. An operator may proceed to `/speckit-implement`, ideally after resolving A1 and A2.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md:248 (FR-001), spec.md:38-40 (US1 Independent Test), contracts/runs-overview.md:124 (§D), research.md:154-159 (R8) | FR-001 and US1's Independent Test say a **timed-out** status is "the real outcome Dagster records", but the normalisation table marks `timed_out` as "(none; local)" — Dagster has no TIMEOUT RunStatus, so a run Dagster reports as `FAILURE`/`CANCELED` can never present as `timed_out` while Dagster is reachable and "wins" (FR-003). The US1 test step "one that times out … confirm each row's Status matches what Dagster shows" is not realisable as written. | Reconcile: either state that `timed_out` derives only from the local report and is therefore shown only when Dagster lacks a distinct signal, or drop "timed out" from FR-001's "outcome Dagster records" list and adjust the US1 Independent Test. Read-path only; no code change to the source of truth. |
| A2 | Inconsistency | MEDIUM | data-model.md:16, contracts/runs-overview.md:128 (§D), tasks.md:60-61 (T003) | The presented-status **set differs across artifacts**: data-model.md lists 6 states (no `unknown`); contract §D and T003 list 7 (add `unknown`). Contract §D routes `unknown` to "shown under All only", so a run with unknown status counts in the `all` badge but in none of in_progress/succeeded/failed — the three sub-tab counts need not sum to `all`. The spec's FR-005 partition never mentions `unknown`. | Add `unknown` to the data-model presented set for parity, and state explicitly (spec Edge Cases or FR-005 note) that an unknown-status run appears under All only and that `all ≥ in_progress + succeeded + failed`, so the intended count behaviour is a requirement, not an implementation surprise. |
| A3 | Coverage Gap | MEDIUM | research.md:16-17 (R1), plan.md:79-80, tasks.md:80-84 (T007) | R1 requires the N=500 enrichment cap be **"surfaced (a note), never silently truncated."** T007 implements the cap but no task renders any user-facing note, and no FR/SC requires one. As written, exceeding 500 filtered runs truncates enrichment silently — the exact outcome R1 forbids. | Add a task to render the cap note in `runs/list.html` (tokens/macros only) when the filtered set exceeds N, or record the cap-surfacing as an explicit FR. Otherwise drop the "surfaced" promise from R1 to keep artifacts honest. |
| A4 | Underspecification | MEDIUM | spec.md:373 (SC-009 gate), checklists/spec-quality.md (all items `[ ]`) | The feature's own `spec-quality.md` checklist is **entirely unchecked** (CHK001–CHK040). The checklist note states `/speckit-implement` reads checklist checkbox state as a gate; an all-unchecked reviewer-owned checklist signals the requirements-quality review has not been signed off. (`requirements.md` is fully `[x]`, so this is specific to the deeper quality checklist.) | Have a reviewer walk `spec-quality.md` and mark satisfied items before `/speckit-implement`, or confirm the gate treats this checklist as advisory. Several items below (A1, A2, A3, A5, A6) correspond directly to its open CHK entries. |
| A5 | Coverage Gap | LOW | spec.md:367-369 (SC-007), tasks.md:188-192 (T025) | SC-007 requires the Runs and Agents overviews share tab header, filter control, and Agent/Model font **"viewed side by side in light and dark themes."** No task verifies theme parity; T025 (the only task citing SC-007) checks columns/agent-link via TestClient, which cannot observe rendered theme. Verification is left to manual quickstart only. | Acceptable if theme parity is delegated to `test_conformance.py` (tokens-only ⇒ both themes by construction) — state that reliance explicitly, or add a note that SC-007 is validated manually per quickstart. Automated pixel/theme parity is out of the suite's reach. |
| A6 | Coverage Gap | LOW | spec.md:330 (FR-032), checklists/spec-quality.md:20 (CHK008) | Accessibility is specified only for the **logo focus state** (FR-032). The new interactive elements — tabs, ghost-Filter control, pagination — carry no explicit keyboard/ARIA requirement, though tasks inherit `aria-*` via shared macros (T032 adds `aria-label="Pagination"`/`aria-disabled`; tabs/filter reuse Agents macros). CHK008 flags this as an open gap. | Either add a brief a11y requirement covering the added controls, or record that a11y is inherited from the shared macros (and thus covered by design-system conformance). No task needs to change if the latter is stated. |
| A7 | Inconsistency | LOW | contracts/runs-overview.md:66 (§B), data-model.md:23, tasks.md:90-92 (T008) | `created_iso` appears in the `/api/runs` payload (§B) and T008's row fields but is **not listed in the data-model Run entity table** (which has `created` with "full ISO on hover"). Minor field-inventory drift. | Add `created_iso` to the data-model Run table (or fold the note into `created`) so the presented-row field list is identical across data-model, contract §B, and T008. |
| A8 | Ambiguity | LOW | research.md:137-145 (R7), spec.md:363-364 (SC-005), tasks.md:186-188 (T023) | Created/Duration local-time formatting is done "template/JS-side against the browser tz" (R7, T023), but the server's first paint has no browser timezone. SC-005 asserts an exact literal (`Sep 17, 1:15 PM`); a no-JS or pre-hydration first paint could render server-tz. The interaction between first-paint (server) truthfulness (per R1) and browser-tz formatting is unstated. | State how first paint handles tz (e.g. server renders a stable label / data-attribute that JS localises), so SC-005's exact-literal expectation and the "truthful on first paint" goal don't conflict for the timestamp columns. |

_No findings were dropped to an overflow summary; total findings (8) are well under the 50-row limit._

## Coverage Summary — Functional Requirements → Tasks

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 true status | ✅ | T003, T007, T010, T013 | See A1 re `timed_out`. |
| FR-002 last-known fallback | ✅ | T004, T007, T011, T012, T013 | Covers both unreachable and no-record cases. |
| FR-003 Dagster wins | ✅ | T012, T013 | Merge precedence in T007. |
| FR-004 status tag intents | ✅ | T003, T010 | |
| FR-005 tabbed partition | ✅ | T003, T014 | `unknown` bucket unstated — see A2. |
| FR-006 count badges over filtered set | ✅ | T007, T014, T018 | |
| FR-007 remove Status dropdown | ✅ | T007, T014, T018 | Old `status` param ignored. |
| FR-008 ghost Filter | ✅ | T015 | |
| FR-009 text filter substring | ✅ | T006, T016, T018 | Em-dash target never matches. |
| FR-010 agent + date filters retained | ✅ | T015 | |
| FR-011 URL state | ✅ | T016, T018 | |
| FR-012 column order | ✅ | T019, T025 | |
| FR-013 remove Date/Time/Attempts | ✅ | T019, T025 | Verified against current `list.html:40-42`. |
| FR-014 Target | ✅ | T004, T021 | |
| FR-015 Launched by | ✅ | T004, T021 | |
| FR-016 Checks like Agents | ✅ | T004, T022 | Reuses `_check_status`/`_parse_checks`. |
| FR-017 Created format | ✅ | T023, T025 | See A8 (tz on first paint). |
| FR-018 Duration | ✅ | T023, T025 | No live ticker. |
| FR-019 Cost `—` not 0 | ✅ | T024, T025 | Reuses `_fmt_cost` (`main.py:358`). |
| FR-020 mono Agent/Model + agent link | ✅ | T020, T025 | |
| FR-021 `—` when unobtainable | ✅ | T021, T025 | |
| FR-022 Dagster link icon | ✅ | T026, T028 | `#external` icon confirmed present. |
| FR-023 run id link | ✅ | T019, T026, T028 | |
| FR-024 no icon when unconfigured | ✅ | T026, T028 | |
| FR-025 30/page pagination | ✅ | T007, T034, T036 | |
| FR-026 filters before pagination | ✅ | T007 | |
| FR-027 change tab/filter → page 1 | ✅ | T017, T036 | Client + server clamp. |
| FR-028 page in URL | ✅ | T016, T034, T035 | |
| FR-029 nav Runs · rule · Agents | ✅ | T038, T040 | |
| FR-030 single Settings entry | ✅ | T038, T040 | |
| FR-031 settings modal reachable (staged) | ✅ | T038 | `/settings` retained unlinked (R4). |
| FR-032 logo → home + focus | ✅ | T039, T040 | A11y scope only covers logo — see A6. |
| FR-033 design-system conformance | ✅ | T027, T033, T037 | |
| FR-034 Pagination design-system-first | ✅ | T029, T030, T031, T032, T037 | Ordering enforced (T029-31 → T032 → T034). |

**FR coverage: 34 / 34 = 100%.**

### Success Criteria → Tasks

| SC | Has Task? | Task IDs | Notes |
|----|-----------|----------|-------|
| SC-001 status truth | ✅ | T013 | |
| SC-002 renders with Dagster down | ✅ | T013 | |
| SC-003 single-action find | ✅ | T018 | |
| SC-004 URL round-trip | ✅ | T018, T036 | |
| SC-005 exact Created/Cost literals | ✅ | T023, T025 | See A8. |
| SC-006 30/page + page-1 reset | ✅ | T036 | |
| SC-007 light/dark cross-overview parity | ⚠️ | T025 (partial) | No theme-parity assertion — see A5. |
| SC-008 nav/settings/logo | ✅ | T040 | |
| SC-009 full suite incl. conformance | ✅ | T037, T043 | |

## Constitution Alignment

No violations. The plan's Constitution Check (plan.md:82-99) is accurate against v1.3.0:

- **VII One Design System** — Pagination is planned design-system-first (component source + specimen + manifest + bundle + readme, then macro, then use; T029-T034), styling tokens-only, no inline styles; enforced by `test_conformance.py` / `test_design_system_docs.py` / `test_design_system_sync.py`. **PASS.**
- **V Ephemeral Runs, Immutable Outputs** — read-path/presentation only; `SCHEMA_VERSION` untouched; no run-record writes. **PASS.**
- **VI Docs Track Reality** — README + design-system readme updates tracked (T041, T042). **PASS.**
- **I–IV** — not engaged (no orchestrator/agent-schema/harness/secret surface). **N/A.**

No CRITICAL findings arise from the constitution.

## Unmapped Tasks

None that are orphaned. The tasks without a direct FR are correctly scoped as infrastructure/quality:
- **T001, T002** — Setup (baseline suite green; confirm reusable assets). Verified: `#external`/`#filter` icons, `tabs` macro (`macros.html:115`), `run_status_tag` (`macros.html:161`), `_fmt_cost` (`main.py:358`), Agents ghost-Filter (`agents/list.html:46-53`) all exist as claimed.
- **T009** — foundational `test_dagster.py` coverage (one-POST guarantee).
- **T041, T042** — docs (constitution VI).
- **T043, T044** — full gate + quickstart walk (SC-009).

## Metrics

- **Total functional requirements**: 34 (FR-001–FR-034)
- **Total success criteria**: 9 (SC-001–SC-009)
- **Total tasks**: 44 (T001–T044)
- **FR coverage**: 100% (34/34 have ≥1 task)
- **SC coverage**: 100% have ≥1 task; SC-007 only partially verifiable in-suite (A5)
- **Ambiguity count**: 2 (A1 partial, A8)
- **Inconsistency count**: 3 (A1, A2, A7)
- **Coverage-gap count**: 3 (A3, A5, A6)
- **Duplication count**: 0
- **Critical issues count**: 0
- **Constitution violations**: 0

## Next Actions

No CRITICAL issues — implementation is **not blocked**. Recommended order before/at `/speckit-implement`:

1. **Resolve A1** (timed_out vs Dagster vocabulary) — a one-line spec/edit to FR-001 + US1 Independent Test; do this before writing T003/T010 tests so the `timed_out` mapping and its test are coherent. Suggested: *Manually edit `spec.md` FR-001 and US1 Independent Test.*
2. **Resolve A2** (add `unknown` to the data-model presented set; state All-only bucketing and the count relationship) so tab-count tests in T018/T036 assert the intended math. Suggested: *Manually edit `data-model.md` and add an FR-005 note in `spec.md`.*
3. **Decide A3** — either add a "showing most recent N" note task to Phase 2/US5, or drop the "surfaced" wording from R1. Suggested: *Add a task to `tasks.md` or amend `research.md` R1.*
4. **A4** — reviewer signs off (or explicitly de-gates) `checklists/spec-quality.md` before `/speckit-implement` reads it as a gate.
5. **A5–A8** are LOW; fold into the same spec/data-model edit pass or accept as documented. No re-plan or re-architecture is warranted — the plan and tasks are sound.

Since no architectural change is implied, there is **no need to rerun `/speckit-plan`**; targeted manual edits to `spec.md` / `data-model.md` / `research.md` (or a light `/speckit-clarify` pass on A1/A2) fully address the findings, after which `/speckit-implement` may proceed.

## Remediation offer

Concrete remediation edits for the top issues (A1–A3) can be drafted on request. Per `/speckit-analyze`'s read-only contract, none were applied — this report changes no `spec.md`, `plan.md`, or `tasks.md` content.

## Extension hooks

`.specify/extensions.yml` was checked: `hooks:` is empty (`hooks: {}`), so no `before_analyze` or `after_analyze` hooks are registered — hook execution skipped, as designed.
