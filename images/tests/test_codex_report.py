"""codex report parser test (spec 007, T013)."""


def test_codex_report(load_module, fixture_lines, report_validator):
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    report = wrapper.parse(fixture_lines("codex.jsonl"))
    d = report.to_dict()

    report_validator(d)
    assert d["status"] == "ok"
    assert d["cost_usd"] is None            # subscription (SC-001)
    assert d["tokens_in"] == 2000           # summed across turn.completed events
    assert d["tokens_out"] == 450
    assert d["turns"] == 2
    assert d["notes"] == "Done; wrote the summary to /output."
    assert d["error"] is None


def test_codex_error_event_is_failed(load_module, report_validator):
    wrapper = load_module("agent-codex/wrapper.py", "agent_codex_wrapper")
    report = wrapper.parse([
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}',
        '{"type":"error","message":"model overloaded"}',
    ])
    d = report.to_dict()
    report_validator(d)
    assert d["status"] == "failed"
    assert "model overloaded" in d["error"]
    assert d["cost_usd"] is None
