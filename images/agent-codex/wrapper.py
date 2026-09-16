"""codex harness wrapper (spec 007).

Runs ``codex``, tees its native events to stdout unchanged (FR-006), parses them into
the common run report, and emits it over Dagster Pipes. Per-harness parsing lives here,
not in the orchestrator (SC-002). ``cost_usd`` is null: codex runs on a subscription
(SC-001).
"""
import json
import sys

from lib.agent_events import (NormalizedEvent, cli_version, edit_diff, find_files,
                              instruction_files, looks_like_edit, mcp_servers_from_names,
                              stringify)
from lib.agent_report import RunReport, run_wrapper


def _mcp_servers(lines):
    """MCP servers + the tools each surfaced, from codex ``mcp__<server>__<tool>`` tool names
    seen in the stream (FR-009). codex emits no exposed-tool list event, so this reflects the
    MCP tools the run actually surfaced (shared parser)."""
    names = []
    for line in lines:
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if not isinstance(evt, dict):
            continue
        item = evt.get("item") or {}
        if isinstance(item, dict) and item.get("name"):
            names.append(item["name"])
    return mcp_servers_from_names(names)


def context_fragment(lines):
    """The codex context fragment (spec 012 US2): the AGENTS.md files the harness loads, the MCP
    tools its stream surfaced, and the completeness statement (the codex vendor base system
    prompt is not disclosed)."""
    files = instruction_files(find_files("/workspace", "AGENTS.md"))
    servers = _mcp_servers(lines)
    return {
        "instruction_files": files,
        "mcp_servers": servers or None,
        "harness_version": cli_version(["codex", "--version"]),
        "completeness": {
            "complete": False,
            "undisclosed": ["vendor base system prompt"],
            "statement": ("The codex vendor base system prompt is not disclosed by the harness. "
                          "Everything agentbox supplied — prompt, appended instructions, AGENTS.md "
                          "files — is shown in full."),
        },
    }


def _apply_patch_diff(command):
    """The codex ``apply_patch`` body as a diff, or None (FR-006).

    codex file edits are ``apply_patch`` shell calls carrying the patch inline. codex does not
    expose the pre-edit file contents, so we surface its patch body verbatim (its ``+``/``-``
    lines render as a diff) rather than reconstruct a unified diff we cannot build faithfully
    (FR-008). ``command`` may be a string or an argv list.
    """
    text = " ".join(command) if isinstance(command, (list, tuple)) else (command or "")
    if "apply_patch" not in text or "*** Begin Patch" not in text:
        return None
    start = text.index("*** Begin Patch")
    marker = "*** End Patch"
    end = text.find(marker)
    body = text[start:end + len(marker)] if end != -1 else text[start:]
    return body.strip() or None


def _tool_item(item):
    """A (tool, args, result, diff) tuple for a codex command/tool item, or None if not one."""
    itype = item.get("type", "")
    if itype in ("command_execution", "local_shell_call", "exec_command", "shell_call"):
        cmd = item.get("command") or item.get("aggregated_command") or ""
        out = item.get("aggregated_output") or item.get("output") or item.get("stdout") or ""
        return "shell", {"command": cmd}, stringify(out), _apply_patch_diff(cmd)
    if itype in ("function_call", "tool_call", "mcp_tool_call"):
        name = item.get("name") or "tool"
        args = item.get("arguments") or item.get("args") or {}
        diff = edit_diff(name, args) if looks_like_edit(name) else None
        return name, args, stringify(item.get("output") or item.get("result")), diff
    return None


def to_events(lines):
    """Turn codex ``exec --json`` events into the normalized stream (spec 012).

    ``turn.started`` bumps the turn; ``item.completed`` reasoning/agent_message → assistant,
    command/tool items → tool_call + tool_result; ``turn.completed`` usage attaches to the
    turn's last assistant event; ``error`` → error; the last agent_message is echoed as final.
    """
    events = []
    turn = 0
    last_assistant = None      # to hang per-turn usage on
    last_msg = None
    total_in = total_out = 0
    saw_usage = False
    for line in lines:
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if not isinstance(evt, dict):
            continue
        t = evt.get("type", "")
        if t == "turn.started":
            turn += 1
            last_assistant = None
        elif t == "item.completed":
            item = evt.get("item") or {}
            itype = item.get("type")
            if itype in ("reasoning", "agent_message"):
                ev = NormalizedEvent(kind="assistant", turn=max(turn, 1), text=item.get("text") or "")
                events.append(ev)
                last_assistant = ev
                if itype == "agent_message" and item.get("text"):
                    last_msg = item["text"]
            else:
                tool = _tool_item(item)
                if tool:
                    name, args, result, diff = tool
                    events.append(NormalizedEvent(kind="tool_call", turn=max(turn, 1),
                                                  tool=name, args=args if isinstance(args, dict) else {}))
                    events.append(NormalizedEvent(kind="tool_result", turn=max(turn, 1),
                                                  result=result, diff=diff))
        elif t == "turn.completed":
            usage = evt.get("usage") or {}
            ti, to = usage.get("input_tokens"), usage.get("output_tokens")
            if ti is not None or to is not None:
                saw_usage = True
                total_in += ti or 0
                total_out += to or 0
                if last_assistant is not None:
                    last_assistant.tokens_in = ti
                    last_assistant.tokens_out = to
        elif t == "error":
            events.append(NormalizedEvent(kind="error", turn=max(turn, 1),
                                          text=evt.get("message") or json.dumps(evt)))
    events.append(NormalizedEvent(
        kind="final", turn=max(turn, 0), text=last_msg or "",
        tokens_in=total_in if saw_usage else None, tokens_out=total_out if saw_usage else None,
    ))
    return events


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
    run_wrapper(["codex", *sys.argv[1:]], parse, to_events, context_fragment)
