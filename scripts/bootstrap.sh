#!/usr/bin/env bash
set -euo pipefail
# Agentbox bootstrap — idempotent host setup for a fresh Pi.
sudo apt update && sudo apt install -y git curl vim htop rsync
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
sudo mkdir -p /etc/docker
[ -f /etc/docker/daemon.json ] || echo '{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
# Raspberry Pi OS ships with cgroup memory accounting off, so `docker run --memory` is silently
# ignored. Enable it in the kernel command line; takes effect after a reboot.
if [ -f /boot/firmware/cmdline.txt ] && ! grep -q cgroup_enable=memory /boot/firmware/cmdline.txt; then
  sudo sed -i '1 s/$/ cgroup_enable=memory cgroup_memory=1/' /boot/firmware/cmdline.txt
  echo "Enabled cgroup memory accounting; reboot for container memory limits to take effect."
fi
sudo mkdir -p /data/{dagster,outputs,workspaces}
sudo mkdir -p /data/credentials/claude
sudo chown -R "$USER":"$USER" /data
chmod 700 /data/credentials
echo "Bootstrap complete."
