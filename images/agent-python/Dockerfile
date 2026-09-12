# Build from the images/ directory so the shared lib (images/lib) is in the build
# context, e.g.:  docker build -f agent-python/Dockerfile -t agentbox/agent-python:latest .
FROM python:3.12-slim
# dagster-pipes: pinned to the orchestrator's Dagster (1.13.21) so the report wire
# format matches (spec 007). Pure-Python, zero-dependency.
RUN pip install --no-cache-dir dagster-pipes==1.13.21
COPY lib/ /app/lib/
COPY agent-python/runner.py /app/runner.py
WORKDIR /workspace
ENTRYPOINT ["python", "/app/runner.py"]
