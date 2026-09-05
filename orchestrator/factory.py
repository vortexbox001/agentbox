"""Turns an agent YAML dict into a Dagster job that docker-runs the agent."""
import os, re, json, shutil, datetime, subprocess
from dagster import job, op, OpExecutionContext, ScheduleDefinition, Config, Field, Permissive

HOST_REPO = os.environ.get("AGENTBOX_HOST_REPO", "/home/vortex/GitHub/agentbox")
CONTAINER_REPO = "/opt/agentbox"
# full per-run transcripts: <root>/<agent>/<YYYY-MM-DD>/<run-id>.jsonl
AGENT_LOG_ROOT = "/data/dagster/agent-logs"

def make_run_op(cfg: dict):
    @op(
        name=f"run_{cfg['name'].replace('-', '_')}",
        config_schema={"env": Field(Permissive(), default_value={}, is_required=False)},
    )
    def run_agent(context: OpExecutionContext):
        name = cfg["name"]
        runtime_env = context.op_config.get("env", {})
        ws = cfg.get("workspace", "/data/workspaces/" + name)
        if cfg.get("wipe_workspace"):
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
            "-v", f"{HOST_REPO}/prompts/{cfg['prompt_file']}:/config/prompt.md:ro",
            "-v", f"{cfg['output_dir']}:/output",
        ]
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
            cmd += [
                # writable, node-owned config dir; only the two credential files come from the host (read-only)
                "--tmpfs", "/creds:uid=1000,gid=1000,mode=700",
                "-v", "/data/credentials/claude/.credentials.json:/creds/.credentials.json:ro",
                "-v", "/data/credentials/claude/.claude.json:/creds/.claude.json:ro",
                "-e", "CLAUDE_CONFIG_DIR=/creds",
                "-v", f"{ws}:/workspace",
                "-w", "/workspace",
                "agentbox/agent-claude:latest",
                "claude", "-p", prompt,
                # stream-json emits one JSON event per line (init, every assistant
                # turn + tool call, every tool result, final summary)
                "--output-format", "stream-json", "--verbose",
                "--max-turns", str(cfg.get("max_turns", 10)),
            ]
            if cfg.get("model"):
                cmd += ["--model", cfg["model"]]
            if cfg.get("permission_mode"):
                cmd += ["--permission-mode", cfg["permission_mode"]]
            if cfg.get("effort"):
                cmd += ["--effort", cfg["effort"]]
            system_extra = (
                "Write all output files to /output (not /workspace)."
                " Name every output file starting with today's date:"
                " YYYY-MM-DD_descriptive_name.md (e.g. 2026-09-05_documentation_review.md)."
                " Never read, list, or edit files in /output — only write new files there."
            )
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
        else:
            raise ValueError(f"unknown harness: {cfg['harness']}")

        context.log.info(f"launching: {' '.join(cmd[:12])} ...")
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=cfg.get("timeout_seconds", 900),
        )
        # persist the full event stream for this run
        log_dir = os.path.join(AGENT_LOG_ROOT, name, datetime.date.today().isoformat())
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
        if final:
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
