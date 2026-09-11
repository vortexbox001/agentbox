# Bug Verification: Model field bypasses the custom dropdown; dropdown should size to its widest option

- **Slug**: model-dropdown-consistency
- **Tested**: 2026-09-11
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom no longer reproduces: on both the create page (codex harness) and a codex agent's edit page, the model field is a `<select class="ax-select">` enhanced into the shared `.ax-dropdown`, with zero `<datalist>` elements in the field. All fix behaviors (custom-id entry, per-harness validation, intrinsic widths, single-line panel options, the reveal-gap addendum) hold, and the full UI regression suite passes.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | Headless Chromium (DevTools protocol, fresh profile) against scratch uvicorn :8089; DOM audit of `/agents/new` with harness=codex and `/agents/repo-librarian-codex` (fixture with off-list `model: my-offlist-model`) | pass | `#f-model` is an enhanced select in `.ax-dropdown`; no datalist; assessment's step-3 symptom gone |
| Fix behaviors | `/tmp/bugassess-ui/verify.mjs` (11 browser checks) | pass | 11/11: codex options = blank + 3 suggestions + "Custom model id…"; arbitrary custom id accepted (no field error); claude-code custom id still regex-rejected; trigger narrower than grid cell, width == sizer width, stable across selection change; open panel width == trigger width with single-line options (scrollbar case included); off-list edit-page model maps to the custom entry pre-filled; long-option dropdown capped at container |
| Addendum (reveal gap) | Browser measurement on `/agents/new` and `/automation` | pass | custom-model input gap 8px, new-prompt panel gap 8px, automation select+cron still on one row |
| New / updated tests | `../.venv/bin/python -m pytest tests/test_ui_consistency.py -q` | pass | 5 passed, incl. `test_model_control_never_uses_a_native_datalist` |
| Regression suite | `cd ui && ../.venv/bin/python -m pytest -q` | pass | 298 passed in 3.36s |
| Lint / type-check | — | not-run | No JS/CSS lint or type-check tooling configured in this repo |

## Output Excerpts

Browser verification:

```
PASS  codex model is enhanced select
PASS  codex options = blank + suggestions + custom
...
PASS  dropdown capped at container width
ALL PASS
```

Addendum gap check: `{"modelGap":8,"promptGap":8,"sameRow":true} PASS`

Test suite: `298 passed in 3.36s`

## Residual Risks

- Verification ran in headless Chromium only; Firefox/Safari were not exercised. The mechanisms used (visually-hidden sizer, `width: max-content`, sibling-margin CSS) are standard, but the 16px classic-scrollbar allowance was calibrated against Chromium's 15px scrollbar — a platform with a wider scrollbar could still wrap a panel option by a pixel or two.
- The intrinsic-width default changes every page's dropdown geometry; only `/agents/new`, the codex edit page, and `/automation` were inspected (DOM measurements + screenshots). Other states (e.g. very narrow viewports) rely on the `max-width: 100%` cap, which was tested only via the prompt-file dropdown.
- The `allowed_tools`/`disallowed_tools` native datalists remain by explicit user decision (out of scope); the consistency test carves out `renderList` accordingly.

## Recommendation

Close the bug — verified end-to-end: the reproduction from the assessment was re-exercised in a real browser post-fix and no longer shows the symptom, the new regression guard passes, and the full suite (298 tests) is green.
