# Specification Analysis Report — 013-event-driven-triggers

**Feature**: Event-Driven Triggers — Asset Dependency Graph
**Artifacts analyzed**: `spec.md`, `plan.md`, `tasks.md` (with `research.md`, `data-model.md`,
`contracts/*`, `quickstart.md`, and `.specify/memory/constitution.md` as supporting context)
**Date**: 2026-09-16
**Mode**: Read-only cross-artifact consistency & quality check (`/speckit-analyze`). No spec/plan/tasks
files were modified.

> Run context: executed unattended. Where the skill would normally pause for a clarifying question,
> the most reasonable option was chosen against the spec/plan/tasks/repo and analysis continued. No
> `hooks.before_analyze` / `hooks.after_analyze` entries are registered in `.specify/extensions.yml`
> (`hooks: {}`), so no extension hooks were invoked.

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency / Untestable AC | HIGH | spec.md:114-125,129-130 (US4 + Acceptance #1) vs plan.md:35-41 & research.md:117-147 & tasks.md:167 (T030) | US4 narrative says "reloading **fails**" and Acceptance US4 #1 says "the **load fails** and the error names the assets" — but the plan/research/tasks deliberately implement **skip-and-log** (offending assets rejected, every unrelated agent still loads; the global load does **not** fail). A tester following the spec literally would mark US4 #1 failed. | Reword US4 / Acceptance #1 to the reconciled behavior ("the offending assets are **rejected** at load, named in the daemon log; unrelated agents still load") so spec, plan (R5), and T030/quickstart §4 agree. The divergence is intentional and already documented in research R5 — only the spec wording lags. |
| F2 | Inconsistency (task cross-ref) | MEDIUM | tasks.md:85 (T014) | T014 says "*The `on_missing` branch is added in US3/**T022**.*" but T022 is a **US2** handoff-wiring task; the `on_missing` branch is actually added by **T026** (US3). The Dependencies section (tasks.md:238-239) correctly cites T026, contradicting the inline note. | Change the T014 parenthetical to reference **T026** (US3). |
| F3 | Ambiguity / Terminology drift | MEDIUM | spec.md:267-268 (FR-020) vs plan.md:269, tasks.md:89,143, contracts/ui-settings-and-form.md §2 | FR-020 requires "The **Automation view** MUST present the two new asset trigger kinds," but there is no Automation view in the UI (routes/templates are `agents/list`, `settings/page`, `runs/*`). Plan/tasks map FR-020 to the **agents-list schedules/sensors column** pills. | Reword FR-020 to name the actual surface (the agents list's schedules/sensors column) or state that "Automation view" == that column, to avoid an operator/tester expecting a distinct page. |
| F4 | Sequencing / Cross-phase coupling | MEDIUM | tasks.md:115 (T021, US2), :195 (T036, US5), :117 (T023) | The US2 handoff builder (T021) reads and writes `chain_depth`/`automated` from materialization metadata, but those values are only **recorded** by T036 (US5), two stories later; T036's `chain_depth` derivation in turn reuses T021's read. Until US5 lands, every handoff file's `chain_depth`/`automated` are null. The coupling is real but is not called out in the US2 checkpoint. | Add a note to US2 (or the Dependencies section) that `chain_depth`/`automated` in the handoff are null until US5's T036 records them — so US2 can be validated independently without treating null as a defect. |
| F5 | Underspecification (stale description) | LOW | tasks.md:111 (T020), :117 (T023), research.md R6 (line 182-186) | T020/R6 describe `asset.upstream_inputs` as "**no longer hardcoded `None`**", but in the repo `orchestrator/factory.py:426` already populates it from `context.op_config["inputs"]` (`… .get("inputs") or None`), not a hardcoded `None`. The intent (populate from handoff) is clear; the premise is inaccurate. | Reword to "currently sourced from op-config `inputs`; now also sourced from the handoff data" to match the actual code. |
| F6 | Inconsistency (schema vs data-model) | LOW | contracts/upstream-handoff.schema.json:7 vs data-model.md:63-73 | The handoff JSON schema's `required` list omits `chain_depth` and `automated`, yet data-model.md lists them among the record's fields (present, null when unmaterialized). With `additionalProperties:false` they're allowed-but-optional. | Either add `chain_depth`/`automated` to `required` (they're always written per §3/T021) or note in data-model.md that they're optional additive fields. |
| F7 | Ambiguity (ownership overlap) | LOW | tasks.md:86 (T015) & :87 (T016) | T015 makes the sensor be "created whenever ANY asset-kind trigger is set — update the sensor-creation **gate** in factory and its call site," while T016 (definitions) also "build[s] the sensor for any asset with any asset-kind trigger." The split of the gate between `factory.py` and `definitions.discover()` is slightly ambiguous. | Clarify that `factory.build_asset_automation_sensor` owns the gate predicate and `definitions.discover()` only decides whether to call it, so the two tasks don't both re-implement the trigger check. |
| F8 | Style (front-matter) | LOW | tasks.md:1-5 | The YAML front-matter has a blank line between the opening `---` and the `description:` key. Parses, but is inconsistent with the other artifacts' front-matter and some strict parsers. | Remove the blank line so the block is `---\ndescription: …\n---`. |
| F9 | Coverage note (by-construction) | LOW | spec.md:213-214 (FR-006), :299 (SC-003); tasks.md T010/T045 | Blocking-check gating (FR-006 / SC-003) has **no unit-test task** — it is "by construction" (a failed blocking check yields an observation, not a materialization) and is only exercised end-to-end by the quickstart (T045). Acceptable, but it is the one P1 behavior with no static test. | Optionally add a focused `test_factory`/`test_definitions` assertion that a blocking-failed upstream records an observation (so `any_deps_updated` cannot fire), to lock the invariant the whole feature relies on. |

No CRITICAL issues. No constitution (MUST-principle) violations detected.

---

## Coverage Summary (Functional Requirements → Tasks)

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 `depends_on` declaration | ✅ | T004, T007, T013, T017 | schema + emit + deps + form card |
| FR-002 reject dangling ref at load, name key | ✅ | T009 (shape), T030 (load), T031 (UI guard), T028 (test) | |
| FR-003 reject cycles at load, name assets | ✅ | T030, T031, T028 | See F1 (spec wording "load fails" vs skip-and-log) |
| FR-004 `on_upstream` trigger | ✅ | T014, T016, T010 | |
| FR-005 `on_upstream` behind `autocond_<name>`, paused | ✅ | T014, T015, T016 | |
| FR-006 blocking-check gating | ⚠️ by construction | T045 (E2E); no unit task | See F9 |
| FR-007 daily→daily one-to-one mapping | ✅ | T012, T013, T014 | |
| FR-008 `on_missing` latest partition only | ✅ | T026, T024 | |
| FR-009 `on_missing` paused, no re-fire | ✅ | T026, T015, T024 | |
| FR-010 both conditions, one sensor | ✅ | T014, T026, T024 | |
| FR-011 one env var per upstream | ✅ | T021, T022, T019 | |
| FR-012 read-only JSON: paths/report/time | ✅ | T021, T019 | |
| FR-012a "no materialization" file | ✅ | T021, T019 | |
| FR-013 read-only `:ro` mount | ✅ | T022, T019 | |
| FR-014 `max_runs_per_hour` rolling window | ✅ | T035, T037, T032/T033 | |
| FR-015 `chain_depth` tag on every automated run | ✅ | T036, T033 | See F4 (recorded only in US5) |
| FR-016 `max_chain_depth` | ✅ | T035, T037, T033 | |
| FR-017 manual runs bypass both | ✅ | T037, T033 | |
| FR-018 governors editable + persist | ✅ | T038, T039, T040, T034 | |
| FR-019 Depends-on card | ✅ | T017, T011 | |
| FR-020 two trigger kinds in Automation view | ✅ | T018, T027 | See F3 (surface naming) |
| FR-021 README docs | ✅ | T042 | |

Success criteria SC-001..SC-006 map to the quickstart scenarios (§1–§7, T045) plus the per-story unit
tests (T010/T019/T024/T028/T032-T034). All six are buildable-verified; none is a post-launch KPI.

**Coverage**: 22/22 functional requirements (incl. FR-012a) have ≥1 associated task (100%). FR-006 is
covered only end-to-end (by-construction, no unit task — F9).

---

## Constitution Alignment

No violations. The plan's Constitution Check (plan.md:152-191) is consistent with the tasks:
- **I / V. Agent Isolation & Immutable Outputs** — the handoff is mounted `:ro` (T022, FR-013); the
  downstream can read but not modify upstream output. Reinforced, not weakened.
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

- **Ambiguity**: FR-020 "Automation view" (F3); the governor "sane upper bound" is unspecified in the
  spec and only pinned in the contracts (`max_runs_per_hour ≤ 10000`, `max_chain_depth ≤ 1000`,
  contracts/ui-settings-and-form.md §5) — acceptable, but the spec itself gives no bound.
- **Duplication**: all cross-artifact duplication found is the *intentional* two-package twinning
  (regex, defaults, transform), explicitly justified in plan Complexity Tracking and pinned by T041.
  No accidental duplicate/near-duplicate requirements were found.

---

## Metrics

- **Total functional requirements**: 22 (FR-001…FR-021 including FR-012a)
- **Total success criteria**: 6 (all buildable-verifiable; 0 post-launch KPIs)
- **Total tasks**: 45 (T001–T045)
- **Requirement coverage**: 100% (22/22 have ≥1 task; FR-006 unit-untested by construction)
- **Ambiguity count**: 2 (Automation-view surface; unspecified governor upper bound)
- **Problematic duplication count**: 0 (all duplication is intentional, pinned)
- **Constitution (MUST) violations**: 0
- **Critical issues**: 0
- **Findings by severity**: HIGH 1, MEDIUM 3, LOW 5

---

## Next Actions

No CRITICAL issues block `/speckit-implement`. Recommended before/alongside implementation:

1. **F1 (HIGH)** — align the US4 narrative + Acceptance #1 wording with the implemented skip-and-log
   behavior (edit `spec.md` — a `/speckit-specify` refinement, or a manual acceptance-criterion
   reword). This is the one finding that would make a spec-literal test fail.
2. **F2 / F3 (MEDIUM)** — fix the T014→T026 task cross-reference and the FR-020 "Automation view"
   naming (small edits to `tasks.md` / `spec.md`).
3. **F4 (MEDIUM)** — add a US2-checkpoint note that handoff `chain_depth`/`automated` are null until
   US5's T036, so US2 stays independently verifiable.
4. **F5–F9 (LOW)** — address opportunistically: correct the `upstream_inputs` description (F5), the
   handoff-schema `required` set (F6), the sensor-gate ownership wording (F7), the tasks front-matter
   blank line (F8), and optionally add a blocking-check-gating unit test (F9).

Because only LOW/MEDIUM issues (plus one HIGH wording alignment) remain, implementation may proceed;
resolving F1–F3 first will keep the acceptance criteria and task cross-references honest.

---

## Remediation Offer

Concrete remediation edits for the top findings (F1: reword US4/AC; F2: fix T014 ref; F3: reword
FR-020; F4: add US2 sequencing note) can be drafted on request. Per the analyze skill's read-only
constraint, none were applied automatically — `spec.md`, `plan.md`, and `tasks.md` are unchanged.
