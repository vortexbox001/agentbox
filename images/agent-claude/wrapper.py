"""claude-code harness wrapper (spec 007).

Runs ``claude``, tees its native ``stream-json`` events to stdout unchanged (FR-006),
parses them into the common run report, and emits it over Dagster Pipes. The
per-harness parsing lives here, not in the orchestrator (SC-002). ``cost_usd`` is
null: claude-code runs on a subscription (SC-001).
"""
import json
import os
import sys

from lib.agent_events import (NormalizedEvent, cli_version, edit_diff, find_files,
                              instruction_files, looks_like_edit, mcp_servers_from_names,
                              stringify)
from lib.agent_report import RunReport, run_wrapper


def to_events(lines):
    """Turn claude-code ``stream-json`` events into the normalized event stream (spec 012).

    system(init) → system; each assistant text block → assistant, each tool_use → tool_call;
    each user tool_result → tool_result (with a synthesized diff for a file edit); the final
    ``result`` → final carrying the run's total usage. Turn increments per assistant message.
    """
    events = []
    turn = 0
    pending = {}  # tool_use_id -> (tool, input) for diff synthesis + result labeling
    for line in lines:
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if not isinstance(evt, dict):
            continue
        t = evt.get("type")
        if t == "system":
            # Only the `init` line is conversation-worthy; claude-code also streams many
            # `subtype:"thinking_tokens"` (and other) system lines that are internal counters —
            # skip them so they don't flood the timeline with duplicate "Session started" entries.
            if evt.get("subtype") != "init":
                continue
            tools = evt.get("tools") or []
            text = "Session started." + (f" Tools: {', '.join(tools)}." if tools else "")
            events.append(NormalizedEvent(kind="system", turn=0, text=text))
        elif t == "assistant":
            turn += 1
            for b in (evt.get("message") or {}).get("content", []) or []:
                if b.get("type") == "text" and b.get("text"):
                    events.append(NormalizedEvent(kind="assistant", turn=turn, text=b["text"]))
                elif b.get("type") == "tool_use":
                    pending[b.get("id")] = (b.get("name"), b.get("input") or {})
                    events.append(NormalizedEvent(kind="tool_call", turn=turn,
                                                  tool=b.get("name") or "", args=b.get("input") or {}))
        elif t == "user":
            for b in (evt.get("message") or {}).get("content", []) or []:
                if b.get("type") == "tool_result":
                    tool, inp = pending.get(b.get("tool_use_id"), (None, {}))
                    events.append(NormalizedEvent(
                        kind="tool_result", turn=turn,
                        result=stringify(b.get("content")),
                        diff=(edit_diff(tool, inp) if looks_like_edit(tool) else None),
                        missing=bool(b.get("is_error")) and not b.get("content"),
                    ))
        elif t == "result":
            usage = evt.get("usage") or {}
            events.append(NormalizedEvent(
                kind="final", turn=turn, text=str(evt.get("result") or ""),
                tokens_in=usage.get("input_tokens"), tokens_out=usage.get("output_tokens"),
            ))
    return events


def _mcp_servers(lines):
    """The MCP servers + the tools each exposed, from the claude-code ``system`` init event.

    claude-code lists every available tool in the init event; MCP tools are named
    ``mcp__<server>__<tool>`` (FR-009), so group those by server (shared parser).
    """
    names = []
    for line in lines:
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict) and evt.get("type") == "system":
            names.extend(evt.get("tools") or [])
    return mcp_servers_from_names(names)


def context_fragment(lines):
    """The claude-code context fragment (spec 012 US2): the CLAUDE.md hierarchy the harness loads,
    the MCP tools each server exposed, and the completeness statement (the vendor base system
    prompt is not disclosed by the harness)."""
    paths = find_files("/workspace", "CLAUDE.md")
    cfg_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg_dir:
        paths.append(os.path.join(cfg_dir, "CLAUDE.md"))
    paths.append(os.path.expanduser("~/.claude/CLAUDE.md"))
    files = instruction_files(list(dict.fromkeys(paths)))
    servers = _mcp_servers(lines)
    return {
        "instruction_files": files,
        "mcp_servers": servers or None,
        "harness_version": cli_version(["claude", "--version"]),
        "completeness": {
            "complete": False,
            "undisclosed": ["vendor base system prompt"],
            "statement": ("The claude-code vendor base system prompt is not disclosed by the "
                          "harness. Everything agentbox supplied — prompt, appended instructions, "
                          "instruction files, tools — is shown in full."),
        },
    }


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
    run_wrapper(sys.argv[1:], parse, to_events, context_fragment)
