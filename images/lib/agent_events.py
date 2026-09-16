"""Normalized run events (spec 012, contract ``normalized-event.schema.json``).

The uniform, harness-agnostic event stream the Conversation view renders identically for
every harness (SC-002). Copied into every harness image alongside :mod:`lib.agent_report`;
each harness supplies a ``to_events(lines)`` that turns its native stream into a list of
:class:`NormalizedEvent`, and this module owns the shape, the JSONL writer, and the small
generic file-tree helpers a wrapper's context fragment builds instruction files from.

This module holds **nothing harness-specific**: the per-harness discovery of *which*
instruction files a CLI loads (the ``CLAUDE.md`` hierarchy vs ``AGENTS.md`` vs pi's files)
lives in each wrapper, using the generic walk/read primitives here (R2/R3).
"""
from __future__ import annotations

import datetime
import difflib
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

# The ephemeral staging mount the orchestrator bind-mounts at /staging (spec 012, T010a): the
# image writes events.jsonl + the context fragment here; the orchestrator redacts + moves them
# into the run directory. Overridable for tests. NOT /output (Constitution V) and NOT /pipes.
STAGING_DIR = os.environ.get("AGENT_STAGING_DIR", "/staging")
# events.jsonl on the staging mount. The orchestrator owns the final run-directory path.
EVENTS_PATH = os.environ.get("AGENT_EVENTS_PATH") or os.path.join(STAGING_DIR, "events.jsonl")
# The harness-contributed context fragment (instruction files, MCP exposed tools, completeness).
CONTEXT_FRAGMENT_PATH = os.environ.get("AGENT_CONTEXT_FRAGMENT_PATH") or os.path.join(
    STAGING_DIR, "context-harness.json"
)


def write_context_fragment(fragment: dict, path: str = CONTEXT_FRAGMENT_PATH) -> str:
    """Write the harness context fragment to the staging mount (merged by the orchestrator).

    Best-effort: a fragment the orchestrator never finds simply yields a snapshot marked
    incomplete, so a write failure must not fail the run.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fragment, f, ensure_ascii=False)
    except OSError:
        pass
    return path

# The seven event kinds — the same across every harness (FR-004). Kept here so a wrapper's
# to_events() and the tests import one authoritative set.
KINDS = ("system", "user", "assistant", "tool_call", "tool_result", "final", "error")

# Kinds that carry a `text` payload (FR-006). tool_call carries tool+args; tool_result result/diff.
_TEXT_KINDS = ("system", "user", "assistant", "final", "error")


def iso_now() -> str:
    """An ISO-8601 timestamp in the container's local zone (the run-stamp clock, TZ-aware)."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class NormalizedEvent:
    """One line of ``events.jsonl`` (``contracts/normalized-event.schema.json``).

    ``kind``/``ts``/``turn`` are always present. The numeric fields are ``None`` when the
    harness did not report them and are **omitted** on serialization — an absent field reads
    back as "not reported", kept distinct from a real ``0`` which is written as ``0`` (FR-005).
    Only the payload fields a kind actually carries are serialized.
    """

    kind: str
    turn: int = 0
    ts: str = field(default_factory=iso_now)
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    text: Optional[str] = None          # system/user/assistant/final/error
    tool: Optional[str] = None          # tool_call
    args: Optional[dict] = None         # tool_call
    result: Optional[str] = None        # tool_result
    diff: Optional[str] = None          # tool_result (file edit → unified diff)
    missing: bool = False               # tool_result (no faithful result — FR-008)

    def to_dict(self) -> dict:
        """The event as a schema-shaped dict: kind/ts/turn always; numerics only when
        reported (a real 0 is kept, ``None`` is dropped so it reads as null); the payload
        fields the kind carries."""
        d: dict = {"kind": self.kind, "ts": self.ts, "turn": self.turn}
        if self.tokens_in is not None:
            d["tokens_in"] = self.tokens_in
        if self.tokens_out is not None:
            d["tokens_out"] = self.tokens_out
        if self.cost_usd is not None:
            d["cost_usd"] = self.cost_usd
        if self.kind in _TEXT_KINDS:
            d["text"] = self.text or ""
        elif self.kind == "tool_call":
            d["tool"] = self.tool or ""
            d["args"] = self.args if self.args is not None else {}
        elif self.kind == "tool_result":
            d["result"] = self.result if self.result is not None else ""
            if self.diff is not None:
                d["diff"] = self.diff
            if self.missing:
                d["missing"] = True
        return d


def write_events(events: List[NormalizedEvent], path: str = EVENTS_PATH) -> str:
    """Write ``events`` to ``path`` as one JSON object per line, in order. Returns the path.

    Faithful order is preserved and content is never summarized (FR-007). The orchestrator
    later redacts every string field as it moves the file into the run directory (FR-013).
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            payload = e.to_dict() if isinstance(e, NormalizedEvent) else dict(e)
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")
    return path


# --- Generic instruction-file primitives (R3) --------------------------------
# A wrapper's context fragment decides WHICH files its harness loads; these helpers only walk
# a tree and read files. No harness-specific discovery lives here.

# Never read a file larger than this into a snapshot (guards a pathological instruction file).
MAX_INSTRUCTION_BYTES = 256 * 1024


def read_text_file(path: str, max_bytes: int = MAX_INSTRUCTION_BYTES) -> Optional[str]:
    """Read ``path`` as UTF-8 text (replacing undecodable bytes), or ``None`` if unreadable.

    Tolerant by design: a missing file, a permission error, or a directory returns ``None`` so
    a wrapper never crashes assembling its fragment.
    """
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", "replace")
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None


def find_files(root: str, filename: str, max_depth: int = 8) -> List[str]:
    """Every file named ``filename`` at or under ``root`` (sorted), to ``max_depth`` levels.

    Used by a harness fragment to discover, e.g., every ``CLAUDE.md`` reachable from the
    workspace. Returns an empty list when ``root`` does not exist.
    """
    root = os.path.abspath(root)
    found: List[str] = []
    if not os.path.isdir(root):
        return found
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - base_depth >= max_depth:
            dirnames[:] = []
        if filename in filenames:
            found.append(os.path.join(dirpath, filename))
    return sorted(found)


def diff_text(old: str, new: str, path: Optional[str] = None) -> str:
    """A unified diff of ``old`` → ``new`` as text (FR-006), for a file-edit tool result.

    The viewer renders each ``+``/``-`` line as an add/delete (FR-020). ``path`` labels the
    hunk headers. A ``Write`` of a new file passes ``old=""``.
    """
    label = path or "file"
    lines = difflib.unified_diff(
        (old or "").splitlines(),
        (new or "").splitlines(),
        fromfile=f"a/{label}", tofile=f"b/{label}", lineterm="",
    )
    return "\n".join(lines)


# Tool-name hints for structured file-edit tools across harnesses (FR-006). Names vary by
# harness (claude-code Edit/Write/MultiEdit/NotebookEdit; pi/others edit_file/write_file/…);
# edit_diff() also guards on the argument shape, so a tool that is not an edit yields no diff.
EDIT_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit",
              "edit_file", "write_file", "create_file", "str_replace", "str_replace_editor"}


def looks_like_edit(tool: Optional[str]) -> bool:
    """Whether ``tool`` names a file-edit tool, by the known set or a name hint (FR-006)."""
    if not tool:
        return False
    if tool in EDIT_TOOLS:
        return True
    low = tool.lower()
    return any(k in low for k in ("edit", "write", "patch", "create_file"))


def edit_diff(tool: Optional[str], args) -> Optional[str]:
    """A unified diff for a structured file-edit tool call, or ``None`` (FR-006).

    Harness-agnostic: recognizes the common ``{path, content | old/new | edits[]}`` argument
    shapes so a file edit renders as a diff for every harness, not only claude-code. Guards on
    the argument shape — a tool that is not actually an edit (or a diff we cannot faithfully
    build) yields ``None`` rather than a reconstruction (FR-008).
    """
    if not isinstance(args, dict):
        return None
    path = (args.get("file_path") or args.get("notebook_path") or args.get("path")
            or args.get("filename"))
    edits = args.get("edits")
    if isinstance(edits, list) and edits:
        chunks = [diff_text(e.get("old_string", e.get("old", "")),
                            e.get("new_string", e.get("new", "")), path)
                  for e in edits if isinstance(e, dict)]
        return "\n".join(c for c in chunks if c) or None
    for a, b in (("old_string", "new_string"), ("old_source", "new_source"),
                 ("old_str", "new_str"), ("old", "new")):
        if a in args or b in args:
            return diff_text(args.get(a, ""), args.get(b, ""), path)
    for key in ("content", "contents", "file_text", "text", "new_content"):
        if key in args:
            return diff_text("", args.get(key) or "", path)
    return None


def cli_version(argv: List[str], timeout: int = 10) -> Optional[str]:
    """Best-effort harness CLI version from ``argv`` (e.g. ``["claude", "--version"]``), or None.

    The first non-empty output line, trimmed. Any failure (missing CLI, timeout, non-zero exit
    with no output) yields ``None`` so a wrapper's fragment never crashes gathering it (FR-009).
    """
    import subprocess
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    text = (out.stdout or "").strip() or (out.stderr or "").strip()
    return text.splitlines()[0].strip() if text else None


def mcp_servers_from_names(names) -> List[dict]:
    """Group ``mcp__<server>__<tool>`` tool names into ``[{name, tools[]}]`` (FR-009).

    The ``mcp__server__tool`` naming is shared across harnesses, so any wrapper can disclose the
    MCP tools its native stream surfaced by feeding this the tool names it saw. Returns ``[]``
    when no MCP tool names are present.
    """
    servers: dict = {}
    for n in names:
        if isinstance(n, str) and n.startswith("mcp__"):
            parts = n.split("__", 2)
            if len(parts) == 3 and parts[1] and parts[2]:
                servers.setdefault(parts[1], set()).add(parts[2])
    return [{"name": name, "tools": sorted(tools)} for name, tools in sorted(servers.items())]


def stringify(value) -> str:
    """Coerce a native tool-result payload (str, or list of content blocks) to text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for b in value:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or "")
            else:
                parts.append(str(b))
        return "\n".join(p for p in parts if p)
    if isinstance(value, dict):
        return value.get("text") or value.get("content") or json.dumps(value, ensure_ascii=False)
    return str(value)


def instruction_files(paths: List[str]) -> List[dict]:
    """Turn a list of candidate paths into ``[{"path", "contents"}]`` (FR-009).

    Paths that do not exist or are unreadable are skipped. Contents are the full text; the
    orchestrator redacts them before they land in ``context.json`` (FR-013).
    """
    out: List[dict] = []
    for p in paths:
        contents = read_text_file(p)
        if contents is not None:
            out.append({"path": p, "contents": contents})
    return out
