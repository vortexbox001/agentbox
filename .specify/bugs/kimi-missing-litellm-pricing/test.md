# Bug Verification: Kimi models declare LiteLLM per-token pricing

- **Slug**: kimi-missing-litellm-pricing
- **Tested**: 2026-09-12
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces. After adding Moonshot pricing to `litellm/config.yaml` and
restarting the LiteLLM container, a live `agent_hello_api_kimi3` run reported a real
`cost_usd=0.007266` (was `None`). The value matches the configured rates exactly, confirming
LiteLLM is now computing cost for the Kimi model. Regression tests and the full UI suite pass.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| New / updated tests | `cd ui && ../.venv/bin/python -m pytest tests/test_litellm_pricing.py -q` | pass | 2 passed (custom-endpoint pricing guard + kimi-priced) |
| Regression suite | `cd ui && ../.venv/bin/python -m pytest -q` | pass | 300 passed; config parses, no alias/golden breakage |
| Config reload | `docker compose restart litellm` | pass | Container `Up`; logs show "Application startup complete", no errors/traceback loading the priced config |
| Reproduction (post-fix) | Launched `agent_hello_api_kimi3` (run `b9f0d397-1878-4f58-addc-f6df99820ab9`) | pass | `SUCCESS`; `cost_usd=0.007266` (real number, was `None`) |
| Cost-math sanity | Hand-check against configured rates | pass | kimi-k3: 172×$3/1M + 450×$15/1M = 0.000516 + 0.006750 = **0.007266** — exact match |

## Output Excerpts

Pre-fix (run `3751ef61`, from the assessment):
```
result: status=ok turns=1 tokens_in/out=172/346 cost_usd=None files_written=1
```

Post-fix (run `b9f0d397-1878-4f58-addc-f6df99820ab9`):
```
[pipes] external process successfully opened dagster pipes.
result: status=ok turns=1 tokens_in/out=172/450 cost_usd=0.007266000000000001 files_written=1
```

## Residual Risks

- **Only `kimi-k3` was exercised live** (via `agent_hello_api_kimi3`). The `kimi` (k2.7-code)
  alias is priced in config and covered by the guard test, but wasn't run end-to-end.
- **pi harness not run.** pi+Kimi uses the same LiteLLM config path, so this fix covers it, but a
  pi+Kimi run would confirm.
- **Cache-hit tier unverified.** This run's input was a cache miss, so it exercised
  `input_cost_per_token` (matched exactly); `cache_read_input_token_cost` was not hit. If the
  installed LiteLLM ignores it for this provider, cached input falls back to the cache-miss rate —
  over-counts slightly, never under-counts, never null.
- **Pricing drift.** Rates are hardcoded from a 2026-09-12 fetch; the computed cost is only as
  accurate as those numbers. Source URL + date are in the config comment.

## Recommendation

Close the bug — verified end-to-end. The Kimi model now returns a real, arithmetically-correct
`cost_usd`, the config reloaded cleanly, and a regression guard blocks any future custom-endpoint
model from shipping without pricing. Optionally spot-check the `kimi` (k2.7-code) alias and a
pi+Kimi run for completeness.
