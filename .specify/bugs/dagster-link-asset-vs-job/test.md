# Bug Verification: Agent edit page "Dagster job" link ignores asset nature

- **Slug**: dagster-link-asset-vs-job
- **Tested**: 2026-09-11
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom no longer reproduces: on a live scratch UI serving the real `agents/` directory, the asset-only agent's edit page links to `/assets/repo-review/agentbox` labeled "Dagster asset", job-only agents keep their job links, and the list rows follow the same rule. Live Dagster (GraphQL, read-only) confirms the premise and the fix target: asset `repo-review/agentbox` **exists** while job `agent_repo_librarian_agentbox` **does not** — so the pre-fix link was genuinely dead and the new one points at a real page. No regressions: full UI suite green.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix), edit page | scratch `uvicorn main:app --port 8899` against repo `agents/`; `curl /agents/repo-librarian-agentbox` | pass | `href=".../assets/repo-review/agentbox"`, label "Dagster asset", no job href |
| Reproduction (post-fix), job-only edit page | `curl /agents/categorize-commits` | pass | `href=".../locations/definitions.py/jobs/agent_categorize_commits"`, label "Dagster job" |
| Reproduction (post-fix), list page | `curl /agents`, extract all Dagster hrefs | pass | 3 asset agents → `/assets/<key>` (incl. key ≠ stem: `repo-review/list-commits`), 10 job agents → job paths |
| Link targets exist in live Dagster | GraphQL `assetOrError` / `pipelineOrError` at `http://localhost:3000/graphql` | pass | Asset `repo-review/agentbox` exists; job `agent_repo_librarian_agentbox` does not (old link was dead); workspace job list matches the UI's job-linked agents |
| New / updated tests | `../.venv/bin/python -m pytest -q tests/test_api.py -k "dagster or asset_agent or both_kind or falls_back or lists_non_template or renders_edit_form"` | pass | 10 passed (asset-only, both-kind asset-wins, broken-file fallback, list page, API rows) |
| Regression suite | `cd ui && ../.venv/bin/python -m pytest -q` (×3) | pass | 298 passed, deterministic across three runs |
| Lint / type-check | — | not-run | Project has no lint/type-check configuration (no pyproject/setup.cfg/ruff config; none in requirements) |

## Output Excerpts

```
=== edit page: asset-only agent ===
Dagster asset
href="http://localhost:3000/assets/repo-review/agentbox"
=== edit page: job-only agent ===
Dagster job
href="http://localhost:3000/locations/definitions.py/jobs/agent_categorize_commits"
```

```
{"assetOrError":{"__typename":"Asset"},
 "missing (agent_repo_librarian_agentbox)":{"__typename":"PipelineNotFoundError"}}
```

```
298 passed in 3.47s
```

## Residual Risks

- The `/assets/<key>` page was validated by asset existence via GraphQL plus href inspection, not by rendering the Dagster SPA in a browser (the webserver returns the SPA shell for any path, so an HTTP probe proves nothing either way). Risk is minimal: `/assets/<key path>` is the OSS webserver's canonical asset route, and the asset key exists.
- One earlier fix-phase run reported "297 passed" where three later runs deterministically collect and pass 298 with only the intended files changed (`git diff`). Unexplained one-off reading; no test is environment- or time-conditional apart from a root-only `skipif` that does not apply here.
- The deployed UI container (if running) still serves pre-fix code until rebuilt/restarted (`docker compose build && docker compose up -d`); verification ran against the working tree.

## Recommendation

Close the bug — verified end-to-end: automated tests, live page rendering against the real agent definitions, and live-Dagster confirmation that the new link targets exist while the old asset-agent job links were dead. Deploy by rebuilding the UI container when convenient.
