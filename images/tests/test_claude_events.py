"""claude-code to_events() test (spec 012, T020)."""


def test_claude_to_events_kinds_order(load_module, fixture_lines, event_validator):
    wrapper = load_module("agent-claude/wrapper.py", "agent_claude_wrapper")
    events = [e.to_dict() for e in wrapper.to_events(fixture_lines("claude-code.jsonl"))]
    for e in events:
        event_validator(e)
    assert [e["kind"] for e in events] == ["system", "assistant", "tool_call", "tool_result", "final"]
    # turns: system=0, then each assistant message bumps the turn (text=1, tool_use=2)
    assert [e["turn"] for e in events] == [0, 1, 2, 2, 2]
    tool_call = events[2]
    assert tool_call["tool"] == "Read"
    assert tool_call["args"] == {"file_path": "factory.py"}
    final = events[-1]
    assert final["tokens_in"] == 8800 and final["tokens_out"] == 1500
    assert final["text"] == "Reviewed the orchestrator; the from_op wiring is subtle."


def test_claude_skips_non_init_system_lines(load_module):
    # claude-code streams many system/subtype:"thinking_tokens" counter lines; only the init line
    # is conversation-worthy (regression: 83 duplicate "Session started" entries).
    import json
    wrapper = load_module("agent-claude/wrapper.py", "agent_claude_wrapper")
    lines = [json.dumps({"type": "system", "subtype": "init", "tools": ["Read"]})]
    lines += [json.dumps({"type": "system", "subtype": "thinking_tokens",
                          "estimated_tokens": 100 + i}) for i in range(5)]
    lines.append(json.dumps({"type": "result", "is_error": False, "num_turns": 1, "result": "done"}))
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    system = [e for e in events if e["kind"] == "system"]
    assert len(system) == 1
    assert system[0]["text"].startswith("Session started.")


def test_claude_edit_renders_a_diff(load_module):
    wrapper = load_module("agent-claude/wrapper.py", "agent_claude_wrapper")
    import json
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Edit",
             "input": {"file_path": "x.py", "old_string": "a = 1", "new_string": "a = 2"}}]}}),
        json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}),
    ]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    result = next(e for e in events if e["kind"] == "tool_result")
    assert "diff" in result
    assert "-a = 1" in result["diff"] and "+a = 2" in result["diff"]
