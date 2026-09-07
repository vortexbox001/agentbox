FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh
USER node
WORKDIR /workspace
ENTRYPOINT ["/app/entrypoint.sh"]
