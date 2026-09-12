# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-pi/Dockerfile -t agentbox/agent-pi:latest .
FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent
# dagster-pipes pinned to Dagster 1.13.21 (spec 007); pure-Python, zero-dependency.
RUN pip3 install --no-cache-dir --break-system-packages dagster-pipes==1.13.21
COPY lib/ /app/lib/
COPY agent-pi/wrapper.py /app/wrapper.py
COPY agent-pi/entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh
USER node
WORKDIR /workspace
# entrypoint.sh registers the LiteLLM provider then hands the massaged pi flags to the
# wrapper, which spawns `pi ...`, tees its events, and reports over Dagster Pipes.
ENTRYPOINT ["/app/entrypoint.sh"]
