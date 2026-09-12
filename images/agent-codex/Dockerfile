# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-codex/Dockerfile -t agentbox/agent-codex:latest .
FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex
# dagster-pipes pinned to Dagster 1.13.21 (spec 007); pure-Python, zero-dependency.
RUN pip3 install --no-cache-dir --break-system-packages dagster-pipes==1.13.21
# credentials and config live in CODEX_HOME, mounted read-write from the host so token refreshes persist
ENV CODEX_HOME=/creds
COPY lib/ /app/lib/
COPY agent-codex/wrapper.py /app/wrapper.py
USER node
WORKDIR /workspace
# the wrapper spawns `codex exec ...` (the argv the orchestrator appends), tees its
# events to stdout, and reports the run over Dagster Pipes.
ENTRYPOINT ["python3", "/app/wrapper.py"]
