"""codex to_events() test (spec 012, T021)."""


def test_codex_to_events_kinds_order_and_final(load_module, fixture_lines, event_validator):
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    events = [e.to_dict() for e in wrapper.to_events(fixture_lines("codex.jsonl"))]
    for e in events:
        event_validator(e)
    # reasoning + two agent_messages → three assistant events, then a synthesized final
    assert [e["kind"] for e in events] == ["assistant", "assistant", "assistant", "final"]
    final = events[-1]
    assert final["text"] == "Done; wrote the summary to /output."
    # per-turn usage summed onto the final (1200+800 / 300+150)
    assert final["tokens_in"] == 2000 and final["tokens_out"] == 450


def test_codex_error_becomes_error_event(load_module):
    import json
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    lines = [
        json.dumps({"type": "turn.started"}),
        json.dumps({"type": "error", "message": "sandbox denied"}),
    ]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    assert any(e["kind"] == "error" and e["text"] == "sandbox denied" for e in events)
    assert events[-1]["kind"] == "final"


def test_codex_command_item_becomes_tool_call_and_result(load_module):
    import json
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    lines = [
        json.dumps({"type": "turn.started"}),
        json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": "ls", "aggregated_output": "a.py\nb.py"}}),
    ]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    kinds = [e["kind"] for e in events]
    assert "tool_call" in kinds and "tool_result" in kinds
    call = next(e for e in events if e["kind"] == "tool_call")
    assert call["tool"] == "shell" and call["args"] == {"command": "ls"}


def test_codex_apply_patch_surfaces_diff(load_module):
    """A codex apply_patch shell call surfaces its patch body as the tool_result diff (FR-006)."""
    import json
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    patch = ("apply_patch <<'EOF'\n*** Begin Patch\n*** Update File: x.py\n@@\n-old\n+new\n"
             "*** End Patch\nEOF")
    lines = [
        json.dumps({"type": "turn.started"}),
        json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": patch, "aggregated_output": "Success"}}),
    ]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    result = next(e for e in events if e["kind"] == "tool_result")
    assert "diff" in result
    assert "*** Begin Patch" in result["diff"] and "-old" in result["diff"] and "+new" in result["diff"]


def test_codex_plain_shell_has_no_diff(load_module):
    import json
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    lines = [
        json.dumps({"type": "turn.started"}),
        json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": "ls -la", "aggregated_output": "x"}}),
    ]
    events = [e.to_dict() for e in wrapper.to_events(lines)]
    result = next(e for e in events if e["kind"] == "tool_result")
    assert "diff" not in result
