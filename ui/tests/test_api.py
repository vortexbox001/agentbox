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
    # The document loads its assets by relative path so they resolve under the mount.
    assert "./support.js" in resp.text
    assert "./archon-tokens.css" in resp.text


def test_design_system_assets_served(client):
    for path in ("/design-system/support.js", "/design-system/archon-tokens.css"):
        assert client.get(path).status_code == 200


def test_design_system_prototype_served_with_space_in_name(client):
    # A filename containing a space must resolve through the static mount (US7).
    resp = client.get("/design-system/Archon%20Prototype.dc.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_agents_page_has_no_design_system_nav_anchor(client):
    # The design system is a developer reference: the tokens stylesheet loads via
    # <link>, but no <a> navigates there from the app (US7, R13).
    html = client.get("/agents").text
    assert not re.search(r'<a\b[^>]*href="/design-system', html)


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


def test_api_schema_carries_produces(client):
    # FR-013: /api/schema drives the form; the Produces card is a runs-group section
    # with the asset/partition fields, and the version is 2.
    data = client.get("/api/schema").json()
    assert data["schema_version"] == 2
    assert {"id": "produces", "label": "Produces", "group": "runs"} in data["sections"]
    by_id = {f["id"]: f for f in data["fields"]}
    assert by_id["asset"]["section"] == "produces"
    assert by_id["partition"]["choices"] == ["none", "daily"]
    # every harness renders both fields (so the card shows for each)
    for h in data["harnesses"]:
        assert "asset" in h["fields"] and "partition" in h["fields"]


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
    assert row["dagster_url"].endswith("/locations/definitions.py/jobs/agent_repo_librarian_agentbox")
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


def test_agents_page_dagster_links_use_code_location_path(client):
    html = client.get("/agents").text
    # Dagster job URLs are <base>/locations/<location>/jobs/<job>; the bare
    # /jobs/<job> form 404s in the Dagster webserver.
    assert "/locations/definitions.py/jobs/agent_repo_librarian_agentbox" in html
    assert "/jobs/agent_repo_librarian_agentbox" not in html.replace(
        "/locations/definitions.py/jobs/agent_repo_librarian_agentbox", ""
    )


def test_agents_page_empty_state(client, tmp_agents):
    for f in tmp_agents.glob("*.yaml"):
        f.unlink()
    html = client.get("/agents").text
    assert "ax-empty" in html
    assert 'href="/agents/new"' in html          # create-first call to action


# ── User Story 2: Create a New Agent (T026) ─────────────
def _valid_pi(**over):
    """A minimal, valid pi agent body (prompt_file exists in tmp_prompts)."""
    agent = {
        "name": "new-pi-agent",
        "enabled": True,
        "harness": "pi",
        "model": "cheap",
        "prompt_file": "repo-librarian.md",
        "output_dir": "/data/outputs/new-pi-agent",
        "network": "agentnet",
    }
    agent.update(over)
    return agent


def test_create_agent_201_writes_file_and_reports_reload(client, dagster_stub, tmp_agents):
    resp = client.post("/api/agents", json={"agent": _valid_pi()})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["file"] == "new-pi-agent.yaml"
    assert set(data["reload"]) == {"requested", "ok", "message"}
    assert data["reload"] == {"requested": True, "ok": True, "message": "Workspace reloaded"}
    # The file really landed and round-trips through the reader.
    written = (tmp_agents / "new-pi-agent.yaml").read_text()
    assert "harness: pi" in written
    assert "# agentbox-schema:" in written
    assert data["agent"]["harness"] == "pi"


def test_create_agent_reload_can_be_skipped(client, dagster_stub):
    resp = client.post("/api/agents", json={"agent": _valid_pi(), "reload_dagster": False})
    assert resp.status_code == 201
    assert resp.json()["reload"]["requested"] is False


def test_create_agent_reload_failure_still_201(client, dagster_stub):
    dagster_stub.reload_result = {"ok": False, "message": "Dagster unreachable"}
    resp = client.post("/api/agents", json={"agent": _valid_pi()})
    assert resp.status_code == 201
    reload = resp.json()["reload"]
    assert reload["requested"] is True and reload["ok"] is False
    assert reload["message"] == "Dagster unreachable"


def test_create_agent_400_for_bad_fields(client, dagster_stub):
    resp = client.post("/api/agents", json={"agent": _valid_pi(name="Bad Name")})
    assert resp.status_code == 400
    assert resp.json()["error"] == "validation"
    assert "name" in resp.json()["fields"]

    resp = client.post("/api/agents", json={"agent": _valid_pi(schedule="not a cron")})
    assert resp.status_code == 400 and "schedule" in resp.json()["fields"]

    resp = client.post("/api/agents", json={"agent": _valid_pi(model="nonsense-no-slash")})
    assert resp.status_code == 400 and "model" in resp.json()["fields"]

    resp = client.post("/api/agents", json={"agent": _valid_pi(timeout_seconds=0)})
    assert resp.status_code == 400 and "timeout_seconds" in resp.json()["fields"]


def test_create_agent_409_when_name_exists(client, dagster_stub):
    resp = client.post("/api/agents", json={"agent": _valid_pi(name="repo-librarian-agentbox")})
    assert resp.status_code == 409
    assert resp.json()["error"] == "exists"


def test_create_agent_secret_confirmation_flow(client, dagster_stub, tmp_agents):
    body = {"agent": _valid_pi(name="secret-agent", env={"GITHUB_TOKEN": "ghp_realtokenvalue12345"})}
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 409
    payload = resp.json()
    assert payload["error"] == "secret_confirmation_required"
    assert "GITHUB_TOKEN" in payload["flagged"]
    assert not (tmp_agents / "secret-agent.yaml").exists()   # nothing written yet

    body["confirm_not_secret"] = payload["flagged"]
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 201, resp.text
    assert (tmp_agents / "secret-agent.yaml").exists()


def test_create_agent_passthrough_env_never_flagged(client, dagster_stub):
    body = {"agent": _valid_pi(name="pass-agent", env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"})}
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 201, resp.text


def test_create_agent_with_new_prompt(client, dagster_stub, tmp_prompts, tmp_agents):
    body = {
        "agent": _valid_pi(name="prompt-agent"),
        "new_prompt": {"filename": "prompt-agent.md", "content": "Do the thing."},
    }
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 201, resp.text
    assert (tmp_prompts / "prompt-agent.md").exists()
    assert "prompt_file: prompt-agent.md" in (tmp_agents / "prompt-agent.yaml").read_text()


def test_preview_returns_yaml_for_valid_body(client):
    resp = client.post("/api/agents/preview", json={"agent": _valid_pi()})
    assert resp.status_code == 200
    data = resp.json()
    assert "yaml" in data and "harness: pi" in data["yaml"]
    assert "warnings" in data


def test_preview_400_for_invalid_body(client):
    resp = client.post("/api/agents/preview", json={"agent": _valid_pi(name="Bad Name")})
    assert resp.status_code == 400
    assert "name" in resp.json()["fields"]


def test_preview_does_not_write(client, tmp_agents):
    client.post("/api/agents/preview", json={"agent": _valid_pi(name="ghost-agent")})
    assert not (tmp_agents / "ghost-agent.yaml").exists()


def test_read_agent_returns_template_for_prefill(client):
    resp = client.get("/api/agents/_template-pi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"]["harness"] == "pi"
    assert data["file"] == "_template-pi.yaml"
    assert data["editable"] is True


def test_read_agent_404_when_absent(client):
    resp = client.get("/api/agents/does-not-exist")
    assert resp.status_code == 404


def test_new_agent_page_renders_form(client):
    html = client.get("/agents/new").text
    assert 'id="ax-agent-form"' in html
    assert "Start from template" in html
    assert "/static/agent-form.js" in html
    assert 'id="ax-reload-checkbox"' in html


# ── User Story 3: Edit an Existing Agent (T033) ─────────
def _write_agent_file(tmp_agents, stem, text):
    (tmp_agents / f"{stem}.yaml").write_text(text, encoding="utf-8")
    return tmp_agents / f"{stem}.yaml"


# A hand-written file: non-standard comments and a key the UI does not manage.
EDIT_FIXTURE = """\
# hand-written note the emitter must not preserve
name: edit-me
enabled: true
harness: pi
model: cheap
prompt_file: repo-librarian.md
output_dir: /data/outputs/edit-me
network: agentnet
custom_unmanaged_key: keep-this-value
"""


def test_update_agent_rewrites_file_and_preserves_others(client, dagster_stub, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    # PUT omits the unmanaged key and changes only the model.
    resp = client.put("/api/agents/edit-me", json={"agent": _valid_pi(name="edit-me", model="smart")})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["file"] == "edit-me.yaml"
    assert set(data["reload"]) == {"requested", "ok", "message"}
    assert data["agent"]["model"] == "smart"

    written = (tmp_agents / "edit-me.yaml").read_text()
    assert "model: smart" in written                          # changed value applied
    assert "harness: pi" in written                           # other values retained
    assert "prompt_file: repo-librarian.md" in written
    assert "hand-written note" not in written                 # hand comments replaced
    assert "# Generated by the agentbox UI" in written        # standard comments present
    assert "custom_unmanaged_key: keep-this-value" in written  # unmanaged key survives


def test_update_agent_reload_can_be_skipped(client, dagster_stub, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    resp = client.put("/api/agents/edit-me",
                      json={"agent": _valid_pi(name="edit-me"), "reload_dagster": False})
    assert resp.status_code == 200
    assert resp.json()["reload"]["requested"] is False


def test_update_agent_rejects_name_change(client, dagster_stub, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    resp = client.put("/api/agents/edit-me", json={"agent": _valid_pi(name="renamed")})
    assert resp.status_code == 400
    assert resp.json()["error"] == "validation"
    assert "name" in resp.json()["fields"]
    # The file on disk is untouched by a rejected rename.
    assert "name: edit-me" in (tmp_agents / "edit-me.yaml").read_text()


def test_update_agent_404_for_unknown_stem(client, dagster_stub):
    resp = client.put("/api/agents/does-not-exist",
                      json={"agent": _valid_pi(name="does-not-exist")})
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_read_agent_broken_file_returns_null_agent_and_raw(client, tmp_agents):
    _write_agent_file(tmp_agents, "broken", "harness: [unclosed\n")
    resp = client.get("/api/agents/broken")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] is None
    assert data["parse_error"] is not None
    assert data["raw"] is not None and "unclosed" in data["raw"]


def test_edit_page_renders_edit_form(client, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    html = client.get("/agents/edit-me").text
    # Fields are rendered client-side by agent-form.js; the server marks the mode
    # and stem the module reads to load the agent, lock the name, and PUT on save.
    assert 'id="ax-agent-form"' in html
    assert 'data-mode="edit"' in html
    assert 'data-stem="edit-me"' in html
    assert "/static/agent-form.js" in html
    assert "edit-me" in html                       # title + breadcrumb carry the name
    assert "/locations/definitions.py/jobs/agent_edit_me" in html


def test_edit_page_broken_file_shows_banner_and_raw(client, tmp_agents):
    _write_agent_file(tmp_agents, "broken", "harness: [unclosed\n")
    html = client.get("/agents/broken").text
    assert "ax-banner" in html                     # error banner
    assert "harness: [unclosed" in html            # read-only raw file block


def test_edit_page_newer_schema_is_readonly_with_delete(client, tmp_agents):
    _write_agent_file(tmp_agents, "futuristic",
                      "# agentbox-schema: 9999\nname: futuristic\nharness: pi\n")
    html = client.get("/agents/futuristic").text
    assert "ax-banner" in html                     # "newer agentbox" banner
    assert "9999" in html
    assert 'id="ax-agent-form"' not in html        # no editable form
    assert 'id="ax-delete-btn"' in html            # delete is still offered
    assert 'data-stem="futuristic"' in html        # the button knows its target
    assert "/static/agent-form.js" in html         # ...and its handler is loaded


def test_edit_page_404_for_unknown_stem(client):
    resp = client.get("/agents/nope-not-here")
    assert resp.status_code == 404


# ── User Story 4: Select or Create Prompts (T037) ───────
def test_api_prompts_lists_files_with_size_and_modified(client):
    data = client.get("/api/prompts").json()
    assert set(data) == {"prompts"}
    names = [p["filename"] for p in data["prompts"]]
    assert "repo-librarian.md" in names
    assert names == sorted(names)               # deterministic ordering
    for p in data["prompts"]:
        assert set(p) == {"filename", "size", "modified"}
        assert isinstance(p["size"], int) and p["size"] > 0
        assert p["modified"].endswith("Z")


def test_api_prompt_content_returned(client):
    data = client.get("/api/prompts/repo-librarian.md").json()
    assert data["filename"] == "repo-librarian.md"
    assert isinstance(data["content"], str) and data["content"]


def test_api_prompt_404_when_missing(client):
    resp = client.get("/api/prompts/does-not-exist.md")
    assert resp.status_code == 404


def test_api_prompt_400_for_traversal(client):
    # A separator or .. must be refused (400), never reaching the filesystem.
    assert client.get("/api/prompts/sub/evil.md").status_code == 400
    assert client.get("/api/prompts/..%2Fx.md").status_code == 400


# ── FR-010a: filename hardening at every endpoint (T051) ─
@pytest.mark.parametrize("bad", [".hidden", "..%2F..%2Fetc%2Fpasswd", "..", "a%5Cb"])
def test_unsafe_agent_stem_is_404_on_read(client, bad):
    # An unsafe agent stem behaves as "no such agent" (404), never touching the FS.
    resp = client.get(f"/api/agents/{bad}")
    assert resp.status_code == 404, resp.text


def test_unsafe_agent_stem_is_404_on_update(client, dagster_stub):
    resp = client.put("/api/agents/.hidden", json={"agent": {"name": ".hidden"}})
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_unsafe_agent_stem_is_404_on_delete(client, dagster_stub):
    resp = client.request("DELETE", "/api/agents/.hidden")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


@pytest.mark.parametrize("bad", [".env", ".hidden.md"])
def test_unsafe_prompt_filename_is_400(client, bad):
    # A leading-dot prompt filename is a validation error (400), like a separator/.. .
    resp = client.get(f"/api/prompts/{bad}")
    assert resp.status_code == 400
    assert resp.json()["error"] == "validation"


def test_new_agent_page_drops_unsafe_from_template(client):
    # A traversal ?from= is dropped before it can reach GET /api/agents/{from}.
    resp = client.get("/agents/new?from=../../etc/passwd")
    assert resp.status_code == 200
    assert 'data-from="../../etc/passwd"' not in resp.text
    assert 'data-from=""' in resp.text


def test_new_agent_page_keeps_safe_from_template(client):
    resp = client.get("/agents/new?from=_template-pi")
    assert resp.status_code == 200
    assert 'data-from="_template-pi"' in resp.text


def test_api_create_prompt_201(client, tmp_prompts):
    resp = client.post("/api/prompts", json={"filename": "fresh.md", "content": "Hello."})
    assert resp.status_code == 201, resp.text
    assert resp.json() == {"filename": "fresh.md"}
    assert (tmp_prompts / "fresh.md").read_text() == "Hello."


def test_api_create_prompt_409_on_collision(client, tmp_prompts):
    client.post("/api/prompts", json={"filename": "dup.md", "content": "one"})
    resp = client.post("/api/prompts", json={"filename": "dup.md", "content": "two"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "exists"
    assert (tmp_prompts / "dup.md").read_text() == "one"   # original untouched


def test_api_create_prompt_400_on_bad_name(client):
    resp = client.post("/api/prompts", json={"filename": "Bad Name.md", "content": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "validation"


def test_api_create_prompt_400_on_empty_content(client):
    resp = client.post("/api/prompts", json={"filename": "empty.md", "content": "   "})
    assert resp.status_code == 400
    assert resp.json()["error"] == "validation"


def test_api_create_prompt_makes_directory_when_missing(client, settings, tmp_path, monkeypatch):
    fresh = tmp_path / "prompts-created-on-demand"
    monkeypatch.setattr(settings, "PROMPTS_DIR", str(fresh))
    assert not fresh.exists()
    resp = client.post("/api/prompts", json={"filename": "first.md", "content": "hi"})
    assert resp.status_code == 201
    assert (fresh / "first.md").is_file()


def test_create_agent_with_new_prompt_writes_prompt_first_and_lists_it(
    client, dagster_stub, tmp_prompts, tmp_agents
):
    body = {
        "agent": _valid_pi(name="fresh-agent", prompt_file="ignored.md"),
        "new_prompt": {"filename": "fresh-agent.md", "content": "Do the thing."},
    }
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 201, resp.text
    # The prompt was written and the agent references it (new_prompt wins).
    assert (tmp_prompts / "fresh-agent.md").exists()
    assert "prompt_file: fresh-agent.md" in (tmp_agents / "fresh-agent.yaml").read_text()
    # The selector source now includes it, no reload of anything needed.
    listed = [p["filename"] for p in client.get("/api/prompts").json()["prompts"]]
    assert "fresh-agent.md" in listed


def test_create_agent_new_prompt_remains_when_agent_write_fails(
    client, dagster_stub, tmp_prompts
):
    # Duplicate stem: the prompt is created first, then the agent write is refused.
    body = {
        "agent": _valid_pi(name="repo-librarian-agentbox"),
        "new_prompt": {"filename": "orphan.md", "content": "kept even on failure"},
    }
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 409
    assert resp.json()["error"] == "exists"
    msg = resp.json()["message"]
    assert "orphan.md" in msg and "created" in msg      # user is told the prompt exists
    assert (tmp_prompts / "orphan.md").exists()          # the two-write partial is surfaced


def test_save_with_prompt_file_removed_from_disk_is_400(client, dagster_stub):
    resp = client.post("/api/agents", json={"agent": _valid_pi(prompt_file="was-deleted.md")})
    assert resp.status_code == 400
    assert "prompt_file" in resp.json()["fields"]


# ── US5: model / harness / network validation ───────────
# Default network per harness (mirrors schema.HARNESSES default_network) so a US5
# body varies only the field under test.
_US5_NETWORK = {
    "claude-code": "bridge",
    "pi": "agentnet",
    "api": "agentnet-isolated",
    "codex": "bridge",
}
# A valid model per harness so a model-matrix case changes one thing at a time.
_US5_MODEL = {"claude-code": "sonnet", "pi": "cheap", "api": "cheap", "codex": ""}


def _agent_for(harness, **over):
    """A minimal, otherwise-valid agent body for a given harness."""
    agent = {
        "name": f"us5-{harness}",
        "enabled": True,
        "harness": harness,
        "model": _US5_MODEL[harness],
        "prompt_file": "repo-librarian.md",
        "output_dir": f"/data/outputs/us5-{harness}",
        "network": _US5_NETWORK[harness],
    }
    agent.update(over)
    return agent


@pytest.mark.parametrize("harness,model,ok", [
    ("claude-code", "sonnet", True),               # alias
    ("claude-code", "claude-opus-4-8[1m]", True),  # full id with 1M suffix
    ("claude-code", "cheap", False),               # a LiteLLM alias is not a claude model
    ("pi", "kimi-k3", True),                        # LiteLLM alias
    ("pi", "openai/gpt-x", True),                   # provider/model passthrough
    ("pi", "sonnet", False),                        # a claude alias is not valid for pi
    ("api", "cheap", True),                         # alias only
    ("api", "claude-sonnet-5", False),              # no custom model form for api
    ("codex", "gpt-6-astra", True),                 # any codex id
    ("codex", "", True),                            # blank = codex default
])
def test_create_agent_model_matrix(client, dagster_stub, harness, model, ok):
    body = {"agent": _agent_for(harness, model=model, name=f"us5-mm-{harness}")}
    resp = client.post("/api/agents", json=body)
    if ok:
        assert resp.status_code == 201, resp.text
    else:
        assert resp.status_code == 400, resp.text
        msg = resp.json()["fields"]["model"]
        assert harness in msg   # the rejection names the harness and the allowed forms


def test_create_api_agent_rejects_blank_model(client, dagster_stub):
    resp = client.post("/api/agents", json={"agent": _agent_for("api", model="", name="us5-api-blank")})
    assert resp.status_code == 400, resp.text
    assert "api" in resp.json()["fields"]["model"]


def test_create_api_agent_rejects_effort(client, dagster_stub):
    # effort does not apply to the api harness; a value must be rejected, not ignored.
    resp = client.post("/api/agents", json={"agent": _agent_for("api", name="us5-api-effort", effort="high")})
    assert resp.status_code == 400, resp.text
    assert "api" in resp.json()["fields"]["effort"]


def test_create_claude_agent_on_isolated_network_warns_but_saves(client, dagster_stub):
    body = {"agent": _agent_for("claude-code", name="us5-cc-iso", network="agentnet-isolated")}
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 201, resp.text
    warnings = resp.json()["warnings"]
    assert warnings and any("bridge" in w for w in warnings)


# ── User Story 6: Delete an Agent (T044) ────────────────
def test_delete_agent_200_removes_file_and_reports_reload(client, dagster_stub, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    resp = client.request("DELETE", "/api/agents/edit-me")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["deleted"] == "edit-me.yaml"
    assert set(data["reload"]) == {"requested", "ok", "message"}
    assert data["reload"] == {"requested": True, "ok": True, "message": "Workspace reloaded"}
    assert not (tmp_agents / "edit-me.yaml").exists()


def test_delete_agent_404_when_absent(client, dagster_stub):
    resp = client.request("DELETE", "/api/agents/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_delete_agent_reload_can_be_skipped(client, dagster_stub, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    resp = client.request("DELETE", "/api/agents/edit-me?reload_dagster=false")
    assert resp.status_code == 200, resp.text
    assert resp.json()["reload"]["requested"] is False


def test_delete_agent_leaves_workspace_and_outputs_untouched(client, dagster_stub, tmp_agents, tmp_path):
    # Point the agent at real directories with content; deleting the YAML must not
    # remove them (FR: delete removes only agents/<stem>.yaml).
    workspace = tmp_path / "ws-keep"
    output = tmp_path / "out-keep"
    workspace.mkdir()
    output.mkdir()
    (workspace / "scratch.txt").write_text("workspace data", encoding="utf-8")
    (output / "run.log").write_text("output data", encoding="utf-8")

    agent_text = (
        "name: keep-dirs\n"
        "enabled: true\n"
        "harness: pi\n"
        "model: cheap\n"
        "prompt_file: repo-librarian.md\n"
        f"output_dir: {output}\n"
        f"workspace: {workspace}\n"
        "network: agentnet\n"
    )
    _write_agent_file(tmp_agents, "keep-dirs", agent_text)

    resp = client.request("DELETE", "/api/agents/keep-dirs")
    assert resp.status_code == 200, resp.text
    assert not (tmp_agents / "keep-dirs.yaml").exists()

    # The referenced directories and their contents survive.
    assert workspace.is_dir() and (workspace / "scratch.txt").read_text() == "workspace data"
    assert output.is_dir() and (output / "run.log").read_text() == "output data"


# ── 002 Design System Compliance: static checks ──────────
# Interactive/visual fidelity is covered by the quickstart browser checklist; these
# assert what is statically checkable (specs/002-design-system-compliance/research.md R7).
def _app_css():
    with open(os.path.join(UI_DIR, "static", "app.css"), encoding="utf-8") as f:
        return f.read()


def _css_block(text, selector):
    """The declaration block for one exact selector (anchored so a shorter selector
    does not match inside a longer one, e.g. `.ax-toggle-track::after` vs. the
    `input:checked + .ax-toggle-track::after` rule)."""
    m = re.search(r"(?:^|[}\n])\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert m, f"no CSS rule for selector {selector!r}"
    return re.sub(r"\s+", "", m.group(1))


# US1 — the custom dropdown is a progressive enhancement over the native select,
# so the rendered form keeps its backing <select> and loads the enhancement module.
def test_new_agent_page_keeps_backing_selects_and_loads_dropdown_module(client):
    html = client.get("/agents/new").text
    assert "<select" in html                        # backing select (value store) stays
    assert "/static/dropdown.js" in html            # enhancement module is loaded
    assert client.get("/static/dropdown.js").status_code == 200


def test_app_css_defines_custom_dropdown_component():
    css = _app_css()
    panel = _css_block(css, ".ax-dropdown-panel")
    assert "var(--ax-bg-card)" in panel
    assert "var(--ax-border-strong)" in panel
    assert "var(--ax-shadow-lg)" in panel
    assert "var(--ax-z-dropdown)" in panel
    selected = _css_block(css, '.ax-dropdown-option[aria-selected="true"]')
    assert "var(--ax-cyan-bg)" in selected
    assert "var(--ax-cyan)" in selected


# US2 — the toggle maps every state to the reference's tokens (research R4).
def test_app_css_toggle_matches_reference_tokens():
    css = _app_css()
    on_track = _css_block(css, ".ax-toggle input:checked + .ax-toggle-track")
    assert "background:var(--ax-cyan)" in on_track
    on_thumb = _css_block(css, ".ax-toggle input:checked + .ax-toggle-track::after")
    assert "background:var(--ax-text-primary)" in on_thumb
    assert "translateX(var(--ax-space-8))" in on_thumb
    off_track = _css_block(css, ".ax-toggle-track")
    assert "background:var(--ax-border-strong)" in off_track
    off_thumb = _css_block(css, ".ax-toggle-track::after")
    assert "background:var(--ax-text-low)" in off_thumb


# US3 — the responsive form grid and the full-row modifier exist as specified.
def test_app_css_defines_form_grid():
    css = _app_css()
    grid = _css_block(css, ".ax-grid-form")
    assert "display:grid" in grid
    assert "auto-fill" in grid
    assert "minmax(" in grid and "280px" in grid      # 280px minimum field width
    assert "gap:var(--ax-space-10)" in grid
    wide = _css_block(css, ".ax-field--wide")
    assert "grid-column:1/-1" in wide


# The inner text of a `@container <condition> { ... }` at-rule (brace-matched so a
# nested rule's braces do not truncate it), whitespace-squashed for comparison.
def _container_block(text, condition):
    start = text.index(f"@container {condition}")
    brace = text.index("{", start)
    depth, i = 1, brace + 1
    while depth and i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, f"unbalanced @container {condition!r}"
    return re.sub(r"\s+", "", text[brace + 1:i - 1])


# ── 003 Agent Form Layout: base grid (US1/US4) ───────────
def test_app_css_defines_base_grid_agent():
    css = _app_css()
    base = _css_block(css, ".ax-grid-agent")
    assert 'grid-template-areas:"runs""job""box"' in base
    assert "align-items:start" in base
    group = _css_block(css, ".ax-form-group")
    assert "min-width:0" in group


# ── 003 US2: three columns on a wide pane ────────────────
def test_app_css_three_column_container_query():
    css = _app_css()
    block = _container_block(css, "ax-content (min-width: 1320px)")
    assert 'grid-template-areas:"runsjobbox"' in block
    assert "grid-template-columns:minmax(0,1fr)minmax(0,1.4fr)minmax(0,1fr)" in block


# ── 003 US3: two columns on a mid-width pane ─────────────
def test_app_css_two_column_container_query():
    css = _app_css()
    block = _container_block(css, "ax-content (min-width: 720px)")
    assert 'grid-template-areas:"runsjob""boxjob"' in block
    assert "grid-template-columns:minmax(0,1fr)minmax(0,1fr)" in block
    # The wider query must come later in the file so it wins the cascade.
    assert css.index("@container ax-content (min-width: 720px)") \
        < css.index("@container ax-content (min-width: 1320px)")


# ── 003 Agent Form Layout: page markup (US1) ─────────────
# The lead strip, group grid, and reload actionbar order are server-rendered; the
# groups and cards themselves are built client-side by agent-form.js.
def test_new_agent_page_has_lead_strip_and_group_grid(client):
    html = client.get("/agents/new").text
    assert 'id="ax-form-lead"' in html
    assert 'class="ax-form-lead ax-grid-form"' in html
    assert 'id="ax-form-lead-fields"' in html
    assert 'id="ax-form-sections"' in html
    sections = re.search(r'<div[^>]*id="ax-form-sections"[^>]*>', html).group(0)
    assert "ax-grid-agent" in sections
    # Document order: actionbar → lead strip → sections mount.
    assert (html.index("ax-form-actionbar")
            < html.index('id="ax-form-lead"')
            < html.index('id="ax-form-sections"'))
    # The template picker lives inside the lead strip, which is not a card.
    lead = re.search(r'<div[^>]*id="ax-form-lead".*?</div>\s*</div>', html, re.S).group(0)
    assert 'id="ax-template-select"' in lead
    lead_open = re.search(r'<div[^>]*id="ax-form-lead"[^>]*>', html).group(0)
    assert "ax-card" not in lead_open


def test_edit_agent_page_has_lead_strip_and_group_grid(client, tmp_agents):
    _write_agent_file(tmp_agents, "edit-me", EDIT_FIXTURE)
    html = client.get("/agents/edit-me").text
    assert 'id="ax-form-lead"' in html
    assert 'id="ax-form-lead-fields"' in html
    sections = re.search(r'<div[^>]*id="ax-form-sections"[^>]*>', html).group(0)
    assert "ax-grid-agent" in sections
    assert (html.index("ax-form-actionbar")
            < html.index('id="ax-form-lead"')
            < html.index('id="ax-form-sections"'))
    # Edit mode has no template picker in the lead strip.
    assert 'id="ax-template-select"' not in html
