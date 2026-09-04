#!/usr/bin/env bash
set -euo pipefail
# Agentbox bootstrap — idempotent host setup for a fresh Pi.
sudo apt update && sudo apt install -y git curl vim htop rsync
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
sudo mkdir -p /etc/docker
[ -f /etc/docker/daemon.json ] || echo '{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
sudo mkdir -p /data/{dagster,outputs,workspaces,logs}
sudo mkdir -p /data/credentials/{claude,keys}
sudo chown -R "$USER":"$USER" /data
chmod 700 /data/credentials
echo "Bootstrap complete."
