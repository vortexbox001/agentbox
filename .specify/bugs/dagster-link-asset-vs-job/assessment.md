# Bug Assessment: Agent edit page "Dagster job" link ignores asset nature

- **Slug**: dagster-link-asset-vs-job
- **Created**: 2026-09-11
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim)

> on asset create/edit page the link up top "dagster job" should be to dasters asset if agent is asset, job otherwise

(Interpreted: on the **agent** create/edit page, the header action link labeled "Dagster job" should point to the Dagster **asset** page when the agent declares an asset (`produces`), and to the Dagster **job** page otherwise.)

## Symptom

On the agent edit page (`/agents/<name>`), the header action link is always labeled "Dagster job" and always points to `<dagster_url>/locations/<location>/jobs/agent_<name>`, even for asset-only agents. Since spec 006 an agent's nature is explicit (`produces` asset and/or `job: true`); an asset-only agent has **no** Dagster job named `agent_<name>`, so for those agents the link is both mislabeled and dead (Dagster shows a "job not found" page). Expected: asset agents link to the agent's Dagster asset page and the label says so.

Note: the create page (`/agents/new`) renders no Dagster link at all (the template gates it on `mode == "edit"`), which is arguably correct — the agent doesn't exist in Dagster yet. The report's "create/edit" is read as referring to the shared form page; only edit mode is affected.

## Reproduction

1. Create (or have) an asset-only agent: `agents/<name>.yaml` with a `produces: { asset: ... }` block and no `job: true`.
2. Open `http://10.0.0.100:8000/agents/<name>` (the UI edit page).
3. Observe the header link says "Dagster job" and its `href` is `/locations/definitions.py/jobs/agent_<name>`.
4. Click it — Dagster has no such job for an asset-only agent.

## Suspected Code Paths

- `ui/templates/agents/form.html:11-15` — the link (`id="ax-job-link"`): hardcoded `{{ dagster_url }}{{ dagster_job_path(dagster_job) }}` href and "Dagster job" label, shown whenever `mode == "edit"`.
- `ui/main.py:172-213` (`_agents_edit_page`) — builds the template context; passes `dagster_job=info["dagster_job"]` but nothing about the agent's asset. `info["agent"]` (from `read_agent`) already carries the lifted flat `asset` field and `job` bool, so the nature is available here.
- `ui/agents_store.py:59-65` — `dagster_job_path()` / `_dagster()`: job-URL helpers; there is no asset-URL counterpart.
- `ui/templates/agents/list.html:52` — the agents list has the same per-row job link with the same problem (out of the reported scope, but same root cause; see Risks).

The link is fully server-rendered — `ui/static/agent-form.js` never touches `ax-job-link` — so the fix is server/template-side only.

## Root Cause Hypothesis

The link predates specs 004/006: when every agent was a job named `agent_<name>`, a static job link was always correct. Spec 006 made nature explicit (asset-only / job-only / both), but the form template and edit-route context were never updated, so the job link is emitted unconditionally. Confidence: **high** — the template branch is unconditional and no asset URL helper exists anywhere in `ui/`.

## Proposed Remediation

**Preferred**: Decide the link target server-side in `_agents_edit_page` and pass a ready-made href + label to the template.

- In `ui/agents_store.py`, add a helper alongside `dagster_job_path`, e.g. `dagster_asset_path(key: str) -> str` returning `/assets/<key>` (Dagster webserver's asset catalog page; a multi-segment key `foo/bar` maps to `/assets/foo/bar`). Verify this path shape once against the live Dagster at `http://10.0.0.100:3000` before locking it in.
- In `_agents_edit_page` (`ui/main.py`), read the agent's nature from `info["agent"]`: `asset = (info.get("agent") or {}).get("asset")`. Pass to the template e.g. `dagster_link_path` and `dagster_link_label` ("Dagster asset" when an asset key is set, "Dagster job" otherwise). When `info["agent"]` is `None` (parse error), fall back to the current job link.
- In `ui/templates/agents/form.html`, render `href="{{ dagster_url }}{{ dagster_link_path }}"` and the passed label; keep the `id="ax-job-link"` element id (nothing references it in JS, but changing ids churns tests/CSS for no gain).

Per the report's rule, an agent that is **both** asset and job gets the asset link (asset wins); see Open Questions.

**Alternatives**:
- Branch in the Jinja template on a passed `asset` value instead of precomputing href/label in Python. Slightly less Python, but spreads URL-shape knowledge into the template; the codebase convention (`dagster_job_path` as a template global) already leans helper-side.
- Show **two** links for a "both" agent (asset + job). More complete, but adds header clutter and exceeds the reported ask.

**Files likely to change**:
- `ui/agents_store.py` (new `dagster_asset_path` helper)
- `ui/main.py` (edit-route context)
- `ui/templates/agents/form.html` (link href + label)
- `ui/tests/test_api.py` or a page-level test module (assertions on the rendered edit page)

**Tests to add or update**:
- Edit page for an asset-only agent: response HTML contains `/assets/<key>` href and the label "Dagster asset", and does **not** contain the `agent_<name>` job path.
- Edit page for a job-only agent: unchanged job link `/locations/<location>/jobs/agent_<name>` with label "Dagster job".
- Edit page for a both-kind agent: whichever target the open question resolves to.
- Edit page for an unparsable agent file: still renders (falls back to job link, no 500).
- Run with `cd ui && ../.venv/bin/python -m pytest -q`.

## Risks & Considerations

- **Asset URL shape**: Dagster's asset page path (`/assets/<key path>`) should be confirmed against the deployed Dagster version once; if it differs, only the new helper needs adjusting.
- **Agents list page** (`ui/templates/agents/list.html:52` + the `/api/agents` rows built in `ui/main.py` around line 141 and `ui/agents_store.py:222`) has the identical stale job link per row. Fixing it means touching the list API payload (`dagster_url` per row) and its tests (`ui/tests/test_api.py:183`). Recommend fixing it in the same pass for consistency, but it is strictly outside the reported page.
- No API/schema/YAML changes; purely presentational. No migration risk.

## Open Questions

- [NEEDS CLARIFICATION: for a "both" agent (asset **and** `job: true`), should the link go to the asset page (the report's literal rule: "asset if agent is asset, job otherwise" — assumed here), the job page, or should both links show?]
- [NEEDS CLARIFICATION: should the agents **list** page rows get the same treatment in this fix, or stay as-is?]
