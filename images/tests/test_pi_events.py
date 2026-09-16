"""pi to_events() test (spec 012, T022)."""


def test_pi_to_events_from_agent_end(load_module, fixture_lines, event_validator):
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    events = [e.to_dict() for e in wrapper.to_events(fixture_lines("pi.jsonl"))]
    for e in events:
        event_validator(e)
    assert [e["kind"] for e in events] == ["user", "assistant", "final"]
    assert events[0]["text"] == "Document the factory."
    assistant = events[1]
    assert assistant["tokens_in"] == 4000 and assistant["tokens_out"] == 600
    assert assistant["cost_usd"] == 0.018
    assert events[-1]["text"] == "Documented the factory; next time start from definitions.py."


def test_pi_no_agent_end_is_error(load_module):
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    events = [e.to_dict() for e in wrapper.to_events(['{"type":"agent_start"}'])]
    assert events[0]["kind"] == "error"


def test_pi_tool_use_block_becomes_tool_call(load_module):
    import json
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    lines = [json.dumps({"type": "agent_end", "messages": [
        {"role": "assistant", "usage": {"input": 10, "output": 5},
         "content": [{"type": "tool_use", "name": "read_file", "input": {"path": "x"}}]},
    ]})]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    assert any(e["kind"] == "tool_call" and e["tool"] == "read_file" for e in events)


def test_pi_file_edit_tool_result_carries_diff(load_module):
    """A pi edit tool_use is paired with its tool_result, which carries a unified diff (FR-006)."""
    import json
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    lines = [json.dumps({"type": "agent_end", "messages": [
        {"role": "assistant", "usage": {"input": 10, "output": 5}, "content": [
            {"type": "tool_use", "id": "t1", "name": "edit_file",
             "input": {"path": "x.py", "old_string": "a", "new_string": "b"}}]},
        {"role": "tool", "tool_use_id": "t1", "content": "ok"},
    ]})]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    result = next(e for e in events if e["kind"] == "tool_result")
    assert "diff" in result and "-a" in result["diff"] and "+b" in result["diff"]


def test_pi_non_edit_tool_result_has_no_diff(load_module):
    import json
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    lines = [json.dumps({"type": "agent_end", "messages": [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "x"}}]},
        {"role": "tool", "tool_use_id": "t1", "content": "data"},
    ]})]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    result = next(e for e in events if e["kind"] == "tool_result")
    assert "diff" not in result
