"""api runner synthesized-events test (spec 012, T023)."""


def test_api_synth_events(load_module, event_validator):
    runner = load_module("agent-python/runner.py", "agent_python_runner")
    report = runner.RunReport(status="ok", tokens_in=120, tokens_out=30, turns=1, cost_usd=0.0011)
    events = [e.to_dict() for e in runner.synth_events("do the thing", "done", report)]
    for e in events:
        event_validator(e)
    assert [e["kind"] for e in events] == ["system", "user", "assistant", "final"]
    assert events[1]["text"] == "do the thing"
    assistant = events[2]
    assert assistant["text"] == "done"
    assert assistant["tokens_in"] == 120 and assistant["cost_usd"] == 0.0011
    assert events[-1]["kind"] == "final" and events[-1]["text"] == "done"
