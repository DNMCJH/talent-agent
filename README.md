# talent-agent

Agentic JD-to-project matching platform. Indexes your real projects, matches against target JDs with a weighted-coverage scorer, generates PR-level improvement tasks, tailors STAR resume bullets, and runs adaptive mock interviews with cross-session weakness tracking.

> 中文版：[README_CN.md](README_CN.md)

## Why this exists

Most "interview prep tools" hand you a generic project to clone. The moment an interviewer pulls up your git log, the story collapses. **talent-agent works against the projects you actually built** — it reads your READMEs, detects your stack, embeds them locally, and tells you exactly which one to pitch for a given JD plus what gap to close before the interview.

### Differentiation vs. shushu-internship-tool

| | shushu-internship-tool | talent-agent |
|---|---|---|
| Direction | JD listing → recommend candidates | Your projects → match a target JD |
| Output | Filter & rank job posts | Match score + improvement plan + resume bullets + mock interview |
| State | Stateless | Persistent: indexed projects, interview sessions, weakness tracking |
| Personalization | None | Built around your real git history |

## What it does

```
JD (paste) → Parse → Match against your indexed projects → Find gaps
  → Generate 3-5 day improvement tasks (PR-level deliverables)
  → Write STAR resume bullets
  → Run adaptive mock interviews (weaknesses persist across sessions)
```

## Tech stack

- **LLM**: DeepSeek API via OpenAI-compatible client (`deepseek-chat`)
- **Embedding**: `BAAI/bge-small-zh-v1.5` local (95MB, 512-dim, bilingual)
- **Vector DB**: Qdrant — local file mode for dev, server mode for prod
- **State**: SQLite (sessions + cross-session weakness store)
- **Orchestration**: Plain async Python — no LangChain runtime, no LangGraph
- **UI**: Streamlit (single-page, two tabs)

Five agents, all `async`: **Parser → Matcher → Improver → Rewriter → Interviewer**. See [ARCHITECTURE.md](ARCHITECTURE.md) for data contracts and the matching algorithm.

## Quick start

```powershell
git clone <repo-url>
cd talent-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Configure DeepSeek API key
cp .env.example .env
# Edit .env: set LLM_API_KEY=sk-...

# Index your local projects (one-shot — re-run when you add new ones)
talent-index

# Run the UI
talent-ui
# → http://localhost:8501
```

Or use the CLI:

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:TQDM_DISABLE="1"
talent-match --jd data/sample_jd.txt --intent full_loop
```

`--intent` accepts: `match_only`, `improve_only`, `resume_only`, `interview_only`, `full_loop`.

## Matching algorithm

`weighted_score = 0.7 × must_coverage + 0.3 × plus_coverage`

When the JD has no plus-skills, weighted collapses to pure must-coverage. This separates "Python-only matches" from "Python + RAG + AWS matches" instead of flattening every project to 100%.

## Configuration

Environment variables (all optional except `LLM_API_KEY`):

```bash
LLM_API_KEY=sk-...                          # required
LLM_BASE_URL=https://api.deepseek.com       # OpenAI-compatible endpoint
LLM_MODEL=deepseek-chat
EMBED_MODEL=BAAI/bge-small-zh-v1.5
EMBED_DEVICE=cpu                            # or "cuda"
QDRANT_URL=                                 # empty = local file mode
QDRANT_LOCAL_PATH=./data/qdrant_storage
PROJECTS_ROOT=a:/VScode/Code/Projects       # what to index
INDEX_EXCLUDE=["talent-agent",".git","node_modules",".venv"]
STATE_DB=./data/state.sqlite
```

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Streamlit UI  (Match & Plan │ Interview Drill)   │
└──────────────────────────┬────────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │  Pipeline (async Python)   │
              │                            │
              │  Parser ─► Matcher ─► Improver  │
              │                    └► Rewriter   │
              │                    └► Interviewer │
              └──────┬──────────┬─────────┬──────┘
                     ▼          ▼         ▼
                ┌────────┐  ┌────────┐  ┌────────┐
                │ Qdrant │  │ SQLite │  │DeepSeek│
                │projects│  │sessions│  │  API   │
                └────────┘  └────────┘  └────────┘
```

## Development

```powershell
pytest                       # 6 unit tests on matcher + parser
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

## Deploy

See [docs/DEPLOY.md](docs/DEPLOY.md) for the Tencent Cloud VPS setup (Qdrant in Docker + Streamlit container + Caddy reverse proxy).

## License

Apache-2.0
