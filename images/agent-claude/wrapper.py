"""claude-code harness wrapper (spec 007).

Runs ``claude``, tees its native ``stream-json`` events to stdout unchanged (FR-006),
parses them into the common run report, and emits it over Dagster Pipes. The
per-harness parsing lives here, not in the orchestrator (SC-002). ``cost_usd`` is
null: claude-code runs on a subscription (SC-001).
"""
import json
import sys

from lib.agent_report import RunReport, run_wrapper


def parse(lines):
    """Turn claude-code ``stream-json`` events into a :class:`RunReport`.

    The final ``result`` event carries ``num_turns``, ``usage``, ``is_error`` and the
    final assistant text (the run's closing ``notes``).
    """
    result = None
    for line in lines:
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict) and evt.get("type") == "result":
            result = evt  # keep the last result event
    if result is None:
        return RunReport(status="failed", cost_usd=None,
                         error="no result event in claude-code output")
    usage = result.get("usage") or {}
    is_error = bool(result.get("is_error"))
    text = result.get("result")
    return RunReport(
        status="failed" if is_error else "ok",
        tokens_in=usage.get("input_tokens"),
        tokens_out=usage.get("output_tokens"),
        turns=result.get("num_turns"),
        cost_usd=None,
        error=((str(text) if text else "claude-code reported is_error") if is_error else None),
        notes=(None if is_error else (str(text) if text else None)),
    )


if __name__ == "__main__":
    # the orchestrator passes the full `claude ...` command as argv
    run_wrapper(sys.argv[1:], parse)
