# Bug Assessment: Kimi-backed runs report cost_usd=None (no LiteLLM pricing)

- **Slug**: kimi-missing-litellm-pricing
- **Created**: 2026-09-12
- **Source**: pasted text + run id `3751ef61-76e2-4bf9-a642-7663e77bc9d5` (`agent_hello_api_kimi3`)
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim or summarized)

> The API + Kimi agent should have but didn't return a real cost:
> `result: status=ok turns=1 tokens_in/out=172/346 cost_usd=None files_written=1`
> `/runs/3751ef61-76e2-4bf9-a642-7663e77bc9d5`

The run succeeded and reported real token counts, but `cost_usd` is `None`. Per the spec-007
report contract (SC-001), `cost_usd` is expected to be a real number for the **api** (and **pi**)
harnesses, and `null` only for the subscription harnesses (claude-code/codex).

## Symptom

- **Observed**: an api-harness run against a Kimi model (`agent_hello_api_kimi3`, model alias
  `kimi-k3`) reports `cost_usd=None` despite `status=ok` and real token counts.
- **Expected**: `cost_usd` is a real dollar figure, as it is for Anthropic-backed api runs (e.g.
  `agent_verify_api` on alias `cheap` reported `cost_usd=9.2e-05`).

## Reproduction

1. Run any api-harness agent whose model alias resolves to a Kimi model (`kimi` or `kimi-k3`) —
   e.g. launch job `agent_hello_api_kimi3`.
2. Read the result line / run metadata.

Result: `status=ok`, real `tokens_in/out`, but `cost_usd=None`. Anthropic-backed api runs on the
same code path report a real cost, which isolates the difference to the model, not the harness.

## Suspected Code Paths

- `litellm/config.yaml:16-25` — the `kimi` and `kimi-k3` model blocks route to
  `openai/kimi-k2.7-code` / `openai/kimi-k3` via `api_base: https://api.moonshot.ai/v1` with **no
  `input_cost_per_token` / `output_cost_per_token`** (confirmed: no pricing keys exist anywhere in
  the file). LiteLLM has no built-in price for these custom models, so it cannot compute a cost.
  **This is the defect.**
- `images/agent-python/runner.py:19-42` (`report_from_response`) — cost is taken from the
  `x-litellm-response-cost` response header; when the header is absent/empty, `cost_usd` is
  `None`. The runner is behaving **correctly** given no cost header — it is not the bug.
- `images/agent-python/runner.py:62-65` — reads `resp.headers.get("x-litellm-response-cost")`;
  LiteLLM omits (or zeroes) this header for models it cannot price.
- Same class applies to the **pi** harness (also calls LiteLLM and derives cost the same way), so
  any pi+Kimi agent has the identical gap. `images/agent-pi/entrypoint.sh` mirrors the Kimi alias
  list (models.json) but carries no pricing either.

## Root Cause Hypothesis

**High confidence.** LiteLLM computes `x-litellm-response-cost` only for models it has pricing
for — either built-in (Anthropic models, hence `cheap`/`smart`/`opus` work) or via explicit
`input_cost_per_token`/`output_cost_per_token` in `litellm_params`/`model_info`. The Kimi models
are third-party OpenAI-compatible endpoints (`openai/kimi-*` at `api.moonshot.ai`) with no pricing
configured, so LiteLLM emits no cost header and the api runner reports `cost_usd=None`. Not an
agentbox code bug — a LiteLLM configuration gap.

## Proposed Remediation

**Preferred**: add per-token pricing to each Kimi model in `litellm/config.yaml` so LiteLLM can
compute cost. LiteLLM accepts cost fields under `litellm_params` (or `model_info`), e.g.:

```yaml
  - model_name: kimi
    litellm_params:
      model: openai/kimi-k2.7-code
      api_base: https://api.moonshot.ai/v1
      api_key: os.environ/KIMI_API_KEY
      input_cost_per_token:  <USD per input token>   # from Moonshot's published pricing
      output_cost_per_token: <USD per output token>
  - model_name: kimi-k3
    litellm_params:
      model: openai/kimi-k3
      api_base: https://api.moonshot.ai/v1
      api_key: os.environ/KIMI_API_KEY
      input_cost_per_token:  <USD per input token>
      output_cost_per_token: <USD per output token>
```

After editing, restart/reload LiteLLM (`docker compose up -d litellm`) and re-run
`agent_hello_api_kimi3`; `cost_usd` should be a real number. The exact rates must come from
Moonshot's current pricing (see Open Questions) — Kimi K2.7 and K3 are priced differently, and
Moonshot bills per 1M tokens, so convert to per-token (or use LiteLLM's
`input_cost_per_million_tokens` fields if that form is preferred).

**Alternatives**:
- Supply a custom price map to LiteLLM (`model_prices_and_context_window`-style JSON via
  `litellm_settings`) instead of inlining per model. More scalable if many custom models are
  added; heavier for two models.
- Accept `cost_usd=None` for models without pricing and relax the SC-001 expectation for
  third-party models. Cheapest, but loses cost tracking for Kimi and contradicts the report
  contract — not recommended.

**Files likely to change**:
- `litellm/config.yaml` (add pricing to the two Kimi blocks)
- Possibly `ui/tests/golden/*.yaml` / config docs if pricing presence is asserted anywhere (none
  known today — verify).

**Tests to add or update**:
- The pricing itself can't be unit-tested against the live Moonshot API cheaply. A cheap guard: a
  config test asserting every non-subscription (`api`/`pi`-reachable) model in `litellm/config.yaml`
  declares cost fields, so a future custom model can't silently ship without pricing.
- Optionally an end-to-end check (bug-test): launch `agent_hello_api_kimi3` and assert
  `cost_usd` is a positive number.

## Risks & Considerations

- **Pricing accuracy/drift**: hardcoded rates go stale when Moonshot changes prices; the computed
  cost is only as correct as the configured numbers. Add a comment with the source/date.
- **No functional impact**: runs still succeed; only the cost metadata is missing — hence
  medium, not high.
- **LiteLLM restart required**: config changes need a LiteLLM reload/restart to take effect
  (unlike the orchestrator code-location reload).
- **Header form**: confirm LiteLLM emits `x-litellm-response-cost` (not just an internal spend
  log) once pricing is set; the runner reads only that header.

## Open Questions

- [NEEDS CLARIFICATION: current Moonshot per-token (or per-1M) input/output prices for
  `kimi-k2.7-code` and `kimi-k3` — needed to fill in the config values. Do not guess these.]
- [NEEDS CLARIFICATION: should the pi harness's Kimi path be verified/fixed in the same change?
  It shares the LiteLLM pricing gap.]
- [NEEDS CLARIFICATION: confirm whether LiteLLM returned an empty/absent header vs `0.0` for this
  run — both yield the symptom, but it affects whether a config guard should also reject `0`.]
