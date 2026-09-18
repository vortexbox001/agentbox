# Specification Analysis Report — Run Detail Page

**Feature**: `017-ui-run-detail-page` (git branch `207-ui-run-detail-page`)
**Generated**: 2026-09-18 by `/speckit-analyze` (read-only, non-destructive)
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md`, cross-checked against `research.md`,
`data-model.md`, `contracts/run-detail.md`, `contracts/design-system.md`, `quickstart.md`, and
`.specify/memory/constitution.md` (v1.3.0).

> **Report location note (decision made unattended).** The invocation asked for
> `specs/$GITHUB_BRANCH/analysis-report.md` (`specs/207-ui-run-detail-page/`), but the spec-kit
> `check-prerequisites.sh` resolves `FEATURE_DIR` to `specs/017-ui-run-detail-page/`, and every
> artifact (plan.md, tasks.md) documents that the `207-…` branch and the `017-…` directory refer to
> the **same** feature (the branch number is a typo in the `015/016/017` sequence). Writing into a
> new `207-…` directory would orphan this report from the artifacts it analyzes, so it is placed in
> the real feature directory. This mismatch is itself recorded as finding **D1** below.

---

## Executive Summary

The three core artifacts are unusually well aligned: requirement identifiers (FR-001…FR-037) are
threaded through the plan, data-model, contracts, quickstart, and every task, and the constitution
gates are satisfied with no violations. Coverage is near-complete (36/37 functional requirements have
at least one implementing task).

The analysis surfaced **one HIGH internal conflict** that will cause an acceptance-test failure if
implemented as written (the *Produced elsewhere* display condition, **I1**), **two MEDIUM findings**
(an `exit`-field contradiction between data-model and plan, **I2**; and the fact that the named
Python test suite structurally cannot exercise the feature's client-side JavaScript behavior, **C1**),
plus several LOW/MEDIUM refinements. **No CRITICAL issues and no constitution violations were found.**

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency (conflicting requirement) | HIGH | spec.md:286-287 (Edge Cases) vs spec.md:337-340 (FR-011), spec.md:166-175 (US4), plan.md:165-166 (R4), data-model.md:47, tasks.md:231-236/249 (T029/T034) | The spec edge case says a run with **both** output files **and** a pull request shows *"Both the file rows and the Produced elsewhere list … and the note counts both"*, but FR-011 + US4 + plan R4 + data-model + T034 all gate the produced-elsewhere list to appear **only when there are no output artifacts**. Under the planned mining logic, the "files + PR both shown" edge case can never occur, and the FR-014 note "N files · M pull requests" with **both** N>0 and M>0 (which SC-004-style counting implies) is unreachable. | Decide the intended behavior and make it consistent. Recommended (matches FR-014's "count both" intent): mine produced-elsewhere **always**, render it whenever evidence exists (below the file rows when files are present), and keep the note counting both. Then correct FR-011's "When the run has no output artifacts" gating, or explicitly scope produced-elsewhere to the files-empty case and delete the contradicting edge case + weaken FR-014. Update plan R4, data-model, and T029/T034 to match whichever is chosen. |
| I2 | Inconsistency | MEDIUM | data-model.md:104 vs plan.md:172 (R6), tasks.md:150-152 (T016) | data-model states each tool from `conversation_entries` already carries an `exit` field (`{tool, arg, result, diff, missing, state, exit}`), but plan R6 says *"the normalized event schema carries **no** exit field"* and T016 derives `exit N` by parsing the **result text** for a recognizable exit code. The two descriptions of where the exit code comes from are contradictory. | Verify against `images/lib/agent_events.py` / `runs_store.conversation_entries` whether an `exit` field actually exists. Reconcile data-model line 104 and plan R6 to describe a single source of truth for the `exit N` marker, and align T016's derivation wording accordingly. |
| C1 | Coverage gap (untestable acceptance criteria) | MEDIUM | tasks.md T011/T012/T018/T051/T053; spec SC-002, SC-007; FR-004/FR-025/FR-028/FR-029/FR-030 | The feature's interactive behavior lives in `ui/static/run-detail.js` (per-browser section persistence, clamp/expand, expand-all, search hide + auto-expand-on-match, raw-log toggle). The named acceptance suite runs through FastAPI's `TestClient`, and AGENTS.md confirms there is **no JS bundler/test harness** (plain ES modules, no `package.json`). So the Python tests in T011/T012/T018/T051/T053 can only assert the **server-rendered markup** (that content/attributes are present for JS to act on) — they cannot verify SC-002 ("remembered 100% of the time") or the SC-007/FR-029 hide/auto-expand behavior. Those criteria are validated **only** by the manual quickstart. | Make this explicit so the SC-010 "full suite passes" gate is not mistaken for coverage of interactive behavior: reword T011/T018/T051/T053 to state they assert rendered-markup hooks (data attributes, `aria-expanded`, IN/OUT text presence, storage key), and flag the JS behaviors as manual-only in quickstart. If automated coverage is desired, add a lightweight DOM/JS test path (out of current scope). |
| A1 | Ambiguity / silent resolution | MEDIUM | spec.md:284-285 (Edge Cases) & spec.md:386-388 (FR-026) vs plan.md:177-178 (R7), data-model.md:115, tasks.md:138/151 (T013/T016) | The spec makes "diff cards expand by default" **conditional** — *"if diff colouring cannot survive the clamped OUT row cleanly"*. The plan/data-model/tasks resolve it to an **unconditional** rule (diff OUT rows always render expanded). Reasonable, but the conditional was decided away silently. | Confirm the decision is intended and update FR-026 to state the unconditional rule (or keep the condition and add a task to evaluate whether clamped diff colouring is acceptable). Either way, make spec and plan say the same thing. |
| U1 | Underspecification | MEDIUM | spec.md:352-360 (FR-015/FR-018) vs data-model.md:76 & contracts/design-system.md:60-64 (CheckRow) & tasks.md:284-285 (T039) | The spec describes check outcomes as **pass / warn / fail**, but the design-system component and data-model introduce two additional statuses — `fail-blocking` and `not-run` — that the spec never names. FR-018's closed-state note builder (T039) defines counts only for passed / warning / failed and does **not** say how a `not-run` check is reflected in the note (e.g. is it counted, or does its presence change "—"?). | Add the full status vocabulary (pass / warn / fail-blocking / not-run) to the spec, and specify FR-018's note wording for the `not-run` case (and whether it participates in the "—" empty determination in FR-017). |
| D1 | Inconsistency (identifier drift) | LOW | spec.md:3, plan.md:3/7-8, tasks.md:13-14; directory `specs/017-ui-run-detail-page/` | The git branch is `207-ui-run-detail-page` while the feature directory is `017-ui-run-detail-page`. Given the `015 → 016 → 017` sequence, `207` is almost certainly a transposed/typo of `017`. Plan and tasks explicitly reconcile the two names, so it is not blocking, but it is a real inconsistency that also forced the report-location decision above. | If cheap, rename the branch to `017-ui-run-detail-page` for consistency; otherwise leave the plan/tasks reconciliation note (already present) as the authoritative statement. No artifact-content change required. |
| G1 | Coverage gap (constraint unverified) | LOW | spec.md:417-419 (FR-035); tasks.md:475-477 (Notes) | FR-035 (presentation/read-path only: no run-record writes, no `SCHEMA_VERSION` bump, no new dependency, no new check types, no subscription-harness cost data) has **no positive verifying task or test** — it is enforced only by the tasks.md "Notes" policy statement and reviewer diligence. | Add a cheap guard, e.g. a test asserting `SCHEMA_VERSION` is unchanged and `ui/requirements.txt` is untouched, or an explicit review-checklist item, so the "no write" guarantee is verifiable rather than assumed. |
| A2 | Ambiguity | LOW | spec.md:314-315 (FR-005), spec.md:316-318 (FR-006), spec.md:220-222 (US6-AC3) | US6-AC3 and the plan say "harness … remain in the rail", but FR-006's rail enumeration names **"Configuration"** (not "harness"), and FR-005's six-stat strip also lists **"Harness"**. Where the harness label surfaces (stat strip vs. the rail's Configuration block) is slightly ambiguous across the three requirements. | Clarify that "Harness" appears as a header stat (FR-005) and that harness *detail* lives inside the rail's Configuration block (FR-006), so the US6 wording "harness remains in the rail" is not read as a second, separate placement. |

*No duplication findings. No unresolved placeholders (TODO/TKTK/???/`<placeholder>`) found. No vague-adjective ambiguities (the spec pins clamp height, degradation behavior, and note wording explicitly).*

---

## Coverage Summary

All 37 functional requirements were mapped to tasks by explicit FR-ID reference. Representative mapping
(story requirements condensed by section; every FR below has ≥1 task except FR-035):

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (five sections, order) | ✅ | T009, T010, T012 | |
| FR-002 (open/closed defaults) | ✅ | T009, T011, T012, T047 | |
| FR-003 (disclosure header, a11y) | ✅ | T004, T006, T007, T011, T012 | |
| FR-004 (per-browser persistence, shared key) | ✅ | T011 | JS-only behavior — see **C1** |
| FR-005 (header + stat strip unchanged) | ✅ | T010, T012 | |
| FR-006 (rail order; two removals) | ✅ | T026, T035, T049 | Removals owned by US3/US4 |
| FR-007 (summary markdown subset) | ✅ | T021, T022, T024, T028 | |
| FR-008 (summary fallback ladder) | ✅ | T025, T028 | |
| FR-009 (summary note) | ✅ | T008, T025 | |
| FR-010–FR-014 (Output + produced-elsewhere) | ✅ | T029–T037 | Display-condition conflict — see **I1** |
| FR-015–FR-018 (Checks) | ✅ | T038–T046 | Status vocabulary gap — see **U1** |
| FR-019–FR-020 (Context) | ✅ | T047, T048, T049 | |
| FR-021–FR-027 (tool cards) | ✅ | T013–T020 | `exit` source — see **I2**; diff-expand — see **A1** |
| FR-028–FR-034 (transcript controls/entries) | ✅ | T017, T018, T050–T053 | Search/toggle JS-only — see **C1** |
| FR-035 (read-path only, no writes) | ⚠️ policy-only | tasks.md Notes | No positive task/test — see **G1** |
| FR-036 (tokens-only styling) | ✅ | T007, T019, T027, T036, T045, T056 | |
| FR-037 (design-system-first) | ✅ | T005, T014, T023, T032, T041, T055 | |

### Success Criteria coverage

| SC | Verified by | Notes |
|----|-------------|-------|
| SC-001 | T012 | Server markup — OK |
| SC-002 | quickstart US1 only | **JS persistence — no automated coverage (C1)** |
| SC-003 | T028 | markdown render golden assertion |
| SC-004 | T037 | **Depends on I1 resolution** (note "0 files · 1 pull request") |
| SC-005 | T020 | overflow affordance in markup — OK |
| SC-006 | T020 | `failed` marker + intent in markup — OK |
| SC-007 | T053 + quickstart US7 | **search hide is JS-only (C1)** — T053 can assert IN/OUT text presence + count hook, not the hide/auto-expand |
| SC-008 | T028, T046 | OK |
| SC-009 | T007/T019/T027/T036/T045 + T056 + manual T058 | conformance + manual theme walk |
| SC-010 | T055, T056, T057 | full suite gate |

**Unmapped tasks (expected — infrastructure / polish, not FR-specific):** T001, T002 (env + baseline),
T003 (golden fixture, supports SC-010), T054 (README, Principle VI), T057, T058 (full-suite gate +
manual theme walk). These are legitimately mapped to SC-010 / Principle VI rather than a single FR.

---

## Constitution Alignment Issues

**None.** Constitution v1.3.0 gates were checked against the plan's Constitution Check (plan.md:122-142)
and the tasks:

- **VII. One Design System** — the five new components are design-system-first (source + specimen +
  manifest + bundle + readme, then macro, then page): T004/T005, T013/T014, T022/T023, T031/T032,
  T040/T041, enforced by T055 (sync) + T056 (conformance) + T036 tokens-only. Compliant.
- **V. Ephemeral Runs, Immutable Outputs** — read-path only; the additive Dagster check-field
  selection is a read (T038, contract §E); no run-record write. Compliant. (See **G1** — compliant but
  not automatically *verified*.)
- **VI. Docs Track Reality** — README refresh (T054) + design-system readme/docs tests (T055 docs
  side). Compliant.
- **I–IV** — not engaged (no orchestrator / schema / harness / secret surface change). Correct.

---

## Metrics

- **Total functional requirements**: 37 (FR-001 … FR-037)
- **Total success criteria**: 10 (SC-001 … SC-010)
- **Total tasks**: 58 (T001 … T058)
- **Requirements coverage**: 36/37 have ≥1 implementing task ≈ **97%** (FR-035 is policy-only — G1)
- **Ambiguity count**: 2 (A1 diff-expand condition, A2 harness placement)
- **Duplication count**: 0
- **Inconsistencies**: 3 (I1 HIGH, I2 MEDIUM, D1 LOW)
- **Underspecification**: 1 (U1)
- **Coverage gaps**: 2 (C1 MEDIUM, G1 LOW)
- **Critical issues**: **0**
- **Constitution violations**: **0**

---

## Next Actions

No CRITICAL issues block `/speckit-implement`, but **finding I1 (HIGH) should be resolved first** — as
written, an implementation that follows FR-011/plan/tasks will fail the spec's own "files + PR both
shown" edge case, and the FR-014 "count both" note becomes unreachable. This is a spec/plan
reconciliation, not a code problem, so it is cheapest to fix now.

Recommended order:

1. **Resolve I1** — pick one behavior for produced-elsewhere (recommended: always mine + render, note
   counts both) and align spec FR-011/edge case, plan R4, data-model, and T029/T034. → run
   `/speckit-specify` (refine FR-011 + edge case) then `/speckit-plan` / edit `tasks.md`.
2. **Resolve I2** — confirm the real source of the `exit` marker and make data-model line 104 and plan
   R6 agree. → edit `plan.md` + `data-model.md`; adjust T016 wording.
3. **Address C1** — reword T011/T018/T051/T053 to state they assert rendered-markup hooks, and mark the
   JS behaviors (FR-004/FR-025/FR-028/FR-029/FR-030, SC-002/SC-007) as manual-only in quickstart.
4. **Clarify A1, U1** (spec edits) and **add G1's guard test**; **D1/A2** are optional polish.

After I1 and I2 are reconciled, the plan is coherent and implementation-ready.

## Offer to remediate

`/speckit-analyze` is read-only and made **no** edits to `spec.md`, `plan.md`, or `tasks.md`. Concrete
remediation edits for the findings above (especially I1 and I2) can be prepared on request — they are
not applied automatically.

---

### Extension hooks

`.specify/extensions.yml` exists but registers no `before_analyze` or `after_analyze` hooks
(`hooks: {}`), so no hook commands were emitted or executed.
