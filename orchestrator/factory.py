"""Turns an agent YAML dict into a Dagster job that docker-runs the agent."""
import os, subprocess
from dagster import job, op, OpExecutionContext, ScheduleDefinition

REPO = "/opt/agentbox"

def make_run_op(cfg: dict):
    @op(name=f"run_{cfg['name'].replace('-', '_')}")
    def run_agent(context: OpExecutionContext):
        name = cfg["name"]
        cmd = [
            "docker", "run", "--rm",
            "--name", f"agent-{name}-{context.run_id[:8]}",
            "--memory", cfg.get("memory", "1g"),
            "--cpus", cfg.get("cpus", "1.5"),
            "--network", cfg.get("network", "agentnet"),
            "-v", f"{REPO}/prompts/{cfg['prompt_file']}:/config/prompt.md:ro",
            "-v", f"{cfg['output_dir']}:/output",
        ]
        if cfg["harness"] == "api":
            cmd += [
                "-e", f"AGENT_MODEL={cfg.get('model', 'cheap')}",
                "-e", f"AGENT_MAX_TOKENS={cfg.get('max_tokens', 1024)}",
                "-e", f"LITELLM_KEY={os.environ['LITELLM_MASTER_KEY']}",
                "agentbox/agent-python:latest",
            ]
        elif cfg["harness"] == "claude-code":
            with open(f"{REPO}/prompts/{cfg['prompt_file']}") as f:
                prompt = f.read()
            cmd += [
                "-v", "/data/credentials/claude:/creds:ro",
                "-e", "CLAUDE_CONFIG_DIR=/creds",
                "-v", f"{cfg.get('workspace', '/data/workspaces/' + name)}:/workspace",
                "-w", "/workspace",
                "agentbox/agent-claude:latest",
                "claude", "-p", prompt,
                "--output-format", "json",
                "--max-turns", str(cfg.get("max_turns", 10)),
            ] + (["--allowedTools"] + cfg["allowed_tools"] if cfg.get("allowed_tools") else [])
        else:
            raise ValueError(f"unknown harness: {cfg['harness']}")

        context.log.info(f"launching: {' '.join(cmd[:12])} ...")
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=cfg.get("timeout_seconds", 900),
        )
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
