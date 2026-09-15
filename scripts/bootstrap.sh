#!/usr/bin/env bash
set -euo pipefail
# Agentbox bootstrap — idempotent host setup for a fresh Pi.
#
# Creates the three roots' host directories (contracts/path-resolution.md §1) with the right
# ownership: the instance-state subtree owned by the runtime user, its credentials/ and keys/
# owner-only (FR-011/FR-022). Reads the same env vars the services do; the defaults match.

# scripts/bootstrap.sh -> repo root (the product checkout).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

AGENTBOX_CONFIG="${AGENTBOX_CONFIG:-$REPO_ROOT/config}"
AGENTBOX_DATA="${AGENTBOX_DATA:-/data/agentbox}"
DAGSTER_HOME="${DAGSTER_HOME:-/data/dagster}"
AGENTBOX_UID="${AGENTBOX_UID:-1000}"
AGENTBOX_GID="${AGENTBOX_GID:-1000}"

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

# --- Instance-state root ($AGENTBOX_DATA) -----------------------------------
# Backed up as a unit; owned by the runtime user (uid:gid the agent images run as).
sudo mkdir -p \
  "$AGENTBOX_DATA"/runs \
  "$AGENTBOX_DATA"/outputs \
  "$AGENTBOX_DATA"/workspaces \
  "$AGENTBOX_DATA"/repo-mirrors \
  "$AGENTBOX_DATA"/provenance \
  "$AGENTBOX_DATA"/credentials/claude \
  "$AGENTBOX_DATA"/keys
sudo chown -R "$AGENTBOX_UID":"$AGENTBOX_GID" "$AGENTBOX_DATA"
# Secrets never in the open: credentials and box keys are owner-only (FR-011).
sudo chmod 700 "$AGENTBOX_DATA"/credentials "$AGENTBOX_DATA"/keys

# --- Dagster-storage root ($DAGSTER_HOME) -----------------------------------
# Dagster's own storage/history/compute_logs live here plus the transient pipes dir; the
# orchestrator/daemon own it.
sudo mkdir -p "$DAGSTER_HOME"
sudo chown -R "$AGENTBOX_UID":"$AGENTBOX_GID" "$DAGSTER_HOME"

# --- Instance-configuration root ($AGENTBOX_CONFIG) -------------------------
# Seed a fresh box by copying examples/config/ here (quickstart US2); left empty otherwise.
sudo mkdir -p "$AGENTBOX_CONFIG"
sudo chown "$AGENTBOX_UID":"$AGENTBOX_GID" "$AGENTBOX_CONFIG"

# /data/logs (if present) is not agentbox-owned — left untouched (Clarification C).

echo "Bootstrap complete."
echo "  config: $AGENTBOX_CONFIG"
echo "  data:   $AGENTBOX_DATA"
echo "  dagster:$DAGSTER_HOME"
