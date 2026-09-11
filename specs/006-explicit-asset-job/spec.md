# Feature Specification: Explicit Asset/Job Model & Automation Shell Cleanup

**Feature Branch**: `006-explicit-asset-job`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Make an agent's nature explicit — is it an asset, a job, or both — and let each carry its own trigger, defined on the agent itself. Fold triggering back out of the standalone `automation/` store into the agent definition, keep the Automation page as a cross-agent trigger editor, and fix its UI to match the design system. Also make the custom dropdown, the save-notice, and the app-shell layout reusable/consistent by default."

## Clarifications

### Session 2026-09-10

- Q: How should an agent's two optional schedules be stored in its YAML definition now that the `automation/` store is retired? → A: One dedicated block — a `triggers:` mapping (its own `# --- Triggers ---` section) with two optional keys, `asset_schedule: "<cron>"` and `job_schedule: "<cron>"`; a blank/absent key means no trigger of that type. Keeps `produces:` purely about asset identity and maps 1:1 to the form's two schedule fields and the Automation page's two rows.
- Q: How should the existing 005 `automation/migrated.yaml` triggers be carried over onto the new per-agent `triggers:` blocks? → A: A one-off migration script, run once in the same change, that reads `automation/migrated.yaml`, writes each cron onto the correct agent's `triggers:` block (asset-mode → `asset_schedule`, job-mode → `job_schedule`), then removes `automation/`. The orchestrator only ever reads the new `triggers:` block — it carries no legacy-format load path.
- Q: When a partitioned asset's on-cron auto-condition can't target the correct partition and the system falls back to a job schedule, how should it surface that the fallback was applied? → A: Both — an orchestrator load-time warning log (auditable in the headless system, per Constitution VI) and a visible marker/notice on the affected agent's schedule row in the Automation page.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare an agent as an asset, a job, or both (Priority: P1)

An operator creating or editing an agent sees two independent cards in the form: an
**Asset card** and a **Job card**, each gated by its own checkbox. Ticking "make agent
an asset" enables and requires the Produces fields (asset key and partition) and enables
an optional **asset schedule** (an auto-condition cron). Ticking "create agent job"
declares a job named `agent_<name>` and enables an optional **job schedule** cron. The
two are independent, with one rule: at least one must be ticked. Leaving both unticked
is rejected on save with a clear message. When both are ticked, the job becomes the
asset's *materializing* job (still `agent_<name>`), so manual materialization, the
auto-condition, and the job schedule all feed one unified asset-materialization history.
When only the job card is ticked, `agent_<name>` is a plain op job. In every case the
single container-launch operation is shared.

**Why this priority**: This is the heart of the feature — an agent's nature (asset, job,
or both) becomes an explicit, operator-chosen property instead of being inferred. Every
other change (per-agent triggers, the reworked Automation page) reads from this model, so
it must exist first, and on its own it already lets operators produce assets and jobs
deliberately.

**Independent Test**: In the agent form, tick only the Asset card, confirm Produces is
required, save, and confirm the orchestrator presents a tracked asset that can be
materialized. Separately tick only the Job card, save, and confirm an `agent_<name>` job
that is launchable by hand. Tick both, save, and confirm the asset has a materializing
job named `agent_<name>` whose run records an asset materialization. Untick both and
confirm the save is rejected with a naming message.

**Acceptance Scenarios**:

1. **Given** the agent form with only the Asset card ticked, **When** the operator leaves Produces empty and saves, **Then** the save is rejected because the asset key is mandatory once the Asset card is on.
2. **Given** an asset-only agent on the primary `on_cron` path, **When** the orchestrator loads it, **Then** it appears as a tracked asset that can be materialized, and no `agent_<name>` job exists for it. (Exception: an asset-only agent that hits the FR-015 partition fallback gains a materializing `agent_<name>` job solely to carry the partition-filling schedule — see FR-015.)
3. **Given** the agent form with only the Job card ticked, **When** the operator saves, **Then** an `agent_<name>` plain op job exists and is launchable by hand, and no asset exists for it.
4. **Given** the agent form with both cards ticked, **When** the operator saves and runs `agent_<name>`, **Then** the run records a materialization of the declared asset and manual Materialize, the auto-condition, and the job schedule all target the same asset.
5. **Given** the agent form with neither card ticked, **When** the operator saves, **Then** the save is rejected with a message stating the agent must be an asset, a job, or both.

---

### User Story 2 - Each agent carries its own trigger(s) (Priority: P1)

Triggering lives on the agent definition, not in a separate store. An asset-mode agent's
asset schedule drives an auto-condition (on-cron); a job-mode agent's job schedule drives
a job schedule. Both schedules are optional. The standalone `automation/` directory, the
`on_demand` keyword, and the 005 migration script are retired. Existing 005 cron entries
carry over into the new per-agent fields so that no agent that was scheduled before this
change silently stops running, and each carried-over trigger keeps its prior on/off state.

**Why this priority**: Feature 005 separated "when it runs" into an external store; this
feature deliberately folds it back onto the agent now that the asset/job distinction makes
the right destination unambiguous (asset schedule vs job schedule). Doing this without loss
is what makes the change safe to adopt, so it ships alongside the model itself at P1.

**Independent Test**: On a repo carrying 005 `automation/` cron entries, perform the
carry-over, then confirm each previously scheduled agent now expresses that cron in its own
definition (as an asset auto-condition or a job schedule as appropriate) with the same cron
value and the same on/off state, that the `automation/` directory and any `on_demand`
keyword are gone, and that the orchestrator reloads with the same set of live triggers.

**Acceptance Scenarios**:

1. **Given** a job-mode agent with a job schedule cron in its definition, **When** the orchestrator loads it, **Then** a job schedule on that cron exists for `agent_<name>`.
2. **Given** an asset-mode agent with an asset schedule cron in its definition, **When** the orchestrator loads it, **Then** the asset has an on-cron auto-condition on that cron rather than a job schedule.
3. **Given** a repo with 005 `automation/migrated.yaml` cron entries, **When** the carry-over is applied, **Then** every previously scheduled agent expresses the same cron in its own definition and retains its prior on/off state.
4. **Given** the migrated repo, **When** the codebase is inspected, **Then** no `automation/` directory and no `on_demand` keyword remain anywhere.
5. **Given** any agent with no schedule set, **When** it loads, **Then** it has no automatic trigger and remains runnable by hand (asset: manual Materialize; job: manual launch).

---

### User Story 3 - Manage triggers on the reworked Automation page (Priority: P2)

An operator opens the Automation page and, per agent, sees the asset schedule and/or the
job schedule the agent's kind entitles it to. Each schedule is editable as **on-demand vs
cron**, independently of the other. For an agent that is both asset and job, its
asset-schedule row and job-schedule row are grouped visually together so it reads as one
agent with two triggers. Saving writes the change back onto the agent definition and
reloads the orchestrator, and the operator is told the save succeeded.

**Why this priority**: The Automation page stays as the cross-agent place to see and change
triggers without hand-editing definitions (Constitution II). It depends on the model
(Story 1) and per-agent triggers (Story 2) existing, so it follows them, but it is what
makes the model usable for operators working through the UI.

**Independent Test**: Open the Automation page; confirm an asset-only agent shows just an
asset-schedule row, a job-only agent shows just a job-schedule row, and a both-kind agent
shows both rows grouped together. Toggle one row from on-demand to cron and save; confirm
the change is written to that agent's definition, the orchestrator reloads, and the trigger
is live. Confirm the other row for a both-kind agent is unaffected.

**Acceptance Scenarios**:

1. **Given** the Automation page, **When** it loads, **Then** each agent shows exactly the schedule rows its kind entitles it to (asset schedule, job schedule, or both).
2. **Given** a both-kind agent on the Automation page, **When** it renders, **Then** its asset-schedule and job-schedule rows are grouped together as one visual unit.
3. **Given** a schedule row set to on-demand, **When** the operator switches it to cron, enters a value, and saves, **Then** that trigger is written onto the agent definition and the orchestrator reloads with it live.
4. **Given** a both-kind agent, **When** the operator changes only its job schedule, **Then** its asset schedule is left unchanged.
5. **Given** a save on the Automation page, **When** it completes, **Then** the operator sees a success notice confirming the save and reload.

---

### User Story 4 - Consistent, reusable UI shell and components (Priority: P2)

Every page in the app shares one shell: the left-hand nav sidebar stays fixed in place while
the main content scrolls, and the top nav/top bar stays pinned at the top over the scrolling
content. The layout still holds at phone width and never overlaps scrollable content. Across
the app, all dropdowns render through one shared custom-dropdown component (no raw select
controls left to restyle later), and every save/reload/error notice uses one shared notice
pattern — so the Automation save notice is pixel-consistent with the agent-save notice. On
the Automation page specifically, the cron-shape warning reserves its space so it never
shifts the layout as it appears or disappears.

**Why this priority**: These are the systemic consistency fixes that stop the same UI issues
from being re-fixed page by page. They ride on the same release because the Automation rework
(Story 3) is where the shared dropdown and notice first get reused, but they are a lower
priority than delivering the model and triggers.

**Independent Test**: Scroll a long page and confirm the sidebar and top bar stay pinned; shrink
to phone width and confirm nothing overlaps and the layout still works. Grep templates and JS for
raw select controls and confirm only the shared component remains. Trigger a save on both the
agent form and the Automation page and confirm the notices are visually identical. Type into a
cron field on the Automation page and confirm the page does not shift as the warning appears.

**Acceptance Scenarios**:

1. **Given** any long page, **When** the operator scrolls the main content, **Then** the left sidebar and the top bar stay fixed in place.
2. **Given** any page at phone width, **When** it renders, **Then** the fixed sidebar and top bar do not overlap or hide scrollable content and the layout remains usable.
3. **Given** the app's templates and scripts, **When** they are inspected for dropdowns, **Then** every dropdown is the shared custom-dropdown component and no raw select control remains.
4. **Given** a successful save on the agent form and on the Automation page, **When** each notice shows, **Then** the two notices are visually identical (same shared pattern).
5. **Given** the Automation page, **When** the operator types a cron value that toggles the shape warning on and off, **Then** the page layout does not shift.

---

### Edge Cases

- **Partition mismatch on an asset auto-condition**: If an on-cron auto-condition cannot target the correct partition for a partitioned asset, the system falls back to the job-schedule path — a partition-filling schedule on the asset's materializing job — and surfaces that this fallback was taken, rather than silently dropping the trigger.
- **Turning an asset-only agent into a job-only agent (or vice versa)** on edit: the schedule that no longer applies (e.g. the asset schedule when the Asset card is unticked) must not linger as a live trigger after save.
- **Carry-over of an agent whose 005 entry was `on_demand`**: it carries over as no automatic trigger (on-demand) and remains runnable by hand.
- **A 005-scheduled agent that is now asset-mode**: its carried-over cron must land as an asset auto-condition, not a job schedule, and vice versa for job-mode.
- **A both-kind agent with only one schedule set**: the unset schedule row shows as on-demand and no trigger is created for it.
- **Editing the same trigger from both the agent form and the Automation page**: both write to the same per-agent location, so the two views stay consistent after either save.

## Requirements *(mandatory)*

### Functional Requirements

#### Agent model

- **FR-001**: The agent create/edit form MUST present an Asset card and a Job card, each gated by an independent checkbox ("make agent an asset" / "create agent job").
- **FR-002**: When the Asset card is checked, the Produces fields (asset key and partition) MUST be enabled and mandatory; when unchecked, they MUST be disabled and the agent produces no asset.
- **FR-003**: When the Asset card is checked, an asset schedule field (an auto-condition cron) MUST be enabled and MUST be optional (blank = no auto-condition).
- **FR-004**: When the Job card is checked, a job named `agent_<name>` MUST be created and a job schedule cron field MUST be enabled and optional (blank = manual/launchable; filled = scheduled).
- **FR-005**: The system MUST reject a save where neither the Asset card nor the Job card is checked, with a message stating the agent must be an asset, a job, or both.
- **FR-006**: When both cards are checked, the job MUST be the asset's materializing job (an asset-materializing job named `agent_<name>`), so that manual materialization, the auto-condition, and the job schedule all record one unified asset-materialization history.
- **FR-007**: When only the Job card is checked, `agent_<name>` MUST be a plain op job (no asset materialization).
- **FR-008**: A single container-launch operation MUST be shared across the asset-only, job-only, and both configurations (per 004's single-op rule).

#### Triggering location & carry-over

- **FR-009**: An asset schedule MUST drive an on-cron auto-condition on the asset; a job schedule MUST drive a job schedule definition. Both MUST be defined on the agent in a single dedicated `triggers:` block with two optional keys — `asset_schedule` (cron) and `job_schedule` (cron) — where a blank or absent key means no trigger of that type; not in a separate store.
- **FR-010**: The standalone `automation/` directory, the `on_demand` keyword, and the 005 migration script MUST be retired and MUST NOT remain in the codebase.
- **FR-011**: Existing 005 cron entries MUST carry over into the new per-agent `triggers:` fields via a one-off migration script (run once in this change) that reads `automation/migrated.yaml`, writes each cron onto the correct agent definition, and then removes `automation/` — such that every agent scheduled before the change is still scheduled after it, on the same cron, and no scheduled agent silently stops running. The orchestrator MUST NOT retain a load-time reader for the legacy `automation/` format.
- **FR-012**: Each carried-over trigger MUST retain its prior on/off (paused) state; a brand-new trigger MUST start paused until an operator turns it on (preserving 005's paused-by-default behavior). The on/off (paused/running) state is Dagster instigator state, toggled in the Dagster UI; the Automation page controls only whether a cron is set (on-demand ↔ cron), not the paused/running toggle.
- **FR-013**: A carried-over cron MUST land on the correct trigger for the agent's kind — an asset auto-condition for an asset-mode agent, a job schedule for a job-mode agent.
- **FR-014**: The carry-over MUST be verifiable — an operator can confirm that the set of live triggers before and after the change is identical.
- **FR-015**: When a partitioned asset's on-cron auto-condition cannot target the correct partition, the system MUST fall back to a partition-filling schedule on the asset's materializing job and MUST surface that this fallback was applied in two places: an orchestrator load-time warning log and a visible marker/notice on that agent's schedule row in the Automation page. For an otherwise asset-only agent, this fallback MAY introduce a materializing `agent_<name>` job to carry that schedule — a deliberate, fallback-only exception to the "asset-only agents have no `agent_<name>` job" rule.
- **FR-016**: The orchestrator MUST preserve 005's orchestrator routing, timezone handling, and paused-by-default behavior for the carried-over and new triggers.

#### Automation page

- **FR-017**: The Automation page MUST remain and MUST show, per agent, the schedule rows the agent's kind entitles it to: an asset-schedule row for asset-mode, a job-schedule row for job-mode, or both.
- **FR-018**: Each schedule row MUST be editable as on-demand vs cron, independently of any other row for the same agent.
- **FR-019**: For a both-kind agent, the asset-schedule and job-schedule rows MUST be grouped together visually as one unit.
- **FR-020**: Saving on the Automation page MUST write the change onto the agent definition and reload the orchestrator, and changing one schedule row MUST NOT alter the other.
- **FR-021**: The Automation page's save/reload notice MUST use the same shared notice pattern as the agent-save notice (visually identical, not a bespoke banner).
- **FR-022**: The cron-shape warning on the Automation page MUST reserve its space so that its appearance/disappearance does not shift the page layout.

#### Shared UI shell & components

- **FR-023**: The left-hand nav sidebar MUST stay fixed in place while the main content scrolls.
- **FR-024**: The top-level nav/top bar MUST stay pinned (sticky/floating) at the top over the scrolling content.
- **FR-025**: The fixed shell MUST NOT break the responsive/phone-width layout and MUST NOT overlap or hide scrollable content at any width.
- **FR-026**: A shared custom-dropdown component MUST be used by every dropdown in the app (agent form, Automation page, and future pages). Every `<select>` MUST carry the shared `ax-select` class and be enhanced through the one component (`dropdown.js`); no *un-enhanced* or bespoke dropdown may remain to be restyled later. (The component progressively enhances native `<select>` elements, so `<select>` markup is expected — what is forbidden is a dropdown outside the shared path.)
- **FR-027**: A single shared notice/banner pattern MUST be used for every save/reload/error notice app-wide.

### Key Entities *(include if feature involves data)*

- **Agent definition**: The single declarative description of an agent. Now explicitly carries its nature — asset flag (via the `produces:` block with asset key and partition), job flag — and its own triggers in a dedicated `triggers:` block: an optional `asset_schedule` (auto-condition cron) and an optional `job_schedule` (cron), each blank/absent when unset. Replaces the external trigger store as the source of truth for when an agent runs.
- **Asset schedule (auto-condition)**: An optional cron expressing when a declared asset should be materialized via an on-cron automation condition; carries an on/off state.
- **Job schedule**: An optional cron expressing when an `agent_<name>` job should run via a job schedule definition; carries an on/off state.
- **Agent job (`agent_<name>`)**: A job the operator can launch by hand or on a schedule. Either a plain op job (job-only agent) or the materializing job for the agent's asset (both-kind agent).
- **Shared UI components**: The custom-dropdown component and the notice/banner pattern, each defined once and reused across every page; and the app shell (fixed sidebar + pinned top bar) applied to every page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of scheduled agents that ran on a cron before the change still run on the same cron after it, with no scheduled agent silently stopping.
- **SC-002**: An operator can create each of the three agent kinds (asset-only, job-only, both) entirely from the form, with the both-kind agent recording asset materializations when its job runs.
- **SC-003**: Saving an agent with neither card checked is always rejected with an actionable message, never saved.
- **SC-004**: A grep of templates and scripts confirms every `<select>` carries `ax-select` and is enhanced via the shared `dropdown.js`, with no bespoke dropdown remaining — zero un-migrated dropdowns.
- **SC-005**: The Automation save notice and the agent-save notice are visually indistinguishable to a reviewer comparing them side by side.
- **SC-006**: On any page, scrolling keeps the sidebar and top bar fixed, and at phone width no fixed element overlaps or hides content.
- **SC-007**: Typing any value into a cron field never shifts surrounding page content (warning space is reserved).
- **SC-008**: After the change, the codebase contains no `automation/` directory and no `on_demand` keyword.

## Assumptions

- **Storage of per-agent schedules (resolved in clarification — see Clarifications §2026-09-10)**: The asset schedule and job schedule are stored on the agent's own YAML definition in a single dedicated `triggers:` block (its own `# --- Triggers ---` section) with two optional keys, `asset_schedule` (cron) and `job_schedule` (cron); a blank or absent key means no trigger of that type. The `produces:` block stays purely about asset identity.
- **Shape of the 005→new carry-over (resolved in clarification — see Clarifications §2026-09-10)**: A one-off migration script, run once as part of this change, reads 005's `automation/migrated.yaml`, writes the equivalent trigger onto each agent's `triggers:` block (asset-mode cron → `asset_schedule`, job-mode cron → `job_schedule`), and then removes `automation/`. It is not a runtime auto-migration: the orchestrator only ever reads the new `triggers:` block and keeps no legacy-format load path.
- This feature builds on a converged feature 005 and retains its orchestrator routing, timezone handling, and paused-by-default behavior.
- It builds on feature 004's rule that all agent runs share a single container-launch operation, whether the agent is an asset, a job, or both.
- Existing shared building blocks (a dropdown script, a shell script, an automation script under `ui/static/`) are the starting point for the shared-component extraction; "shared component" means one implementation reused everywhere, not a new framework.
- Out of scope (per the brief): multiple crons per trigger (no lists), event-driven triggers/sensors beyond cron + auto-condition (deferred to 008), and a non-materializing op job for an asset agent (the both-on job always materializes the asset).
- The management UI remains the primary way operators configure agents; hand-editing YAML remains possible and must stay consistent with what the UI writes.
