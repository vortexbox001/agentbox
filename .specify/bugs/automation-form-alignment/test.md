# Bug Verification: Automation page schedule-row alignment

- **Slug**: automation-form-alignment
- **Tested**: 2026-09-11
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom (schedule controls packing left at content width with no cross-row
alignment or structure) is gone: every schedule row renders as a fixed-track grid with the kind
label above the dropdown and constant-width, vertically aligned controls. Note the acceptance
target moved during the fix — the user revised the desired layout from "right-anchored at the
card edge" (the assessment's reading of the report) to "left-aligned, fields at fixed widths,
label above dropdown" — and this verification is against that final direction. No regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | Headless chromium (DevTools protocol) against scratch uvicorn :8089 serving copies of the real `agents/`/`prompts/` (13 agents, 14 schedule rows); geometry assertions via `Runtime.evaluate` (`/tmp/bugfix-align/verify.mjs`, exit 0) | pass | All 14 dropdowns share one left/right edge (289/449) at the row indent (card content starts ~273); all cron wraps share one right edge (749) vs card edge 1237 — aligned columns, fields not stretched; every label sits above and left-aligned with its dropdown |
| Mobile layout (SC-006) | Same session, viewport 400×800 | pass | Rows stack label → dropdown → cron; horizontal overflow 0 px; screenshot eyeballed |
| Badge placement | DOM query in same session | pass (structural) | No `.ax-badge--fallback` outside `.ax-automation-kind`; no fixture agent yields `fallback: true` on the installed Dagster, so only the "no stray badge" invariant was exercised |
| Screenshot review | `Page.captureScreenshot` at 1280×900 and 400×800 | pass | Desktop and phone both match the requested layout; per-agent grouping intact |
| Regression suite | `cd ui && ../.venv/bin/python -m pytest -q` | pass | 293 passed in 3.27s |
| Lint / type-check | — | not-run | No linter/type-checker configured for `ui/` in this repo |

## Output Excerpts

```
rows: 14
dropdown left edges (unique): 289
dropdown right edges (unique): 449
cron right edges (unique): 749
card left/right edge: 248 / 1237
label above + left-aligned with dropdown, all rows: true
left-anchored: true, fields not stretched to card edge: true
ALIGNMENT OK
phone horizontal overflow px: 0
verify exit: 0
```

```
293 passed in 3.27s
```

## Residual Risks

- The "partition fallback" badge path is untested with real data — no current agent yields
  `fallback: true` (it requires `AGENTBOX_PARTITION_FALLBACK=1` or a Dagster where `on_cron`
  cannot target the daily partition). Its placement inside the inline-flex label should wrap
  fine, but eyeball it when the fallback ever fires.
- Verification ran against a scratch uvicorn with `DAGSTER_URL` unreachable; the save/reload
  round-trip was not exercised in the browser (unchanged by this fix; covered by the pytest
  suite's API tests).
- Widths between the 640px breakpoint and full desktop were not screenshotted; the
  `minmax(min(16rem, 100%), 18rem)` cron track guards against overflow there by construction.

## Recommendation

Close the bug — verified end-to-end against the user's final layout direction (label above
dropdown, left-aligned fixed-width controls, aligned across rows, clean phone stacking), with
the ui regression suite green. The change is part of the uncommitted spec 006 work on branch
`006-explicit-asset-job` and should land with it.
