#!/usr/bin/env bash
# Configure Docker registry mirrors for users behind GFW.
set -euo pipefail

sudo mkdir -p /etc/docker
cat <<'JSON' | sudo tee /etc/docker/daemon.json > /dev/null
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me",
    "https://hub.fast360.xyz",
    "https://docker.m.daocloud.io"
  ]
}
JSON

echo "--- /etc/docker/daemon.json ---"
cat /etc/docker/daemon.json

sudo service docker restart
sleep 3
sudo service docker status | head -5

echo "--- docker info mirrors ---"
sudo docker info 2>/dev/null | grep -A 5 "Registry Mirrors" || true
