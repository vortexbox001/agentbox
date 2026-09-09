# Feature Specification: Agent Management UI

**Feature Branch**: `web-ui`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "Replace the existing minimal FastAPI control panel with a full agentbox web UI — app shell with left-hand navigation (LHN), top-level navigation (TLN), and main window pane (MWP). Agents page for viewing, creating, and editing agent YAML configurations. Design system component library accessible at /design-system. Prompt library integration, model/harness validation, and all meaningful agent parameters exposed."

## Clarifications

### Session 2026-09-08

- Q: After a user saves an agent, should the UI tell Dagster to reload its workspace so the change takes effect, and if so, automatically or on request? → A: The save action carries a "Reload Dagster after saving" option that is checked by default; when checked, a successful save triggers the reload and shows its status (including a clear error if the reload fails); when unchecked, the file is saved without reloading.
- Q: When the UI saves an existing agent, what happens to the hand-written explanatory comments in the current YAML files? → A: The file is regenerated on every save with the UI's own standard field explanations written as comments; hand-written comments are replaced.
- Q: Should users be able to delete an agent from the UI in this release? → A: Yes; delete removes the agent's YAML file after a confirmation step, leaving the workspace and output directories untouched.
- Q: How should the UI treat environment-variable values that look like actual secrets rather than `${NAME}` passthrough references? → A: Accept them, but show an inline warning on the field as soon as the input looks secret-like, and on save require an explicit confirmation that the value is not a secret before the file is written. Additionally, wherever a parameter has a known set of valid values, the form offers those as choices rather than free-text input.
- Q: Should the agent detail page show the generated YAML alongside the form, and can users edit it directly there? → A: A read-only YAML preview is available on demand (the user opens it; it is not shown by default) and reflects the form's current values; the form is the only way to edit.

## User Scenarios & Testing

### User Story 1 - View Existing Agents (Priority: P1)

A user opens the agentbox UI and sees a list of all agents currently defined as YAML files. Each agent card shows the agent's name, harness type, model, schedule status, and enabled/disabled state. The user can quickly scan which agents exist and their current configuration at a glance.

**Why this priority**: This is the foundational view. Without the ability to see existing agents, no other interaction is meaningful. It also validates that the UI can read and parse the agent YAML files correctly.

**Independent Test**: Can be fully tested by navigating to the Agents page and verifying that all agent YAML files in the agents/ directory appear as entries with correct metadata displayed.

**Acceptance Scenarios**:

1. **Given** the agents/ directory contains 3 agent YAML files, **When** the user navigates to the Agents page, **Then** 3 agent entries appear with name, harness, model, and schedule visible for each
2. **Given** an agent has `enabled: false` in its YAML, **When** the user views the agent list, **Then** the agent row is rendered at reduced opacity and carries a "disabled" badge
3. **Given** the agents/ directory contains template files (prefixed with `_`), **When** the user views the agent list, **Then** template files do not appear in the list (they are offered on the New Agent page as "Start from template")

---

### User Story 2 - Create a New Agent (Priority: P1)

A user wants to create a new agent. They click a "New Agent" action from the Agents page and are presented with a form. The form exposes every meaningful agent parameter organized by section (identity, model, prompt, workspace, scheduling, container resources, execution, environment). Each parameter has an inline explanation of what it does. The user fills in the form, and the system writes a valid YAML file to the agents/ directory.

**Why this priority**: Creating agents through the UI is the core value proposition — it replaces manual YAML editing with a guided, validated experience.

**Independent Test**: Can be fully tested by completing the new-agent form, submitting, and verifying a syntactically correct YAML file appears in the agents/ directory with the values entered.

**Acceptance Scenarios**:

1. **Given** the user is on the Agents page, **When** they click "New Agent", **Then** a creation form appears with all configurable agent parameters
2. **Given** the user is filling out the agent form, **When** they select a harness type (claude-code, pi, api, or codex), **Then** only the parameters relevant to that harness are shown, and model options are filtered to compatible choices
3. **Given** the user has entered a name "my-new-agent" and filled required fields, **When** they save, **Then** a file named `my-new-agent.yaml` is written to the agents/ directory with valid YAML syntax
4. **Given** the user enters an agent name that already exists, **When** they attempt to save, **Then** the system warns that an agent with that name already exists and prevents overwriting
5. **Given** the "Reload Dagster after saving" option is checked (its default), **When** the user saves successfully, **Then** the system triggers a Dagster workspace reload and shows whether it succeeded
6. **Given** the user unchecks "Reload Dagster after saving", **When** they save, **Then** the file is written and no reload is triggered
7. **Given** the user types a value that looks like a secret into an environment-variable field, **When** the input is entered, **Then** an inline warning appears on that field suggesting `${NAME}` passthrough or an env file
8. **Given** a flagged secret-like value is still present, **When** the user saves, **Then** the system asks them to confirm the value is not a secret, and writes the file only if they confirm
9. **Given** a parameter with a known set of valid values (e.g., permission_mode), **When** the user edits it, **Then** they choose from those values rather than typing free text

---

### User Story 3 - Edit an Existing Agent (Priority: P1)

A user clicks on an agent name in the list to open its detail/edit view. The form is pre-populated with the agent's current YAML values. The user modifies parameters and saves, which updates the YAML file on disk.

**Why this priority**: Editing is as essential as creating — agents evolve over time. Without edit capability, users must still fall back to manual YAML editing.

**Independent Test**: Can be fully tested by opening an existing agent, changing a parameter (e.g., the model), saving, and verifying the YAML file reflects the change, retains all other values, and carries the UI's standard field explanations as comments.

**Acceptance Scenarios**:

1. **Given** an agent YAML file exists with specific values, **When** the user opens the agent detail page, **Then** the form is pre-populated with all current values from the YAML, with the name shown read-only
2. **Given** the user changes the model from "sonnet" to "opus", **When** they save, **Then** the YAML file is updated with the new model value and all other values are retained
3. **Given** an agent file with hand-written comments, **When** the user saves it through the UI, **Then** the file is regenerated with the UI's standard field explanations as comments in place of the hand-written ones
4. **Given** the user has unsaved changes, **When** they attempt to navigate away, **Then** they are warned about unsaved changes
5. **Given** the user is on the create or edit form, **When** they open the YAML preview, **Then** a read-only view shows the YAML that would be written from the form's current values, and closing it returns them to the form unchanged

---

### User Story 4 - Select or Create Prompts (Priority: P2)

When configuring an agent's prompt, the user can either select from existing prompt files in the prompts/ directory or create a new prompt inline. New prompts are saved as markdown files in the prompts/ directory and automatically become available for selection by other agents.

**Why this priority**: Prompt management is a key part of agent configuration, but agents can function with a manually created prompt file. This story adds convenience rather than core capability.

**Independent Test**: Can be fully tested by creating a new agent, choosing to create a new prompt, entering prompt content, saving, and verifying the prompt file exists in prompts/ and the agent YAML references it.

**Acceptance Scenarios**:

1. **Given** the prompts/ directory contains 2 prompt files, **When** the user opens the prompt selector in the agent form, **Then** both existing prompts appear as selectable options
2. **Given** the user chooses to create a new prompt, **When** they enter content and a filename, **Then** a new .md file is saved to the prompts/ directory
3. **Given** the user creates a new prompt during agent creation, **When** the agent is saved, **Then** the agent's `prompt_file` field references the newly created prompt

---

### User Story 5 - Model and Harness Validation (Priority: P2)

The system prevents users from selecting model/harness combinations that are incompatible. When a user selects a harness, the available models are filtered. When a user selects a model, incompatible harnesses are indicated. The UI explains why certain combinations are not available.

**Why this priority**: Invalid configurations lead to runtime failures that are hard to diagnose. Validation at input time saves significant debugging effort.

**Independent Test**: Can be fully tested by selecting each harness type and verifying that only compatible models appear in the model selector, and vice versa.

**Acceptance Scenarios**:

1. **Given** the user selects the "claude-code" harness, **When** they open the model selector, **Then** only Claude model IDs and aliases are available (sonnet, opus, haiku, fable, and full model IDs)
2. **Given** the user selects the "pi" harness, **When** they open the model selector, **Then** only LiteLLM aliases (cheap, smart, opus, kimi, kimi-k3) and pi-compatible model strings are available
3. **Given** the user selects the "api" harness, **When** they open the model selector, **Then** only LiteLLM model names (cheap, smart, opus, kimi, kimi-k3) are available
4. **Given** the user selects the "codex" harness, **When** they open the model selector, **Then** only Codex-compatible model IDs are available (or left blank for the default)
5. **Given** an incompatible combination is attempted, **When** the system blocks it, **Then** a clear explanation is shown for why the combination does not work

---

### User Story 6 - Delete an Agent (Priority: P2)

From an agent's detail page, the user chooses to delete the agent. After confirming, the agent's YAML file is removed from the agents/ directory and the user is returned to the agent list. The agent's workspace and output directories are not touched, so past run outputs remain available.

**Why this priority**: Deleting completes the agent lifecycle the UI owns, but it is less frequent than viewing, creating, or editing, and users can fall back to removing the file by hand.

**Independent Test**: Can be fully tested by deleting an agent from its detail page, confirming, and verifying the YAML file is gone from agents/ while its workspace and output directories still exist.

**Acceptance Scenarios**:

1. **Given** the user is on an agent's detail page, **When** they choose delete, **Then** a confirmation step names the agent and explains that only its definition file will be removed
2. **Given** the user confirms the deletion, **When** it completes, **Then** the agent's YAML file no longer exists, the agent disappears from the list, and its workspace and output directories are unchanged
3. **Given** the user cancels the confirmation, **When** they return to the detail page, **Then** the agent and its file are unchanged
4. **Given** the "Reload Dagster" option is checked (its default), **When** a deletion completes, **Then** a Dagster workspace reload is triggered and its outcome shown

---

### User Story 7 - Access Design System Component Library (Priority: P3)

A developer navigating to /design-system sees the component library specimen page. This page is not linked from the main navigation and serves as a reference for developers extending the UI.

**Why this priority**: This supports future development velocity but has no end-user impact. It is useful from day one for anyone building out the UI.

**Independent Test**: Can be fully tested by navigating to /design-system in the browser and verifying the component library renders correctly without any link from the main navigation.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** a user navigates to /design-system, **Then** the component library page renders showing all design system components
2. **Given** the main navigation is visible, **When** the user inspects all navigation items, **Then** no link to /design-system exists

---

### Edge Cases

- What happens when the agents/ directory is empty? The Agents page shows an empty state with a prompt to create the first agent.
- What happens when an agent YAML file has invalid syntax? The list row shows an "error" badge and the parse message inline (in place of the harness/model/schedule metadata, which cannot be read), and the row still links to the detail page, where the full raw file contents are shown alongside the error banner so the operator can re-enter the values and save.
- What happens when the user enters a cron expression in an invalid format? The form validates the cron expression and shows an error with the expected format.
- What happens when the prompts/ directory does not exist? The system creates it when the user saves a new prompt.
- What happens when two users edit the same agent simultaneously? The last save wins (single-user assumption for v1); the system reads the current file state when the edit form is opened.
- What happens when an agent name contains invalid characters? The form validates that the name is kebab-case (lowercase letters, numbers, and hyphens only).
- What happens when the Dagster reload fails after a successful save or delete? The file change stands; the UI shows a clear error stating the change was made but Dagster was not reloaded, and offers to retry the reload.
- What happens when a user deletes an agent whose file has already been removed outside the UI? The UI reports that the agent no longer exists and returns to the list.
- What happens when a file is valid YAML but not a mapping, or lacks `name` or `harness`? It is listed with an error badge and the reason; opening it behaves like the invalid-syntax case (form defaults, error banner, raw contents shown); it can be deleted.
- What happens when a file carries a schema-version marker newer than this UI understands? It is listed with an error badge ("written by a newer agentbox"), cannot be opened for editing, and can be deleted.
- What happens when a new prompt is created but the agent save then fails? The prompt file remains and is listed; the error message states that the prompt was created and only the agent failed, so the user can retry the agent save selecting that prompt.
- What happens when the selected prompt file has been removed from disk between loading the form and saving? The save fails with a validation error on `prompt_file` and the selector is refreshed.
- What happens when the agents/ or prompts/ directory cannot be read or written (permissions, read-only mount)? A distinct error names the directory and the operation so the operator can fix the mount, rather than a generic failure.
- What happens when the file changed on disk after the form was loaded? The save proceeds (last write wins, per the single-user assumption); no conflict detection is performed in this release.

## Requirements

### Functional Requirements

- **FR-001**: System MUST display a list of all agent YAML files found in the agents/ directory. Template files (prefixed with `_`) MUST be hidden from this list and offered instead as "Start from template" choices on the New Agent page (see FR-023)
- **FR-002**: System MUST provide a form for creating new agents that includes every configurable parameter organized in this fixed section order: Identity (name, enabled, harness), Model (model, effort, fallback_model, max_tokens), Prompt & output (prompt_file, append_system_prompt, output_dir), Workspace (workspace, wipe_workspace), Execution (timeout_seconds, max_turns, permission_mode, allowed_tools, disallowed_tools, mcp_config), Scheduling (schedule), Container resources (network, memory, cpus), and Environment (env_file, env). The same order is used for the written YAML file. The harness selector MUST present each harness with its label, a one-line description, and the container image it runs (e.g., `agentbox/agent-claude`), so the choice is made in terms of the runtime image. Parameter availability varies by harness (see FR-007)
- **FR-003**: System MUST display an inline explanation for each form field describing what the parameter does, its valid values, and its default. These explanations live in exactly one place — `ui/schema.py` (surfaced by `GET /api/schema`) — and the same text is emitted as the YAML comment for that field (FR-004) and is the wording the README reference must match, so the three never drift (Constitution VI). Every field applicable to a harness MUST carry such an explanation, and for a field with a bounded value set or a numeric range the explanation MUST state those values/bounds and the default (e.g., `timeout_seconds`: "1 to 86400; default 900"). This is checkable against the schema module
- **FR-003a**: Wherever a parameter has a known, finite set of valid values (e.g., harness, enabled, effort, permission_mode, network, allowed tool names), the form MUST present those values as selectable choices rather than free-text input; free text is used only where valid values are open-ended (e.g., name, paths, cron expression, environment values). The model field follows the per-harness rules in FR-006
- **FR-004**: System MUST save agent configurations as syntactically valid YAML files to the agents/ directory using the agent name as the filename; every save regenerates the whole file, writing the UI's standard field explanation as a comment alongside each field (the same explanations shown in the form per FR-003) and replacing any hand-written comments. The regenerated file MUST carry a schema-version marker in its header comments, and any key present in the loaded file that the UI does not recognise MUST be preserved verbatim in a clearly labelled trailing section rather than dropped
- **FR-004a**: Every file write (agent or prompt) MUST be atomic — written to a temporary file in the same directory and renamed into place — so an interrupted save never leaves a truncated or empty file; files MUST be written as UTF-8 with LF line endings and a single trailing newline regardless of the host operating system
- **FR-005**: System MUST pre-populate the edit form with all current values when opening an existing agent
- **FR-006**: System MUST filter available models based on the selected harness type: claude-code accepts the aliases `sonnet`, `opus`, `haiku`, `fable` (as choices), a full Claude model id matching `claude-<id>` with an optional `[1m]` suffix (free text), or blank for the CLI default; pi accepts the LiteLLM aliases defined in litellm/config.yaml (as choices) or a `provider/model` string containing `/` (free text); api accepts only the LiteLLM aliases (choices, no free text); codex accepts any non-empty model id (free text with suggestions) or blank for the codex default. The model field is rendered as one control per harness, never a separate alias-picker plus free-text box: `api` is a plain select of the aliases; `claude-code`, `pi`, and `codex` are a single free-text input backed by a suggestions list (the harness's aliases plus any curated model suggestions) so the operator can pick a suggestion or type into the same field, and the field's literal text is exactly what is validated and written — there is no ambiguous "both populated" state. The `codex` suggestions are a curated static list maintained in the schema module so they stay current with the model line-up
- **FR-007**: System MUST show only harness-relevant parameters when a harness is selected (e.g., max_turns and permission_mode are specific to claude-code; max_tokens is specific to api; codex has no max_turns or system-prompt flag)
- **FR-007a**: When the user changes harness on the form, values in fields shared by both harnesses MUST be retained; values in fields the new harness does not use MUST be excluded from what is saved but kept in the form's memory for the duration of the page so switching back restores them; `model` and `effort` MUST be reset to unset when their current value is not valid for the new harness; and `network` MUST be set to the new harness's recommended default unless the user has explicitly changed it on this page
- **FR-008**: System MUST allow users to select an existing prompt file from the prompts/ directory or create a new prompt inline
- **FR-009**: System MUST save new inline prompts as .md files in the prompts/ directory
- **FR-010**: System MUST validate agent names as unique kebab-case identifiers before saving. The filename (without extension) is the agent's identity: `name` is read-only on the edit form and renaming is done by delete and recreate. If a loaded file's `name` differs from its filename, the list and form MUST show a mismatch warning, and saving MUST write `name` equal to the filename
- **FR-010a**: Every user-supplied filename or identity — an agent stem in a route (`/agents/{name}`, `GET/PUT/DELETE /api/agents/{name}`), the `?from=` template stem, `prompt_file`, and a new prompt's filename — MUST be rejected before it touches the filesystem if it contains a path separator (`/`, `\`) or `..`, so no request can read or write outside `agents/` or `prompts/`. This check MUST be applied consistently at every endpoint, not only when reading a single prompt. A rejected agent stem behaves as "no such agent" (404); a rejected prompt filename is a validation error (400)
- **FR-011**: System MUST validate cron expressions in the schedule field before saving. Accepted syntax is standard five-field cron (minute hour day-of-month month day-of-week, with ranges, lists, and steps); named macros such as `@daily` and six-field seconds syntax are rejected with a message stating the expected format. An empty value means manual-only
- **FR-012**: System MUST present the app shell with a left-hand navigation sidebar (LHN), a top bar (TLN), and a main content pane (MWP). In this release the top bar carries the current page title, a breadcrumb (e.g., "Agents / my-agent"), and nothing else; top-level navigation items are reserved for later releases. The shell's exact dimensions (sidebar width, top-bar height, content padding, breadcrumb slot) are not fixed by this spec; they are taken from the design system's `--ax-*` tokens in the shipped token file, which is the single authoritative source for them (the derived values reproduced from the prototype are recorded in research R13)
- **FR-013**: The left-hand navigation MUST include an "Agents" page as its initial and only entry
- **FR-014**: System MUST serve the design system component library at the /design-system route without including it in the main navigation
- **FR-015**: System MUST apply the agentbox design system consistently across all UI surfaces. "Consistently" means: every colour, font, size, spacing, and radius in the application's own stylesheet and templates is expressed through the design system's `--ax-*` tokens (loaded from the shipped token file); no hard-coded colour or font values appear outside that token file. This is checkable by searching the application's CSS and templates for literal colour/font values, and is enforced by an automated test (`test_no_literal_colours_or_fonts`) that scans `ui/static/app.css` and every template for literal hex, `rgb()`/`rgba()`, and `font-family` values and fails on any match
- **FR-016**: System MUST warn users when they attempt to navigate away from a form with unsaved changes. A form is "unsaved" when its current values differ from the values it was loaded with (a change that is then reverted does not count). In-app navigation (sidebar, breadcrumb, list links, cancel) MUST show the application's own confirmation; browser navigation (back/forward, refresh, tab close) MUST trigger the browser's native leave-page prompt
- **FR-017**: (Consequence of FR-010) Creating a new agent whose name matches an existing file MUST be refused with a message naming the existing file; no file is overwritten
- **FR-018**: The agent save and delete actions MUST offer a "Reload Dagster" option, checked by default; when checked, a successful save or delete MUST trigger a Dagster workspace reload and report its outcome; when unchecked, the action MUST complete without triggering a reload. The option resets to checked on every page load and is not remembered between pages or sessions. A reload that receives no response within 10 seconds MUST be reported as "Dagster unreachable"; a reload that Dagster answers with an error MUST report Dagster's message. The outcome MUST be shown as a status message that stays visible until dismissed or until the next save/reload, and a failed outcome MUST include a "Retry reload" action that re-runs only the reload. When the action itself navigates away (a delete returns to the Agents list), the outcome and its retry action MUST be shown on the destination page
- **FR-019**: Users MUST be able to delete an agent from its detail page; deletion MUST require an explicit confirmation, MUST remove only the agent's YAML file, and MUST NOT modify or remove the agent's workspace or output directories. Delete MUST work regardless of the file's content or condition — a file with a parse error, one written by a newer schema version (which cannot be opened for editing), or one whose stored `name` differs from its filename are all deletable, since delete acts on the file by its filename and never reads or migrates it. "Never touches the workspace or outputs" is a testable invariant: deleting an agent whose `workspace`/`output_dir` point at existing directories leaves those directories and their contents unchanged
- **FR-020**: When an environment-variable name or value looks secret-like and is not a `${NAME}` passthrough reference, the form MUST show an inline warning on that field immediately, pointing the user to `${NAME}` passthrough or an env file; on save, the system MUST require the user to explicitly confirm that each flagged value is not a secret before the file is written, and MUST abort the save if the confirmation is declined. "Secret-like" is defined as: the name matches TOKEN, SECRET, PASSWORD, PASSWD, API_KEY/APIKEY, PRIVATE_KEY, CREDENTIAL, or AUTH (case-insensitive substring); or the value starts with a known credential prefix (`sk-`, `sk-ant-`, `ghp_`, `github_pat_`, `gho_`, `xoxa-`/`xoxb-`/`xoxp-`, `AKIA`, `AIza`, `-----BEGIN`); or the value is 20 or more characters with no whitespace and contains at least three of {lowercase, uppercase, digit, symbol}. Confirmation is per save and per flagged key, is asked again on every subsequent save while the value still matches, and is not recorded anywhere. Reference cases: `GITHUB_USER: leeclemmer` is not flagged; `MY_TOKEN: abc123` is flagged (name); `REPO: sk-live-a1B2c3D4e5F6g7H8i9J0` is flagged (value). Only the `env` map is checked; `append_system_prompt`, prompt content, and path fields are not, because they are not designed to carry credentials and a false positive there would block ordinary text
- **FR-021**: The create and edit forms MUST offer an on-demand, read-only preview of the YAML that would be written from the form's current values; the preview MUST NOT be shown by default and MUST NOT be editable — the form is the only editing surface. If the form is not currently valid, the preview MUST show the validation errors instead of YAML
- **FR-022**: The agent list and detail page MUST link each agent to its Dagster job page (`agent_<name>` with hyphens as underscores) so run history is one click away even though it is not shown in this UI, and the sidebar MUST show whether Dagster is reachable, checked once on each page load (no polling)
- **FR-023**: The New Agent page MUST offer a "Start from template" choice listing the `_`-prefixed template files; choosing one pre-fills every field from the template with `name` cleared and `enabled` set to false, and marks the form as unsaved
- **FR-024**: The form MUST show a non-blocking warning (not an error) when the harness and network are a known mismatch: `claude-code` or `codex` with a network other than `bridge` (they need direct internet to reach their provider), or `api` with `bridge` (it only needs LiteLLM). The user may still save
- **FR-025**: The UI MUST give explicit progress and outcome feedback for its asynchronous actions. The agent list and the form's fields MUST show a loading placeholder in place of the not-yet-ready content until their data is available. The outcome of every save, delete, and Dagster reload MUST be surfaced to the operator: a recoverable error (a validation failure or an unreachable server) as a transient toast, and the result of a completed save or delete together with its reload outcome as the persistent status message defined in FR-018. A successful save MUST name the agent that was written. These are the same feedback surfaces on the list page and the form

### Key Entities

- **Agent Definition**: A configuration representing a single agent. Key attributes: name (unique identifier), enabled state, harness type, model, prompt reference, workspace paths, schedule, resource limits, environment variables. Stored as individual YAML files.
- **Prompt**: A markdown file containing instructions for an agent. Key attributes: filename, content. Stored in the prompts/ directory and referenced by agent definitions via the prompt_file field.
- **Harness**: A runtime environment type that determines which parameters are available and which models are compatible. Types: claude-code, pi, api, codex. Each has distinct parameter sets and model compatibility rules.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A new agent for any harness can be created from the New Agent page alone: every required field, its explanation, and its valid choices are on the page, and no link to external documentation is needed (verified by completing the quickstart "Create" walkthrough once per harness)
- **SC-002**: 100% of agent YAML files in the agents/ directory are correctly displayed in the UI with accurate metadata
- **SC-003**: Users cannot save an agent configuration with an incompatible model/harness combination
- **SC-004**: All agent parameters available in the YAML schema are exposed and editable through the UI
- **SC-005**: New prompts created through the UI are persisted immediately and become selectable without a server restart: a prompt created inline is referenced by the saving agent in that same request, and it then appears in the prompt selector's source — the `prompts` list in `GET /api/schema` (the endpoint the form reads to populate the selector), which is the same set served by `GET /api/prompts` — so any agent form opened afterward lists it
- **SC-006**: Changing one value on an existing agent takes three interactions — open the agent, change the field, save — with no intermediate pages
- **SC-007**: The agent list responds within 1 second for 50 agent files (measured by an automated test against generated files) and renders within 3 seconds in the browser
- **SC-008**: The quickstart "Create" checklist can be completed for a harness using only the page's inline explanations, with zero references to the README or any other external document — verified by a reviewer new to the UI who works the checklist end to end without leaving the page (an observable pass/fail, not a time-to-complete or a percentage of users)

## Assumptions

- The application is single-user; concurrent editing conflicts are not a concern for v1
- The UI has no authentication and is reachable on port 8080 by anyone on the host's network; this is an accepted decision for a single-operator tool on a trusted LAN, and exposing it beyond that network is out of scope
- The `/design-system` page needs internet access (its runtime and fonts load from public CDNs); the main application works without internet apart from web fonts, for which system fallbacks are defined
- The agents/ directory and prompts/ directory are accessible on the local filesystem where the server runs
- Agent YAML files follow the established schema as demonstrated by existing template and agent files
- Performance monitoring, tools configuration, and run history are explicitly out of scope — placeholders may exist in the UI but are non-functional
- Prompt management beyond select-or-create-inline is out of scope for this release: no editing of an existing prompt's content, no standalone prompt library page, no markdown preview in the inline editor, and no prompt deletion (deferred 2026-09-08)
- The existing FastAPI control panel (ui/main.py — agent listing with Dagster deep links) is the starting point and will be replaced with the full UI
- The design system (tokens, fonts, component patterns) is defined in ARCHON-DESIGN-SYSTEM.md, archon-tokens.css, and the companion .dc.html component library and prototype files; these ship with this branch and are the authoritative source for the agentbox UI's visual language, rebranded from "Archon" to "agentbox"
- Template YAML files (prefixed with `_`) serve as reference templates: hidden from the agent list and offered as "Start from template" on the New Agent page (FR-001, FR-023)
- Environment variable values that use `${VAR}` passthrough syntax are displayed as-is and not resolved in the UI; passthrough references are never flagged as secrets
- The harness container images (agentbox/agent-claude, agentbox/agent-pi, agentbox/agent-python, agentbox/agent-codex) are pre-built and not managed through this UI
- The LiteLLM proxy provides model routing for pi and api harnesses; the aliases (cheap, smart, opus, kimi, kimi-k3) are defined in litellm/config.yaml and the UI should reflect these as available options
- **Supported browsers and viewport**: the UI targets current evergreen desktop browsers (Chromium, Firefox, Safari) at a desktop viewport; the fixed sidebar plus content pane assume a minimum width of about 1024 px. A responsive or mobile layout is out of scope for this release
- **Keyboard and focus**: interaction relies on native form controls, links, and buttons, which are reachable and operable by Tab/Enter with the browser's default focus outline (the design tokens do not suppress focus rings); the confirmation, preview, and secret dialogs move focus to their primary action when opened and close on Escape or a click outside. A full WCAG keyboard and screen-reader audit is out of scope for this release
- **Audit trail and logging**: the agent and prompt files under version control are the record of configuration changes — committing them captures who changed what and when — which satisfies the constitution's auditable-configuration intent (II) through git rather than an application log; the UI does not add separate server-side write logging for create/update/delete/reload in this release (deferred)
