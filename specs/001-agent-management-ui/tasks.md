# Tasks: Agent Management UI

**Input**: Design documents from `/specs/001-agent-management-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, contracts/agent-yaml.md, quickstart.md

**Tests**: Included. The plan commits to `pytest` + `TestClient` coverage (research R11) and the constitution prefers automated verification (Principle VI). Test tasks precede implementation within each phase; write them first and confirm they fail.

**Organization**: Tasks are grouped by user story so each story is an independently testable increment. Paths are repository-relative; everything lives under `ui/` per plan.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US7 from spec.md
- Every task names the exact file(s) it touches

## Path Conventions

Single package at `ui/`: modules at `ui/*.py`, pages in `ui/templates/`, browser code in `ui/static/`, design reference in `ui/design-system/`, tests in `ui/tests/`. Repo-level files touched: `docker-compose.yml`, `.env.example`, `README.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Get the package, container, and test harness in place

- [x] T001 Rename the design reference folder with `git mv "ui/Archon Agent Orchestration Platform" ui/design-system` (no content changes; verify `ui/design-system/support.js`, `archon-tokens.css`, and the three `.dc.html` files are present)
- [x] T002 Create `ui/requirements.txt` (pinned: fastapi, uvicorn, jinja2, python-multipart, httpx, pyyaml, croniter, pytest) and change `ui/Dockerfile` to `COPY requirements.txt` + `pip install --no-cache-dir -r requirements.txt`, keeping the existing `WORKDIR`/`CMD`
- [x] T003 [P] Update the `ui` service in `docker-compose.yml`: add `./prompts:/opt/agentbox/prompts` (rw) and `./litellm/config.yaml:/opt/agentbox/litellm/config.yaml:ro`, add `user: "${AGENTBOX_UID:-1000}:${AGENTBOX_GID:-1000}"`, and pass `AGENTS_DIR`, `PROMPTS_DIR`, `LITELLM_CONFIG`, `DAGSTER_URL` as environment
- [x] T004 [P] Document `AGENTBOX_UID` / `AGENTBOX_GID` (with `id -u` / `id -g` hint) in `.env.example`
- [x] T005 [P] Create `ui/config.py` exposing `AGENTS_DIR`, `PROMPTS_DIR`, `LITELLM_CONFIG`, `DAGSTER_URL`, `DESIGN_SYSTEM_DIR`, `RELOAD_TIMEOUT_S = 10` from environment variables with the container-path defaults from plan.md
- [x] T006 [P] Create `ui/tests/conftest.py` with fixtures: `tmp_agents` (copies of every repo `agents/*.yaml` into `tmp_path`), `tmp_prompts` (copies of `prompts/*.md`), `litellm_cfg` (copy of `litellm/config.yaml`), a `settings` fixture that monkeypatches `ui/config.py` to those paths, a `client` fixture returning `fastapi.testclient.TestClient(app)`, and a `dagster_stub` fixture that monkeypatches `ui/dagster.py` reload/status to return canned `{ok, message}` values
- [x] T007 [P] Create `ui/pytest.ini` (`testpaths = tests`, `pythonpath = .`) so `pytest -q` runs from `ui/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema, stores, emitter, Dagster client, secret heuristic, app skeleton, and shell that every story builds on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Create `ui/schema.py` with `SCHEMA_VERSION = 1`, `MIGRATIONS: list[tuple[int, Callable]] = []`, `SECTIONS` in the FR-002 order (identity, model, prompt_output, workspace, execution, scheduling, resources, environment), and `FIELDS` — one `SchemaField` per key in data-model.md with `id, section, label, type, required, default, choices|choice_source, pattern, min, max, help, harnesses` (help strings verbatim from the data model; every string states what it does, valid values, and default)
- [X] T009 Extend `ui/schema.py` with `HARNESSES` (id, label, description, image, fields, `model_rule {choices, custom, blank_ok}`, `effort_choices`, `default_network`, codex `model_suggestions`) per research R4, plus `litellm_aliases()` that reads `model_list[].model_name` from `config.LITELLM_CONFIG` and falls back to `["cheap","smart","opus","kimi","kimi-k3"]`
- [X] T010 Extend `ui/schema.py` with `applicable_fields(harness)`, `validate(agent: dict, *, prompt_exists: Callable) -> dict[str, str]` (name pattern, enum membership, int/number ranges, `memory` pattern, five-field cron via `croniter.is_valid` with macros/6-field rejected, per-harness model rule incl. `[1m]` suffix regex and pi `provider/model`, env key pattern, `prompt_file` existence), `network_mismatch_warning(agent) -> str | None` (FR-024), `apply_migrations(data: dict, from_version: int) -> dict` (raises `SchemaTooNew` when `from_version > SCHEMA_VERSION`), and `to_public() -> dict` producing the `/api/schema` payload shape from contracts/http-api.md
- [X] T011 (after T010) Write `ui/tests/test_schema.py`: per-harness `applicable_fields` matches the data-model matrix (env_file on all four; effort absent for api; allowed_tools absent for codex); model rule table (aliases, `claude-opus-4-8[1m]`, `openai/gpt-x` for pi, blank for codex, invalid combos); cron table (`0 7 * * *` ok, `@daily` rejected, 6 fields rejected, `""` ok); `apply_migrations` no-op at v1 and `SchemaTooNew` at v2; `litellm_aliases()` with and without the config file; `network_mismatch_warning` cases
- [X] T012 Create `ui/agents_store.py` read side: `list_agents()` and `read_agent(stem)` that glob `config.AGENTS_DIR/*.yaml`, parse the `# agentbox-schema: N` header (absent → 0), `yaml.safe_load`, classify errors (syntax, non-mapping, missing name/harness, `SchemaTooNew`) into `parse_error` with `raw` text, split known vs `unmanaged` keys, apply migrations, flag `name_mismatch` when `name != stem`, set `editable = False` only for the `SchemaTooNew` case, set `is_template = stem.startswith("_")`, and derive `dagster_job` / `dagster_url`
- [X] T013 Extend `ui/agents_store.py` write side: `emit_yaml(agent: dict) -> str` implementing every rule in contracts/agent-yaml.md (header with harness description + generated line + version stamp; section comments in order; `key: value  # help` with PyYAML flow-style scalars; commented `#key:  # help` for unset; lists as block sequences; `env` map lines; trailing `# --- Unmanaged (not edited by the UI) ---` via `safe_dump`; always-written set incl. `network` and `schedule`), `write_agent(stem, agent)` (atomic temp+`os.replace` in the same dir, UTF-8, LF, one trailing newline, `name` forced to `stem`), and `delete_agent(stem)` (raises `FileNotFoundError`; never touches other paths)
- [X] T014 (after T013) Write `ui/tests/test_agents_store.py`: golden-file comparison for one agent per harness in `ui/tests/golden/{claude-code,pi,api,codex}.yaml`; `safe_load(emit_yaml(cfg)) == cfg` for every repo agent and template; emitting twice is byte-identical; unmanaged key round-trips; `name_mismatch` flagged and normalised on write; newer version → `parse_error`; write is atomic (no `*.tmp` left, file present after a simulated failure); delete removes only the file
- [X] T015 [P] Create `ui/prompts_store.py`: `list_prompts()` (filename, size, modified ISO-8601 UTC), `read_prompt(filename)`, `create_prompt(filename, content)` with `^[a-z0-9][a-z0-9._-]*\.md$` validation (auto-append `.md`), rejection of `/`, `\`, `..`, non-empty content, `os.makedirs(PROMPTS_DIR, exist_ok=True)`, atomic write, `FileExistsError` on collision
- [X] T016 [P] Write `ui/tests/test_prompts_store.py` covering list ordering, read, create (auto `.md`, collision, traversal rejected, empty content rejected, directory created)
- [X] T017 [P] Create `ui/secret_scan.py` (NOT `secrets.py` — that filename shadows the stdlib `secrets` module that Starlette imports at startup, breaking `uvicorn main:app`): `is_passthrough(value)` (`^\$\{\w+\}$`), `is_secret_like(name, value)` implementing the FR-020 rule exactly (name substrings TOKEN/SECRET/PASSWORD/PASSWD/API_KEY/APIKEY/PRIVATE_KEY/CREDENTIAL/AUTH; value prefixes `sk-`, `sk-ant-`, `ghp_`, `github_pat_`, `gho_`, `xoxa-`, `xoxb-`, `xoxp-`, `AKIA`, `AIza`, `-----BEGIN`; ≥20 chars, no whitespace, ≥3 of 4 character classes), and `flagged_keys(env: dict) -> list[str]`
- [X] T018 [P] Write `ui/tests/test_secrets.py` as a parametrised table including the FR-020 reference cases (`GITHUB_USER: leeclemmer` not flagged; `MY_TOKEN: abc123` flagged by name; `REPO: sk-live-a1B2c3D4e5F6g7H8i9J0` flagged by value; `GITHUB_TOKEN: ${GITHUB_TOKEN}` not flagged)
- [X] T019 [P] Create `ui/dagster.py`: `async reload() -> dict` posting `mutation { reloadWorkspace { __typename ... on PythonError { message } ... on UnauthorizedError { message } } }` to `f"{DAGSTER_URL}/graphql"` with `httpx` and `RELOAD_TIMEOUT_S`, mapping to `{ok, message}` ("Workspace reloaded" / Dagster's message / "Dagster unreachable (timeout after 10s)"), and `async status() -> dict` (`{url, reachable}`)
- [X] T020 Rewrite `ui/main.py` as the app skeleton: `Jinja2Templates(ui/templates)`, `StaticFiles` mounts at `/static` (`ui/static`) and `/design-system` (`config.DESIGN_SYSTEM_DIR`, `html=False`), `GET /design-system` → `302 /design-system/`, `GET /design-system/` → `FileResponse("Archon Design System.dc.html", media_type="text/html")`, `GET /` → `302 /agents`, a JSON error handler producing `{"error", "message", ...}` for `HTTPException`/validation, `GET /api/schema` (`schema.to_public()` + `litellm_aliases` + `prompts_store.list_prompts()` names), `POST /api/dagster/reload`, `GET /api/dagster/status`
- [X] T021 Create the app shell: `ui/templates/base.html` (220 px sidebar with the "agentbox" brand mark on `--ax-gradient-brand`, single "Agents" nav item, Dagster status block linking to `DAGSTER_URL`; 56 px top bar with `{% block title %}` and breadcrumb slot; scrollable 28 px-padded content `{% block content %}`; status/toast region; modal root), `ui/static/app.css` (component styles using only `--ax-*` tokens from `/design-system/archon-tokens.css`: nav item, card, table, badges incl. status/disabled/error, inputs, buttons, toggle, modal, toast, form sections, help text), `ui/static/shell.js` (nav active state, toast/status API with dismiss and persistent-until-next-action semantics, `flashStatus(status)` that stores a status in `sessionStorage` so the next page load displays it with its Retry action, `registerDirtyForm()` guard: in-app link interception modal + `beforeunload`, Dagster status fetch on page load only), all styling via `--ax-*` tokens only (no literal colours or fonts), `ui/static/icons.svg` (agents, plus, trash, eye, refresh icons at 16 px, stroke 1.4)
- [X] T022 (after T021) Write foundational cases in `ui/tests/test_api.py`: `GET /` redirects to `/agents`; `GET /design-system` → 302 with `Location: /design-system/`; `GET /design-system/` returns HTML containing `./support.js`; `GET /design-system/support.js` and `/design-system/archon-tokens.css` are 200; `GET /api/schema` has `sections`, `fields`, `harnesses` (4), `litellm_aliases`, `prompts`; `POST /api/dagster/reload` and `GET /api/dagster/status` return the stubbed shapes; base page contains no link to `/design-system`; a token-discipline test asserts `ui/static/app.css` and every file under `ui/templates/` contain no literal hex/rgb colour or `font-family` value (FR-015)

**Checkpoint**: `pytest -q` passes for schema, stores, secrets, and skeleton routes; `uvicorn main:app` serves the empty shell and `/design-system/` renders with styling

---

## Phase 3: User Story 1 — View Existing Agents (Priority: P1) 🎯 MVP

**Goal**: The Agents page lists every non-template agent with name, harness, model, schedule, enabled state, Dagster link, and error/mismatch indicators; empty state when there are none

**Independent Test**: Start the UI against the repo's `agents/` directory; every non-`_` file appears with correct metadata, templates are absent, a deliberately broken file shows an error badge, and an empty directory shows the empty state

### Tests for User Story 1

- [ ] T023 [P] [US1] Add to `ui/tests/test_api.py`: `GET /api/agents` lists every non-template file with `name, file, enabled, harness, model, schedule, dagster_job, dagster_url, parse_error, name_mismatch`, lists templates separately under `templates`, reports a broken file with `parse_error` set and other fields null, marks a newer-schema file `editable: false`, returns empty lists for an empty directory, and responds in under 1 second with 50 generated agent files (SC-007); `GET /agents` HTML contains each agent name as a link to `/agents/{name}` and the "New agent" link

### Implementation for User Story 1

- [ ] T024 [US1] Implement `GET /api/agents` in `ui/main.py` returning `{"agents": [...], "templates": [{"file", "harness"}]}` from `agents_store.list_agents()` per contracts/http-api.md
- [ ] T025 [US1] Create `ui/templates/agents/list.html` and `GET /agents` in `ui/main.py`: table (name link, harness badge, model in mono, schedule or "manual", enabled → reduced opacity + "disabled" badge, error badge with message, mismatch warning badge, Dagster "runs" link), "New agent" primary button, empty state card with a "Create your first agent" call to action; page title "Agents"

**Checkpoint**: US1 is demoable — the list reflects the filesystem exactly

---

## Phase 4: User Story 2 — Create a New Agent (Priority: P1)

**Goal**: A schema-driven form creates a valid, commented YAML file with harness-appropriate fields, constrained inputs, inline explanations, secret warnings with confirm-on-save, an on-demand YAML preview, "Start from template", and an optional Dagster reload

**Independent Test**: From the Agents page, create an agent for each harness through the form and confirm a file matching contracts/agent-yaml.md appears in `agents/`, duplicates are refused, a secret-like env value forces a confirmation, and the reload outcome is reported

### Tests for User Story 2

- [ ] T026 [P] [US2] Add to `ui/tests/test_api.py`: `POST /api/agents` → 201 with `file` and `reload {requested, ok, message}`; 400 with `fields` for bad name/cron/model/range; 409 `exists`; 409 `secret_confirmation_required` with `flagged`, then 201 when `confirm_not_secret` lists them; `reload_dagster: false` → `reload.requested == false`; stubbed reload failure still 201 with `ok: false`; `POST /api/agents/preview` returns `yaml` for a valid body and 400 `fields` for an invalid one; `GET /api/agents/_template-pi` returns the template for pre-fill

### Implementation for User Story 2

- [ ] T027 [US2] Implement `POST /api/agents` and `POST /api/agents/preview` in `ui/main.py`: parse body `{agent, new_prompt?, confirm_not_secret?, reload_dagster=true}`; run `schema.validate` (400); refuse existing stem (409 `exists`); compute `secrets.flagged_keys(agent.env)` minus confirmed → 409 `secret_confirmation_required`; create `new_prompt` first via `prompts_store` (409 `prompt_exists`) and set `prompt_file`; `agents_store.write_agent`; call `dagster.reload()` when requested; respond per contract. Preview validates and returns `emit_yaml` without writing or checking secrets
- [ ] T028 [US2] Implement `GET /api/agents/{name}` read endpoint in `ui/main.py` (needed for `?from=` template pre-fill; returns `{agent, file, parse_error, raw, name_mismatch}`; 404 when absent; templates addressable)
- [ ] T029 [US2] Create `ui/templates/agents/form.html` and `GET /agents/new` in `ui/main.py`: page title "New agent", breadcrumb "Agents / New", "Start from template" select (populated from the `templates` array of `GET /api/agents` — requires T024), form skeleton with a `<div data-sections>` mount point, action bar (Save, Preview YAML, Cancel, "Reload Dagster after saving" checkbox checked by default), status region; pass `mode="create"` and optional `?from=` stem to the page
- [ ] T030 [US2] Create `ui/static/agent-form.js` core: fetch `/api/schema`; render sections and fields in schema order from `FIELDS` filtered by `applicable_fields` of the selected harness; input kinds by type (enum → `<select>`, bool → toggle, int/number → `<input type=number min max>`, string/path → text with placeholder, `output_dir` placeholder `/data/outputs/<name>`, cron → text with client-side 5-field shape check, list → chip editor with suggestions, map → key/value rows); render each field's `help` beneath it; name field with kebab-case pattern; harness select showing each harness's label, description, and container image (`agentbox/agent-…`) from `/api/schema`; collect values → payload; POST and map 400 `fields` to inline errors; show toast on success then navigate to `/agents/{name}`
- [ ] T031 [US2] Extend `ui/static/agent-form.js`: env editor calls `secrets` logic mirrored client-side to show an inline warning immediately for secret-like plain values (never for `${NAME}`); on 409 `secret_confirmation_required` open a confirmation modal listing the flagged keys with "These are not secrets — save anyway" / "Cancel", resubmitting with `confirm_not_secret` on confirm; "Preview YAML" button opens a read-only modal with the response of `POST /api/agents/preview` (or the validation errors when invalid); "Start from template" loads `GET /api/agents/{name}` and pre-fills with `name` cleared and `enabled` false, marking the form dirty
- [ ] T032 [US2] Wire form lifecycle in `ui/static/agent-form.js` + `ui/static/shell.js`: snapshot loaded values, dirty = current ≠ snapshot, register with `registerDirtyForm()` (in-app modal + `beforeunload`), clear dirty after successful save; render the `reload` outcome as a persistent status message with a "Retry reload" action that calls `POST /api/dagster/reload` only; reset the checkbox to checked on every page load

**Checkpoint**: US1 + US2 — agents can be listed and created end-to-end through the browser; quickstart "Create" items pass

---

## Phase 5: User Story 3 — Edit an Existing Agent (Priority: P1)

**Goal**: Opening an agent pre-fills the form (name read-only); saving regenerates the file with standard comments, retains all other values, preserves unmanaged keys, and warns before discarding unsaved edits

**Independent Test**: Open a hand-written agent, change the model, save; the file has the new value, every other value retained, hand-written comments replaced by standard ones, and unknown keys kept

### Tests for User Story 3

- [ ] T033 [P] [US3] Add to `ui/tests/test_api.py`: `PUT /api/agents/{name}` → 200 and the rewritten file loads with the changed value and all others intact; hand-written comments are gone and standard comments present; an unmanaged key survives; changing `name` → 400 `fields.name`; unknown stem → 404; `GET /api/agents/{name}` for a broken file returns `agent: null` with `raw`; `GET /agents/{name}` HTML has the name input `readonly` and, for the broken file, shows the error banner and raw block

### Implementation for User Story 3

- [ ] T034 [US3] Implement `PUT /api/agents/{name}` in `ui/main.py`: 404 when absent; 400 when `agent.name != stem`; same validation/secret/prompt/reload pipeline as create; preserve `unmanaged` from the loaded file when the payload omits it
- [ ] T035 [US3] Add `GET /agents/{name}` in `ui/main.py` rendering `ui/templates/agents/form.html` with `mode="edit"`, title = agent name, breadcrumb "Agents / {name}", Dagster job link in the action bar, and — when `parse_error` — an error banner plus a read-only `<pre>` of `raw`; when `editable` is false (newer schema version) render only the banner "written by a newer agentbox", the raw block, and the Delete action — no form; 404 page when the file does not exist
- [ ] T036 [US3] Extend `ui/static/agent-form.js` edit mode: load `GET /api/agents/{name}`, pre-fill every applicable field (name rendered read-only with the "delete and recreate to rename" hint), carry `unmanaged` through to the PUT payload untouched, show the name-mismatch warning when flagged, submit via PUT, and reuse the preview/secret/reload/dirty behaviour from US2

**Checkpoint**: US1–US3 — the full create/edit loop works; quickstart "Edit" items pass

---

## Phase 6: User Story 4 — Select or Create Prompts (Priority: P2)

**Goal**: The prompt field offers every `prompts/*.md` file and an inline "create new prompt" path that saves the file and references it from the agent

**Independent Test**: Create an agent choosing "new prompt" with a filename and content; the `.md` file exists in `prompts/`, the agent's `prompt_file` references it, and the selector lists it without a page reload

### Tests for User Story 4

- [ ] T037 [P] [US4] Add to `ui/tests/test_api.py`: `GET /api/prompts` lists files with size/modified; `GET /api/prompts/{filename}` returns content, 404 when missing, 400 for `../x.md`; `POST /api/prompts` → 201, 409 on collision, 400 on bad name/empty content, creates the directory when missing; `POST /api/agents` with `new_prompt` writes the prompt first and sets `prompt_file`; when the agent write then fails (e.g., duplicate stem) the prompt remains and the 409 message says the prompt was created; saving with a `prompt_file` removed from disk → 400 `fields.prompt_file`

### Implementation for User Story 4

- [ ] T038 [US4] Implement `GET /api/prompts`, `GET /api/prompts/{filename}`, `POST /api/prompts` in `ui/main.py` backed by `ui/prompts_store.py`; make the create/update handlers append "the prompt `<file>` was created" to their error message when a `new_prompt` succeeded but the agent write failed
- [ ] T039 [US4] Extend `ui/static/agent-form.js`: render `prompt_file` as a select populated from `GET /api/prompts` (with size/modified as secondary text) plus a "Create new prompt…" option that reveals filename + content inputs; include `new_prompt` in the save payload; after a successful save re-fetch `/api/prompts` so the selector updates without a page reload; map a `prompt_file` 400 to the field and refresh the selector

**Checkpoint**: Prompts can be chosen or authored inline; quickstart "Prompts" items pass

---

## Phase 7: User Story 5 — Model and Harness Validation (Priority: P2)

**Goal**: Only compatible model/effort/field combinations can be chosen or saved per harness; harness switches preserve what they can; harness/network mismatches warn without blocking

**Independent Test**: For each harness, the model control offers only compatible values, an incompatible model in the payload is rejected server-side with an explanation, switching harness and back restores hidden values, and a claude-code agent on `agentnet-isolated` shows a warning but saves

### Tests for User Story 5

- [ ] T040 [P] [US5] Add to `ui/tests/test_api.py`: parametrised `POST /api/agents` matrix — claude-code accepts `sonnet` and `claude-opus-4-8[1m]`, rejects `cheap`; pi accepts `kimi-k3` and `openai/gpt-x`, rejects `sonnet`; api accepts only aliases, rejects `claude-sonnet-5` and blank when required rule says so; codex accepts blank and `gpt-6-astra`; api with `effort` → 400; every rejection message names the harness and the allowed forms; claude-code + `agentnet-isolated` → 201 and the response carries `warnings: ["network …"]`

### Implementation for User Story 5

- [ ] T041 [US5] Extend `ui/main.py` create/update/preview responses with `warnings: [...]` from `schema.network_mismatch_warning` and ensure `schema.validate` rejects non-applicable fields that carry values (e.g., `effort` on api) with a message naming the harness
- [ ] T042 [US5] Implement the model control in `ui/static/agent-form.js` per research R4: claude-code → alias `<select>` (sonnet/opus/haiku/fable, blank = CLI default) plus "Custom model id…" option revealing a text input validated against the `claude-…[1m]?` pattern; pi → alias select from `litellm_aliases` plus "provider/model…" custom option; api → strict alias select; codex → text input with `<datalist>` from `model_suggestions`; effort `<select>` from the harness's `effort_choices`; a one-line explanation under the control stating why other forms are unavailable for this harness
- [ ] T043 [US5] Implement harness-switch semantics in `ui/static/agent-form.js` per FR-007a: keep a per-page memory of values for fields hidden by the switch and restore them when the harness returns; reset `model`/`effort` when invalid for the new harness; set `network` to the harness `default_network` unless the user changed it on this page; exclude hidden fields from the payload; show the FR-024 network mismatch warning inline (non-blocking) and surface server `warnings` in the status region

**Checkpoint**: Incompatible combinations are impossible to save; quickstart "Validation" items pass

---

## Phase 8: User Story 6 — Delete an Agent (Priority: P2)

**Goal**: Delete an agent from its detail page after confirmation; only the YAML file is removed; optional Dagster reload

**Independent Test**: Delete an agent; its file is gone, it disappears from the list, and pre-created workspace/output directories are untouched

### Tests for User Story 6

- [ ] T044 [P] [US6] Add to `ui/tests/test_api.py`: `DELETE /api/agents/{name}` → 200 `{deleted, reload}`; 404 when absent; `reload_dagster=false` → not requested; create dummy workspace/output directories under `tmp_path`, point the agent at them, delete, and assert they still exist with contents

### Implementation for User Story 6

- [ ] T045 [US6] Implement `DELETE /api/agents/{name}` in `ui/main.py` with `reload_dagster` query/body flag (default true), 404 mapping, and the same reload outcome shape
- [ ] T046 [US6] Add the Delete action to `ui/templates/agents/form.html` (edit mode only) and `ui/static/agent-form.js`: confirmation modal naming the agent and stating that only `agents/<stem>.yaml` is removed while workspace and outputs remain, with the "Reload Dagster" checkbox; on confirm call DELETE, hand the `reload` outcome to `shell.js` `flashStatus()`, and navigate to `/agents`, where the list page displays it (with "Retry reload" on failure, per FR-018); on 404 flash "agent no longer exists" and return to the list

**Checkpoint**: Full lifecycle (list → create → edit → delete) works; quickstart "Delete" items pass

---

## Phase 9: User Story 7 — Access Design System Component Library (Priority: P3)

**Goal**: `/design-system` serves the reference library with its assets resolving, and nothing in the main navigation links to it

**Independent Test**: `/design-system` redirects to `/design-system/`, the page renders styled, the Network tab shows `/design-system/support.js` and `/design-system/archon-tokens.css` as 200, and no nav item points there

### Tests for User Story 7

- [ ] T047 [P] [US7] Extend `ui/tests/test_api.py`: `GET /design-system/` `Content-Type` is `text/html`; the body contains `./archon-tokens.css` and `./support.js`; `GET /design-system/Archon%20Prototype.dc.html` is 200; rendered `/agents` HTML contains no `href="/design-system`

### Implementation for User Story 7

- [ ] T048 [US7] Verify and finalise the `/design-system` routes in `ui/main.py` from T020 (explicit `media_type="text/html"` on the index response, correct handling of the space-containing filename, `Cache-Control: no-store` off — default caching is fine) and confirm `ui/templates/base.html` links only `/design-system/archon-tokens.css` as a stylesheet, never as navigation

**Checkpoint**: All seven stories independently pass their quickstart sections

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation accuracy (Constitution VI), operational logging, and final validation

- [ ] T049 [P] Update `README.md`: "Adding an agent" describes the UI flow (New agent → form → save with Dagster reload) with the hand-edit path as the alternative; note that UI saves regenerate files with standard comments and preserve unknown keys; "Repository layout" lists `ui/` modules and `ui/design-system/`; the `ui` service section documents the new mounts and `AGENTBOX_UID/GID`; mark `env_file` as common (it already is), refresh the "Models and LiteLLM" alias table to match `litellm/config.yaml` (`cheap`, `smart`, `opus`, `kimi`, `kimi-k3`), and link to `/design-system`
- [ ] T050 [P] Add structured log lines in `ui/main.py` for every create/update/delete/reload/prompt-create (`event=agent_created stem=… reload_ok=…`) via the standard `logging` module at INFO, never logging env values
- [ ] T051 [P] Harden filename inputs in `ui/main.py`: reject stems and prompt filenames containing `/`, `\`, `..`, or leading `.` before touching the filesystem (400) for `/api/agents/{name}`, `/api/prompts/{filename}`, and `?from=`; add cases to `ui/tests/test_api.py`
- [ ] T052 Run the full `ui/tests` suite (`cd ui && pytest -q`) and the browser checklist in `specs/001-agent-management-ui/quickstart.md` §3–4 against `docker compose up -d --build ui`; record outcomes in the quickstart checkboxes and fix anything that fails
- [ ] T053 Remove the legacy table view and `/reload` form route left from the old `ui/main.py` if still present, and delete `ui/design-system/.thumbnail` from the static mount if it is not needed (keep it in git if the design tool relies on it)
- [X] T054 Map storage failures to a distinct error: catch `PermissionError`/`OSError` in `ui/agents_store.py` and `ui/prompts_store.py`, raise a `StorageError(operation, path)` that `ui/main.py` turns into `507 {"error": "storage", "message": "cannot <op> <dir>/<file>: <os error>"}` per contracts/http-api.md; add cases to `ui/tests/test_api.py` using a read-only `tmp_path` (chmod) and a missing, uncreatable prompts directory. (Belongs logically to Phase 2; numbered here to keep earlier IDs stable — do it before T052.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T003–T007 parallel after T001/T002
- **Foundational (Phase 2)**: depends on Phase 1; blocks every story. Order inside: T008 → T009 → T010 (same file) → T012 → T013 (same file); T011, T014–T019, T022 parallel once their targets exist; T020 after T010/T015/T019; T021 after T020
- **US1 (Phase 3)**: after Phase 2; no story dependencies
- **US2 (Phase 4)**: after Phase 2 **and T024** (US1's `GET /api/agents` supplies the `templates` array that "Start from template" reads); the rest of US1 is needed only for navigation
- **US3 (Phase 5)**: after US2 (extends `form.html` and `agent-form.js`)
- **US4 (Phase 6)**: after US2 (extends the form's prompt field and the create pipeline)
- **US5 (Phase 7)**: after US2 (extends the form's model/harness controls); independent of US3/US4
- **US6 (Phase 8)**: after US3 (the Delete action lives on the edit page)
- **US7 (Phase 9)**: after Phase 2 only; can run any time
- **Polish (Phase 10)**: after all desired stories

### User Story Dependencies

- **US1** → none
- **US2** → T024 (US1's list endpoint); rest of US1 optional
- **US3** → US2
- **US4** → US2
- **US5** → US2
- **US6** → US3
- **US7** → none

### Within Each User Story

- Test task first; confirm it fails
- API endpoint before page/template before browser module
- Story complete and its quickstart section green before the next priority

### Parallel Opportunities

- Phase 1: T003, T004, T005, T006, T007
- Phase 2: T015 ∥ T017 ∥ T019 (independent modules) and T016 ∥ T018 (their tests); T011, T014, and T022 each start as soon as their target (T010, T013, T021) lands
- After US2: US3, US4, US5 can proceed in parallel by different people (they touch different regions of `agent-form.js`; coordinate merges)
- US7 and Phase 10 documentation (T049) can run alongside any story

---

## Parallel Example: Phase 2

```bash
# After T008–T010 and T012–T013 land, run these together:
Task: "Write ui/tests/test_schema.py"            # T011
Task: "Write ui/tests/test_agents_store.py"      # T014
Task: "Create ui/prompts_store.py"               # T015
Task: "Create ui/secrets.py"                     # T017
Task: "Create ui/dagster.py"                     # T019
```

## Parallel Example: After User Story 2

```bash
Task: "US3 — PUT /api/agents/{name} + edit page"        # T033–T036
Task: "US4 — prompts endpoints + selector"               # T037–T039
Task: "US5 — model control + harness switch semantics"   # T040–T043
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Phase 1 Setup → Phase 2 Foundational (this is where most of the logic lives: schema, emitter, stores)
2. Phase 3 US1 — the list; **validate**: list matches `agents/`
3. Phase 4 US2 — the form; **validate**: create one agent per harness, files match the contract
4. Demo: the UI already replaces "copy a template and edit YAML by hand"

### Incremental Delivery

1. US3 edit → hand-written agents become UI-managed
2. US4 prompts → authoring without touching `prompts/` by hand
3. US5 validation hardening → bad combinations impossible
4. US6 delete → full lifecycle
5. US7 design system → developer reference
6. Polish → README accuracy, logging, quickstart sign-off

### Parallel Team Strategy

With two people: one takes Foundational schema/emitter/stores (T008–T018), the other the app skeleton/shell/Dagster (T019–T022). After US2, split US3+US6 / US4+US5.

---

## Notes

- [P] tasks touch different files and have no dependency on incomplete work
- `agent-form.js` is shared by US2–US6; land US2 first, then extend in small commits to avoid conflicts
- Every write goes through `agents_store.write_agent` / `prompts_store.create_prompt` so atomicity and encoding rules (FR-004a) are enforced in one place
- The help strings in `ui/schema.py` are the single source for form explanations, YAML comments, and (via README T049) documentation — edit them there only
- Commit after each task or logical group; stop at any checkpoint to validate the story independently
