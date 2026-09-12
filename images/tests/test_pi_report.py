"""pi report parser test (spec 007, T013)."""


def test_pi_report(load_module, fixture_lines, report_validator):
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    report = wrapper.parse(fixture_lines("pi.jsonl"))
    d = report.to_dict()

    report_validator(d)
    assert d["status"] == "ok"
    assert d["cost_usd"] == 0.018           # non-null for pi (SC-001)
    assert d["tokens_in"] == 4000
    assert d["tokens_out"] == 600
    assert d["turns"] == 1
    assert d["notes"] == "Documented the factory; next time start from definitions.py."
    assert d["error"] is None


def test_pi_error_stop_reason_is_failed(load_module, report_validator):
    wrapper = load_module("agent-pi/wrapper.py", "agent_pi_wrapper")
    report = wrapper.parse([
        '{"type":"agent_end","messages":[{"role":"assistant","stopReason":"error",'
        '"errorMessage":"provider timeout","usage":{"cost":{"total":0.0}}}]}',
    ])
    d = report.to_dict()
    report_validator(d)
    assert d["status"] == "failed"
    assert "provider timeout" in d["error"]
    assert d["cost_usd"] == 0.0             # still non-null for pi
