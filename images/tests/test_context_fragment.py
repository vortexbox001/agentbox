"""Per-harness context-fragment tests (spec 012, T037).

Each harness wrapper contributes the instruction-file contents it loaded, the MCP tools each
server exposed (claude-code), and a completeness statement (claude/codex: vendor base prompt
undisclosed; pi/api: complete).
"""
import json


def test_claude_fragment_instruction_files_mcp_and_completeness(load_module, monkeypatch, tmp_path):
    wrapper = load_module("agent-claude/wrapper.py", "agent_claude_wrapper")
    # a CLAUDE.md reachable via CLAUDE_CONFIG_DIR (workspace scan is empty in the test env)
    (tmp_path / "CLAUDE.md").write_text("project rules: be careful")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    lines = [json.dumps({"type": "system", "subtype": "init",
                         "tools": ["Read", "mcp__github__create_issue", "mcp__github__list_prs"]})]
    frag = wrapper.context_fragment(lines)
    # instruction-file contents captured in full
    contents = [f["contents"] for f in frag["instruction_files"]]
    assert any("project rules" in c for c in contents)
    # MCP exposed tools grouped by server
    gh = next(s for s in frag["mcp_servers"] if s["name"] == "github")
    assert gh["tools"] == ["create_issue", "list_prs"]
    # completeness names the vendor base prompt as undisclosed
    assert frag["completeness"]["complete"] is False
    assert "vendor base system prompt" in frag["completeness"]["undisclosed"]


def test_codex_fragment_completeness_vendor_undisclosed(load_module):
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    frag = wrapper.context_fragment([])
    assert frag["completeness"]["complete"] is False
    assert "vendor base system prompt" in frag["completeness"]["undisclosed"]
    assert isinstance(frag["instruction_files"], list)
    assert "harness_version" in frag  # populated by cli_version (None in the test env)


def test_codex_fragment_mcp_from_stream(load_module):
    """codex has no exposed-tool list event, so MCP disclosure derives from mcp__ tool names."""
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    lines = [json.dumps({"type": "item.completed", "item": {
        "type": "mcp_tool_call", "name": "mcp__github__create_issue"}})]
    frag = wrapper.context_fragment(lines)
    gh = next(s for s in frag["mcp_servers"] if s["name"] == "github")
    assert gh["tools"] == ["create_issue"]


def test_pi_fragment_is_complete(load_module):
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    frag = wrapper.context_fragment([])
    assert frag["completeness"]["complete"] is True
    assert frag["completeness"]["undisclosed"] == []
    assert "harness_version" in frag


def test_pi_fragment_mcp_from_stream(load_module):
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    lines = [json.dumps({"type": "agent_end", "messages": [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "mcp__db__query", "input": {}}]}]})]
    frag = wrapper.context_fragment(lines)
    db = next(s for s in frag["mcp_servers"] if s["name"] == "db")
    assert db["tools"] == ["query"]


def test_api_fragment_is_complete_no_files(load_module):
    runner = load_module("agent-python/runner.py", "agent_python_runner")
    frag = runner.context_fragment()
    assert frag["completeness"]["complete"] is True
    assert frag["instruction_files"] == []
    assert frag["harness_version"].startswith("python ")  # the api harness runtime (FR-009)
