# Talent Agent

部署网址：https://projfit.top

AI 驱动的求职工具包：将你的 GitHub 项目与职位描述匹配，运行自适应模拟面试并提供实时反馈，生成定制化 STAR 简历要点。

> English version: [README.md](README.md)
> **V2（当前版本）**：全栈 SaaS，Next.js 前端 + FastAPI 后端 + 多租户向量搜索。

## 为什么做这个

市面上的「面试准备工具」大多让你 clone 一个别人的项目。面试官一查 git log，故事就崩了。**Talent Agent 直接基于你真实写过的项目工作** —— 读你的 README、识别技术栈、向量化索引，然后告诉你哪个项目最适合投这个岗位，以及面试前应该补哪个坑。

## 功能

- **智能匹配** — 粘贴任意 JD，按技能覆盖率排名你的项目（混合评分：50% 必须技能 + 30% 加分技能 + 20% 向量相似度）
- **模拟面试** — AI 面试官根据你的项目技术栈和目标岗位动态调整问题；每轮评分 + 弱点检测
- **简历生成** — 针对特定 JD 生成 STAR 格式简历要点，带指标占位符
- **GitHub 集成** — OAuth 登录，浏览并批量导入仓库（公开 + 私有），LLM 自动提取技术栈
- **双语 UI** — 中英文一键切换

## 架构

```
┌─────────────────┐        ┌──────────────────────────────────────┐
│  Next.js 14     │───────▶│  FastAPI 后端                        │
│  Auth.js v5     │        │  ┌────────────────────────────────┐  │
│  shadcn/ui      │        │  │ 5-Agent 流水线：                │  │
│  SWR + i18n     │        │  │ Parser → Matcher → Improver    │  │
│                 │        │  │ → Rewriter → Interviewer       │  │
└─────────────────┘        │  └────────────────────────────────┘  │
                           │  DeepSeek LLM (deepseek-chat)        │
                           │  BGE-small-zh-v1.5 (512维 embedding) │
                           │  Qdrant (多租户向量搜索)              │
                           │  PostgreSQL · Redis                   │
                           └──────────────────────────────────────┘
```

## 快速开始

### 前置条件

- Docker & Docker Compose
- Node.js 18+ & pnpm
- GitHub OAuth App（回调地址：`http://localhost:3000/api/auth/callback/github`）

### 后端

```bash
cd backend
cp .env.example .env  # 填入 API 密钥
docker compose up -d
```

### 前端

```bash
cd frontend
cp .env.local.example .env.local  # 填入 OAuth 凭据
pnpm install
pnpm dev
```

打开 http://localhost:3000

## 匹配算法

```
blended_score = 0.5 × must_coverage + 0.3 × plus_coverage + 0.2 × vector_similarity
```

解析器从 JD 中提取细粒度技能（带别名）。当必须技能较少时，向量相似度防止所有项目得分相同。

## 技术栈

- **前端**：Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Auth.js v5, SWR
- **后端**：FastAPI, SQLAlchemy (async), Pydantic v2
- **AI**：DeepSeek（OpenAI 兼容）, BGE-small-zh-v1.5（512 维 embedding）
- **存储**：PostgreSQL, Qdrant（多租户 payload filter）, Redis
- **基础设施**：Docker Compose, pnpm

## 开发

```bash
# 后端
cd backend && pytest
ruff check . && ruff format .

# 前端
cd frontend && pnpm lint && npx tsc --noEmit
```

## 许可证

MIT
