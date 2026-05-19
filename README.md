# Talent Agent

[中文文档](README_CN.md)

AI-powered career toolkit that matches your GitHub projects to job descriptions, runs adaptive mock interviews with real-time feedback, and generates tailored STAR resume bullets.

> **V2 (current)**: Full-stack SaaS with Next.js frontend + FastAPI backend + multi-tenant vector search.
> V1 was a local Streamlit prototype — see git history for the original.

## Why this exists

Most "interview prep tools" hand you a generic project to clone. The moment an interviewer pulls up your git log, the story collapses. **Talent Agent works against the projects you actually built** — it reads your READMEs, detects your stack, embeds them, and tells you exactly which one to pitch for a given JD plus what gap to close before the interview.

## Features

- **Smart Matching** — Paste any JD, get your projects ranked by skill coverage (blended: 50% must-skill + 30% plus-skill + 20% vector similarity)
- **Mock Interviews** — AI interviewer adapts questions based on your project stack and target role; per-turn scoring and weakness detection
- **Resume Generation** — STAR-format bullets tailored to specific JDs, with metric placeholders
- **GitHub Integration** — OAuth login, browse & batch-import repos (public + private), auto-extract tech stack via LLM
- **Bilingual UI** — Chinese/English toggle, instant switch

## Architecture

```
┌─────────────────┐        ┌──────────────────────────────────────┐
│  Next.js 14     │───────▶│  FastAPI Backend                     │
│  Auth.js v5     │        │  ┌────────────────────────────────┐  │
│  shadcn/ui      │        │  │ 5-Agent Pipeline:               │  │
│  SWR + i18n     │        │  │ Parser → Matcher → Improver    │  │
│                 │        │  │ → Rewriter → Interviewer       │  │
└─────────────────┘        │  └────────────────────────────────┘  │
                           │  DeepSeek LLM (deepseek-chat)        │
                           │  BGE-small-zh-v1.5 (512-dim embed)   │
                           │  Qdrant (multi-tenant vector search) │
                           │  PostgreSQL · Redis                   │
                           └──────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ & pnpm
- GitHub OAuth App (callback: `http://localhost:3000/api/auth/callback/github`)

### Backend

```bash
cd backend
cp .env.example .env  # fill in API keys
docker compose up -d
```

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
pnpm install
pnpm dev
```

Open http://localhost:3000

## Matching Algorithm

```
blended_score = 0.5 × must_coverage + 0.3 × plus_coverage + 0.2 × vector_similarity
```

The parser extracts granular skills with aliases from the JD. When must_skills are few, vector similarity prevents all projects from scoring identically.

## Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Auth.js v5, SWR
- **Backend**: FastAPI, SQLAlchemy (async), Pydantic v2
- **AI**: DeepSeek (OpenAI-compatible), BGE-small-zh-v1.5 (512-dim embeddings)
- **Storage**: PostgreSQL, Qdrant (multi-tenant via payload filter), Redis
- **Infra**: Docker Compose, pnpm

## Development

```bash
# Backend
cd backend && pytest
ruff check . && ruff format .

# Frontend
cd frontend && pnpm lint && npx tsc --noEmit
```

## License

MIT
