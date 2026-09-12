# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-claude/Dockerfile -t agentbox/agent-claude:latest .
FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code
# dagster-pipes pinned to Dagster 1.13.21 (spec 007); pure-Python, zero-dependency.
RUN pip3 install --no-cache-dir --break-system-packages dagster-pipes==1.13.21
COPY lib/ /app/lib/
COPY agent-claude/wrapper.py /app/wrapper.py
USER node
WORKDIR /workspace
# the wrapper spawns `claude ...` (the argv the orchestrator appends), tees its
# stream-json to stdout, and reports the run over Dagster Pipes.
ENTRYPOINT ["python3", "/app/wrapper.py"]
