"""Tests for litellm/generate.py — template+overlay merge and the missing-key guard.

Contract: specs/010-file-layout-overhaul/contracts/litellm-generator.md §4.
"""
import textwrap
from pathlib import Path

import pytest
import yaml

import generate


TEMPLATE = textwrap.dedent(
    """
    model_list:
      - model_name: cheap
      - model_name: smart
      - model_name: kimi
    litellm_settings:
      drop_params: true
    general_settings:
      master_key: os.environ/LITELLM_MASTER_KEY
    """
)

OVERLAY = textwrap.dedent(
    """
    model_list:
      - model_name: cheap
        litellm_params:
          model: anthropic/claude-haiku-4-5-20251001
          api_key: os.environ/ANTHROPIC_API_KEY
      - model_name: smart
        litellm_params:
          model: anthropic/claude-sonnet-5
          api_key: os.environ/ANTHROPIC_API_KEY
      - model_name: kimi
        litellm_params:
          model: openai/kimi-k2.7-code
          api_base: https://api.moonshot.ai/v1
          api_key: os.environ/KIMI_API_KEY
          input_cost_per_token: 0.00000095
    """
)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Point generate at a fixture template + a config root holding the overlay."""
    template = tmp_path / "config.template.yaml"
    template.write_text(TEMPLATE)
    monkeypatch.setattr(generate, "TEMPLATE", template)

    cfg_root = tmp_path / "config"
    cfg_root.mkdir()
    monkeypatch.setenv("AGENTBOX_CONFIG", str(cfg_root))
    (cfg_root / "litellm.overlay.yaml").write_text(OVERLAY)
    return cfg_root


def _by_name(model_list):
    return {m["model_name"]: m for m in model_list}


def test_rendered_binds_each_tier_to_overlay_provider(wired, monkeypatch):
    """R-LL-1: every template tier is bound to the overlay's provider/model on render."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-xxx")

    assert generate.main() == 0

    rendered = wired / "litellm.rendered.yaml"
    assert rendered.exists()
    models = _by_name(yaml.safe_load(rendered.read_text())["model_list"])
    # Product tier names preserved; overlay supplied the concrete provider model.
    assert set(models) == {"cheap", "smart", "kimi"}
    assert models["cheap"]["litellm_params"]["model"] == "anthropic/claude-haiku-4-5-20251001"
    assert models["kimi"]["litellm_params"]["api_base"] == "https://api.moonshot.ai/v1"
    assert models["kimi"]["litellm_params"]["input_cost_per_token"] == 0.00000095


def test_os_environ_refs_preserved_and_never_expanded(wired, monkeypatch):
    """Constitution III: api_key stays an os.environ/<NAME> ref; the secret is never written."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET-VALUE")
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-SECRET-VALUE")

    assert generate.main() == 0

    text = (wired / "litellm.rendered.yaml").read_text()
    assert "os.environ/ANTHROPIC_API_KEY" in text
    assert "os.environ/KIMI_API_KEY" in text
    assert "SECRET-VALUE" not in text


def test_missing_key_exits_nonzero_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """R-LL-2: an api_key referencing an absent env var fails render — non-zero, no file."""
    template = tmp_path / "config.template.yaml"
    template.write_text("model_list:\n  - model_name: cheap\n")
    monkeypatch.setattr(generate, "TEMPLATE", template)

    cfg_root = tmp_path / "config"
    cfg_root.mkdir()
    monkeypatch.setenv("AGENTBOX_CONFIG", str(cfg_root))
    (cfg_root / "litellm.overlay.yaml").write_text(
        "model_list:\n"
        "  - model_name: cheap\n"
        "    litellm_params:\n"
        "      model: anthropic/claude-haiku-4-5-20251001\n"
        "      api_key: os.environ/MISSING_KEY\n"
    )
    monkeypatch.delenv("MISSING_KEY", raising=False)

    rc = generate.main()
    assert rc != 0
    assert "MISSING_KEY" in capsys.readouterr().err
    assert not (cfg_root / "litellm.rendered.yaml").exists()


def test_missing_overlay_exits_nonzero(tmp_path, monkeypatch, capsys):
    """No overlay in the config root → clear non-zero failure, nothing written."""
    template = tmp_path / "config.template.yaml"
    template.write_text("model_list:\n  - model_name: cheap\n")
    monkeypatch.setattr(generate, "TEMPLATE", template)

    cfg_root = tmp_path / "config"
    cfg_root.mkdir()
    monkeypatch.setenv("AGENTBOX_CONFIG", str(cfg_root))

    assert generate.main() != 0
    assert "overlay" in capsys.readouterr().err.lower()
    assert not (cfg_root / "litellm.rendered.yaml").exists()
