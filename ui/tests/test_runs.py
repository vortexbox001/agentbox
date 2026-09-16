"""Run viewer route/render tests (spec 012). US1 Conversation tab here; US2/US3 extend this file."""
import json

import pytest


def write_run(runs_dir, agent, date, run_id, *, report=None, context=None, events=None,
              transcript=None):
    d = runs_dir / agent / date / run_id
    d.mkdir(parents=True)
    if report is not None:
        (d / "report.json").write_text(json.dumps(report))
    if context is not None:
        (d / "context.json").write_text(json.dumps(context))
    if events is not None:
        (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    if transcript is not None:
        (d / "transcript.jsonl").write_text(transcript)
    return d


def _events_with_tools():
    return [
        {"kind": "system", "ts": "t", "turn": 0, "text": "Session started."},
        {"kind": "user", "ts": "t", "turn": 0, "text": "Do the upgrade."},
        {"kind": "assistant", "ts": "t", "turn": 1, "text": "Checking outdated deps.",
         "tokens_in": 1200, "tokens_out": 300},
        {"kind": "tool_call", "ts": "t", "turn": 1, "tool": "Bash", "args": {"command": "npm outdated"}},
        {"kind": "tool_result", "ts": "t", "turn": 1, "result": "date-fns 2.29 -> 2.30"},
        {"kind": "tool_call", "ts": "t", "turn": 2, "tool": "Edit", "args": {"file_path": "package.json"}},
        {"kind": "tool_result", "ts": "t", "turn": 2, "result": "",
         "diff": "--- a/package.json\n+++ b/package.json\n-  \"date-fns\": \"2.29.3\",\n+  \"date-fns\": \"2.30.0\","},
        {"kind": "tool_call", "ts": "t", "turn": 3, "tool": "Bash", "args": {"command": "npm test"}},
        {"kind": "tool_result", "ts": "t", "turn": 3, "missing": True},
        {"kind": "final", "ts": "t", "turn": 3, "text": "Done.", "tokens_in": 8000, "tokens_out": 1500},
    ]


@pytest.mark.parametrize("harness", ["api", "claude-code", "codex", "pi"])
def test_conversation_renders_same_components_each_harness(settings, tmp_runs, client, harness):
    write_run(tmp_runs, harness, "2026-09-15", f"run-{harness}",
              report={"status": "ok", "tokens_in": 8000, "tokens_out": 1500, "turns": 3,
                      "cost_usd": None, "transcript_path": "x"},
              context={"harness": {"harness": harness}, "model": {"model": "m"}},
              events=_events_with_tools())
    html = client.get(f"/runs/run-{harness}").text
    # the same threaded shape for every harness (SC-002)
    assert "ax-timeline" in html
    assert "ax-entry" in html
    assert "ax-tool" in html
    assert "ax-tool-name" in html
    # a file edit renders as a diff (FR-020)
    assert "ax-diff-add" in html and "ax-diff-del" in html
    # a missing tool result is marked missing, not hidden (FR-021)
    assert "recorded as missing" in html


def test_conversation_pruned_note(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "pruned",
              report={"status": "ok"}, context={"harness": {"harness": "api"}})  # no events.jsonl
    html = client.get("/runs/pruned").text
    assert "Conversation pruned" in html
    assert "ax-timeline" not in html


def test_events_api_returns_normalized_events(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "with-events",
              report={"status": "ok"}, context={}, events=_events_with_tools())
    r = client.get("/api/runs/with-events/events")
    assert r.status_code == 200
    events = r.json()["events"]
    assert [e["kind"] for e in events][:2] == ["system", "user"]


def test_events_api_404_for_unknown(settings, tmp_runs, client):
    assert client.get("/api/runs/nope/events").status_code == 404


# --- US2: Context tab -------------------------------------------------------

def _claude_context():
    return {
        "prompt": {"prompt_text": "Upgrade the deps.", "append_system_prompt": "Write to /output"},
        "model": {"model": "sonnet", "effort": "high", "fallback_model": None},
        "harness": {"harness": "claude-code", "image_ref": "agentbox/agent-claude:latest",
                    "image_digest": "sha256:abc"},
        "tools": {"allowed_tools": ["Read", "Write"], "permission_mode": "acceptEdits",
                  "mcp_servers": [{"name": "github", "tools": ["create_issue", "list_prs"]}]},
        "instruction_files": [{"path": "/workspace/CLAUDE.md", "contents": "PROJECT RULES: be careful"}],
        "runtime": {"env_names": ["TZ", "OPENAI_API_KEY"], "mounts": [
            {"source": "/data/ws", "target": "/workspace", "mode": "rw"}],
            "network": "agentnet", "working_dir": "/workspace"},
        "file_trees": {"workspace": [{"path": "a.py", "size": 12}], "output": []},
        "completeness": {"complete": False, "undisclosed": ["vendor base system prompt"],
                         "statement": "The claude-code vendor base system prompt is not disclosed."},
    }


def test_context_tab_renders_instruction_files_and_completeness(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "ctx",
              report={"status": "ok"}, context=_claude_context())
    html = client.get("/runs/ctx").text
    # full instruction-file contents shown (SC-008)
    assert "PROJECT RULES: be careful" in html
    assert "/workspace/CLAUDE.md" in html
    # completeness statement naming the vendor base prompt undisclosed
    assert "vendor base system prompt is not disclosed" in html
    # MCP servers + exposed tools
    assert "github" in html and "create_issue" in html


def test_context_tab_shows_env_names_only_and_flags_secret(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "ctx2",
              report={"status": "ok"}, context=_claude_context())
    html = client.get("/runs/ctx2").text
    assert "ax-env-pill" in html
    assert "OPENAI_API_KEY" in html and "TZ" in html
    # the secret-looking name is flagged, but no value is present anywhere (FR-015)
    assert "data-secret" in html


# --- US3: Runs list (disk-only, filters) ------------------------------------

@pytest.fixture
def three_runs(tmp_runs):
    write_run(tmp_runs, "hello", "2026-09-14", "r1",
              report={"status": "ok", "cost_usd": 0.01, "model": "cheap"},
              context={"model": {"model": "cheap"}, "harness": {"harness": "api"}})
    write_run(tmp_runs, "hello", "2026-09-15", "r2",
              report={"status": "failed", "error": "boom"},
              context={"model": {"model": "smart"}, "harness": {"harness": "claude-code"}})
    write_run(tmp_runs, "other", "2026-09-15", "r3",
              report={"status": "ok"}, context={"model": {"model": "smart"}})
    return tmp_runs


def test_runs_list_renders_from_disk(settings, three_runs, client):
    # No Dagster stub is installed — the page must render purely from disk (SC-007).
    html = client.get("/runs").text
    assert "ax-runs-table" in html or "ax-table" in html
    for rid in ("r1", "r2", "r3"):
        assert f"/runs/{rid}" in html


def test_runs_list_has_all_fr017_columns(settings, three_runs, client):
    # FR-017: the list surfaces agent, time, status, model, cost, and attempts.
    html = client.get("/runs").text
    for col in ("Agent", "Time", "Status", "Model", "Cost", "Attempts"):
        assert f">{col}</th>" in html


def test_runs_list_filters_by_agent(settings, three_runs, client):
    html = client.get("/runs?agent=other").text
    assert "/runs/r3" in html
    assert "/runs/r1" not in html and "/runs/r2" not in html


def test_runs_list_filters_by_status_and_date(settings, three_runs, client):
    html = client.get("/runs?status=failed").text
    assert "/runs/r2" in html and "/runs/r1" not in html
    html2 = client.get("/runs?date_from=2026-09-15&date_to=2026-09-15").text
    assert "/runs/r2" in html2 and "/runs/r3" in html2 and "/runs/r1" not in html2


def test_api_runs_json(settings, three_runs, client):
    rows = client.get("/api/runs?agent=hello").json()["runs"]
    assert {r["run_id"] for r in rows} == {"r1", "r2"}


def test_context_tab_complete_for_pi(settings, tmp_runs, client):
    ctx = _claude_context()
    ctx["harness"]["harness"] = "pi"
    ctx["completeness"] = {"complete": True, "undisclosed": [], "statement": "Complete — pi adds no vendor prompt."}
    write_run(tmp_runs, "hello", "2026-09-15", "ctx-pi", report={"status": "ok"}, context=ctx)
    html = client.get("/runs/ctx-pi").text
    assert "Complete — pi adds no vendor prompt." in html
