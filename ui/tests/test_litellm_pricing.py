"""Regression guard for bug kimi-missing-litellm-pricing.

LiteLLM computes cost by multiplying token counts by a per-token price it holds for the
model, and exposes it via the ``x-litellm-response-cost`` header the api/pi runners read.
It has that price built in for first-party providers (Anthropic ``cheap``/``smart``/``opus``),
but NOT for a custom OpenAI-compatible endpoint (a model carrying its own ``api_base``, like
the Moonshot/Kimi models). Without explicit ``*_cost_per_token`` fields such a model reports
``cost_usd=None`` (the original bug). This test fails if a custom-endpoint model is added
without pricing, so the gap can't ship silently again.
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "litellm" / "config.yaml"


def _model_list():
    data = yaml.safe_load(CONFIG.read_text()) or {}
    return data.get("model_list", [])


def test_custom_endpoint_models_declare_pricing():
    """Every model with a custom api_base must declare input+output per-token cost.

    First-party models (no api_base) are priced by LiteLLM's built-in table and are
    intentionally exempt.
    """
    missing = []
    for m in _model_list():
        params = m.get("litellm_params", {}) or {}
        if not params.get("api_base"):
            continue  # first-party provider — LiteLLM prices it natively
        if not (params.get("input_cost_per_token") and params.get("output_cost_per_token")):
            missing.append(m.get("model_name"))
    assert not missing, (
        f"custom-endpoint models missing per-token pricing (will report cost_usd=None): {missing}"
    )


def test_kimi_models_priced():
    """The two Kimi aliases specifically carry pricing (the models from the bug report)."""
    priced = {
        m["model_name"]
        for m in _model_list()
        if (m.get("litellm_params") or {}).get("input_cost_per_token")
    }
    assert {"kimi", "kimi-k3"} <= priced, priced
