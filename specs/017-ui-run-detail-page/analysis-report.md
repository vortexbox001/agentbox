# Specification Analysis Report — Run Detail Page

**Feature**: `017-ui-run-detail-page` (git branch `207-ui-run-detail-page`)
**Generated**: 2026-09-18 by `/speckit-analyze`; **remediated**: 2026-09-18 (this revision reflects the
post-remediation state — every finding below has been acted on in the artifacts).
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md`, cross-checked against `research.md`,
`data-model.md`, `contracts/run-detail.md`, `contracts/design-system.md`, `quickstart.md`, and
`.specify/memory/constitution.md` (v1.3.0).

> **Report location note.** The invocation asked for `specs/$GITHUB_BRANCH/analysis-report.md`
> (`specs/207-ui-run-detail-page/`), but the spec-kit `check-prerequisites.sh` resolves `FEATURE_DIR`
> to `specs/017-ui-run-detail-page/`, and every artifact documents that the `207-…` branch and the
> `017-…` directory refer to the **same** feature (`207` is a transposition of `017`). Writing into a
> new `207-…` directory would orphan this report from the artifacts it analyzes, so it stays in the
> real feature directory. This mismatch was finding **D1** and is now reconciled in all three core
> artifacts.

---

## Status: all findings remediated

The original analysis surfaced **8 findings** (1 HIGH, 4 MEDIUM, 3 LOW), **no CRITICAL issues, and no
constitution violations**. All 8 have been addressed by editing `spec.md`, `plan.md`, `tasks.md`, and
`data-model.md`. The four judgment/ambiguity resolutions (I1, A1, U1, A2) are recorded in the spec's
`## Clarifications → Session 2026-09-18 (analysis remediation)` subsection so the decisions are visible
and reviewable. A re-scan of the edited artifacts finds the original contradictions gone and **no new
inconsistencies introduced**.

---

## Findings — remediation log

| ID | Category | Severity | Resolution | Where fixed |
|----|----------|----------|------------|-------------|
| I1 | Inconsistency (conflicting requirement) | HIGH | **RESOLVED.** Decision (recorded in Clarifications): Produced-elsewhere is **scoped to the no-output-artifacts case** — the reading FR-011, US4, plan R4, data-model, and T034 already encode. The lone contradicting edge case ("both file rows and the Produced-elsewhere list appear, note counts both") was corrected to say the list is not shown when the run wrote `/output` files. FR-014 was clarified: the note reads "N files" when artifacts exist and "0 files · M pull request(s)" only when there are none. | spec.md Clarifications, Edge Cases ("A run with output files that also opened a pull request"), FR-014 |
| I2 | Inconsistency | MEDIUM | **RESOLVED.** Verified against code: `conversation_entries` (`ui/runs_store.py:287`) emits an `exit` key that is **always `None`** and never populated — the normalized event schema (`images/lib/agent_events.py`) carries no exit code. Single source of truth established: the `exit N` marker is **derived by parsing the result text** (plan R6 / T016); the `exit` key is a vestigial placeholder, not the source. data-model.md:104 now says so and plan R6 cross-references it. | data-model.md "Tool card view model", plan.md R6 |
| C1 | Coverage gap (untestable acceptance criteria) | MEDIUM | **RESOLVED (made explicit).** Added a **Test-surface note** to tasks.md stating the UI suite runs through FastAPI's `TestClient` with no JS harness, so Python tests assert only server-rendered markup hooks. T012/T053 reworded to markup-hook scope (section order, `aria-expanded`/`data-*`, storage-key wiring, IN/OUT text, match-count element). The JS-only behaviours (FR-004/FR-025/FR-028/FR-029/FR-030, SC-002/SC-007) are flagged **manual-only via quickstart** on the implementing tasks (T011/T018/T051). | tasks.md Tests preamble, T011, T012, T018, T051, T053 |
| A1 | Ambiguity / silent resolution | MEDIUM | **RESOLVED.** Decision (recorded in Clarifications): diff OUT rows **always render expanded by default** while non-diff cards clamp — the unconditional rule plan R7, data-model, and T013/T016 already implement. The conditional phrasing in the edge case and FR-026 was removed. | spec.md Clarifications, Edge Cases ("A diff result longer than the clamp height"), FR-026 |
| U1 | Underspecification | MEDIUM | **RESOLVED.** Decision (recorded in Clarifications): the full status vocabulary is **pass / warn / fail-blocking / not-run** (the values `ui/dagster.py:_check_status` returns). Added it to FR-015, US5 narrative/independent-test/acceptance-scenario, and the Key Entity. FR-018 now specifies the note counts passed/warning/failed/not-run (each only when non-zero, `fail-blocking` counted as "failed") and that a `not-run` check still counts and does **not** trigger the "—" empty note. T039/T046 updated to match. | spec.md Clarifications, FR-015, FR-017/FR-018, US5, Key Entity, tasks.md T039/T046 |
| D1 | Inconsistency (identifier drift) | LOW | **RESOLVED (reconciled, not renamed).** The `207` branch vs `017` directory drift is now reconciled in the spec header the same way plan.md and tasks.md already do — all three artifacts state the two names refer to one feature. The branch is not renamed (out of scope for an artifact-reconciliation pass and unnecessary given the note). | spec.md header |
| G1 | Coverage gap (constraint unverified) | LOW | **RESOLVED.** Added task **T059**: a read-path/no-write guard test asserting `SCHEMA_VERSION` unchanged, `ui/requirements.txt` untouched (no new dependency), no run-record mutation, and no new check types — making the FR-035 guarantee verifiable rather than policy-only. | tasks.md T059 |
| A2 | Ambiguity | LOW | **RESOLVED.** Decision (recorded in Clarifications): "Harness" appears **both** as a header stat (FR-005) **and** as harness detail inside the rail's Configuration block (FR-006) — not one instead of the other. FR-006 now says so, so US6's "harness remains in the rail" is not read as a second placement. | spec.md Clarifications, FR-006 |

*No duplication findings. No unresolved placeholders. No vague-adjective ambiguities.*

---

## Coverage Summary (post-remediation)

All 37 functional requirements map to tasks by explicit FR-ID reference. **FR-035, previously
policy-only, now has a positive verifying task (T059).**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 (five sections, order) | ✅ | T009, T010, T012 | |
| FR-002 (open/closed defaults) | ✅ | T009, T011, T012, T047 | |
| FR-003 (disclosure header, a11y) | ✅ | T004, T006, T007, T011, T012 | |
| FR-004 (per-browser persistence, shared key) | ✅ | T011 | JS-only — markup hooks tested (T012); behaviour manual (quickstart US1), see **C1** |
| FR-005 (header + stat strip unchanged) | ✅ | T010, T012 | |
| FR-006 (rail order; two removals; harness placement) | ✅ | T026, T035, T049 | Harness placement clarified — see **A2** |
| FR-007 (summary markdown subset) | ✅ | T021, T022, T024, T028 | |
| FR-008 (summary fallback ladder) | ✅ | T025, T028 | |
| FR-009 (summary note) | ✅ | T008, T025 | |
| FR-010–FR-014 (Output + produced-elsewhere) | ✅ | T029–T037 | Display condition resolved (files-empty gate) — see **I1** |
| FR-015–FR-018 (Checks) | ✅ | T038–T046 | Full status vocabulary + note rules — see **U1** |
| FR-019–FR-020 (Context) | ✅ | T047, T048, T049 | |
| FR-021–FR-027 (tool cards) | ✅ | T013–T020 | `exit` source clarified — see **I2**; diff-expand unconditional — see **A1** |
| FR-028–FR-034 (transcript controls/entries) | ✅ | T017, T018, T050–T053 | Search/toggle JS-only — see **C1** |
| FR-035 (read-path only, no writes) | ✅ | **T059** (guard test), tasks.md Notes | Now verifiable — see **G1** |
| FR-036 (tokens-only styling) | ✅ | T007, T019, T027, T036, T045, T056 | |
| FR-037 (design-system-first) | ✅ | T005, T014, T023, T032, T041, T055 | |

### Success Criteria coverage

| SC | Verified by | Notes |
|----|-------------|-------|
| SC-001 | T012 | Server markup — OK |
| SC-002 | quickstart US1 (manual) | JS persistence — no automated coverage by design (**C1**, now explicit in tasks.md) |
| SC-003 | T028 | markdown render golden assertion |
| SC-004 | T037 | "0 files · 1 pull request" — consistent with the **I1** files-empty gate |
| SC-005 | T020 | overflow affordance in markup — OK |
| SC-006 | T020 | `failed` marker + intent in markup — OK |
| SC-007 | T053 (markup hooks) + quickstart US7 (manual) | search hide/auto-expand is JS-only (**C1**) |
| SC-008 | T028, T046 | includes fail-blocking/not-run counting (**U1**) |
| SC-009 | T007/T019/T027/T036/T045 + T056 + manual T058 | conformance + manual theme walk |
| SC-010 | T055, T056, T057, T059 | full suite gate + read-path guard |

**Unmapped tasks (expected — infrastructure / polish):** T001, T002, T003, T054, T057, T058. Mapped to
SC-010 / Principle VI rather than a single FR.

---

## Constitution Alignment Issues

**None.** Constitution v1.3.0 gates remain satisfied (plan.md:122–142). The remediation added no
run-record write, no dependency, and no new check type; T059 now makes the Principle V "read-path only"
guarantee automatically verifiable rather than assumed.

---

## Metrics (post-remediation)

- **Total functional requirements**: 37 (FR-001 … FR-037)
- **Total success criteria**: 10 (SC-001 … SC-010)
- **Total tasks**: 59 (T001 … T059) — T059 added for **G1**
- **Requirements coverage**: 37/37 have ≥1 implementing task = **100%** (FR-035 now covered by T059)
- **Open findings**: **0** (was 8: 1 HIGH, 4 MEDIUM, 3 LOW — all remediated)
- **Ambiguity count**: 0 (A1, A2 resolved in Clarifications)
- **Duplication count**: 0
- **Inconsistencies**: 0 (I1, I2, D1 resolved)
- **Underspecification**: 0 (U1 resolved)
- **Coverage gaps**: 0 (C1 made explicit + manual-tested; G1 given T059)
- **Critical issues**: **0**
- **Constitution violations**: **0**

---

## Decisions recorded (unattended remediation)

Because remediation ran without a human to confirm, the four judgment findings were resolved by the
most reasonable reading of the spec + plan + repo and recorded in the spec's `## Clarifications`
(`Session 2026-09-18 (analysis remediation)`):

1. **I1** — Produced-elsewhere is scoped to the no-output-artifacts case (files-empty gate).
2. **A1** — Diff OUT rows always render expanded; non-diff cards clamp.
3. **U1** — Check vocabulary is pass / warn / fail-blocking / not-run; the note counts all four,
   `fail-blocking` counts as "failed", and `not-run` still counts (never yields "—").
4. **A2** — "Harness" surfaces both as a header stat (FR-005) and as detail in the rail's Configuration
   block (FR-006).

The mechanical/factual findings (I2 `exit` source, C1 test-surface scope, D1 name reconciliation, G1
guard task) were fixed directly in the relevant artifact.

---

## Next Actions

No CRITICAL or HIGH issues remain. The spec, plan, tasks, data-model, and contracts are mutually
consistent and implementation-ready — `/speckit-implement` can proceed.

### Extension hooks

`.specify/extensions.yml` exists but registers no `before_analyze` or `after_analyze` hooks
(`hooks: {}`), so no hook commands were emitted or executed.
