# Specification Analysis Report — 013-event-driven-triggers

**Feature**: Event-Driven Triggers — Asset Dependency Graph
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md` (with `research.md`, `data-model.md`,
`contracts/*`, `quickstart.md`, and `.specify/memory/constitution.md` as supporting context)
**Date**: 2026-09-16
**Mode**: Post-remediation re-run. The original `/speckit-analyze` pass (read-only) surfaced 9
findings; those have now been **remediated** by editing `spec.md`, `tasks.md`, and
`contracts/upstream-handoff.schema.json`. This report reflects the post-remediation state.

> Run context: executed unattended. Judgment/ambiguity findings were resolved by choosing the most
> reasonable option against the spec/plan/tasks/repo and recording the decision in the spec's
> `## Clarifications` section (Session 2026-09-16). No `hooks.before_analyze` / `hooks.after_analyze`
> entries are registered in `.specify/extensions.yml` (`hooks: {}`), so no extension hooks were
> invoked.

---

## Outstanding Findings

**None.** All 9 findings from the prior pass have been resolved. A fresh cross-artifact scan after
the edits surfaced no new inconsistencies, coverage gaps, or constitution violations.

---

## Resolved Findings (remediation log)

| ID | Category | Severity | Resolution | Artifact edited |
|----|----------|----------|------------|-----------------|
| F1 | Inconsistency / Untestable AC | HIGH | Reworded US4 narrative, Independent Test, and Acceptance #1 & #3 from "reloading/​load fails" to the implemented **skip-and-log** behavior (offending assets rejected + named in daemon log; unrelated agents still load; rejected assets get no sensor). Decision recorded in Clarifications. | `spec.md` |
| F2 | Inconsistency (task cross-ref) | MEDIUM | Fixed the T014 parenthetical from "added in US3/**T022**" to "added in US3/**T026**", matching the Dependencies section and the actual US3 task. | `tasks.md` |
| F3 | Ambiguity / Terminology drift | MEDIUM | Reworded FR-020 from "The **Automation view**" to "the agents list's schedules/sensors column (the 'Automation' surface — there is no separate Automation page) … as pills", matching plan/tasks (T018/T027). Decision recorded in Clarifications. | `spec.md` |
| F4 | Sequencing / Cross-phase coupling | MEDIUM | Added a sequencing note to the US2 checkpoint stating the handoff's `chain_depth`/`automated` are null until US5's T036 records them, so US2 is validated independently without treating null as a defect. | `tasks.md` |
| F5 | Underspecification (stale description) | LOW | Reworded T020 from "no longer hardcoded `None`" to "currently sourced from op-config `inputs` at `orchestrator/factory.py:426`; now also sourced from the handoff data", matching the actual code. | `tasks.md` |
| F6 | Inconsistency (schema vs data-model) | LOW | Added `chain_depth` and `automated` to the handoff schema's `required` list (they are always written per §3/T021 and are listed in data-model.md and every schema example), reconciling schema ↔ data-model ↔ T021. | `contracts/upstream-handoff.schema.json` |
| F7 | Ambiguity (ownership overlap) | LOW | Clarified that `factory.build_asset_automation_sensor` **owns the gate predicate** (T015) and `definitions.discover()` only **decides whether to call it** (T016), so the trigger-check is not re-implemented in both. | `tasks.md` |
| F8 | Style (front-matter) | LOW | Removed the blank line between the opening `---` and the `description:` key in the tasks front-matter. | `tasks.md` |
| F9 | Coverage note (by-construction) | LOW | Extended T010 (`test_factory`) with a focused FR-006 assertion — a blocking-check-failed upstream records an `AssetObservation` (not an `AssetMaterialization`), so `any_deps_updated()` sees no new materialization and cannot fire the downstream — locking the by-construction invariant with a static test. | `tasks.md` |

No CRITICAL issues were present. No constitution (MUST-principle) violations were detected.

### Judgment decisions recorded in `## Clarifications` (Session 2026-09-16)

- **F1** — Cycle/dangling `depends_on` ⇒ **skip-and-log** only the offending assets (not a whole-load
  abort), per the resilient loader (spec 006 FR-010) and research R5. Preserves Agent Isolation while
  keeping the observable intent (mistake named; no automation on a bad graph).
- **F3** — FR-020's "Automation view" == the **agents list's schedules/sensors column** (pills); there
  is no separate Automation page (UI surfaces are `agents/list`, `settings/page`, `runs/*`).

---

## Coverage Summary (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 `depends_on` declaration | ✅ | T004, T007, T013, T017 | schema + emit + deps + form card |
| FR-002 reject dangling ref at load, name key | ✅ | T009 (shape), T030 (load), T031 (UI guard), T028 (test) | skip-and-log (F1 resolved) |
| FR-003 reject cycles at load, name assets | ✅ | T030, T031, T028 | skip-and-log; spec wording now matches (F1 resolved) |
| FR-004 `on_upstream` trigger | ✅ | T014, T016, T010 | |
| FR-005 `on_upstream` behind `autocond_<name>`, paused | ✅ | T014, T015, T016 | |
| FR-006 blocking-check gating | ✅ | T010 (unit, F9 resolved), T045 (E2E) | now has a focused unit assertion |
| FR-007 daily→daily one-to-one mapping | ✅ | T012, T013, T014 | |
| FR-008 `on_missing` latest partition only | ✅ | T026, T024 | |
| FR-009 `on_missing` paused, no re-fire | ✅ | T026, T015, T024 | |
| FR-010 both conditions, one sensor | ✅ | T014, T026, T024 | |
| FR-011 one env var per upstream | ✅ | T021, T022, T019 | |
| FR-012 read-only JSON: paths/report/time | ✅ | T021, T019 | |
| FR-012a "no materialization" file | ✅ | T021, T019 | |
| FR-013 read-only `:ro` mount | ✅ | T022, T019 | |
| FR-014 `max_runs_per_hour` rolling window | ✅ | T035, T037, T032/T033 | |
| FR-015 `chain_depth` tag on every automated run | ✅ | T036, T033 | recorded in US5; handoff null until then (F4 noted) |
| FR-016 `max_chain_depth` | ✅ | T035, T037, T033 | |
| FR-017 manual runs bypass both | ✅ | T037, T033 | |
| FR-018 governors editable + persist | ✅ | T038, T039, T040, T034 | |
| FR-019 Depends-on card | ✅ | T017, T011 | |
| FR-020 two trigger kinds in schedules/sensors column | ✅ | T018, T027 | surface naming fixed (F3 resolved) |
| FR-021 README docs | ✅ | T042 | |

Success criteria SC-001..SC-006 map to the quickstart scenarios (§1–§7, T045) plus the per-story unit
tests (T010/T019/T024/T028/T032-T034). All six are buildable-verified; none is a post-launch KPI.

**Coverage**: 22/22 functional requirements (incl. FR-012a) have ≥1 associated task (100%). FR-006 is
now covered by both a unit task (T010) and end-to-end (T045).

---

## Constitution Alignment

No violations. The plan's Constitution Check (plan.md:152-191) is consistent with the tasks:
- **I / V. Agent Isolation & Immutable Outputs** — the handoff is mounted `:ro` (T022, FR-013); the
  downstream can read but not modify upstream output. The F1 skip-and-log resolution further honors
  Agent Isolation (one bad edge cannot take down unrelated agents).
- **II. Configuration over Code** — `depends_on`, the two triggers, and both governors are declarative
  (agent YAML + `settings.yaml`), discovered at reload (T004/T007/T016/T035/T038).
- **III. Secrets** — no secret enters the handoff, tags, or governors.
- **IV. Uniform Interface** — the handoff/trigger/governor surfaces are harness-agnostic (`_ALL`).
- **VI. Docs Track Reality** — README (T042), schema 6→7 + golden regen (T001/T043), daemon-log
  warnings for the partition fallback and cycle/dangling rejection.
- **VII. One Design System** — the Depends-on card, trigger toggles, and governors card use shared
  macros/tokens; T044 runs the design-system + docs-hygiene gates.

The deliberate cross-container duplications (asset-key regex; cron rule; governor defaults 12/5;
handoff filename/env-var transform) are each stated once per package and pinned by parity tests
(T041) — consistent with the Complexity Tracking table and prior features 004–012.

---

## Unmapped Tasks

None. Every task maps to a requirement, a success criterion, or an explicit cross-cutting concern
(T041 parity, T042 docs, T043 golden, T044 design-system gates, T045 quickstart).

---

## Ambiguity / Duplication Notes

- **Ambiguity**: FR-020's surface naming (F3) is now explicit. The governor "sane upper bound" remains
  specified only in the contracts (`max_runs_per_hour ≤ 10000`, `max_chain_depth ≤ 1000`,
  contracts/ui-settings-and-form.md §5) rather than in the spec itself — acceptable and intentional
  (the spec sets defaults; the contract pins the guard rails); no change made.
- **Duplication**: all cross-artifact duplication found is the *intentional* two-package twinning
  (regex, defaults, transform), explicitly justified in plan Complexity Tracking and pinned by T041.
  No accidental duplicate/near-duplicate requirements were found.

---

## Metrics

- **Total functional requirements**: 22 (FR-001…FR-021 including FR-012a)
- **Total success criteria**: 6 (all buildable-verifiable; 0 post-launch KPIs)
- **Total tasks**: 45 (T001–T045)
- **Requirement coverage**: 100% (22/22 have ≥1 task; FR-006 now unit-tested via T010)
- **Ambiguity count**: 0 outstanding (FR-020 surface and cycle-rejection behavior clarified)
- **Problematic duplication count**: 0 (all duplication is intentional, pinned)
- **Constitution (MUST) violations**: 0
- **Critical issues**: 0
- **Findings**: 9 original (HIGH 1, MEDIUM 3, LOW 5) — **all resolved**; 0 outstanding

---

## Next Actions

No outstanding findings block `/speckit-implement`. The spec/plan/tasks artifacts are internally
consistent and each requirement is covered by ≥1 task. Implementation may proceed.
