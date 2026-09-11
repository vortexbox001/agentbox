"""Turns an agent YAML dict into a Dagster job that docker-runs the agent."""
import os, re, json, uuid, shutil, datetime, subprocess
from dagster import (
    job, op, OpExecutionContext, ScheduleDefinition, Config, Field, Permissive,
    AssetKey, AssetsDefinition, DailyPartitionsDefinition, MetadataValue,
    AutomationCondition, AutomationConditionSensorDefinition, AssetSelection,
    DefaultSensorStatus, define_asset_job,
)

HOST_REPO = os.environ.get("AGENTBOX_HOST_REPO", "/home/vortex/GitHub/agentbox")
CONTAINER_REPO = "/opt/agentbox"

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
# full per-run transcripts: <root>/<agent>/<YYYY-MM-DD>/<run-id>.jsonl
AGENT_LOG_ROOT = "/data/dagster/agent-logs"
# harnesses that mount /workspace; `workspace` and `wipe_workspace` are ignored for the rest
WORKSPACE_HARNESSES = {"claude-code", "pi", "codex"}
# harnesses whose runner reads /config/prompt.md; the others get the prompt on the command line
PROMPT_MOUNT_HARNESSES = {"api"}

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
        ws = cfg.get("workspace", "/data/workspaces/" + name)
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
        cmd = [
            "docker", "run", "--rm",
            "--name", f"agent-{name}-{context.run_id[:8]}",
            "--memory", str(cfg.get("memory", "1g")),
            "--cpus", str(cfg.get("cpus", "1.5")),
            "--network", cfg.get("network", "agentnet"),
            "-v", f"{cfg['output_dir']}:/output",
        ]
        if cfg["harness"] in PROMPT_MOUNT_HARNESSES:
            cmd += ["-v", f"{HOST_REPO}/prompts/{cfg['prompt_file']}:/config/prompt.md:ro"]
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
            with open(f"{CONTAINER_REPO}/prompts/{cfg['prompt_file']}") as f:
                prompt = f.read()
            # writable, node-owned config dir; anything from the host is mounted read-only
            cmd += ["--tmpfs", "/creds:uid=1000,gid=1000,mode=700", "-e", "CLAUDE_CONFIG_DIR=/creds"]
            if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
                # long-lived token from `claude setup-token`: passthrough by name so the value
                # never appears in the command line, and no refreshable credentials file to go stale
                cmd += ["-e", "CLAUDE_CODE_OAUTH_TOKEN"]
            else:
                # fallback: a copied interactive login, which expires when the host login refreshes
                cmd += ["-v", "/data/credentials/claude/.credentials.json:/creds/.credentials.json:ro"]
            if os.path.exists("/data/credentials/claude/.claude.json"):
                # CLI settings/onboarding state; harmless without it but avoids first-run prompts
                cmd += ["-v", "/data/credentials/claude/.claude.json:/creds/.claude.json:ro"]
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
            with open(f"{CONTAINER_REPO}/prompts/{cfg['prompt_file']}") as f:
                prompt = f.read()
            # codex has no system-prompt flag; the output convention is appended to the prompt itself
            message = prompt.rstrip() + "\n\n" + output_convention(stamp, session_id)
            if cfg.get("append_system_prompt"):
                message += " " + cfg["append_system_prompt"]
            cmd += [
                # CODEX_HOME (auth.json, config.toml, sessions) is a dedicated host dir, mounted read-write so
                # codex can persist the token refreshes it performs; see README "Codex credentials"
                "-v", "/data/credentials/codex:/creds",
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
            with open(f"{CONTAINER_REPO}/prompts/{cfg['prompt_file']}") as f:
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

        # snapshot the output dir before launch so we can tell, after, which files this
        # run produced (FR-008a). The partition key is NEVER used here: the launch is
        # identical regardless of partition (FR-008b) — it is a metadata label only.
        output_before = _snapshot_dir(cfg["output_dir"])

        context.log.info(f"launching: {' '.join(cmd[:12])} ...")
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=cfg.get("timeout_seconds", 900),
        )
        # persist the full event stream for this run
        log_dir = os.path.join(AGENT_LOG_ROOT, name, stamp[:10])
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{context.run_id}.jsonl")
        with open(log_path, "w") as f:
            f.write(result.stdout)
        context.log.info(f"transcript: {log_path}")

        # After the container exits and the transcript is written, snapshot again and
        # attach materialization metadata to the op's single output. Harmless in job-mode
        # (nothing consumes the output); surfaced as materialization metadata in asset-mode
        # once from_op binds this output to the asset key (FR-008/FR-008a/FR-008b/FR-009).
        # The dict is deliberately open-ended so feature 005 can add token/cost fields here
        # with no change to the produces schema.
        output_files = _changed_files(output_before, _snapshot_dir(cfg["output_dir"]))
        metadata = {
            "output_files": MetadataValue.json(output_files),
            "transcript": MetadataValue.path(log_path),
            "run_stamp": stamp,
            "session_id": session_id,
            "harness": cfg["harness"],
            "model": str(cfg.get("model") or ""),
        }
        if context.has_partition_key:
            metadata["partition"] = context.partition_key
        context.add_output_metadata(metadata)

        # surface just the final "result" event in the Dagster log
        final = None
        for line in reversed(result.stdout.splitlines()):
            try:
                evt = json.loads(line)
            except ValueError:
                continue
            if isinstance(evt, dict) and evt.get("type") == "result":
                final = evt
                break
        if final is None and cfg["harness"] == "codex":
            usage = {"input_tokens": 0, "output_tokens": 0}; last_msg = ""; errors = []
            for line in result.stdout.splitlines():
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(evt, dict):
                    continue
                t = evt.get("type", "")
                if t == "turn.completed":
                    for k in usage:
                        usage[k] += (evt.get("usage") or {}).get(k, 0)
                elif t == "item.completed" and (evt.get("item") or {}).get("type") == "agent_message":
                    last_msg = evt["item"].get("text", "")
                elif t == "error":
                    errors.append(evt.get("message") or json.dumps(evt))
                final = evt
            if final is not None:
                context.log.info(
                    f"result: codex | tokens in/out={usage['input_tokens']}/{usage['output_tokens']}"
                    f" | is_error={bool(errors)}\n{last_msg[:4000]}"
                )
                if errors:
                    context.log.error("\n".join(errors)[-2000:])
        if final is None and cfg["harness"] == "pi":
            # summarise pi's agent_end event the way the claude-code result event is summarised
            for line in reversed(result.stdout.splitlines()):
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if isinstance(evt, dict) and evt.get("type") == "agent_end":
                    msgs = [m for m in evt.get("messages", []) if m.get("role") == "assistant"]
                    cost = sum((m.get("usage", {}).get("cost", {}) or {}).get("total", 0) for m in msgs)
                    errors = [m.get("errorMessage") for m in msgs if m.get("stopReason") == "error"]
                    text = ""
                    for m in reversed(msgs):
                        text = " ".join(b.get("text", "") for b in m.get("content", []) if b.get("type") == "text").strip()
                        if text:
                            break
                    context.log.info(
                        f"result: pi | turns={len(msgs)} | cost_usd={cost:.4f} | is_error={bool(errors)}\n{text[:4000]}"
                    )
                    if errors:
                        raise Exception(f"{name}: model error: {errors[-1]}")
                    final = evt
                    break
        if final:
            if final.get("type") == "result":
              context.log.info(
                f"result: {final.get('subtype')} | turns={final.get('num_turns')}"
                f" | is_error={final.get('is_error')}\n{str(final.get('result', ''))[:4000]}"
              )
        else:
            context.log.info(result.stdout[-4000:])

        if result.returncode != 0:
            context.log.error(result.stderr[-4000:])
            raise Exception(f"{name} exited {result.returncode}")
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
