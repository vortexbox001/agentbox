"""pi harness wrapper (spec 007).

Runs ``pi``, tees its native events to stdout unchanged (FR-006), parses the
``agent_end`` event into the common run report, and emits it over Dagster Pipes.
Per-harness parsing lives here, not in the orchestrator (SC-002). ``cost_usd`` is
non-null: it is summed from pi's own per-message usage (SC-001).
"""
import json
import sys

from lib.agent_report import RunReport, run_wrapper


def _sum_tokens(msgs, kind):
    """Sum a token dimension across assistant messages, tolerant of key naming
    (``input``/``output``, ``input_tokens``/``output_tokens``). None if pi reported
    no token counts at all (schema allows null)."""
    total = 0
    seen = False
    for m in msgs:
        usage = m.get("usage") or {}
        for key in (kind, f"{kind}_tokens", f"{kind}Tokens"):
            v = usage.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                total += v
                seen = True
                break
    return int(total) if seen else None


def _from_agent_end(evt):
    msgs = [m for m in evt.get("messages", []) if m.get("role") == "assistant"]
    cost = sum((m.get("usage", {}).get("cost", {}) or {}).get("total", 0) or 0 for m in msgs)
    errors = [m.get("errorMessage") for m in msgs if m.get("stopReason") == "error"]
    failed = any(errors)
    text = None
    for m in reversed(msgs):
        t = " ".join(
            b.get("text", "") for b in m.get("content", []) if b.get("type") == "text"
        ).strip()
        if t:
            text = t
            break
    return RunReport(
        status="failed" if failed else "ok",
        tokens_in=_sum_tokens(msgs, "input"),
        tokens_out=_sum_tokens(msgs, "output"),
        turns=len(msgs) or None,
        cost_usd=float(cost),
        error="; ".join(e for e in errors if e) if failed else None,
        notes=(None if failed else text),
    )


def parse(lines):
    """Turn pi events into a :class:`RunReport` from the terminal ``agent_end`` event."""
    for line in reversed(lines):
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict) and evt.get("type") == "agent_end":
            return _from_agent_end(evt)
    return RunReport(status="failed", error="no agent_end event in pi output")


if __name__ == "__main__":
    # entrypoint.sh registers the LiteLLM provider and passes the massaged pi flags
    run_wrapper(["pi", *sys.argv[1:]], parse)
