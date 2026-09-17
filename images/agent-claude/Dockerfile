# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-claude/Dockerfile -t agentbox/agent-claude:latest .
FROM agentbox/agent-base
# Common OS/tools, the Python runtime, the report library, and the working dir all come from
# agent-base (the single source of truth) — this thin layer adds only the harness.
RUN npm install -g @anthropic-ai/claude-code
COPY lib/ /app/lib/
COPY agent-claude/wrapper.py /app/wrapper.py
USER node
# the wrapper spawns `claude ...` (the argv the orchestrator appends), tees its
# stream-json to stdout, and reports the run over Dagster Pipes.
ENTRYPOINT ["python3", "/app/wrapper.py"]
