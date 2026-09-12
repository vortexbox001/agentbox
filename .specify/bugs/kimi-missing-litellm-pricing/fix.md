# Bug Fix: Kimi models declare LiteLLM per-token pricing

- **Slug**: kimi-missing-litellm-pricing
- **Fixed**: 2026-09-12
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The Kimi models routed to Moonshot (`openai/kimi-*` with a custom `api_base`) had no pricing, so
LiteLLM couldn't compute a cost and emitted no `x-litellm-response-cost` header, making api/pi
runs report `cost_usd=None`. Added Moonshot's published per-token rates to both Kimi blocks in
`litellm/config.yaml`, plus a regression test that fails if any custom-endpoint model ships
without pricing.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `litellm/config.yaml` | modified | Added `input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost` to `kimi` and `kimi-k3`, with a source/date comment. Rates from the Kimi pricing page (fetched 2026-09-12), converted USD-per-1M ÷ 1e6. |
| `ui/tests/test_litellm_pricing.py` | added tests | Guards that every custom-endpoint (`api_base`) model declares per-token cost, and that the two Kimi aliases are priced. |

## Diff Highlights

```yaml
  - model_name: kimi
    litellm_params:
      model: openai/kimi-k2.7-code
      api_base: https://api.moonshot.ai/v1
      api_key: os.environ/KIMI_API_KEY
      input_cost_per_token: 0.00000095          # $0.95 / 1M (cache miss)
      output_cost_per_token: 0.000004           # $4.00 / 1M
      cache_read_input_token_cost: 0.00000019   # $0.19 / 1M (cache hit)
  - model_name: kimi-k3
    litellm_params:
      model: openai/kimi-k3
      ...
      input_cost_per_token: 0.000003            # $3.00 / 1M (cache miss)
      output_cost_per_token: 0.000015           # $15.00 / 1M
      cache_read_input_token_cost: 0.0000003    # $0.30 / 1M (cache hit)
```

## Tests Added or Updated

- `ui/tests/test_litellm_pricing.py::test_custom_endpoint_models_declare_pricing` — every model
  with a custom `api_base` must declare `input_cost_per_token` + `output_cost_per_token`
  (first-party providers with no `api_base` are exempt — LiteLLM prices them natively). This is
  the cheapest check that would have caught the bug and blocks future custom models from shipping
  unpriced.
- `ui/tests/test_litellm_pricing.py::test_kimi_models_priced` — asserts `kimi` and `kimi-k3`
  specifically carry pricing.

## Local Verification

- `cd ui && ../.venv/bin/python -m pytest tests/test_litellm_pricing.py -q` → **2 passed**.
- `cd ui && ../.venv/bin/python -m pytest -q` → **300 passed** (full UI suite; config parses, no
  alias/golden breakage).
- **Not yet done** (bug-test's job): reload LiteLLM (`docker compose up -d litellm`) and re-run
  `agent_hello_api_kimi3`, asserting `cost_usd` is now a real positive number. Config changes need
  a LiteLLM restart to take effect (unlike the orchestrator code-location reload).

## Deviations from Assessment

None. Applied the preferred remediation (per-model pricing in `litellm/config.yaml`) and the
proposed config regression guard. The assessment's open question on exact rates was resolved from
the Kimi pricing page the user supplied; added the cache-hit tier
(`cache_read_input_token_cost`) as well so cached input isn't over-counted.

## Follow-ups

- **Reload required**: `docker compose up -d litellm` (or restart the litellm container) before
  the fix takes effect on live runs.
- **Pricing drift**: the rates are hardcoded from a 2026-09-12 fetch; revisit if Moonshot changes
  pricing. The source URL + date are in the config comment.
- **Verify pi harness**: pi+Kimi shares the same LiteLLM path and is covered by this config fix,
  but wasn't run — a pi+Kimi run would confirm.
- **Confirm `cache_read_input_token_cost`** is honored for this OpenAI-compatible provider in the
  installed LiteLLM version; if not, cached input falls back to the cache-miss rate (slightly
  over-counts, never under-counts). Cost is still non-null either way.
