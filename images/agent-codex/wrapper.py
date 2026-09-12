"""codex harness wrapper (spec 007).

Runs ``codex``, tees its native events to stdout unchanged (FR-006), parses them into
the common run report, and emits it over Dagster Pipes. Per-harness parsing lives here,
not in the orchestrator (SC-002). ``cost_usd`` is null: codex runs on a subscription
(SC-001).
"""
import json
import sys

from lib.agent_report import RunReport, run_wrapper


def parse(lines):
    """Turn codex events into a :class:`RunReport`.

    Aggregates ``turn.completed`` usage, takes the last ``item.completed``
    ``agent_message`` text as ``notes``, and collects ``error`` events.
    """
    tokens_in = tokens_out = turns = 0
    saw_usage = False
    last_msg = None
    errors = []
    for line in lines:
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if not isinstance(evt, dict):
            continue
        t = evt.get("type", "")
        if t == "turn.completed":
            usage = evt.get("usage") or {}
            tokens_in += usage.get("input_tokens", 0) or 0
            tokens_out += usage.get("output_tokens", 0) or 0
            turns += 1
            saw_usage = True
        elif t == "item.completed" and (evt.get("item") or {}).get("type") == "agent_message":
            last_msg = evt["item"].get("text")
        elif t == "error":
            errors.append(evt.get("message") or json.dumps(evt))
    failed = bool(errors)
    return RunReport(
        status="failed" if failed else "ok",
        tokens_in=tokens_in if saw_usage else None,
        tokens_out=tokens_out if saw_usage else None,
        turns=turns or None,
        cost_usd=None,
        error="\n".join(errors) if failed else None,
        notes=(None if failed else (last_msg or None)),
    )


if __name__ == "__main__":
    # the image's historical entrypoint was `codex`; the orchestrator passes `exec ...`
    run_wrapper(["codex", *sys.argv[1:]], parse)
