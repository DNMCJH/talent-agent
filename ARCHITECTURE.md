# talent-agent Architecture

> Agentic JD-to-project matching platform. Indexes user's real projects, matches against target JDs, generates PR-level improvement tasks, tailors resume bullets, and runs adaptive interview drills with cross-session weakness tracking.

## Design principles

1. **Real projects beat fake projects.** Match against the user's actual git history; never recommend cloning a stranger's repo.
2. **Closed loop ends in code, not in slides.** Every match produces concrete, time-boxed PR tasks.
3. **State is first-class.** Interview weaknesses persist across sessions via SQLite.
4. **One JD, one session.** All artifacts (match, gaps, resume, interview log) belong to a `Session` keyed by `(jd_hash, user_id)`.
5. **No framework tax.** Use the right tool at each layer. Frameworks serve the product, not the other way around.

## Tech stack

| Layer | Choice | Reason |
|---|---|---|
| LLM calls | **Anthropic SDK** (direct `client.messages.create` with tool_use) | full prompt control, structured output via tool_use, no abstraction tax |
| RAG pipeline | **LangChain** (document loaders + text splitters + Qdrant wrapper) | genuinely saves time for file ingestion; only used here |
| Agent orchestration | **Custom async Python** (state machine + router functions) | each agent is a plain async function; no framework lock-in, easy to debug |
| Embeddings | **BGE-M3** (local via sentence-transformers) | free, multilingual (中文+英文 JD both work), strong on retrieval |
| Vector DB | **Qdrant** (self-hosted on Tencent VPS) | payload filtering, gRPC, hybrid search, prod-grade |
| State store | **SQLite** (via `aiosqlite` + Pydantic models) | full schema control, direct SQL queries for weakness analytics |
| UI (MVP) | **Streamlit** | fastest path to a clickable demo |
| UI (v2) | FastAPI + React | when MVP gets traction |

### Why NOT full LangGraph

LangGraph's StateGraph + checkpointer solves state persistence, but:
- Locks state format into their serialization — hard to query weaknesses with raw SQL
- Debugging requires understanding their internal checkpoint schema
- The "graph" abstraction adds complexity for what is essentially a linear pipeline with one branch point
- Interview loop needs flexible mid-turn strategy changes that don't map well to fixed node edges

We keep LangChain only where it genuinely earns its keep (document loading, text splitting, Qdrant vector store wrapper). Everything else is direct Anthropic SDK + custom code.

## Data model

### `ParsedJD`
Output of Parser agent. Single source of truth for all downstream agents.

```python
class ParsedJD(BaseModel):
    raw: str                       # 原始 JD 文本
    language: Literal["en", "zh"]
    company: str
    role: str
    location: str | None
    work_mode: Literal["onsite", "hybrid", "remote"] | None
    must_skills: list[Skill]       # 硬性要求
    plus_skills: list[Skill]       # 加分项
    responsibilities: list[str]    # 工作内容
    implicit_signals: ImplicitSignals  # 团队风格、生产 vs 研究、资历预期
    keywords_for_search: list[str] # 用于向量检索的关键词
    jd_hash: str                   # sha256(raw) 前 12 位

class Skill(BaseModel):
    name: str                      # 规范化后的技能名 (e.g. "LangChain")
    level: Literal["basic", "intermediate", "advanced"]
    aliases: list[str]             # 同义词 (e.g. ["LC", "langchain"])
```

### `ProjectDoc`
Output of Indexer. One row per real project the user owns.

```python
class ProjectDoc(BaseModel):
    name: str
    path: str                      # 绝对路径
    readme: str                    # README 主体（截断到 8k token）
    stack: list[str]               # 从依赖文件抽取的技术栈
    languages: dict[str, float]    # {"Python": 0.82, "JS": 0.18}
    topics: list[str]              # LLM 抽取的主题词
    last_commit_date: str          # ISO 8601
    commit_count: int
    has_dockerfile: bool
    has_tests: bool
    deployment_signal: bool        # 是否找到 docker-compose / k8s / CI 配置
    complexity_loc: int            # 总 LOC
    sample_files: list[str]        # 3-5 个代表性文件路径
```

Stored in Qdrant collection `projects`. Vector = `embed(name + topics + stack + readme_summary)`. Payload = full `ProjectDoc`.

### `MatchResult`
Output of Matcher.

```python
class Match(BaseModel):
    project: ProjectDoc
    coverage: float                # 0-1: 覆盖 JD must_skills 的比例
    matched_skills: list[str]
    missing_skills: list[str]      # JD 要求但项目没有
    bonus_skills: list[str]        # 项目有但 JD 没要求（可能加分）
    match_reason: str              # LLM 用一句话说为啥匹配

class MatchResult(BaseModel):
    jd: ParsedJD
    matches: list[Match]           # 按 coverage 降序
    overall_best: Match
```

### `ImprovementPlan`
Output of Improver.

```python
class Task(BaseModel):
    title: str                     # e.g. "Add LangGraph multi-agent orchestrator"
    addresses_gaps: list[str]      # 哪些 missing_skills
    effort_days: int               # 1-7
    deliverables: list[str]        # 具体可交付物
    implementation_hints: str      # 实施提示
    resume_impact: str             # 完成后简历能加什么

class ImprovementPlan(BaseModel):
    project_name: str
    tasks: list[Task]              # 按 ROI 排序
```

### `ResumeBundle`
Output of Resume Rewriter.

```python
class ResumeBundle(BaseModel):
    project_title: str
    stack_line: str                # "Python · LangChain · LangGraph · Qdrant · Docker"
    star_bullets: list[str]        # 3-5 条 STAR 格式
    metrics_placeholders: list[str]  # 哪里要填数字
    tailored_for_role: str         # 针对哪个 role 调过
```

### `InterviewSession`
Persisted via SQLite (table `interview_sessions` + `weaknesses`).

```python
class WeaknessEntry(BaseModel):
    topic: str
    count: int                     # 累计被问到次数
    severity: Literal["mild", "moderate", "severe"]
    last_seen: str                 # ISO
    last_failure_summary: str

class InterviewSession(BaseModel):
    session_id: str                # uuid
    jd_hash: str
    project_name: str
    history: list[ChatTurn]
    weaknesses: dict[str, WeaknessEntry]
    current_focus: str | None
    turn_count: int
```

Weaknesses are **global across sessions** (keyed by topic), but `history` is per session.

## Agent contracts

| Agent | Input | Output | Side effects |
|---|---|---|---|
| **Parser** | `str` (raw JD) | `ParsedJD` | none |
| **Indexer** | `path` | `list[ProjectDoc]` | upsert to Qdrant |
| **Matcher** | `ParsedJD` | `MatchResult` | none (read-only Qdrant query) |
| **Improver** | `MatchResult` | `ImprovementPlan` | none |
| **Rewriter** | `ProjectDoc`, `ParsedJD`, `ImprovementPlan?` | `ResumeBundle` | none |
| **Interviewer** | `InterviewSession`, `str` (user turn) | `InterviewSession`, `str` (next question) | SQLite checkpoint write |

Each agent is a plain async function with typed input/output. No agent calls another directly — the orchestrator decides sequencing.

## Orchestration

The orchestrator is a simple async pipeline, not a graph framework:

```python
async def run_pipeline(raw_jd: str, intent: Intent, session: Session) -> Session:
    session.parsed = await parser(raw_jd)
    session.match = await matcher(session.parsed, qdrant_client)

    if intent in ("full_loop", "improve_only"):
        session.plan = await improver(session.match)

    if intent in ("full_loop", "resume_only"):
        session.resume = await rewriter(session.match, session.plan)

    if intent in ("full_loop", "interview_only"):
        # interview is interactive — returns control to UI for multi-turn
        session.interview = await interviewer_init(session)

    return session
```

Each agent function signature:

```python
async def parser(raw_jd: str) -> ParsedJD: ...
async def matcher(jd: ParsedJD, qdrant: QdrantClient) -> MatchResult: ...
async def improver(match: MatchResult) -> ImprovementPlan: ...
async def rewriter(match: MatchResult, plan: ImprovementPlan | None) -> ResumeBundle: ...
async def interviewer_turn(session: InterviewSession, user_msg: str) -> tuple[InterviewSession, str]: ...
```

No decorators, no graph DSL, no magic. Each function is independently testable.

## Indexing strategy

For each subdirectory under `PROJECTS_ROOT` (excluding `INDEX_EXCLUDE`):

1. **Read README** — prefer `README.md`, fall back to `README_CN.md`, then `*.md` in root.
2. **Detect stack** — parse `pyproject.toml` / `requirements.txt` / `package.json` / `Cargo.toml` / `go.mod`.
3. **Sample code** — pick the largest 3 source files + the `main`/`app`/`__main__` entry.
4. **Git facts** — `last_commit_date`, `commit_count`, branch list, top-5 commit messages.
5. **Signal flags** — `has_dockerfile`, `has_tests` (look for `tests/`, `*_test.go`, etc.), `deployment_signal`.
6. **Topic extraction** — feed README + stack to LLM, return ≤8 topic keywords.
7. **Embed** — `BGE-M3` on `name + topics + stack + readme[:2000]`.
8. **Upsert** — to Qdrant with full `ProjectDoc` as payload.

Re-index trigger: file watcher on `PROJECTS_ROOT` (later); manual `talent-index` CLI for MVP.

## Matching strategy (hybrid)

```
1. embed(jd.keywords_for_search) → vector search top-20
2. filter by payload: project must have ≥1 of jd.must_skills (alias-aware)
3. rerank by coverage = |jd.must_skills ∩ project.stack ∪ project.topics| / |jd.must_skills|
4. tie-break by deployment_signal + last_commit_date freshness
5. return top-3 with LLM-generated match_reason
```

Skill alias matching uses a hand-curated normalization map (`data/skill_aliases.yaml`): `LC`/`langchain`/`Langchain` → `LangChain`.

## Cross-session weakness tracking

`Interviewer` node, every turn:

1. Pick next question:
   - 70% from weaknesses (weighted by `count * severity`), only if any are >= moderate
   - 30% breadth from `parsed.must_skills` not yet covered
2. After candidate answer, critique with LLM:
   ```
   { "score": 0-5, "topics_revealed": [...], "weakness_topics": [...], "severity_delta": -1|0|+1 }
   ```
3. Update weaknesses table.

Weaknesses are stored in SQLite **globally** (key: `topic`), so prepping for SAP today reuses gaps surfaced while prepping for ByteDance last week.

## Deployment plan

**Local dev**:
- Qdrant via `docker compose up` (local container).
- BGE-M3 runs on CPU (~600MB model, ~200ms per embed).
- Claude API for all LLM calls.

**Production-ish (Tencent VPS)**:
- Qdrant container with persistent volume + API key auth.
- Streamlit container reverse-proxied behind Caddy (TLS).
- Single `docker-compose.yml` at repo root.

## What this is NOT

- Not a job board scraper. JDs come in via paste.
- Not an autocrafter — Improver outputs tasks, not code. The user does the actual coding (so they can talk about it in interviews).
- Not a SaaS — single-user MVP. Multi-tenant comes only if proven.

## Open decisions (deferred)

- Embedding API vs local: starting local (BGE-M3). Switch if recall is bad.
- LangSmith tracing: skip in MVP, add when graph gets messy.
- Frontend rewrite: only after Streamlit hits its limits.
