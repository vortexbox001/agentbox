# Bug Verification: Dagster link base URL missing port (and malformed DAGSTER_PUBLIC_URL)

- **Slug**: dagster-link-base-url
- **Tested**: 2026-09-15
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom no longer reproduces: rendering the UI with the exact malformed host
value (`DAGSTER_PUBLIC_URL=http://http://10.0.0.100`) now emits `http://10.0.0.100:3000` in
both the sidebar "Dagster" link and every per-agent "runs" link. New unit tests and the
full UI suite pass with no regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) — sidebar link | TestClient GET `/agents` with `DAGSTER_PUBLIC_URL=http://http://10.0.0.100` | pass | `id="ax-dagster-link"` href = `http://10.0.0.100:3000` (was `http://http://10.0.0.100`) |
| Reproduction (post-fix) — runs links | TestClient GET `/agents`, inspect row "runs" hrefs | pass | all start `http://10.0.0.100:3000/…` |
| New / updated tests | `pytest tests/test_dagster_url.py -q` | pass | 8 passed |
| Regression suite | `pytest -q` (full UI suite) | pass | 380 passed |
| Lint / type-check | — | not-run | project has no configured lint/type-check step for `ui/` |

## Output Excerpts

```
# tests/test_dagster_url.py
8 passed in 0.59s
# full suite
380 passed in 2.78s

# end-to-end reproduction
HTTP 200
sidebar Dagster href: http://10.0.0.100:3000
REPRODUCTION PASS: malformed value normalized end-to-end
sample runs hrefs: ['http://10.0.0.100:3000/locations/definitions.py/jobs/agent_categorize_commits', ...]
RUNS LINKS PASS
```

## Residual Risks

- Verified at the app/render layer via TestClient, not against the live container. The fix
  additionally depends on a runtime redeploy so the container picks up the new
  `DAGSTER_HOST_PORT` env and the corrected `.env` (`docker compose up -d ui`); that
  redeploy was not performed here.
- An explicit-port `DAGSTER_PUBLIC_URL` behind a proxy (e.g. `:443`) is covered by unit
  test but not exercised against a real proxy.

## Recommendation

Close the bug — verified end-to-end at the render layer with the exact reported malformed
value, plus unit and full-suite coverage. After merge, run `docker compose up -d ui` on the
host and click-through the sidebar and a "runs" link to confirm the live container serves
`http://10.0.0.100:3000/…`.
