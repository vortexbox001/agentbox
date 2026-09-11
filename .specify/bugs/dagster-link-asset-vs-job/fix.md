# Bug Fix: Agent edit page "Dagster job" link ignores asset nature

- **Slug**: dagster-link-asset-vs-job
- **Fixed**: 2026-09-11
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The agent edit page's header link and the agents list rows now point at the Dagster **asset** page (`/assets/<key>`) when the agent declares a `produces` asset, and at the job page (`/locations/<location>/jobs/agent_<name>`) otherwise. The edit-page label follows suit ("Dagster asset" / "Dagster job"). Both open questions from the assessment were answered by the user: asset wins for a both-kind agent, and the list page is fixed in the same pass.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `ui/agents_store.py` | modified | New `dagster_asset_path()` helper; `read_agent` now also returns `dagster_kind` + `dagster_path` (job by default, overridden to the asset page when the parsed agent has a non-empty `asset`; `dagster_url` follows). `list_agents` rows carry `dagster_path`. |
| `ui/main.py` | modified | Edit route passes `dagster_path`/`dagster_kind` instead of `dagster_job`; removed the now-unused `dagster_job_path` Jinja global. |
| `ui/templates/agents/form.html` | modified | Header link uses `dagster_path` and labels itself `Dagster {{ dagster_kind }}`. Element id stays `ax-job-link`. |
| `ui/templates/agents/list.html` | modified | Row "runs" link uses `a.dagster_path`. |
| `ui/tests/test_api.py` | modified | Updated two stale assertions; added four tests (see below). |

## Diff Highlights

`ui/agents_store.py` — the nature decision, at the end of a successful `read_agent`:

```python
# An agent that declares an asset lives on Dagster's asset page, not the job page
# (asset wins for a both-kind agent — its job exists only to materialize the asset).
asset = managed.get("asset")
if isinstance(asset, str) and asset.strip():
    result["dagster_kind"] = "asset"
    result["dagster_path"] = dagster_asset_path(asset.strip())
    result["dagster_url"] = config.DAGSTER_URL + result["dagster_path"]
```

Parse-error/too-new files keep the job-link defaults set earlier in `read_agent` (nature unknown → historical behavior).

## Tests Added or Updated

- `test_edit_page_asset_agent_links_to_dagster_asset` — asset-only agent: `/assets/<key>` href, "Dagster asset" label, no dead job link.
- `test_edit_page_both_kind_agent_asset_wins` — `produces` + `job: true`: asset link wins (user's answer to open question 1).
- `test_edit_page_broken_file_falls_back_to_job_link` — unparsable file still renders with the job link.
- `test_agents_page_asset_agent_links_to_asset_page` — list row for the asset agent links to `/assets/...` (open question 2).
- `test_edit_page_renders_edit_form` — added "Dagster job" label assertion for the job-only fixture.
- `test_api_agents_lists_non_template_files` — `repo-librarian-agentbox` (asset-only) now asserts asset path/URL; added a job-only row check (`categorize-commits`) and `dagster_path` to the required row fields.
- `test_agents_page_dagster_links_use_code_location_path` — retargeted from `repo-librarian-agentbox` (now an asset agent) to job-only `categorize-commits`.

## Local Verification

- Commands run: `cd ui && ../.venv/bin/python -m pytest -q` → **297 passed** (was 293 before the fix; one interim failure was a too-loose substring assertion — `agent_repo_librarian_agentbox` is a prefix of the job-only `..._fable` agent's job name — fixed by pinning the href's closing quote).
- Manual checks: none — the Dagster asset route shape (`/assets/<key segments>`) is standard for the OSS webserver but was not clicked against the live instance; see Follow-ups.

## Deviations from Assessment

- The nature decision moved from the edit route in `main.py` into `read_agent` (`ui/agents_store.py`) so the list rows and the edit page share one source of truth — the assessment computed it in the route and would have duplicated the logic once the list page (open question 2, answered "yes") was included. Same behavior, one decision point.
- The list-row API field `dagster_url` now also reflects the asset page (it is derived from the same path). The spec-001 contract doc (`specs/001-agent-management-ui/contracts/http-api.md:60`) was left untouched — it is a merged-feature artifact already stale in other ways (predates the `/locations/...` job-path fix).
- Removed the now-dead `dagster_job_path` Jinja global registration in `ui/main.py` (no template references it after the change).

## Follow-ups

- Click one asset link against the live Dagster at http://10.0.0.100:3000 (e.g. edit page of `repo-librarian-agentbox` → should land on asset `repo-review/agentbox`) to confirm the `/assets/<key>` route shape on the deployed Dagster version.
- Optional: the list row's link text/title still say "runs" / "Open this agent's runs in Dagster", which is slightly off for an asset page (it shows materializations); left as-is to keep the change minimal.
- Optional: rename the `ax-job-link` element id if it ever bothers anyone; kept to avoid churn.
