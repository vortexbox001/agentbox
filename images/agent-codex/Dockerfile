# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-codex/Dockerfile -t agentbox/agent-codex:latest .
FROM agentbox/agent-base
# Common OS/tools, the Python runtime, the report library, and the working dir all come from
# agent-base (the single source of truth) — this thin layer adds only the harness.
RUN npm install -g @openai/codex
# credentials and config live in CODEX_HOME, mounted read-write from the host so token refreshes persist
ENV CODEX_HOME=/creds
COPY lib/ /app/lib/
COPY agent-codex/wrapper.py /app/wrapper.py
USER node
# the wrapper spawns `codex exec ...` (the argv the orchestrator appends), tees its
# events to stdout, and reports the run over Dagster Pipes.
ENTRYPOINT ["python3", "/app/wrapper.py"]
