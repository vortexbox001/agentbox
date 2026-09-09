"""Read and write agent definition files (agents/*.yaml).

The read side parses each file, classifies parse errors, runs schema migrations,
and separates schema-managed keys from unmanaged ones. The write side regenerates
the whole file from the schema via the emitter (contracts/agent-yaml.md): a
commented, sectioned, deterministic YAML document that ``yaml.safe_load`` turns
back into exactly the mapping the orchestrator expects.
"""
from __future__ import annotations

import glob
import os
import re
import tempfile

import yaml

import config
import schema
from schema import FIELDS, FIELDS_BY_ID, SECTIONS, HARNESS_BY_ID, ALWAYS_WRITTEN, SchemaTooNew


class StorageError(Exception):
    """A filesystem operation failed (permission, read-only mount, missing dir)."""

    def __init__(self, operation: str, path: str, os_error: OSError):
        self.operation = operation  # "read" | "write" | "delete"
        self.path = path
        self.os_error = os_error
        super().__init__(f"cannot {operation} {path}: {os_error}")


_SCHEMA_HEADER_RE = re.compile(r"^#\s*agentbox-schema:\s*(\d+)\s*$", re.MULTILINE)
_MISSING = object()


def _agents_dir() -> str:
    return config.AGENTS_DIR


def _path(stem: str) -> str:
    return os.path.join(_agents_dir(), f"{stem}.yaml")


def _safe_stem(stem: str) -> bool:
    """Reject path traversal and separators in a filename stem (FR-010a).

    The agent stem is the sole component of ``agents/<stem>.yaml``; a stem that
    carries a separator or ``..`` could escape the mount. Every store entry point
    checks this so traversal is refused consistently, not only at one endpoint.
    """
    return bool(stem) and not ("/" in stem or "\\" in stem or ".." in stem)


def _dagster(name: str) -> tuple[str, str]:
    job = "agent_" + str(name).replace("-", "_")
    return job, f"{config.DAGSTER_URL}/jobs/{job}"


def agent_exists(stem: str) -> bool:
    """Whether ``agents/<stem>.yaml`` already exists (create uniqueness check)."""
    return _safe_stem(stem) and os.path.isfile(_path(stem))


def read_agent(stem: str) -> dict:
    """Read one agent file into a rich definition dict.

    The returned dict always has: ``stem``, ``file``, ``agent`` (the definition,
    or None on parse error), ``parse_error``, ``raw`` (file text when unparsable),
    ``name_mismatch``, ``editable``, ``is_template``, ``schema_version``,
    ``dagster_job``, ``dagster_url``, and ``name`` (best-effort identity).
    """
    if not _safe_stem(stem):
        # Traversal or a separator in the stem: no such addressable agent (404).
        raise FileNotFoundError(stem)
    path = _path(stem)
    is_template = stem.startswith("_")
    result = {
        "stem": stem,
        "name": stem,
        "file": f"{stem}.yaml",
        "agent": None,
        "parse_error": None,
        "raw": None,
        "name_mismatch": False,
        "editable": True,
        "is_template": is_template,
        "schema_version": None,
    }
    result["dagster_job"], result["dagster_url"] = _dagster(stem)

    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise
    except OSError as e:
        raise StorageError("read", f"agents/{stem}.yaml", e)

    m = _SCHEMA_HEADER_RE.search(text)
    file_version = int(m.group(1)) if m else 0
    result["schema_version"] = file_version

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as e:
        result["parse_error"] = f"not valid YAML: {e}"
        result["raw"] = text
        return result

    if loaded is None or not isinstance(loaded, dict):
        result["parse_error"] = "file is empty or not a mapping"
        result["raw"] = text
        return result

    if "name" not in loaded or "harness" not in loaded:
        missing = [k for k in ("name", "harness") if k not in loaded]
        result["parse_error"] = f"missing required key(s): {', '.join(missing)}"
        result["raw"] = text
        return result

    try:
        loaded = schema.apply_migrations(loaded, file_version)
    except SchemaTooNew as e:
        result["parse_error"] = str(e)
        result["editable"] = False
        result["raw"] = text
        return result
    except Exception as e:
        # A migration function raised on this file: surface it as a parse error and
        # leave the file untouched (read never writes). It can still be deleted.
        result["parse_error"] = f"schema migration failed: {e}"
        result["raw"] = text
        return result

    # Separate schema-managed keys from unmanaged ones.
    managed: dict = {}
    unmanaged: dict = {}
    for k, v in loaded.items():
        if k in FIELDS_BY_ID:
            managed[k] = v
        else:
            unmanaged[k] = v
    if unmanaged:
        managed["unmanaged"] = unmanaged

    stored_name = loaded.get("name")
    result["name"] = stored_name if stored_name is not None else stem
    result["name_mismatch"] = stored_name != stem
    result["agent"] = managed
    return result


def list_agents() -> dict:
    """List all agent files, split into ``agents`` (non-template) and ``templates``.

    Each agent row carries the list-page fields from contracts/http-api.md; each
    template row carries just ``file`` and ``harness``.
    """
    agents: list[dict] = []
    templates: list[dict] = []
    try:
        paths = sorted(glob.glob(os.path.join(_agents_dir(), "*.yaml")))
    except OSError as e:
        raise StorageError("read", "agents/", e)

    for path in paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        info = read_agent(stem)
        if info["is_template"]:
            harness = info["agent"].get("harness") if info["agent"] else None
            templates.append({"file": info["file"], "harness": harness})
            continue
        agent = info["agent"] or {}
        row = {
            "name": info["name"],
            "file": info["file"],
            "enabled": agent.get("enabled") if info["agent"] else None,
            "harness": agent.get("harness") if info["agent"] else None,
            "model": agent.get("model") if info["agent"] else None,
            "schedule": agent.get("schedule") if info["agent"] else None,
            "dagster_job": info["dagster_job"],
            "dagster_url": info["dagster_url"],
            "parse_error": info["parse_error"],
            "name_mismatch": info["name_mismatch"],
            "editable": info["editable"],
        }
        agents.append(row)
    return {"agents": agents, "templates": templates}


# --- Emitter --------------------------------------------------------------
_HEADER_GENERATED = "# Generated by the agentbox UI — edits made here are replaced on the next save from the UI."


def _emit_scalar(value) -> str:
    """Serialise a single scalar the way it should appear after ``key:``.

    Uses PyYAML flow style so quoting is always valid, then strips the trailing
    document-end marker PyYAML adds for a bare scalar.
    """
    text = yaml.safe_dump(value, default_flow_style=True, allow_unicode=True, width=10**9)
    lines = text.splitlines()
    if lines and lines[-1] == "...":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _value_for(agent: dict, fid: str, harness: str):
    """The value to emit for a field, filling always-written defaults when missing."""
    if fid in agent:
        return agent[fid]
    if fid == "schedule":
        return ""
    if fid == "network":
        return HARNESS_BY_ID[harness]["default_network"]
    if fid == "enabled":
        return True
    return _MISSING


def _field_lines(agent: dict, f, harness: str) -> list[str]:
    """The emitted line(s) for one applicable field (real, commented, or list/map)."""
    help_text = schema.field_help(f.id, harness)
    raw = _value_for(agent, f.id, harness)
    unset = raw is _MISSING or schema._is_unset(f, raw)

    if unset and f.id not in ALWAYS_WRITTEN:
        return [f"#{f.id}:  # {help_text}"]

    if unset and f.id in ALWAYS_WRITTEN:
        # substitute a concrete default so the line is real
        raw = {"schedule": "", "network": HARNESS_BY_ID[harness]["default_network"],
               "enabled": True}.get(f.id, "")

    if f.type == "list":
        lines = [f"{f.id}:  # {help_text}"]
        for item in raw:
            lines.append(f"  - {_emit_scalar(item)}")
        return lines
    if f.type == "map":
        lines = [f"{f.id}:  # {help_text}"]
        for k, v in raw.items():
            lines.append(f"  {k}: {_emit_scalar(v)}")
        return lines
    return [f"{f.id}: {_emit_scalar(raw)}  # {help_text}"]


def emit_yaml(agent: dict) -> str:
    """Render an agent definition to its full YAML file text (contract agent-yaml.md).

    ``agent`` is a flat mapping of schema fields plus an optional ``unmanaged``
    sub-mapping (or unmanaged keys left at the top level). Output is deterministic:
    the same definition always produces byte-identical text.
    """
    harness = agent.get("harness")
    if harness not in HARNESS_BY_ID:
        raise ValueError(f"unknown harness: {harness!r}")

    desc = HARNESS_BY_ID[harness]["description"]
    lines = [f"# {desc}", _HEADER_GENERATED, f"# agentbox-schema: {schema.SCHEMA_VERSION}"]

    applicable = set(schema.applicable_fields(harness))
    for section in SECTIONS:
        sec_fields = [f for f in FIELDS if f.section == section["id"] and f.id in applicable]
        rendered: list[str] = []
        for f in sec_fields:
            raw = _value_for(agent, f.id, harness)
            has_value = not (raw is _MISSING or schema._is_unset(f, raw))
            if has_value or f.id in ALWAYS_WRITTEN:
                rendered.extend(_field_lines(agent, f, harness))
            else:
                rendered.append(f"#{f.id}:  # {schema.field_help(f.id, harness)}")
        # A section appears only if it holds at least one real (uncommented) line.
        if any(not ln.startswith("#") for ln in rendered):
            lines.append("")
            lines.append(f"# --- {section['label']} ---")
            lines.extend(rendered)

    # Unmanaged keys, emitted verbatim so the UI never drops what it does not know.
    unmanaged = dict(agent.get("unmanaged") or {})
    for k, v in agent.items():
        if k not in FIELDS_BY_ID and k != "unmanaged":
            unmanaged[k] = v
    if unmanaged:
        lines.append("")
        lines.append("# --- Unmanaged (not edited by the UI) ---")
        dumped = yaml.safe_dump(unmanaged, default_flow_style=False, allow_unicode=True, width=10**9)
        lines.extend(dumped.rstrip("\n").splitlines())

    return "\n".join(lines) + "\n"


def write_agent(stem: str, agent: dict) -> str:
    """Write an agent definition atomically. Returns the file path.

    ``name`` is forced to the filename stem (the identity, FR-010). The write is
    a temp file in the same directory then ``os.replace``; UTF-8, LF endings, one
    trailing newline.
    """
    if not _safe_stem(stem):
        raise ValueError(f"unsafe agent name: {stem!r}")
    agent = dict(agent)
    agent["name"] = stem
    text = emit_yaml(agent)
    directory = _agents_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{stem}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp, _path(stem))
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
    except OSError as e:
        raise StorageError("write", f"agents/{stem}.yaml", e)
    return _path(stem)


def delete_agent(stem: str) -> str:
    """Delete an agent file. Raises FileNotFoundError if absent. Touches nothing else."""
    if not _safe_stem(stem):
        raise FileNotFoundError(stem)
    path = _path(stem)
    try:
        os.remove(path)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise StorageError("delete", f"agents/{stem}.yaml", e)
    return f"{stem}.yaml"
