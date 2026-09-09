FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex
# credentials and config live in CODEX_HOME, mounted read-write from the host so token refreshes persist
ENV CODEX_HOME=/creds
USER node
WORKDIR /workspace
ENTRYPOINT ["codex"]
