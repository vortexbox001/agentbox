"""api-harness report parser test (spec 007, T013).

api builds its report from the LiteLLM response (tokens from ``usage``, ``cost_usd``
from the ``x-litellm-response-cost`` header) rather than a native event stream, so the
fixture is a recorded response body and the cost header is supplied to the parser.
"""
import json


def test_api_report_from_response(load_module, fixture_lines, report_validator):
    runner = load_module("agent-python/runner.py", "agent_python_runner")
    data = json.loads(fixture_lines("api.jsonl")[0])
    text = data["choices"][0]["message"]["content"]

    report = runner.report_from_response(data, "0.0231", files_written=1, text=text)
    d = report.to_dict()

    report_validator(d)
    assert d["status"] == "ok"
    assert d["cost_usd"] == 0.0231          # non-null for api (SC-001)
    assert d["tokens_in"] == 5231
    assert d["tokens_out"] == 812
    assert d["turns"] == 1
    assert d["files_written"] == 1
    assert d["notes"] == text
    assert d["transcript_path"] is None     # the orchestrator fills this
    assert d["error"] is None


def test_api_missing_cost_header_is_null(load_module, fixture_lines, report_validator):
    runner = load_module("agent-python/runner.py", "agent_python_runner")
    data = json.loads(fixture_lines("api.jsonl")[0])
    report = runner.report_from_response(data, None, files_written=0, text="hi")
    report_validator(report.to_dict())
    assert report.cost_usd is None
