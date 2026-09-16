"""Run-directory capture: writer + context-snapshot builder (spec 012).

Owns the write side of ``runs/<agent>/<date>/<run-id>/`` (contracts/run-directory.md ownership
table): create the directory, write ``context.json`` first (so the audit record exists even for a
crash before the first event), stream+redact the transcript, redact+move ``events.jsonl`` from the
image staging mount, and co-locate ``report.json``. Every string that lands in the directory
passes ``redact`` first, so the whole directory is secret-free (FR-013..016).

The context-snapshot builder assembles the orchestrator-known launch facts (contract R3) and
merges the small image-contributed fragment (instruction-file contents, MCP exposed tools,
completeness). Env values never appear — only ``runtime.env_names`` (FR-015), by construction.
"""
from __future__ import annotations

import json
import os
from typing import Iterable, Optional

import paths
import redact

# Files/directories with these permissions are readable by the non-root ui service (uid 1000),
# which mounts the data root read-only (contracts/run-directory.md).
_DIR_MODE = 0o755
_FILE_MODE = 0o644

# A workspace/output tree snapshot never descends past this many entries (guards a huge tree).
_MAX_TREE_ENTRIES = 2000


def _chmod(path: str, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass  # not owner (e.g. under tests) — leave as-is


def _file_tree(root: str) -> list[dict]:
    """Every file under ``root`` as ``[{"path": <relative>, "size": <bytes>}]`` (FR-010).

    Paths are relative to ``root`` so the snapshot is stable across relocation. Missing root →
    empty list. Bounded by ``_MAX_TREE_ENTRIES``.
    """
    out: list[dict] = []
    if not root or not os.path.isdir(root):
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            out.append({"path": os.path.relpath(full, root), "size": size})
            if len(out) >= _MAX_TREE_ENTRIES:
                return out
    return sorted(out, key=lambda e: e["path"])


def build_context(
    cfg: dict,
    *,
    prompt_text: str,
    append_system_prompt: Optional[str],
    image_ref: str,
    image_digest: str,
    env_names: list[str],
    mounts: list[dict],
    network: str,
    working_dir: Optional[str],
    workspace_dir: Optional[str],
    output_dir: Optional[str],
    memory: Optional[str] = None,
    cpus: Optional[str] = None,
    asset: Optional[dict] = None,
    fragment: Optional[dict] = None,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    stamp: Optional[str] = None,
) -> dict:
    """Assemble the context snapshot (``contracts/context-snapshot.schema.json``).

    Orchestrator-known fields come from ``cfg`` + the launch facts passed in; the image
    ``fragment`` (instruction files, per-server exposed tools, completeness) is merged when
    present. The result is NOT yet redacted — the writer redacts it on write.
    """
    tools: dict = {}
    if cfg.get("allowed_tools"):
        tools["allowed_tools"] = list(cfg["allowed_tools"])
    if cfg.get("disallowed_tools"):
        tools["disallowed_tools"] = list(cfg["disallowed_tools"])
    if cfg.get("permission_mode"):
        tools["permission_mode"] = cfg["permission_mode"]
    # MCP servers: names from cfg; the tools each exposed come from the image fragment.
    mcp_from_fragment = (fragment or {}).get("mcp_servers")
    if mcp_from_fragment:
        tools["mcp_servers"] = mcp_from_fragment

    context = {
        "prompt": {
            "prompt_text": prompt_text,
            "append_system_prompt": append_system_prompt,
        },
        "model": {
            "model": str(cfg.get("model") or ""),
            "effort": cfg.get("effort"),
            "fallback_model": cfg.get("fallback_model"),
        },
        "harness": {
            "harness": cfg["harness"],
            "harness_version": (fragment or {}).get("harness_version"),
            "image_ref": image_ref,
            "image_digest": image_digest,
        },
        "tools": tools,
        "instruction_files": list((fragment or {}).get("instruction_files") or []),
        "runtime": {
            "env_names": sorted(set(env_names)),
            "mounts": mounts,
            "network": network,
            "memory": memory,
            "cpus": cpus,
            "working_dir": working_dir,
        },
        "file_trees": {
            "workspace": _file_tree(workspace_dir) if workspace_dir else [],
            "output": _file_tree(output_dir) if output_dir else [],
        },
        "completeness": _completeness(fragment),
    }
    if asset:
        context["asset"] = asset
    if run_id or session_id or stamp:
        # Identity the viewer's Files tab uses to associate this run's /output artifacts (the output
        # convention embeds the session id in each filename); output_dir is the /output mount source.
        context["run"] = {"run_id": run_id, "session_id": session_id, "stamp": stamp,
                          "output_dir": output_dir}
    return context


def _completeness(fragment: Optional[dict]) -> dict:
    """The completeness statement (FR-012): the image fragment's when present, else a scaffold
    marking the snapshot incomplete (the fragment was not captured — e.g. crash before events)."""
    if fragment and isinstance(fragment.get("completeness"), dict):
        return fragment["completeness"]
    return {
        "complete": False,
        "undisclosed": ["harness context fragment"],
        "statement": "Harness context fragment was not captured for this run.",
    }


def merge_fragment(context: dict, fragment: Optional[dict]) -> dict:
    """Merge a late-arriving image fragment into an already-built context (T044).

    ``context.json`` is written first at launch (orchestrator-known fields only, so the audit
    record survives a crash before the first event); after the run the fragment's instruction
    files, MCP exposed tools, and completeness are merged in and the file rewritten.
    """
    if not fragment:
        return context
    if fragment.get("instruction_files"):
        context["instruction_files"] = list(fragment["instruction_files"])
    if fragment.get("mcp_servers"):
        context.setdefault("tools", {})["mcp_servers"] = fragment["mcp_servers"]
    if fragment.get("harness_version"):
        context.setdefault("harness", {})["harness_version"] = fragment["harness_version"]
    if isinstance(fragment.get("completeness"), dict):
        context["completeness"] = fragment["completeness"]
    return context


class RunCapture:
    """Writer for one run directory. All writes redact first (FR-013)."""

    def __init__(self, agent: str, date: str, run_id: str):
        self.agent = agent
        self.date = date
        self.run_id = run_id
        self.dir = paths.run_dir(agent, date, run_id)

    def path(self, filename: str) -> str:
        return os.path.join(self.dir, filename)

    @property
    def transcript_path(self) -> str:
        return self.path(paths.RUN_TRANSCRIPT)

    @property
    def events_path(self) -> str:
        return self.path(paths.RUN_EVENTS)

    @property
    def context_path(self) -> str:
        return self.path(paths.RUN_CONTEXT)

    @property
    def report_path(self) -> str:
        return self.path(paths.RUN_REPORT)

    def create(self) -> None:
        os.makedirs(self.dir, exist_ok=True)
        _chmod(self.dir, _DIR_MODE)

    def write_context(self, context: dict) -> str:
        """Redact every string in ``context`` and write ``context.json`` (written first)."""
        redacted = redact.redact_obj(context)
        with open(self.context_path, "w", encoding="utf-8") as f:
            json.dump(redacted, f, ensure_ascii=False, indent=2)
        _chmod(self.context_path, _FILE_MODE)
        return self.context_path

    @staticmethod
    def redact_line(line: str) -> str:
        """Redact one streamed transcript line (used by the factory's live stream)."""
        return redact.redact(line)

    def write_transcript_lines(self, lines: Iterable[str]) -> str:
        """Append redacted transcript lines (batch path; the factory streams live instead)."""
        with open(self.transcript_path, "a", encoding="utf-8") as f:
            for line in lines:
                f.write(redact.redact(line))
        _chmod(self.transcript_path, _FILE_MODE)
        return self.transcript_path

    def ingest_events(self, staging_path: str, remove_source: bool = True) -> bool:
        """Redact and move ``events.jsonl`` from the image staging mount into the run dir.

        Every string field of every event is redacted (FR-014). Returns True when a staged file
        was ingested, False when none was produced (e.g. the container crashed early).
        """
        if not staging_path or not os.path.exists(staging_path):
            return False
        with open(staging_path, encoding="utf-8") as src, \
                open(self.events_path, "w", encoding="utf-8") as dst:
            for raw in src:
                line = raw.rstrip("\n")
                if not line:
                    continue
                try:
                    evt = redact.redact_obj(json.loads(line))
                    dst.write(json.dumps(evt, ensure_ascii=False) + "\n")
                except ValueError:
                    dst.write(redact.redact(line) + "\n")  # non-JSON line: redact as text
        _chmod(self.events_path, _FILE_MODE)
        if remove_source:
            try:
                os.remove(staging_path)
            except OSError:
                pass
        return True

    def write_report(self, report: dict) -> str:
        """Co-locate ``report.json`` in the run dir (the spec-007 report).

        The report is NOT in the redaction set (contracts/redaction.md lists transcript, events,
        context only): it is the same spec-007 shape already carried in Dagster metadata, and its
        ``transcript_path`` is an orchestrator-authored path that must survive verbatim so the
        viewer's ``transcript`` link resolves.
        """
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        _chmod(self.report_path, _FILE_MODE)
        return self.report_path
