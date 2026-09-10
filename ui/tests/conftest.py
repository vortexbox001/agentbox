"""Shared pytest fixtures for the agentbox UI test suite.

Every fixture points the app's file stores at temporary copies of the real
``agents/``, ``prompts/``, and ``litellm/config.yaml`` so tests never touch the
repository. Imports of app modules (``config``, ``main``, ``dagster``) are done
lazily inside fixtures: those modules are built across later phases, so the suite
stays collectable before they exist.
"""
import shutil
from pathlib import Path

import pytest

# Repository root: ui/tests/conftest.py -> ui/ -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_agents(tmp_path):
    """A writable copy of every repo agents/*.yaml in a temp directory."""
    dest = tmp_path / "agents"
    dest.mkdir()
    src = REPO_ROOT / "agents"
    if src.is_dir():
        for f in src.glob("*.yaml"):
            shutil.copy(f, dest / f.name)
    return dest


@pytest.fixture
def tmp_prompts(tmp_path):
    """A writable copy of every repo prompts/*.md in a temp directory."""
    dest = tmp_path / "prompts"
    dest.mkdir()
    src = REPO_ROOT / "prompts"
    if src.is_dir():
        for f in src.glob("*.md"):
            shutil.copy(f, dest / f.name)
    return dest


@pytest.fixture
def tmp_automation(tmp_path):
    """A writable, initially-empty automation/ dir in a temp directory (spec 005)."""
    dest = tmp_path / "automation"
    dest.mkdir()
    return dest


@pytest.fixture
def litellm_cfg(tmp_path):
    """A copy of the repo litellm/config.yaml in a temp directory."""
    dest = tmp_path / "config.yaml"
    src = REPO_ROOT / "litellm" / "config.yaml"
    if src.is_file():
        shutil.copy(src, dest)
    return dest


@pytest.fixture
def settings(monkeypatch, tmp_agents, tmp_prompts, litellm_cfg, tmp_automation):
    """Point ui/config.py at the temp stores for the duration of a test."""
    import config

    monkeypatch.setattr(config, "AGENTS_DIR", str(tmp_agents))
    monkeypatch.setattr(config, "PROMPTS_DIR", str(tmp_prompts))
    monkeypatch.setattr(config, "LITELLM_CONFIG", str(litellm_cfg))
    monkeypatch.setattr(config, "AUTOMATION_DIR", str(tmp_automation))
    return config


@pytest.fixture
def client(settings):
    """A FastAPI TestClient bound to the app, with stores pointed at temp dirs."""
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)


@pytest.fixture
def dagster_stub(monkeypatch):
    """Replace the Dagster reload/status calls with canned outcomes.

    Returns a small object whose ``reload_result`` / ``status_result`` attributes
    a test can set before acting; defaults describe a healthy, reachable Dagster.
    """
    import dagster

    class Stub:
        reload_result = {"ok": True, "message": "Workspace reloaded"}
        status_result = {"url": "http://dagster-test:3000", "reachable": True}

    stub = Stub()

    async def fake_reload():
        return stub.reload_result

    async def fake_status():
        return stub.status_result

    monkeypatch.setattr(dagster, "reload", fake_reload)
    monkeypatch.setattr(dagster, "status", fake_status)
    return stub
