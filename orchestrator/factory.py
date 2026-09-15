"""Turns an agent YAML dict into a Dagster job that docker-runs the agent."""
import os, re, json, uuid, shutil, tempfile, threading, datetime, subprocess
from collections import namedtuple
from dagster import (
    job, op, Output, OpExecutionContext, ScheduleDefinition, Config, Field, Permissive,
    AssetKey, AssetMaterialization, AssetObservation, AssetsDefinition, DailyPartitionsDefinition,
    MetadataValue,
    AutomationCondition, AutomationConditionSensorDefinition, AssetSelection,
    DefaultSensorStatus, define_asset_job,
    Out, Nothing,
    AssetSpec, AssetCheckSpec, AssetCheckResult, AssetCheckSeverity, MaterializeResult,
    open_pipes_session, PipesEnvContextInjector, PipesFileMessageReader,
)
from dagster_pipes import (
    encode_env_var, decode_env_var,
    DAGSTER_PIPES_CONTEXT_ENV_VAR, DAGSTER_PIPES_MESSAGES_ENV_VAR,
)

import paths

# Every state/config path derives from the single resolution point (orchestrator/paths.py,
# FR-002/SC-009): no literal /data or /opt/agentbox appears in this module.


def _output_dir(cfg: dict) -> str:
    """An agent's ``output_dir`` (mounted at ``/output``), or its documented default
    ``$AGENTBOX_DATA/outputs/<name>`` when omitted (FR-026)."""
    return cfg.get("output_dir") or paths.default_output_dir(cfg["name"])

# One or more kebab segments joined by "/" — the asset key an agent may declare in its
# `produces` block. Deliberately duplicated in ui/schema.py (research R6): the two run in
# separate containers with no shared import, and a shared-fixture test pins them in agreement.
ASSET_KEY_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"


def cron_timezone() -> str:
    """The timezone agent crons run in — the box's `TZ` (already the clock for run stamps),
    falling back to UTC. Applied to both job schedules and asset `on_cron` conditions so a cron
    fires at the operator's local wall-clock time, the way ordinary cron does — not silently in
    UTC. Set `TZ=UTC` in `.env` to keep UTC. Read at build time so a reload picks up a change.
    """
    return os.environ.get("TZ") or "UTC"


def is_valid_cron(value) -> bool:
    """The five-field / no-macro cron rule the removed `schedule` field enforced (FR-009).

    Deliberately duplicated in the UI's ``automation_store.py`` (research R6 / plan Complexity):
    the orchestrator and UI run in separate containers with no shared import, and a
    shared-fixture test pins the two copies in agreement. This orchestrator copy is a
    structural backstop (no ``croniter`` in the orchestrator image); the UI copy additionally
    runs ``croniter.is_valid`` as the stricter authoring guard.
    """
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s or s.startswith("@"):
        return False
    return len(s.split()) == 5


class RejectAgent(Exception):
    """One agent file was rejected at load; carries the offending file name so the
    caller can log a message that names it and skip only that file (FR-012/FR-019)."""

    def __init__(self, file: str, message: str):
        self.file = file
        self.message = message
        super().__init__(f"{file}: {message}")


def validate_asset_key(cfg: dict, file: str) -> str:
    """Validate an agent's `produces` block; return the asset key or raise RejectAgent.

    ``file`` is the name used in the rejection message (contract §4). A block with no
    asset, an asset not matching ASSET_KEY_RE, or a partition outside {none, daily} is
    rejected. An omitted partition is treated as ``none``.
    """
    produces = cfg.get("produces") or {}
    if not isinstance(produces, dict):
        raise RejectAgent(file, "produces must be a mapping with an asset")
    asset = produces.get("asset")
    if not asset:
        raise RejectAgent(file, "an asset declaration must name an asset")
    if not re.match(ASSET_KEY_RE, str(asset)):
        raise RejectAgent(file, f'invalid produces.asset "{asset}" — must match {ASSET_KEY_RE}')
    partition = produces.get("partition", "none")
    if partition not in ("none", "daily"):
        raise RejectAgent(file, f'invalid produces.partition "{partition}" — must be none or daily')
    return str(asset)


def validate_checks(cfg: dict, file: str) -> None:
    """Structural backstop for ``produces.checks`` at load (contract check-execution §6, FR-010).

    The UI's ``schema.validate`` is the authoring guard; this is the load-time backstop that
    keeps a hand-written bad file from reaching the container path. Raise ``RejectAgent`` (naming
    ``file``) when checks are present without a valid ``produces.asset``, when a check lacks a
    ``name`` or ``command``, or when two checks share a ``name``. An agent with no checks is a
    no-op here (FR-013). Fuller per-field validation (kebab pattern, timeout range, network enum)
    lives in the UI copy; this backstop enforces only the three structural invariants of §6.
    """
    produces = cfg.get("produces")
    checks = produces.get("checks") if isinstance(produces, dict) else None
    if not checks:
        return
    # Checks are children of the produced asset — they are meaningless without one (FR-010).
    asset = produces.get("asset") if isinstance(produces, dict) else None
    if not asset or not re.match(ASSET_KEY_RE, str(asset)):
        raise RejectAgent(file, "produces.checks requires a valid produces.asset (FR-010)")
    if not isinstance(checks, list):
        raise RejectAgent(file, "produces.checks must be a list of check objects")
    seen: set[str] = set()
    for i, c in enumerate(checks):
        if not isinstance(c, dict):
            raise RejectAgent(file, f"check #{i + 1} must be a mapping with a name and a command")
        name = c.get("name")
        if not name or not isinstance(name, str):
            raise RejectAgent(file, f"check #{i + 1} is missing a name")
        command = c.get("command")
        if not command or not isinstance(command, str) or not command.strip():
            raise RejectAgent(file, f'check "{name}" is missing a command')
        if name in seen:
            raise RejectAgent(
                file,
                f'duplicate check name "{name}" — check names must be unique within the agent',
            )
        seen.add(name)
# full per-run transcripts: <root>/<agent>/<YYYY-MM-DD>/<run-id>.jsonl. Now under
# $AGENTBOX_DATA/runs (moved out of the Dagster home — FR-010/R3).
RUNS_ROOT = paths.RUNS_ROOT
# per-run Dagster Pipes messages dirs. MUST live under a path bind-mounted identically
# on the host and inside the orchestrator container: agent containers are launched
# Docker-outside-of-Docker, so the host daemon resolves the `-v <pipes_dir>:/pipes`
# source against the HOST filesystem. /tmp is container-private and does not cross that
# boundary; the Dagster home is mounted host==container, so PIPES stays there (FR-010/FR-012).
PIPES_ROOT = paths.PIPES_ROOT
# harnesses that mount /workspace; `workspace` and `wipe_workspace` are ignored for the rest
WORKSPACE_HARNESSES = {"claude-code", "pi", "codex"}
# harnesses whose runner reads /config/prompt.md; the others get the prompt on the command line
PROMPT_MOUNT_HARNESSES = {"api"}
# Default check image = the producing agent's harness image (research R6): guaranteed present on
# the host (the agent just ran in it), so common shell checks need nothing built or pulled. The
# same image refs `_build_agent_cmd` launches, named here so `run_checks` can resolve a check's
# default image — a small, acknowledged duplication in the spirit of the ASSET_KEY_RE twin.
HARNESS_IMAGE = {
    "api": "agentbox/agent-python:latest",
    "claude-code": "agentbox/agent-claude:latest",
    "codex": "agentbox/agent-codex:latest",
    "pi": "agentbox/agent-pi:latest",
}

def output_convention(stamp: str, session_id: str) -> str:
    """System-prompt addition every tool-using harness gets, word for word."""
    return (
        "Write all output files to /output (not /workspace)."
        f" Name every output file exactly {stamp}_<descriptive_name>_{session_id}.md,"
        f" e.g. {stamp}_documentation_review_{session_id}.md"
        " (lowercase snake_case descriptive name; keep the prefix and suffix verbatim)."
        " Never read, list, or edit files in /output — only write finished files there,"
        " each in a single write. Use /workspace for drafts, scratch, and temporary files."
    )

# The feature epoch: fixed start for the daily partition set so it is bounded and
# identical across reloads (research R5 / contract §3).
PARTITION_START_DATE = "2026-09-09"


def _snapshot_dir(path: str) -> dict:
    """Map each file directly under ``path`` to ``(mtime, size)``; empty if absent.

    Non-recursive: the output convention writes flat files. Used for the before/after
    diff that tells the materialization which files a run produced (FR-008a / research R4).
    """
    snap: dict[str, tuple[float, int]] = {}
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                st = entry.stat()
                snap[entry.path] = (st.st_mtime, st.st_size)
    except FileNotFoundError:
        pass
    return snap


def _changed_files(before: dict, after: dict) -> list[str]:
    """Paths present in ``after`` that are new or whose mtime/size changed vs ``before``."""
    return sorted(p for p, meta in after.items() if before.get(p) != meta)


# --- Run report: read-back and metadata union (spec 007) --------------------
#
# The report the container hands back over Dagster Pipes has the fixed shape in
# contracts/run-report.schema.json. The orchestrator holds ZERO per-harness parsing
# (SC-002): every harness image translates its own native events into this shape.

REPORT_NUMERIC_FIELDS = ("tokens_in", "tokens_out", "turns", "cost_usd")
# rendered for a null numeric so it stays visually distinct from a real 0 (metadata.md).
NULL_NUMERIC_PLACEHOLDER = "—"


def _extract_report(session, is_asset: bool) -> dict | None:
    """Recover the report *fields* the container reported over Pipes, or ``None``.

    Used strictly as a data channel (contract §3): the reported result is read for
    its fields only and is NOT re-emitted, so an asset's happy path records exactly
    one materialization (the ``from_op`` output). Asset steps report via
    ``report_asset_materialization`` (read from ``get_reported_results``); job steps
    via ``report_custom_message({"report": ...})`` (read from ``get_custom_messages``).
    """
    if is_asset:
        results = session.get_reported_results()
        if results:
            md = getattr(results[-1], "metadata", None) or {}
            # metadata values arrive as typed MetadataValue objects; recover the raw value
            return {k: (v.value if hasattr(v, "value") else v) for k, v in md.items()}
        return None
    for msg in reversed(list(session.get_custom_messages())):
        if isinstance(msg, dict) and isinstance(msg.get("report"), dict):
            return dict(msg["report"])
    return None


def _stream_output(stream, transcript_file, forward) -> None:
    """Drain ``stream`` line by line (US3/R5): append each line to the transcript so
    the byte stream is unchanged (FR-006) and forward it live via ``forward`` (e.g.
    ``context.log.info``) so it appears in the Dagster run log while the run is still
    in flight (FR-003), rather than in one dump after the container exits.
    """
    for line in stream:
        transcript_file.write(line)
        forward(line.rstrip("\n"))


def _authored_report(status: str, error: str, files_written: int = 0) -> dict:
    """A report the orchestrator authors when the container could not report one —
    a timeout kill, or a missing/malformed report on a normal exit (FR-009/R8).

    Every numeric field is null (unmeasured), kept distinct from a real 0.
    """
    return {
        "status": status,
        "tokens_in": None,
        "tokens_out": None,
        "turns": None,
        "cost_usd": None,
        "files_written": files_written,
        "transcript_path": None,
        "error": error,
        "notes": None,
    }


def _numeric_md(value):
    """A numeric report field as Dagster metadata, keeping null distinct from 0."""
    if value is None:
        return MetadataValue.text(NULL_NUMERIC_PLACEHOLDER)
    if isinstance(value, bool):  # bool is an int subclass; render as text, never 0/1
        return MetadataValue.text(str(value))
    if isinstance(value, int):
        return MetadataValue.int(value)
    return MetadataValue.float(float(value))


def build_metadata(cfg: dict, report: dict, output_files: list[str], log_path: str,
                   stamp: str, session_id: str, context: OpExecutionContext) -> dict:
    """The metadata union attached to a run/materialization (contract metadata.md).

    The union of the run-report fields and the run-context fields recorded today.
    ``transcript_path`` from the report maps onto the existing ``transcript`` key
    (same host path) rather than a second key. Null numerics render distinct from 0
    and a null ``notes`` is omitted (never ``MetadataValue.md(None)``).
    """
    metadata = {
        # existing run-context fields (superset rule: every one of these stays present)
        "output_files": MetadataValue.json(output_files),
        "transcript": MetadataValue.path(log_path),
        "run_stamp": stamp,
        "session_id": session_id,
        "harness": cfg["harness"],
        "model": str(cfg.get("model") or ""),
        # report fields
        "status": MetadataValue.text(str(report.get("status"))),
        "tokens_in": _numeric_md(report.get("tokens_in")),
        "tokens_out": _numeric_md(report.get("tokens_out")),
        "turns": _numeric_md(report.get("turns")),
        "cost_usd": _numeric_md(report.get("cost_usd")),
        "files_written": MetadataValue.int(int(report.get("files_written") or 0)),
    }
    if report.get("error") is not None:
        metadata["error"] = MetadataValue.text(str(report["error"]))
    if report.get("notes") is not None:
        # markdown so an operator reads the run's closing note inline (FR-010/SC-006)
        metadata["notes"] = MetadataValue.md(str(report["notes"]))
    if context.has_partition_key:
        metadata["partition"] = context.partition_key
    return metadata


def _build_agent_cmd(cfg: dict, context: OpExecutionContext, stamp: str,
                     session_id: str, ws: str, runtime_env: dict) -> list[str]:
    """Build the full ``docker run`` argv for one agent launch.

    Extracted verbatim from the op body so the launch is defined in one place and the
    op can layer the Dagster Pipes flags onto it (spec 007). Every isolation flag is
    produced here exactly as before; the Pipes additions are inserted by the caller
    (contract pipes-transport.md §1), never here (FR-011/SC-007)."""
    name = cfg["name"]
    cmd = [
        "docker", "run", "--rm",
        "--name", f"agent-{name}-{context.run_id[:8]}",
        "--memory", str(cfg.get("memory", "1g")),
        "--cpus", str(cfg.get("cpus", "1.5")),
        "--network", cfg.get("network", "agentnet"),
        "-v", f"{_output_dir(cfg)}:/output",
    ]
    if cfg["harness"] in PROMPT_MOUNT_HARNESSES:
        # the prompt lives under the config root; the `-v` source is its HOST path (the host
        # daemon resolves bind sources — Docker-outside-of-Docker).
        cmd += ["-v", f"{paths.PROMPTS_DIR_HOST}/{cfg['prompt_file']}:/config/prompt.md:ro"]
    if cfg.get("env_file"):
        cmd += ["--env-file", cfg["env_file"]]
    for k, v in cfg.get("env", {}).items():
        ref = re.fullmatch(r"\$\{(\w+)\}", str(v))
        if ref:
            # passthrough: forward host env var into container without exposing the value
            cmd += ["-e", ref.group(1)]
        else:
            cmd += ["-e", f"{k}={v}"]
    for k, v in runtime_env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += ["-e", f"AGENTBOX_RUN_STAMP={stamp}", "-e", f"AGENTBOX_SESSION_ID={session_id}"]
    if os.environ.get("TZ"):
        # same clock inside the container, so `date` agrees with the run stamp
        cmd += ["-e", f"TZ={os.environ['TZ']}"]
    if cfg["harness"] == "api":
        cmd += [
            "-e", f"AGENT_MODEL={cfg.get('model', 'cheap')}",
            "-e", f"AGENT_MAX_TOKENS={cfg.get('max_tokens', 1024)}",
            "-e", f"LITELLM_KEY={os.environ['LITELLM_MASTER_KEY']}",
            "agentbox/agent-python:latest",
        ]
    elif cfg["harness"] == "claude-code":
        with open(os.path.join(paths.PROMPTS_DIR, cfg['prompt_file'])) as f:
            prompt = f.read()
        # writable, node-owned config dir; anything from the host is mounted read-only
        cmd += ["--tmpfs", "/creds:uid=1000,gid=1000,mode=700", "-e", "CLAUDE_CONFIG_DIR=/creds"]
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            # long-lived token from `claude setup-token`: passthrough by name so the value
            # never appears in the command line, and no refreshable credentials file to go stale
            cmd += ["-e", "CLAUDE_CODE_OAUTH_TOKEN"]
        else:
            # fallback: a copied interactive login, which expires when the host login refreshes
            cmd += ["-v", f"{paths.CREDENTIALS_ROOT}/claude/.credentials.json:/creds/.credentials.json:ro"]
        if os.path.exists(f"{paths.CREDENTIALS_ROOT}/claude/.claude.json"):
            # CLI settings/onboarding state; harmless without it but avoids first-run prompts
            cmd += ["-v", f"{paths.CREDENTIALS_ROOT}/claude/.claude.json:/creds/.claude.json:ro"]
        cmd += [
            "-v", f"{ws}:/workspace",
            "-w", "/workspace",
            "agentbox/agent-claude:latest",
            "claude", "-p", prompt,
            # stream-json emits one JSON event per line (init, every assistant
            # turn + tool call, every tool result, final summary)
            "--output-format", "stream-json", "--verbose",
            "--max-turns", str(cfg.get("max_turns", 10)),
            # fixed up front so the filename convention below can embed it
            "--session-id", session_id,
        ]
        if cfg.get("model"):
            cmd += ["--model", cfg["model"]]
        if cfg.get("permission_mode"):
            cmd += ["--permission-mode", cfg["permission_mode"]]
        if cfg.get("effort"):
            cmd += ["--effort", cfg["effort"]]
        system_extra = output_convention(stamp, session_id)
        if cfg.get("append_system_prompt"):
            system_extra += " " + cfg["append_system_prompt"]
        cmd += ["--append-system-prompt", system_extra]
        if cfg.get("fallback_model"):
            cmd += ["--fallback-model", cfg["fallback_model"]]
        if cfg.get("mcp_config"):
            cmd += ["--mcp-config", cfg["mcp_config"]]
        if cfg.get("disallowed_tools"):
            cmd += ["--disallowedTools"] + cfg["disallowed_tools"]
        if cfg.get("allowed_tools"):
            cmd += ["--allowedTools"] + cfg["allowed_tools"]
    elif cfg["harness"] == "codex":
        with open(os.path.join(paths.PROMPTS_DIR, cfg['prompt_file'])) as f:
            prompt = f.read()
        # codex has no system-prompt flag; the output convention is appended to the prompt itself
        message = prompt.rstrip() + "\n\n" + output_convention(stamp, session_id)
        if cfg.get("append_system_prompt"):
            message += " " + cfg["append_system_prompt"]
        cmd += [
            # CODEX_HOME (auth.json, config.toml, sessions) is a dedicated host dir, mounted read-write so
            # codex can persist the token refreshes it performs; see README "Codex credentials"
            "-v", f"{paths.CREDENTIALS_ROOT}/codex:/creds",
            "-v", f"{ws}:/workspace",
            "-w", "/workspace",
            "agentbox/agent-codex:latest",
            "exec", "--json", "--skip-git-repo-check", "-C", "/workspace",
            # the container is the sandbox; codex's own landlock sandbox is not available inside it
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        if cfg.get("model"):
            cmd += ["-m", cfg["model"]]
        if cfg.get("effort"):
            cmd += ["-c", f'model_reasoning_effort="{cfg["effort"]}"']
        cmd += [message]
    elif cfg["harness"] == "pi":
        with open(os.path.join(paths.PROMPTS_DIR, cfg['prompt_file'])) as f:
            prompt = f.read()
        model = cfg.get("model", "smart")
        if "/" not in model:
            model = f"litellm/{model}"   # provider registered by the image's entrypoint
        cmd += [
            "-e", "LITELLM_MASTER_KEY",      # passthrough; the entrypoint writes it into models.json
            "-v", f"{ws}:/workspace",
            "-w", "/workspace",
            "agentbox/agent-pi:latest",
            # print mode runs the full tool loop and exits; json emits one event per line
            "-p", "--mode", "json", "--model", model,
            "--append-system-prompt", output_convention(stamp, session_id)
            + ((" " + cfg["append_system_prompt"]) if cfg.get("append_system_prompt") else ""),
        ]
        if cfg.get("effort"):
            cmd += ["--thinking", cfg["effort"]]   # same level names as claude-code's effort
        if cfg.get("allowed_tools"):
            cmd += ["--tools", ",".join(cfg["allowed_tools"])]
        if cfg.get("disallowed_tools"):
            context.log.warning("pi has no tool denylist flag; disallowed_tools ignored")
        cmd += [prompt]
    else:
        raise ValueError(f"unknown harness: {cfg['harness']}")
    return cmd


# What a producer launch hands back to the emission logic (the caller decides whether to
# materialize, observe-and-raise, or run checks). ``report`` is the spec-007 report dict,
# ``metadata`` the built metadata union, ``log_path`` the transcript path.
_ProducerResult = namedtuple(
    "_ProducerResult", "report metadata returncode timed_out stderr log_path"
)


def _run_producer(context: OpExecutionContext, cfg: dict, session, cmd: list[str],
                  pipes_dir: str, msg_path: str, stamp: str, session_id: str,
                  is_asset: bool) -> "_ProducerResult":
    """Launch the producing container and hand back its report + metadata union.

    The shared launch+report core (spec 008 FR-013), extracted from ``make_run_op`` so both the
    checkless ``from_op`` op and the check-bearing ``@multi_asset`` op launch the producer the
    exact same way. Runs INSIDE an already-open Dagster Pipes ``session`` with ``cmd`` already
    built by ``_build_agent_cmd``: it layers the Pipes flags onto the launch, snapshots ``/output``,
    Popens and streams stdout live while draining stderr, enforces the agent ``timeout_seconds``
    (killing the container by name on expiry), recovers the spec-007 report over Pipes (data
    channel only — never re-emitted) or authors a fallback on timeout/missing report, and builds
    the metadata union. Emission and the per-run pipes-dir cleanup stay with the caller (checks
    must run before the dir is removed)."""
    name = cfg["name"]
    # PipesFileMessageReader.read_messages() has already created `msg_path` root-owned
    # 0644 (synchronously, before the session yielded); a non-root container cannot append to
    # that, so widen it to 0666 or claude-code/codex/pi emit() hit PermissionError on
    # /pipes/messages even though the dir is world-writable.
    os.chmod(msg_path, 0o666)
    boot = dict(session.get_bootstrap_env_vars())
    # the container writes messages at the mount path, not the host path
    msg_params = decode_env_var(boot[DAGSTER_PIPES_MESSAGES_ENV_VAR])
    msg_params["path"] = "/pipes/messages"
    pipes_flags = [
        "-v", f"{pipes_dir}:/pipes",
        "-e", f"{DAGSTER_PIPES_CONTEXT_ENV_VAR}={boot[DAGSTER_PIPES_CONTEXT_ENV_VAR]}",
        "-e", f"{DAGSTER_PIPES_MESSAGES_ENV_VAR}={encode_env_var(msg_params)}",
    ]
    # insert the Pipes flags immediately before the image name, so they are
    # docker-run flags (never container args) and every prior flag is untouched.
    img_idx = next(i for i, a in enumerate(cmd) if str(a).startswith("agentbox/"))
    cmd[img_idx:img_idx] = pipes_flags

    # snapshot /output before launch so we can report which files this run
    # produced (FR-005). The partition key is never used here: the launch is
    # identical regardless of partition (FR-008b) — it is a metadata label only.
    output_before = _snapshot_dir(_output_dir(cfg))

    context.log.info(f"launching: {' '.join(cmd[:12])} ...")
    timeout_seconds = cfg.get("timeout_seconds", 900)
    container = f"agent-{name}-{context.run_id[:8]}"
    log_dir = os.path.join(RUNS_ROOT, name, stamp[:10])
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{context.run_id}.jsonl")

    # Popen + line-by-line draining: each stdout line streams live into the
    # Dagster run log (FR-003) while being written to the transcript unchanged
    # (FR-006). stderr drains on a second thread so a chatty run cannot deadlock
    # on a full stderr pipe buffer (R5).
    timed_out = False
    stderr_chunks: list[str] = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1)
    with open(log_path, "w") as tf:
        stdout_thread = threading.Thread(
            target=_stream_output, args=(proc.stdout, tf, context.log.info),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=stderr_chunks.extend, args=(proc.stderr,), daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # kill the container by its deterministic name so `docker run` exits
            # (its stdout closes and the drain ends); `--rm` removes it (SC-004).
            timed_out = True
            subprocess.run(["docker", "kill", container], capture_output=True, text=True)
            context.log.error(f"{name}: timeout after {timeout_seconds}s; killed {container}")
            proc.wait()
        stdout_thread.join()
        stderr_thread.join()
    returncode = proc.returncode
    stderr = "".join(stderr_chunks)
    context.log.info(f"transcript: {log_path}")

    output_files = _changed_files(output_before, _snapshot_dir(_output_dir(cfg)))
    if timed_out:
        # the container was killed before it could report — the orchestrator
        # authors the report itself (FR-009/R8).
        report = _authored_report(
            "timeout",
            f"timeout_seconds ({timeout_seconds}) elapsed; container "
            f"agent-{name}-{context.run_id[:8]} was killed before it could report",
            len(output_files),
        )
    else:
        # Recover the structured report the container emitted over Pipes — as a
        # DATA channel only (contract §3): read for its fields, never re-emitted,
        # so an asset's happy path records exactly one materialization. All
        # per-harness event parsing lives in the images now; the orchestrator holds
        # none (SC-002).
        report = _extract_report(session, is_asset)
        if report is None:
            # normal exit but no readable/well-formed report — record the absence
            report = _authored_report(
                "failed", "run report was missing or malformed", len(output_files),
            )
    # the orchestrator owns the host transcript path (the container leaves it
    # null); it surfaces through the existing `transcript` metadata key.
    report["transcript_path"] = log_path

    metadata = build_metadata(cfg, report, output_files, log_path, stamp, session_id, context)
    context.log.info(
        f"result: status={report.get('status')} turns={report.get('turns')}"
        f" tokens_in/out={report.get('tokens_in')}/{report.get('tokens_out')}"
        f" cost_usd={report.get('cost_usd')} files_written={report.get('files_written')}"
    )
    if report.get("notes"):
        context.log.info(str(report["notes"])[:4000])
    return _ProducerResult(report, metadata, returncode, timed_out, stderr, log_path)


def _check_argv(cfg: dict, context: OpExecutionContext, check: dict, image: str,
                pipes_dir: str, ws: str) -> list[str]:
    """The full ``docker run`` argv for one check container (contract check-execution §3).

    ``/output`` and (when the agent has a workspace) ``/workspace`` are mounted **read-only**,
    the spec-007 report is mounted read-only at ``/report.json``, the command runs as
    ``sh -c "<command>"``, and the network is the check's ``network`` or ``none`` (no network,
    no env, no creds — Constitution I/III/V). The container is named deterministically and
    ``--rm``'d so no check container survives the run.
    """
    name = check["name"]
    network = check.get("network") or "none"
    cname = f"check-{cfg['name']}-{name}-{context.run_id[:8]}"
    argv = [
        "docker", "run", "--rm", "--name", cname,
        "--network", network,
        "-v", f"{_output_dir(cfg)}:/output:ro",
    ]
    if cfg["harness"] in WORKSPACE_HARNESSES:
        argv += ["-v", f"{ws}:/workspace:ro"]
    argv += [
        "-v", f"{os.path.join(pipes_dir, 'report.json')}:/report.json:ro",
        "--entrypoint", "sh", image, "-c", check["command"],
    ]
    return argv


def run_checks(cfg: dict, context: OpExecutionContext, checks: list, pipes_dir: str,
               ws: str) -> list:
    """Run each declared check in a fresh container, in declared order → [AssetCheckResult].

    For each check: resolve its image (``check.image`` or the harness default, R6), launch one
    ``--rm`` check container (``_check_argv``), capture combined stdout+stderr, and record one
    ``AssetCheckResult`` — ``passed`` on exit 0, else failed — carrying the last 4 KB of output,
    the exit code, ``timed_out``, and the check's ``blocking``/``image`` for legibility
    (contract §3). Each check is bounded by its own ``timeout_seconds`` (default 300, never
    unbounded): on expiry the container is ``docker kill``ed by name and the check fails with
    ``timed_out=True``; every remaining check still runs (no short-circuit, FR-008/FR-017).
    agentbox reads only the exit code; it attaches no meaning to what the command does
    (Constitution II).
    """
    # the partition key labels each check result on a partitioned materialize (FR-014, R10);
    # None for an unpartitioned asset, in which case no `partition` metadata key is set.
    partition = context.partition_key if getattr(context, "has_partition_key", False) else None
    results = []
    for check in checks:
        name = check["name"]
        blocking = bool(check.get("blocking", True))
        severity = AssetCheckSeverity.ERROR if blocking else AssetCheckSeverity.WARN
        image = check.get("image") or HARNESS_IMAGE.get(cfg["harness"])
        if not image:
            # the check's image could not be resolved (unknown harness, no explicit image) —
            # report THIS check failed with the resolution error and move on; a bad image never
            # aborts the materialization or the remaining checks (FR-015, contract §3).
            err = (
                f'could not resolve a check image: check "{name}" set no image and harness '
                f'"{cfg.get("harness")}" has no default image'
            )
            context.log.error(f"check {name}: {err}")
            metadata = {
                "output": MetadataValue.text(err),
                "exit_code": MetadataValue.text(NULL_NUMERIC_PLACEHOLDER),
                "timed_out": False,
                "blocking": blocking,
                "image": MetadataValue.text(str(check.get("image") or "")),
            }
            if partition is not None:
                metadata["partition"] = MetadataValue.text(partition)
            results.append(
                AssetCheckResult(check_name=name, passed=False, severity=severity,
                                 metadata=metadata)
            )
            continue
        argv = _check_argv(cfg, context, check, image, pipes_dir, ws)
        # each check is bounded by its own timeout_seconds — default 300, never unbounded (FR-008).
        timeout_seconds = int(check.get("timeout_seconds") or 300)
        cname = f"check-{cfg['name']}-{name}-{context.run_id[:8]}"
        context.log.info(f"check {name}: {' '.join(argv[:8])} ...")
        timed_out = False
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_seconds)
            exit_code = proc.returncode
            combined = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired as e:
            # kill the (still-running) container by name so none survives (--rm + kill),
            # then fail the check; every remaining check still runs (no short-circuit, FR-017).
            timed_out = True
            exit_code = -1
            subprocess.run(["docker", "kill", cname], capture_output=True, text=True)
            partial = (e.stdout or b"") if isinstance(e.stdout, bytes) else (e.stdout or "")
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            combined = f"{partial}\ncheck timed out after {timeout_seconds}s; killed {cname}"
            context.log.error(f"check {name}: timeout after {timeout_seconds}s; killed {cname}")
        # keep only the tail: the end (usually the failure) within 4 KB (FR-007/SC-006).
        tail = combined.encode("utf-8", "replace")[-4096:].decode("utf-8", "replace")
        passed = (exit_code == 0) and not timed_out
        metadata = {
            "output": MetadataValue.text(tail),
            "exit_code": MetadataValue.int(exit_code),
            "timed_out": timed_out,
            "blocking": blocking,
            "image": MetadataValue.text(str(image)),
        }
        # label the check with the producing run's partition when partitioned (FR-014, R10).
        if partition is not None:
            metadata["partition"] = MetadataValue.text(partition)
        context.log.info(f"check {name}: exit={exit_code} timed_out={timed_out} passed={passed}")
        # A blocking check is an ERROR (gates downstream automation), a non-blocking
        # one a WARN (advisory only) — the asset materializes either way (FR-006, R3).
        results.append(
            AssetCheckResult(
                check_name=name,
                passed=passed,
                severity=severity,
                metadata=metadata,
            )
        )
    return results


def make_run_op(cfg: dict):
    @op(
        name=f"run_{cfg['name'].replace('-', '_')}",
        config_schema={"env": Field(Permissive(), default_value={}, is_required=False)},
    )
    def run_agent(context: OpExecutionContext):
        name = cfg["name"]
        runtime_env = context.op_config.get("env", {})
        # every output file this run writes is named <stamp>_<descriptive_name>_<session_id>.md;
        # the stamp follows the Dagster process clock (set TZ in .env for local time)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        session_id = str(uuid.uuid4())
        context.log.info(f"session_id={session_id} stamp={stamp}")
        ws = cfg.get("workspace") or paths.default_workspace(name)
        if cfg.get("wipe_workspace") and cfg["harness"] in WORKSPACE_HARNESSES:
            # empty the workspace but keep the directory itself so its ownership
            # (uid 1000, which the agent image's user needs) is preserved.
            # Done before launch so runs killed by timeout still start clean.
            os.makedirs(ws, exist_ok=True)
            for entry in os.scandir(ws):
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path)
                else:
                    os.remove(entry.path)
            context.log.info(f"wiped workspace {ws}")
        cmd = _build_agent_cmd(cfg, context, stamp, session_id, ws, runtime_env)

        # Whether this op runs bound to an asset (asset-mode via from_op / a materializing
        # job) or as a plain job. The container decides report_asset_materialization vs
        # report_custom_message from the injected Pipes context; the orchestrator reads the
        # matching channel back. Both agree with cfg's produces block.
        is_asset = bool((cfg.get("produces") or {}).get("asset"))

        # Per-run Pipes messages file on a host temp dir, bind-mounted read-write at /pipes
        # (never /output — Constitution V). Layer Dagster Pipes over the existing docker run:
        # the launch argv is preserved verbatim except the /pipes mount and the two
        # DAGSTER_PIPES_* env vars (contract §1, FR-011/SC-007). It MUST sit under PIPES_ROOT
        # (a host==container shared mount), not the container-private /tmp: the host daemon
        # resolves the bind-mount source, so a /tmp dir would never reach the agent container.
        os.makedirs(PIPES_ROOT, exist_ok=True)
        pipes_dir = tempfile.mkdtemp(prefix=f"agentbox-pipes-{context.run_id[:8]}-", dir=PIPES_ROOT)
        # All harnesses but api run their container non-root (node, uid 1000 — see each image's
        # `USER`), while the orchestrator runs as root, so the per-run Pipes files must be
        # traversable and writable by that non-root user. mkdtemp makes the dir 0700; open it up
        # so the container can traverse into it (o+x) and, as a fallback, create the messages
        # file itself. The dir is ephemeral and rmtree'd below.
        msg_path = os.path.join(pipes_dir, "messages")
        os.chmod(pipes_dir, 0o777)
        try:
            with open_pipes_session(
                context,
                context_injector=PipesEnvContextInjector(),
                message_reader=PipesFileMessageReader(path=msg_path),
            ) as session:
                pr = _run_producer(
                    context, cfg, session, cmd, pipes_dir, msg_path, stamp, session_id, is_asset
                )

                if not pr.timed_out and pr.report.get("status") == "ok" and pr.returncode == 0:
                    # success: return the op's single output carrying the metadata union.
                    # from_op records the one materialization in asset-mode (harmless in
                    # job-mode). open_pipes_session puts the op in typed-event-stream mode,
                    # so the output must be produced explicitly rather than falling through.
                    return Output(value=None, metadata=pr.metadata)

                # failure (status != ok, non-zero exit, or timeout) — FR-007/FR-008, contract §3.
                if pr.stderr:
                    context.log.error(pr.stderr[-4000:])
                if is_asset:
                    # record the failed run as an OBSERVATION, not a materialization, then raise
                    # to mark the run failed. A materialization event is Dagster's positive signal
                    # that greens a partition, so emitting one here made a failed partition render
                    # MATERIALIZED (bug failed-asset-shows-materialized). An AssetObservation
                    # attaches the same report WITHOUT marking the partition materialized, so the
                    # failed run leaves the partition red WITH the report (SC-003). log_event emits
                    # it immediately, so it survives the raise.
                    context.log_event(
                        AssetObservation(
                            asset_key=AssetKey(cfg["produces"]["asset"].split("/")),
                            partition=context.partition_key if context.has_partition_key else None,
                            metadata=pr.metadata,
                        )
                    )
                else:
                    # job-only: attach the report to the run/output path (also visible as the
                    # logged Pipes custom message + transcript), then raise (FR-008).
                    context.add_output_metadata(pr.metadata)
                raise Exception(
                    f"{name}: run failed (status={pr.report.get('status')}, exit={pr.returncode})"
                )
        finally:
            shutil.rmtree(pipes_dir, ignore_errors=True)
    return run_agent

def build_asset(cfg: dict, file: str | None = None, cron: str | None = None):
    """Represent an agent that declares `produces` as a Dagster asset (contract §3).

    Wraps the SAME op ``make_run_op(cfg)`` would build for a job via
    ``AssetsDefinition.from_op`` — the container launch is not re-implemented and the
    compute step stays named ``run_<name>`` (Null Action / FR-010 / research R1–R2).
    ``partition: daily`` attaches a bounded ``DailyPartitionsDefinition``; ``none`` or
    omitted attaches none. The partition is a label only — materializing any partition
    (including a past date) launches the identical container (FR-008b).

    When ``cron`` is given (the agent's ``triggers.asset_schedule``), an
    ``AutomationCondition.on_cron`` is attached to the asset (FR-008). On a daily-partitioned
    root asset ``on_cron`` targets the latest (current-day) partition per tick (research R5);
    the operator-facing on/off toggle is the per-asset sensor from
    ``build_asset_automation_sensor`` (FR-021).
    """
    validate_asset_key(cfg, file or cfg.get("name", "<agent>"))
    key = AssetKey(cfg["produces"]["asset"].split("/"))
    partition = (cfg["produces"] or {}).get("partition", "none")
    partitions_def = (
        DailyPartitionsDefinition(start_date=PARTITION_START_DATE) if partition == "daily" else None
    )
    checks = (cfg["produces"] or {}).get("checks") or []
    if checks:
        # Check-bearing asset: a @multi_asset whose generator op runs the producer AND its checks
        # (from_op cannot declare check_specs — research R1). Checkless assets keep from_op (FR-013).
        return _build_checked_asset(cfg, key, partitions_def, cron, checks)
    the_op = make_run_op(cfg)  # the same op object job-mode would use
    automation_conditions = (
        {"result": AutomationCondition.on_cron(cron, cron_timezone=cron_timezone())} if cron else None
    )
    return AssetsDefinition.from_op(
        the_op,
        keys_by_output_name={"result": key},
        partitions_def=partitions_def,
        automation_conditions_by_output_name=automation_conditions,
    )


def _build_checked_asset(cfg: dict, key: AssetKey, partitions_def, cron: str | None,
                         checks: list):
    """A check-bearing asset whose one op runs the producer AND its checks (contract §1–§4).

    ``from_op`` cannot declare check specs (research R1), and ``@multi_asset`` derives each check's
    op-output name from the check name — which Dagster 1.13.21 rejects for a kebab name (a hyphen
    is not in ``^[A-Za-z0-9_]+$``). So the asset is assembled from a plain generator ``@op`` plus
    ``AssetsDefinition.dagster_internal_init``: check *i* is the op output ``check_<i>`` (a valid
    name) while its ``AssetCheckSpec`` keeps the operator's kebab ``name`` — so the asset check
    shows in Dagster exactly as written in YAML. One ``AssetSpec`` reattaches the daily partition
    and any ``on_cron`` condition unchanged.

    The op body launches the producer via the shared launch+report core (``_run_producer``), writes
    the report to ``<pipes_dir>/report.json`` for the checks to read, runs every check
    (``run_checks``), and — on producer success — yields one ``MaterializeResult`` carrying the
    metadata union and all the check results (R3). The per-run pipes dir is ``rmtree``d in
    ``finally``, after the checks have run.
    """
    name = cfg["name"]
    automation_condition = (
        AutomationCondition.on_cron(cron, cron_timezone=cron_timezone()) if cron else None
    )
    # check i -> output "check_<i>" (Dagster-valid) mapped to an AssetCheckSpec keeping the kebab
    # name. `blocking` (default true when omitted) makes a failing check gate downstream automation
    # while the asset still materializes (FR-006, contract §4).
    check_specs_by_output_name = {
        f"check_{i}": AssetCheckSpec(name=c["name"], asset=key,
                                     blocking=bool(c.get("blocking", True)))
        for i, c in enumerate(checks)
    }
    outs = {"result": Out(is_required=False)}
    for out_name in check_specs_by_output_name:
        outs[out_name] = Out(Nothing, is_required=False)

    @op(
        name=f"run_{name.replace('-', '_')}",
        out=outs,
        config_schema={"env": Field(Permissive(), default_value={}, is_required=False)},
    )
    def run_agent_checked(context: OpExecutionContext):
        runtime_env = context.op_config.get("env", {})
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        session_id = str(uuid.uuid4())
        context.log.info(f"session_id={session_id} stamp={stamp}")
        ws = cfg.get("workspace") or paths.default_workspace(name)
        if cfg.get("wipe_workspace") and cfg["harness"] in WORKSPACE_HARNESSES:
            os.makedirs(ws, exist_ok=True)
            for entry in os.scandir(ws):
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path)
                else:
                    os.remove(entry.path)
            context.log.info(f"wiped workspace {ws}")
        cmd = _build_agent_cmd(cfg, context, stamp, session_id, ws, runtime_env)

        os.makedirs(PIPES_ROOT, exist_ok=True)
        pipes_dir = tempfile.mkdtemp(prefix=f"agentbox-pipes-{context.run_id[:8]}-", dir=PIPES_ROOT)
        msg_path = os.path.join(pipes_dir, "messages")
        os.chmod(pipes_dir, 0o777)
        try:
            with open_pipes_session(
                context,
                context_injector=PipesEnvContextInjector(),
                message_reader=PipesFileMessageReader(path=msg_path),
            ) as session:
                pr = _run_producer(
                    context, cfg, session, cmd, pipes_dir, msg_path, stamp, session_id,
                    is_asset=True,
                )
                # Write the report where the checks can read it: a per-run file under PIPES_ROOT
                # (host==container shared), bind-mounted read-only at /report.json (R5). 0644 so a
                # non-root check container can read it; it is removed with the pipes dir below.
                report_path = os.path.join(pipes_dir, "report.json")
                with open(report_path, "w") as rf:
                    json.dump(pr.report, rf)
                os.chmod(report_path, 0o644)

                # Checks run regardless of the producer's outcome (clarification / R2/R4).
                results = run_checks(cfg, context, checks, pipes_dir, ws)

                if not pr.timed_out and pr.report.get("status") == "ok" and pr.returncode == 0:
                    # Producer OK: record the materialization with the metadata union and every
                    # check result in one step (R3, contract §4).
                    yield MaterializeResult(
                        asset_key=key, metadata=pr.metadata, check_results=results
                    )
                    return
                # Producer FAILED / TIMEOUT (contract §4, edge case): the checks already ran, so
                # yield every check verdict, then record the failed run as an OBSERVATION rather
                # than a materialization — an AssetObservation attaches the spec-007 report WITHOUT
                # greening the partition, so the partition stays red WITH its report (spec 007,
                # dagster-materialization-greens-partition). log_event / an explicit yield both emit
                # immediately, so they survive the raise below (asserted against the run's event log,
                # not all_events — quickstart §0 test lens).
                for r in results:
                    yield r
                context.log_event(
                    AssetObservation(
                        asset_key=key,
                        partition=context.partition_key if context.has_partition_key else None,
                        metadata=pr.metadata,
                    )
                )
                if pr.stderr:
                    context.log.error(pr.stderr[-4000:])
                raise Exception(
                    f"{name}: run failed (status={pr.report.get('status')}, exit={pr.returncode})"
                )
        finally:
            shutil.rmtree(pipes_dir, ignore_errors=True)

    return AssetsDefinition.dagster_internal_init(
        keys_by_input_name={},
        keys_by_output_name={"result": key},
        node_def=run_agent_checked,
        selected_asset_keys={key},
        can_subset=False,
        resource_defs=None,
        backfill_policy=None,
        check_specs_by_output_name=check_specs_by_output_name,
        selected_asset_check_keys=None,
        is_subset=False,
        specs=[AssetSpec(key=key, partitions_def=partitions_def,
                         automation_condition=automation_condition)],
        execution_type=None,
        hook_defs=None,
    )


def build_asset_automation_sensor(cfg: dict, asset_def: AssetsDefinition):
    """A per-asset automation-condition sensor for an asset-mode agent with a cron (FR-021).

    Named ``autocond_<name>`` and STOPPED by default, so an asset's cron is operator-toggleable
    and paused-by-default — the asset-mode parallel to a job schedule's per-schedule toggle
    (research R4). One sensor per automation asset means Dagster does not also attach its global
    default automation sensor to it.
    """
    return AutomationConditionSensorDefinition(
        name=f"autocond_{cfg['name'].replace('-', '_')}",
        target=AssetSelection.assets(asset_def),
        default_status=DefaultSensorStatus.STOPPED,
    )


def build_job(cfg: dict):
    """The agent's plain-op Dagster job — named ``agent_<name>`` — launching the container op.

    Used for a job-only agent (spec 006): its runs record no asset materialization. Triggering
    is read from the agent's own ``triggers.job_schedule`` and wired by ``build_schedule``
    against the job object this returns.
    """
    the_op = make_run_op(cfg)

    @job(name=f"agent_{cfg['name'].replace('-', '_')}")
    def agent_job():
        the_op()

    return agent_job


def build_materializing_job(cfg: dict, asset_def: AssetsDefinition):
    """The both-kind agent's job ``agent_<name>``: a job whose runs MATERIALIZE the asset (FR-006).

    ``define_asset_job`` selects the asset that already wraps ``make_run_op(cfg)`` via
    ``AssetsDefinition.from_op`` — the launch op is NOT re-implemented (FR-008), so a manual
    materialize, the asset's ``on_cron`` auto-condition, and this job's schedule all feed the
    one asset-materialization history. Also used as the carrier for the partition Null-Action
    fallback schedule (FR-015).
    """
    return define_asset_job(
        name=f"agent_{cfg['name'].replace('-', '_')}",
        selection=AssetSelection.assets(asset_def),
    )


def partition_on_cron_supported() -> bool:
    """Whether ``AutomationCondition.on_cron`` can target the correct partition on the installed
    Dagster (research R5 / FR-015). True on the pinned 1.13.21 — the primary path, where
    ``on_cron`` on a ``DailyPartitionsDefinition`` targets the latest (current-day) partition.

    The quickstart §8 build-time check gates which path ships; the primary path is the default.
    Setting ``AGENTBOX_PARTITION_FALLBACK=1`` forces the documented fallback (a partition-filling
    job schedule) — for an older Dagster where ``on_cron`` cannot target the right partition, or
    to exercise the fallback in tests. Duplicated in the UI's ``automation_store`` so the
    Automation page's ``fallback`` marker agrees with what the orchestrator wired (research R6).
    """
    return os.environ.get("AGENTBOX_PARTITION_FALLBACK", "").lower() not in ("1", "true", "yes")


def build_schedule(job_def, cron: str):
    """A ``ScheduleDefinition`` on ``cron`` for an already-built job (FR-007).

    Takes the SAME job object registered in the ``jobs`` list so exactly one ``agent_<name>``
    job exists per agent (a second job of that name would make Dagster reject the
    ``Definitions``). The name stays ``sched_<name>`` — identical to before spec 005 — so
    Dagster preserves a migrated schedule's prior on/off state (FR-014); no ``default_status``
    is set, so a new schedule starts paused (FR-021).
    """
    return ScheduleDefinition(
        job=job_def,
        cron_schedule=cron,
        name=f"sched_{job_def.name.removeprefix('agent_')}",
        execution_timezone=cron_timezone(),
    )
