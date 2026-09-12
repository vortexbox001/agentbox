"""claude-code report parser test (spec 007, T013)."""


def test_claude_report(load_module, fixture_lines, report_validator):
    wrapper = load_module("agent-claude/wrapper.py", "agent_claude_wrapper")
    report = wrapper.parse(fixture_lines("claude-code.jsonl"))
    report.files_written = 2
    d = report.to_dict()

    report_validator(d)
    assert d["status"] == "ok"
    assert d["cost_usd"] is None            # subscription (SC-001)
    assert d["tokens_in"] == 8800
    assert d["tokens_out"] == 1500
    assert d["turns"] == 7
    assert d["files_written"] == 2
    assert d["notes"] == "Reviewed the orchestrator; the from_op wiring is subtle."
    assert d["error"] is None


def test_claude_no_result_event_is_failed(load_module, report_validator):
    wrapper = load_module("agent-claude/wrapper.py", "agent_claude_wrapper")
    report = wrapper.parse(["not json", '{"type":"assistant"}'])
    d = report.to_dict()
    report_validator(d)
    assert d["status"] == "failed"
    assert d["error"] and d["cost_usd"] is None
