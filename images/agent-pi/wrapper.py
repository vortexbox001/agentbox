"""pi harness wrapper (spec 007).

Runs ``pi``, tees its native events to stdout unchanged (FR-006), parses the
``agent_end`` event into the common run report, and emits it over Dagster Pipes.
Per-harness parsing lives here, not in the orchestrator (SC-002). ``cost_usd`` is
non-null: it is summed from pi's own per-message usage (SC-001).
"""
import json
import sys

from lib.agent_events import (NormalizedEvent, cli_version, edit_diff, find_files,
                              instruction_files, looks_like_edit, mcp_servers_from_names,
                              stringify)
from lib.agent_report import RunReport, run_wrapper


def _mcp_servers(lines):
    """MCP servers + the tools each surfaced, from ``mcp__<server>__<tool>`` tool_use names in
    pi's ``agent_end`` messages (FR-009, shared parser). ``[]``/None when pi used no MCP tool."""
    names = []
    for line in reversed(lines):
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict) and evt.get("type") == "agent_end":
            for m in evt.get("messages", []) or []:
                for b in m.get("content", []) or []:
                    if isinstance(b, dict) and b.get("type") in ("tool_use", "toolUse") and b.get("name"):
                        names.append(b["name"])
            break
    return mcp_servers_from_names(names)


def context_fragment(lines):
    """The pi context fragment (spec 012 US2): the instruction files pi loads, the MCP tools its
    stream surfaced, and a completeness statement of COMPLETE — pi adds no undisclosed vendor
    prompt, so the snapshot is exhaustive."""
    paths = find_files("/workspace", "AGENTS.md") + find_files("/workspace", "PI.md")
    files = instruction_files(list(dict.fromkeys(paths)))
    servers = _mcp_servers(lines)
    return {
        "instruction_files": files,
        "mcp_servers": servers or None,
        "harness_version": cli_version(["pi", "--version"]),
        "completeness": {
            "complete": True,
            "undisclosed": [],
            "statement": ("Complete — pi adds no undisclosed vendor system prompt. Everything the "
                          "agent was given (prompt, appended instructions, instruction files) is "
                          "shown in full."),
        },
    }


def _msg_usage(m):
    """(input, output, cost) from a pi assistant message's usage, tolerant of key naming."""
    usage = m.get("usage") or {}
    ti = usage.get("input", usage.get("input_tokens"))
    to = usage.get("output", usage.get("output_tokens"))
    cost = (usage.get("cost") or {}).get("total") if isinstance(usage.get("cost"), dict) else None
    return ti, to, cost


def _messages_to_events(messages):
    """Turn pi ``messages[]`` (from agent_end) into the normalized stream.

    A file-edit ``tool_use`` block is paired with its ``tool_result`` so the result carries a
    unified diff (FR-006) — by ``tool_use_id`` when pi provides one, else FIFO within the stream.
    """
    events = []
    turn = 0
    pending_by_id = {}   # tool_use_id -> diff, when pi pairs tool_use/result by id
    pending_diffs = []   # FIFO fallback for edit diffs awaiting their result

    def _take_diff(rid):
        if rid is not None and rid in pending_by_id:
            return pending_by_id.pop(rid)
        return pending_diffs.pop(0) if pending_diffs else None

    def _stash_diff(b):
        if not looks_like_edit(b.get("name")):
            return
        d = edit_diff(b.get("name"), b.get("input") or {})
        if not d:
            return
        bid = b.get("id") or b.get("toolUseId") or b.get("tool_use_id")
        if bid:
            pending_by_id[bid] = d
        else:
            pending_diffs.append(d)

    for m in messages:
        role = m.get("role")
        content = m.get("content") or []
        if role == "user":
            events.append(NormalizedEvent(kind="user", turn=turn,
                                          text=stringify([b for b in content if b.get("type") == "text"])))
            continue
        if role == "tool":
            rid = m.get("tool_use_id") or m.get("toolUseId") or m.get("id")
            events.append(NormalizedEvent(kind="tool_result", turn=turn,
                                          result=stringify(content), diff=_take_diff(rid)))
            continue
        if role == "assistant":
            turn += 1
            ti, to, cost = _msg_usage(m)
            first = True
            for b in content:
                bt = b.get("type")
                if bt == "text" and b.get("text"):
                    events.append(NormalizedEvent(
                        kind="assistant", turn=turn, text=b["text"],
                        tokens_in=ti if first else None, tokens_out=to if first else None,
                        cost_usd=cost if first else None,
                    ))
                    first = False
                elif bt in ("tool_use", "toolUse"):
                    events.append(NormalizedEvent(kind="tool_call", turn=turn,
                                                  tool=b.get("name") or "", args=b.get("input") or {}))
                    _stash_diff(b)
                elif bt in ("tool_result", "toolResult"):
                    rid = b.get("tool_use_id") or b.get("toolUseId") or b.get("id")
                    events.append(NormalizedEvent(kind="tool_result", turn=turn,
                                                  result=stringify(b.get("content")),
                                                  diff=_take_diff(rid)))
            if first:  # an assistant message with only non-text blocks still records usage once
                events.append(NormalizedEvent(kind="assistant", turn=turn, text="",
                                              tokens_in=ti, tokens_out=to, cost_usd=cost))
    return events


def to_events(lines):
    """Turn pi events into the normalized stream from the terminal ``agent_end`` (spec 012).

    ``agent_end.messages[]`` is the authoritative full transcript (content blocks incl. tool use +
    per-message usage); a final event echoes the last assistant text.
    """
    for line in reversed(lines):
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict) and evt.get("type") == "agent_end":
            events = _messages_to_events(evt.get("messages", []))
            last = next((e.text for e in reversed(events)
                         if e.kind == "assistant" and e.text), "")
            turn = events[-1].turn if events else 0
            events.append(NormalizedEvent(kind="final", turn=turn, text=last))
            return events
    return [NormalizedEvent(kind="error", turn=0, text="no agent_end event in pi output")]


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
    run_wrapper(["pi", *sys.argv[1:]], parse, to_events, context_fragment)
