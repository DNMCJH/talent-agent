#!/usr/bin/env bash
# One-shot Docker install for WSL2 Ubuntu.
# Run in WSL: bash scripts/install_docker_wsl.sh
# Requires NOPASSWD sudo for fully non-interactive operation.

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

echo "=== [1/7] Checking sudo (NOPASSWD expected) ==="
sudo -n true || { echo "ERROR: sudo requires password — set NOPASSWD first"; exit 1; }

echo "=== [2/7] Working around WSL systemctl shims (so post-install scripts don't fail) ==="
# WSL without systemd: stub deb-systemd-invoke to no-op so openssh-server etc. don't break apt
if [ ! -L /usr/bin/deb-systemd-invoke.orig ] && [ -f /usr/bin/deb-systemd-invoke ]; then
  sudo cp -n /usr/bin/deb-systemd-invoke /usr/bin/deb-systemd-invoke.orig 2>/dev/null || true
fi
# If systemctl is missing or fails, replace it with a no-op stub for the duration of installs.
# We DON'T overwrite a real systemctl if one exists; only stub if missing.
if ! command -v systemctl >/dev/null 2>&1; then
  echo "  systemctl missing — installing no-op stub"
  sudo tee /usr/local/sbin/systemctl > /dev/null <<'EOF'
#!/bin/sh
echo "systemctl stub (WSL non-systemd): $*" >&2
exit 0
EOF
  sudo chmod +x /usr/local/sbin/systemctl
fi

echo "=== [3/7] Repairing any half-installed packages from prior runs ==="
# Force-remove openssh-server if it's stuck in half-configured state (post-inst calls systemctl which doesn't work in WSL without systemd).
# It's not needed for docker, and re-installing only fixes it briefly.
if dpkg -s openssh-server 2>/dev/null | grep -q "Status:.*half-configured\|Status:.*unpacked"; then
  echo "  removing half-broken openssh-server"
  sudo -E dpkg --remove --force-remove-reinstreq openssh-server || true
fi
# Stub deb-systemd-invoke too — it calls dbus/systemd-run; not just systemctl.
if [ ! -L /usr/bin/deb-systemd-invoke.orig ] && [ -f /usr/bin/deb-systemd-invoke ]; then
  sudo cp -n /usr/bin/deb-systemd-invoke /usr/bin/deb-systemd-invoke.orig 2>/dev/null || true
  sudo tee /usr/bin/deb-systemd-invoke > /dev/null <<'EOF'
#!/bin/sh
echo "deb-systemd-invoke stub (WSL non-systemd): $*" >&2
exit 0
EOF
  sudo chmod +x /usr/bin/deb-systemd-invoke
fi
sudo -E dpkg --configure -a || true
{ sudo -E apt-get install -f -y || true; } 2>&1 | tail -20

echo "=== [4/7] Installing prerequisites ==="
sudo -E apt-get update -y
sudo -E apt-get install -y --no-install-recommends ca-certificates curl gnupg

echo "=== [5/7] Adding Docker apt repository ==="
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
fi
ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "=== [6/7] Installing Docker engine + compose plugin ==="
sudo -E apt-get update -y
sudo -E apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "=== [7/7] Adding $USER to docker group + starting daemon ==="
sudo usermod -aG docker "$USER"
sudo service docker start || sudo dockerd > /tmp/dockerd.log 2>&1 &
sleep 3

echo
echo "=== Verify ==="
sudo docker version || true
sudo docker compose version || true

echo
echo "DONE."
