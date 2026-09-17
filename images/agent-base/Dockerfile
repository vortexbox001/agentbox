# agentbox/agent-base — the SINGLE SOURCE OF TRUTH for the common OS + tool set and the
# shared Python/dagster-pipes runtime every shell-based harness (agent-claude, agent-pi,
# agent-codex) builds `FROM`. Add or remove a tool shared by all shell-based agents HERE and
# nowhere else: change the one apt-get line below, rebuild the base and the harnesses, done —
# no harness Dockerfile changes (FR-003/SC-001/US2).
#
# Build from the images/ directory so the shared lib (images/lib) is in the build context and
# `COPY lib/` in the harnesses resolves, e.g.:
#   docker build -f agent-base/Dockerfile -t agentbox/agent-base .
#
# node:20-slim = Debian bookworm-slim (arm64 on the Pi target); provides Node 20 + npm (so
# harnesses can `npm install -g …`) and the uid-1000 `node` user each harness switches to.
FROM node:20-slim

# The one place the common CLI tool set lives (FR-002/FR-007). One apt-get layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates ripgrep jq unzip build-essential python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI ships from its own apt repo. Key + signed-by source list, arch pinned via
# dpkg --print-architecture so it matches the arm64 Pi target (research.md R2).
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Shared run-report runtime: dagster-pipes pinned to the orchestrator's Dagster (1.13.21) so the
# report wire format matches (spec 007). Identical pin to the current harnesses (FR-013/R3).
RUN pip3 install --no-cache-dir --break-system-packages dagster-pipes==1.13.21

WORKDIR /workspace

# Final USER is left as the image default (root) on purpose so each thin harness can `npm install -g …`;
# the uid-1000 `node` user is inherited and available, and every harness switches to it (`USER node`)
# as its own last step — preserving today's non-root run (data-model.md).
