# Deploy: Tencent Cloud VPS

Target: `tcloud` host (43.128.24.23, Ubuntu 24.04, 1C/1G/40G, SSH on 443).

## Capacity note

The VPS has only 1 GB RAM. Embedding model + Streamlit + Qdrant fit tightly.
Compose caps memory at 700M (app) + 300M (qdrant). Keep an eye on `docker stats`
during first run; if OOM, increase swap (`fallocate -l 2G /swapfile` …) before
shrinking limits.

## Port allocation

Already in use on `tcloud`: 443 (SSH), 9001 (ai-gateway), 9002 (vc-info-agent).
This deploy uses **9003** for the Streamlit container, bound to `127.0.0.1`.
External access is via Caddy on 443 (TLS termination).

## One-time setup

```bash
ssh tcloud
sudo mkdir -p /opt/talent-agent && sudo chown ubuntu:ubuntu /opt/talent-agent
cd /opt/talent-agent
git clone https://github.com/DNMCJH/talent-agent.git .
```

Create `/opt/talent-agent/.env`:

```ini
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
QDRANT_API_KEY=                      # set if exposing Qdrant publicly
```

## Ship the project index

Two options.

**Option A — copy local Qdrant data** (recommended; saves re-running LLM topic
extraction for every project on the VPS):

```powershell
# from your dev box
$src = 'a:\VScode\Code\Projects\talent-agent\data\qdrant_storage'
ssh tcloud "docker volume create talent-agent_qdrant_data >/dev/null && docker run --rm -v talent-agent_qdrant_data:/dst alpine sh -c 'rm -rf /dst/*'"
scp -r -P 443 $src/* tcloud:/tmp/qdrant_snapshot/
ssh tcloud "docker run --rm -v talent-agent_qdrant_data:/dst -v /tmp/qdrant_snapshot:/src alpine sh -c 'cp -r /src/* /dst/'"
```

**Option B — re-index on the host.** Push the parts of `PROJECTS_ROOT` you want
visible to the demo, then run `talent-index` inside the app container. Slower
and costs LLM tokens.

## Bring up the stack

```bash
ssh tcloud
cd /opt/talent-agent
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f app
```

Verify: `curl -I http://127.0.0.1:9003/` should return 200.

## Caddy reverse proxy

Append to `/etc/caddy/Caddyfile` (assuming Caddy is already handling 443):

```caddy
talent.<your-domain> {
    reverse_proxy 127.0.0.1:9003 {
        # Streamlit needs websockets for live updates
        header_up Host {host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

```bash
sudo systemctl reload caddy
```

If you don't have a domain pointed at the VPS yet, you can temporarily
`ssh -L 9003:127.0.0.1:9003 tcloud` and visit http://localhost:9003 from your
laptop while you set DNS up.

## Update flow

```bash
ssh tcloud
cd /opt/talent-agent
git pull
docker compose -f docker-compose.prod.yml up -d --build app
docker compose -f docker-compose.prod.yml logs --tail=100 app
```

Qdrant data persists in a named volume across rebuilds.

## Rollback

```bash
git log --oneline -5
git checkout <prev-sha>
docker compose -f docker-compose.prod.yml up -d --build app
```
