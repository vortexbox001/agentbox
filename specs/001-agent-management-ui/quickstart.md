# Quickstart: validating the Agent Management UI

Runnable checks that prove the feature end-to-end. Server behaviour is covered by `pytest`; the browser checks are a manual pass against the acceptance scenarios in [spec.md](spec.md).

## Prerequisites

- Docker + Compose on the agentbox host (or Python 3.12 locally for the non-container path)
- `.env` with `AGENTBOX_UID`/`AGENTBOX_GID` set to your host user (see `.env.example`) so files written by the UI stay yours
- Dagster services running for the reload checks (`docker compose up -d dagster-webserver dagster-daemon`); everything else works without Dagster

## 1. Automated tests (no Docker needed)

```bash
cd ui
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

Expected: all tests pass. They exercise the schema matrix, the YAML emitter (including a golden file per harness and a round-trip over every real `agents/*.yaml`), the stores, the secret heuristic, and every API route against temp directories.

## 2. Run the UI

```bash
docker compose up -d --build ui
docker compose logs -f ui        # uvicorn on :8080
```

Local alternative: `AGENTS_DIR=../agents PROMPTS_DIR=../prompts LITELLM_CONFIG=../litellm/config.yaml DAGSTER_URL=http://localhost:3000 uvicorn main:app --reload --port 8080` from `ui/`.

Open `http://<host>:8080`.

## 3. Browser checklist

Tick each item; all map to spec scenarios.

> **Automated validation run 2026-09-09** — `cd ui && pytest -q` is green (186 passed). A headless
> smoke test against `docker compose up -d --build ui` confirmed: `/` → `/agents` (302), `/agents`
> and `/agents/new` (200), the full `/design-system` route set (redirect, `text/html` index,
> `support.js` + `archon-tokens.css` + `Archon%20Prototype.dc.html` all 200), no `<a>` in `/agents`
> links to `/design-system`, `POST /api/dagster/reload` returns `{ok: true}`, and FR-010a hardening
> holds (`/api/agents/.hidden` → 404, `/api/prompts/.env` → 400, a traversal `?from=` is dropped).
> The items below that need visual rendering or interaction (styling, unsaved-changes prompt, secret
> confirmation dialog, harness-switch dynamics, inline cron/secret warnings) still require a manual
> pass in a real browser and are left unticked.

**Shell & list (US1, FR-012/13/15)**
- [ ] `/` redirects to `/agents`; sidebar shows the "agentbox" mark and a single "Agents" item; top bar shows the page title
- [ ] Every non-`_` file in `agents/` appears with name, harness, model, schedule (or "manual"), enabled state; disabled agents are visually muted
- [ ] `_template-*.yaml` files do not appear in the list
- [ ] Temporarily break a file (`echo "x: [" >> agents/zzz.yaml`): the list shows it with an error badge; remove it afterwards

**Create (US2, FR-002/003/003a/004/010/011/017/018/020)**
- [ ] "New agent" opens the form; choosing a harness shows only that harness's sections/fields and every field has an explanation
- [ ] "Start from template" lists the `_template-*.yaml` files; picking one pre-fills the form with `name` empty and `enabled` off, and the form is marked unsaved
- [ ] With harness `claude-code`, `network` pre-fills to `bridge`; changing it to `agentnet-isolated` shows a non-blocking mismatch warning and save still succeeds
- [ ] Fill some claude-code-only fields, switch harness to `pi`, then back: the claude-code values reappear; switching to `api` resets `effort` and offers only LiteLLM aliases for `model`
- [ ] Enum fields (harness, enabled, effort, permission_mode, network) are selectors, not text boxes; the harness selector shows each harness's description and container image (`agentbox/agent-…`)
- [ ] The top bar shows only the page title and breadcrumb; the sidebar Dagster block reflects reachability on load
- [ ] claude-code model selector lists `sonnet/opus/haiku/fable` plus a custom-id input; api model selector lists only LiteLLM aliases; codex model is a text field with suggestions
- [ ] Entering an existing name shows the duplicate error on save and nothing is overwritten
- [ ] Entering `5 * *` in schedule shows a cron error; `0 7 * * *` is accepted
- [ ] Adding `MY_TOKEN = abc123` under env shows an inline warning immediately; clicking save asks for confirmation; declining aborts, confirming writes the file
- [ ] `GITHUB_TOKEN = ${GITHUB_TOKEN}` shows no warning
- [ ] With "Reload Dagster after saving" checked (default), saving shows the reload outcome; with it unchecked, no reload message appears
- [ ] The written file `agents/<name>.yaml` matches [contracts/agent-yaml.md](contracts/agent-yaml.md): sections, one comment per field, valid YAML (`python -c "import yaml,sys;yaml.safe_load(open(sys.argv[1]))" agents/<name>.yaml`)

**Edit (US3, FR-005/016/021)**
- [ ] Clicking an agent opens its form pre-filled with every stored value; the name field is read-only
- [ ] Change the model and save: the file has the new value, all other values retained, hand-written comments replaced by the standard ones
- [ ] Edit a field and click the sidebar link: an unsaved-changes prompt appears
- [ ] "Preview YAML" opens a read-only view matching what save would write; closing it leaves the form unchanged

**Prompts (US4, FR-008/009)**
- [ ] The prompt selector lists every `prompts/*.md`
- [ ] "Create new prompt" with a filename and content, then save the agent: the file exists in `prompts/` and the agent's `prompt_file` references it; the selector now lists it without a page reload

**Validation (US5, FR-006/007)**
- [ ] Switching harness from claude-code to api hides `max_turns`/`permission_mode` and shows `max_tokens`; the model selector's options change accordingly
- [ ] A saved pi agent with `model: kimi-k3` reloads in the form with that value selected

**Delete (US6, FR-019)**
- [ ] Delete from the detail page shows a confirmation naming the agent; cancel leaves everything intact
- [ ] Confirm: the file is gone, the list no longer shows it, `/data/workspaces/<name>` and the output dir are untouched (`ls` them before/after)
- [ ] After the redirect, the Agents list shows the delete's reload outcome; with Dagster stopped it shows the failure with a working "Retry reload"

**Design system (US7, FR-014)**
- [ ] `/design-system` redirects to `/design-system/` and renders the component library with the token styling applied (dark background, Playfair headings) — proves `./archon-tokens.css` and `./support.js` resolved; needs internet for React/fonts. No navigation item links to it
- [x] Browser devtools Network tab shows `/design-system/support.js` and `/design-system/archon-tokens.css` as 200 (not `/support.js`)
- [x] `/design-system/Archon%20Prototype.dc.html` renders the prototype

**Dagster reload edge case**
- [ ] Stop Dagster (`docker compose stop dagster-webserver`), save an agent: the file is written, the UI reports the reload failure and offers retry; start Dagster and retry succeeds

## 4. Orchestrator compatibility

After creating an agent through the UI with `enabled: true`, reload (or restart) Dagster and confirm the job `agent_<name>` appears in the Dagster UI and, if scheduled, has a schedule `sched_<name>`. Launch it once to confirm the generated YAML drives a run exactly like a hand-written one.
