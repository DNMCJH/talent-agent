# Backend Smoke Test (Phase 1.5 起步)

目标：确认 `docker compose up -d` 起得来，`GET /health` 返回 200，Alembic 能在 Postgres 里建表。

## TL;DR — WSL2 Ubuntu 一键脚本

```bash
cd /mnt/a/VScode/Code/Projects/talent-agent

# 装 docker（需要 sudo NOPASSWD，否则中途会问密码）
bash scripts/install_docker_wsl.sh

# 境内必跑：换 docker registry 镜像源（否则拉 docker.io 卡 TLS handshake）
bash scripts/setup_docker_mirror.sh

# 跑 smoke test（自动 .env、起容器、alembic migrate、curl /health）
bash scripts/smoke_test.sh
```

脚本自动复制 `.env.example → .env`、生成随机 `API_SECRET`、起 4 个容器、等 postgres healthy、alembic autogenerate+upgrade、把 migration 拷回宿主、curl /health + /auth/me + /match 验证。

下方是手动版（脚本失败时 debug 用）。

## 前置准备

### 装 Docker（WSL2 Ubuntu，推荐）

```bash
# 在 WSL Ubuntu 里
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 允许非 root 用 docker
sudo usermod -aG docker $USER
newgrp docker

# 启动 daemon (WSL2 systemd 模式需要先开 systemd)
sudo service docker start

# 验证
docker version && docker compose version
```

如果用 Docker Desktop：直接装 Windows 版，安装时勾选 "Use WSL 2 based engine"，装完 PowerShell / WSL 里都能用 `docker` 命令。

### 准备 .env

```bash
cd /mnt/a/VScode/Code/Projects/talent-agent  # 或 WSL 路径
cp .env.example .env
```

最少要填这几个才能 smoke test：
```
LLM_API_KEY=sk-...        # 你的 DeepSeek key（smoke test 不调，可留空）
API_SECRET=随便一个32字符以上的字符串
GITHUB_CLIENT_ID=          # 测 /auth/github 才需要，否则留空
GITHUB_CLIENT_SECRET=
```

Postgres / Redis / Qdrant 的 DSN 不用改，compose 里已经 override 成容器名。

## Step 1: 起服务

```bash
cd /path/to/talent-agent
docker compose up -d --build
```

首次 build backend 镜像约 5-10 分钟（拉 python 镜像 + uv 装依赖 + 拉 sentence-transformers 时下载 torch CPU 包 ~200MB）。

观察启动日志：
```bash
docker compose logs -f backend
```

## Step 2: 跑 Alembic 迁移

第一次需要生成 migration（autogenerate 从 ORM 推断）：

```bash
docker compose exec backend alembic revision --autogenerate -m "initial schema"
docker compose exec backend alembic upgrade head
```

预期：在 `backend/alembic/versions/` 下出现 `xxxx_initial_schema.py`，Postgres 里出现 `users / projects / interview_sessions / weaknesses / alembic_version` 5 张表。

检查表：
```bash
docker compose exec postgres psql -U talent -d talent -c "\dt"
```

## Step 3: 健康检查

```bash
curl http://localhost:8000/health
# 期望: {"status":"ok"}

curl http://localhost:8000/docs
# 期望: Swagger UI HTML
```

## Step 4: 测 /auth/me（应该 401）

```bash
curl -i http://localhost:8000/auth/me
# 期望: HTTP/1.1 401 Unauthorized, body: {"detail":"missing bearer token"}
```

## 验收清单
- [ ] `docker compose ps` 显示 4 个容器 `Up` 状态
- [ ] `/health` 返回 `{"status":"ok"}`
- [ ] Postgres 里能 `\dt` 看到 5 张表
- [ ] `/auth/me` 不带 token 返回 401
- [ ] `/match` 返回 501 (说明路由注册了，业务待接)

## 常见问题

**backend 容器起不来，报 `asyncpg` 连不上 postgres**
- 看 `docker compose logs postgres` 是不是还在初始化（首次启动会慢 20-30s）
- compose 里加了 `depends_on: postgres: condition: service_healthy`，理论上不会先于 pg ready 起 backend；如果你改了 compose 把这个删了，记得加回来

**alembic autogenerate 生成的 migration 是空的**
- 检查 `backend/alembic/env.py` 里 `from app.models import *  # noqa` 这行有没有被删
- 检查 `target_metadata = Base.metadata` 引用的 Base 是不是 `app.core.db.Base`

**docker 镜像 build 卡在 torch 那一行**
- pytorch CPU index 偶尔慢，换镜像源：在 Dockerfile 的 `--index-url` 后面换 `https://mirrors.aliyun.com/pytorch-wheels/cpu` 之类

**端口冲突**
- 5432 / 6379 / 6333 / 8000 任何一个被占用，改 compose 的 ports 映射，比如 `"15432:5432"`

## VPS 部署提醒

不要急着推 VPS。2G 内存只够跑 backend + postgres + redis + qdrant（不加 BGE 模型也要约 1.2GB）。先在本地把 Phase 1 跑通，部署留到 Phase 2 — 而且 embedding 服务建议剥离到单独的 GPU 机器或调外部 API（OpenAI / 智谱）。
