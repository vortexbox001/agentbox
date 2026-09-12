"""The common run report and its Dagster Pipes emit path (spec 007, contract
``run-report.schema.json`` + ``pipes-transport.md`` §2).

Copied into every harness image so all four harnesses (api, claude-code, codex, pi)
hand back **one identical shape**. Each harness supplies its own parser that turns
its native events into a :class:`RunReport`; this module owns the shape, the
``/output`` file counter, and the single Pipes emit call — nothing harness-specific.

The container always leaves ``transcript_path`` null: only the orchestrator knows
the host path of the ``.jsonl`` transcript and fills it when merging metadata.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

# The report's field order, matching contracts/run-report.schema.json (required set).
REPORT_FIELDS = (
    "status",
    "tokens_in",
    "tokens_out",
    "turns",
    "cost_usd",
    "files_written",
    "transcript_path",
    "error",
    "notes",
)

# Where every harness writes its finished output files; the orchestrator mounts the
# run's host output dir here. Overridable for tests.
OUTPUT_DIR = os.environ.get("AGENT_OUTPUT_DIR", "/output")


@dataclass
class RunReport:
    """One run's structured record. Fields and nullability match the JSON schema.

    ``status`` is required; numeric fields are ``None`` when the run could not
    measure them (e.g. a timeout the orchestrator authors). ``cost_usd`` is
    ``None`` for subscription harnesses (claude-code, codex). ``transcript_path``
    is always left ``None`` here (the orchestrator fills it). ``error`` must be a
    string when ``status != "ok"`` and ``None`` when ``status == "ok"``.
    """

    status: str
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    turns: Optional[int] = None
    cost_usd: Optional[float] = None
    files_written: int = 0
    transcript_path: Optional[str] = None
    error: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """The report as a plain dict in schema field order."""
        return {k: getattr(self, k) for k in REPORT_FIELDS}


def snapshot_output(path: str = OUTPUT_DIR) -> dict:
    """Map each file directly under ``path`` to ``(mtime, size)``; empty if absent.

    Non-recursive, mirroring the orchestrator's ``/output`` snapshot: the output
    convention writes flat files. Take this once before the run, and pass it to
    :func:`count_written` after, to count the files the run wrote.
    """
    snap: dict[str, tuple] = {}
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                st = entry.stat()
                snap[entry.path] = (st.st_mtime, st.st_size)
    except FileNotFoundError:
        pass
    return snap


def count_written(before: dict, after: Optional[dict] = None, path: str = OUTPUT_DIR) -> int:
    """Count files in ``/output`` that are new or changed since ``before``.

    This is the harness's own in-container count. It is intentionally independent
    of — and may differ from — the orchestrator's ``output_files`` path-list diff
    (spec Assumptions / metadata contract): neither is derived from the other.
    """
    if after is None:
        after = snapshot_output(path)
    return sum(1 for p, meta in after.items() if before.get(p) != meta)


def emit(report: RunReport, is_asset: Optional[bool] = None) -> None:
    """Report ``report`` back to the orchestrator over the Dagster Pipes messages file.

    Opens the Pipes session (reading ``DAGSTER_PIPES_CONTEXT`` /
    ``DAGSTER_PIPES_MESSAGES`` from the env, writing to ``/pipes/messages``) and
    routes by step kind (contract §2.4):

    - **asset step** — an asset key is present in the injected context ⇒
      ``report_asset_materialization(metadata=<report fields>)``. The orchestrator
      recovers the fields via ``session.get_reported_results()`` (as data only).
    - **job step** — no asset key ⇒ ``report_custom_message({"report": <report>})``,
      read back via ``session.get_custom_messages()``.

    ``is_asset`` defaults to the injected context's ``is_asset_step`` so a harness
    wrapper need not know its own kind; pass it explicitly only to override.
    """
    from dagster_pipes import open_dagster_pipes

    data = report.to_dict()
    with open_dagster_pipes() as pipes:
        if is_asset is None:
            is_asset = pipes.is_asset_step
        if is_asset:
            # each report field becomes one metadata entry; Dagster wraps the plain
            # int/float/str/None values into typed MetadataValues the orchestrator
            # reads back via result.metadata[k].value.
            pipes.report_asset_materialization(metadata=data)
        else:
            pipes.report_custom_message({"report": data})


def tee_run(cli_argv: List[str], out=None) -> Tuple[int, List[str]]:
    """Spawn ``cli_argv``, echoing each stdout line to ``out`` (the container's stdout
    by default) **unchanged** as it arrives, and returning ``(returncode, lines)``.

    Teeing keeps the transcript byte stream identical to running the CLI directly
    (FR-006) while giving the wrapper the same lines to parse. stderr is left attached
    to the container's stderr (never merged into stdout) so it cannot pollute the
    ``.jsonl`` transcript.
    """
    out = out if out is not None else sys.stdout
    proc = subprocess.Popen(cli_argv, stdout=subprocess.PIPE, text=True, bufsize=1)
    lines: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        out.write(line)
        out.flush()
        lines.append(line.rstrip("\n"))
    proc.wait()
    return proc.returncode, lines


def run_wrapper(cli_argv: List[str], parse: "Callable[[List[str]], RunReport]") -> None:
    """The standard CLI-harness wrapper flow (claude-code, codex, pi).

    Snapshot ``/output``; spawn ``cli_argv`` teeing its native events to stdout;
    parse those events into a :class:`RunReport` with the harness-specific ``parse``;
    fill ``files_written`` from the ``/output`` count; emit the report over Pipes; and
    exit with a code matching the outcome — non-zero iff the run failed (FR-008). If
    the CLI exits non-zero but its events did not record a failure, the report is
    downgraded to ``failed`` so the two never disagree.
    """
    before = snapshot_output()
    returncode, lines = tee_run(cli_argv)
    report = parse(lines)
    report.files_written = count_written(before)
    if returncode != 0 and report.status == "ok":
        report.status = "failed"
        report.error = report.error or f"{cli_argv[0]} exited {returncode}"
    emit(report)
    sys.exit(0 if report.status == "ok" and returncode == 0 else (returncode or 1))
