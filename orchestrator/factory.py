"""Turns an agent YAML dict into a Dagster job that docker-runs the agent."""
import os, re, json, uuid, shutil, datetime, subprocess
from dagster import job, op, OpExecutionContext, ScheduleDefinition, Config, Field, Permissive

HOST_REPO = os.environ.get("AGENTBOX_HOST_REPO", "/home/vortex/GitHub/agentbox")
CONTAINER_REPO = "/opt/agentbox"
# full per-run transcripts: <root>/<agent>/<YYYY-MM-DD>/<run-id>.jsonl
AGENT_LOG_ROOT = "/data/dagster/agent-logs"
# harnesses that mount /workspace; `workspace` and `wipe_workspace` are ignored for the rest
WORKSPACE_HARNESSES = {"claude-code", "pi"}
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

def build_job_and_schedule(cfg: dict):
    the_op = make_run_op(cfg)

    @job(name=f"agent_{cfg['name'].replace('-', '_')}")
    def agent_job():
        the_op()

    sched = None
    if cfg.get("schedule"):
        sched = ScheduleDefinition(
            job=agent_job,
            cron_schedule=cfg["schedule"],
            name=f"sched_{cfg['name'].replace('-', '_')}",
        )
    return agent_job, sched
