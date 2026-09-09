"""Foundational API/route tests: shell routes, schema, Dagster, storage errors."""
import asyncio
import glob
import json
import os
import re

import pytest


UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Pages & redirects ───────────────────────────────────
def test_root_redirects_to_agents(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/agents"


def test_design_system_redirects_with_trailing_slash(client):
    resp = client.get("/design-system", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/design-system/"


def test_design_system_index_is_html(client):
    resp = client.get("/design-system/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "./support.js" in resp.text


def test_design_system_assets_served(client):
    for path in ("/design-system/support.js", "/design-system/archon-tokens.css"):
        assert client.get(path).status_code == 200


def test_agents_page_renders_shell(client):
    resp = client.get("/agents")
    assert resp.status_code == 200
    assert "ax-sidebar" in resp.text
    assert "agentbox" in resp.text


# ── Schema ──────────────────────────────────────────────
def test_api_schema_shape(client):
    data = client.get("/api/schema").json()
    assert {"sections", "fields", "harnesses", "litellm_aliases", "prompts"} <= set(data)
    assert len(data["harnesses"]) == 4
    assert isinstance(data["prompts"], list)
    assert "repo-librarian.md" in data["prompts"]
    assert "cheap" in data["litellm_aliases"]


# ── Dagster (stubbed) ───────────────────────────────────
def test_dagster_reload_uses_stub(client, dagster_stub):
    dagster_stub.reload_result = {"ok": True, "message": "Workspace reloaded"}
    data = client.post("/api/dagster/reload").json()
    assert data == {"ok": True, "message": "Workspace reloaded"}


def test_dagster_reload_reports_failure(client, dagster_stub):
    dagster_stub.reload_result = {"ok": False, "message": "boom"}
    resp = client.post("/api/dagster/reload")
    assert resp.status_code == 200          # always 200; outcome is data
    assert resp.json() == {"ok": False, "message": "boom"}


def test_dagster_status_uses_stub(client, dagster_stub):
    data = client.get("/api/dagster/status").json()
    assert set(data) == {"url", "reachable"}


# ── No navigation link to the design system (R13) ───────
def test_base_page_has_no_design_system_nav_link(client):
    html = client.get("/agents").text
    # the tokens stylesheet is loaded via <link>, but no <a> navigates there
    assert not re.search(r'<a\b[^>]*href="/design-system', html)


# ── Token discipline (FR-015) ───────────────────────────
_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"\brgba?\(")
_FONT_FAMILY = re.compile(r"font-family")


def _token_discipline_files():
    files = [os.path.join(UI_DIR, "static", "app.css")]
    files += glob.glob(os.path.join(UI_DIR, "templates", "**", "*.html"), recursive=True)
    return files


@pytest.mark.parametrize("path", _token_discipline_files())
def test_no_literal_colours_or_fonts(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert not _HEX.search(text), f"literal hex colour in {path}"
    assert not _RGB.search(text), f"literal rgb() colour in {path}"
    assert not _FONT_FAMILY.search(text), f"literal font-family in {path}"


# ── Storage-error mapping to 507 (T054) ─────────────────
def test_storage_error_maps_to_507():
    import main
    from agents_store import StorageError

    exc = StorageError("write", "agents/x.yaml", OSError(13, "Permission denied"))
    resp = asyncio.new_event_loop().run_until_complete(main._storage_error(None, exc))
    assert resp.status_code == 507
    body = json.loads(resp.body)
    assert body["error"] == "storage"
    assert "cannot write agents/x.yaml" in body["message"]


# ── User Story 1: View Existing Agents (T023) ───────────
def _write(dir_path, name, text):
    p = dir_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_api_agents_lists_non_template_files(client):
    data = client.get("/api/agents").json()
    assert set(data) == {"agents", "templates"}

    names = {a["name"] for a in data["agents"]}
    assert "repo-librarian-agentbox" in names
    # Templates (leading underscore) never appear as agents.
    assert not any(a["file"].startswith("_") for a in data["agents"])

    required = {"name", "file", "enabled", "harness", "model", "schedule",
                "dagster_job", "dagster_url", "parse_error", "name_mismatch"}
    for a in data["agents"]:
        assert required <= set(a)

    row = next(a for a in data["agents"] if a["name"] == "repo-librarian-agentbox")
    assert row["harness"] == "claude-code"
    assert row["dagster_job"] == "agent_repo_librarian_agentbox"
    assert row["dagster_url"].endswith("/jobs/agent_repo_librarian_agentbox")
    assert row["parse_error"] is None
    assert row["name_mismatch"] is False


def test_api_agents_lists_templates_separately(client):
    data = client.get("/api/agents").json()
    template_files = {t["file"] for t in data["templates"]}
    assert "_template-pi.yaml" in template_files
    for t in data["templates"]:
        assert set(t) == {"file", "harness"}
        assert t["file"].startswith("_")


def test_api_agents_reports_broken_file(client, tmp_agents):
    _write(tmp_agents, "broken.yaml", "harness: [unclosed\n")
    data = client.get("/api/agents").json()
    row = next(a for a in data["agents"] if a["file"] == "broken.yaml")
    assert row["parse_error"] is not None
    for field in ("enabled", "harness", "model", "schedule"):
        assert row[field] is None


def test_api_agents_marks_newer_schema_uneditable(client, tmp_agents):
    _write(tmp_agents, "futuristic.yaml",
           "# agentbox-schema: 9999\nname: futuristic\nharness: pi\n")
    data = client.get("/api/agents").json()
    row = next(a for a in data["agents"] if a["file"] == "futuristic.yaml")
    assert row["editable"] is False
    assert row["parse_error"] is not None
    assert "9999" in row["parse_error"]


def test_api_agents_empty_directory(client, tmp_agents):
    for f in tmp_agents.glob("*.yaml"):
        f.unlink()
    data = client.get("/api/agents").json()
    assert data == {"agents": [], "templates": []}


def test_api_agents_under_one_second_with_50_files(client, tmp_agents):
    import time
    for f in tmp_agents.glob("*.yaml"):
        f.unlink()
    for i in range(50):
        _write(tmp_agents, f"gen-{i:02d}.yaml",
               f"name: gen-{i:02d}\nharness: pi\nprompt_file: p.md\n")
    start = time.perf_counter()
    data = client.get("/api/agents").json()
    elapsed = time.perf_counter() - start
    assert len(data["agents"]) == 50
    assert elapsed < 1.0, f"listing 50 agents took {elapsed:.3f}s (SC-007)"


def test_agents_page_links_each_agent_and_new(client):
    html = client.get("/agents").text
    assert 'href="/agents/repo-librarian-agentbox"' in html
    assert 'href="/agents/new"' in html          # "New agent" link
    # Template files are not rendered as rows.
    assert "_template-pi" not in html


def test_agents_page_empty_state(client, tmp_agents):
    for f in tmp_agents.glob("*.yaml"):
        f.unlink()
    html = client.get("/agents").text
    assert "ax-empty" in html
    assert 'href="/agents/new"' in html          # create-first call to action
