# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-pi/Dockerfile -t agentbox/agent-pi:latest .
FROM agentbox/agent-base
# Common OS/tools, the Python runtime, the report library, and the working dir all come from
# agent-base (the single source of truth) — this thin layer adds only the harness.
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent
COPY lib/ /app/lib/
COPY agent-pi/wrapper.py /app/wrapper.py
COPY agent-pi/entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh
USER node
# entrypoint.sh registers the LiteLLM provider then hands the massaged pi flags to the
# wrapper, which spawns `pi ...`, tees its events, and reports over Dagster Pipes.
ENTRYPOINT ["/app/entrypoint.sh"]
