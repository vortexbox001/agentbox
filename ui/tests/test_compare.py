"""Compare view tests (spec 012, T059 / SC-005)."""
from test_runs import write_run


def _ctx(effort="high", harness="claude-code", extra=None):
    ctx = {
        "prompt": {"prompt_text": "do it", "append_system_prompt": None},
        "model": {"model": "sonnet", "effort": effort, "fallback_model": None},
        "harness": {"harness": harness, "image_ref": "img", "image_digest": "sha256:x"},
        "tools": {"allowed_tools": ["Read"]},
        "instruction_files": [],
        "runtime": {"env_names": ["TZ"], "mounts": [], "network": "agentnet", "working_dir": "/workspace"},
        "file_trees": {"workspace": [{"path": "a.py", "size": 1}], "output": []},
        "completeness": {"complete": True, "undisclosed": [], "statement": "complete"},
        "run": {"session_id": "sX", "output_dir": "/o"},
    }
    if extra:
        ctx.update(extra)
    return ctx


def test_single_field_change_is_one_diff(settings, tmp_runs, client):
    # two runs differing ONLY by effort (file_trees / run identity are excluded) → exactly one row
    write_run(tmp_runs, "hello", "2026-09-15", "a1", report={"status": "ok"}, context=_ctx(effort="high"))
    write_run(tmp_runs, "hello", "2026-09-15", "b1", report={"status": "ok"}, context=_ctx(effort="low"))
    r = client.get("/runs/compare?a=a1&b=b1")
    assert r.status_code == 200
    rows = client.app  # noqa: F841 (kept for clarity)
    from runs_store import compare_contexts, read_run
    diffs = compare_contexts(read_run("a1")["context"], read_run("b1")["context"])
    assert len(diffs) == 1
    assert diffs[0]["path"] == "model.effort"
    assert diffs[0]["a"] == "high" and diffs[0]["b"] == "low"
    assert "model.effort" in r.text


def test_harness_specific_field_shown_present_on_one(settings, tmp_runs, client):
    from runs_store import compare_contexts
    a = _ctx()
    b = _ctx(harness="pi")
    b["tools"] = {"allowed_tools": ["Read"], "mcp_servers": [{"name": "gh", "tools": ["x"]}]}
    diffs = {d["path"]: d for d in compare_contexts(a, b)}
    # harness differs (changed) and the b-only mcp_servers field is present-on-one (added)
    assert diffs["harness.harness"]["state"] == "changed"
    assert diffs["tools.mcp_servers"]["state"] == "added"
    assert diffs["tools.mcp_servers"]["a"] is None


def test_identical_contexts_no_diff(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "sa", report={"status": "ok"}, context=_ctx())
    write_run(tmp_runs, "hello", "2026-09-15", "sb", report={"status": "ok"}, context=_ctx())
    html = client.get("/runs/compare?a=sa&b=sb").text
    assert "No differences" in html


def test_compare_missing_run(settings, tmp_runs, client):
    html = client.get("/runs/compare?a=nope&b=alsonope").text
    assert "was not found" in html


def test_compare_not_captured_as_run_id(settings, tmp_runs, client):
    # /runs/compare must resolve to the compare page, never the detail page for run "compare".
    r = client.get("/runs/compare")
    assert r.status_code == 200
    assert "Compare" in r.text or "compare" in r.text