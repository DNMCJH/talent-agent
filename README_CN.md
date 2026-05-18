# talent-agent

智能体驱动的「岗位 → 个人项目」匹配平台。索引你的真实项目，针对目标 JD 做加权打分匹配，生成 PR 级别的项目改进任务，定制 STAR 格式简历要点，并以跨会话弱点记忆运行自适应模拟面试。

> English version: [README.md](README.md)

## 为什么做这个

市面上的「面试准备工具」大多让你 clone 一个别人的项目。面试官一查 git log，故事就崩了。**talent-agent 直接基于你真实写过的项目工作** —— 读你的 README、识别技术栈、本地向量化索引，然后告诉你哪个项目最适合投这个岗位，以及面试前应该补哪个坑。

### 与 shushu-internship-tool 的差异

| | shushu-internship-tool | talent-agent |
|---|---|---|
| 方向 | JD 池 → 推荐候选人 | 你的项目 → 匹配目标 JD |
| 输出 | 筛选和排序招聘信息 | 匹配分 + 改进计划 + 简历要点 + 模拟面试 |
| 状态 | 无状态 | 持久化：项目索引、面试 session、弱点记录 |
| 个性化 | 无 | 围绕你真实的 git 历史 |

## 它做了什么

```
JD（粘贴）→ 解析 → 匹配你索引过的项目 → 找差距
  → 生成 3-5 天的改进任务（PR 级交付物）
  → 写 STAR 简历要点
  → 运行自适应模拟面试（弱点跨会话持久）
```

## 技术栈

- **LLM**：DeepSeek API（OpenAI 兼容客户端，`deepseek-chat`）
- **Embedding**：`BAAI/bge-small-zh-v1.5` 本地运行（95MB，512 维，中英双语）
- **向量库**：Qdrant —— 开发用本地文件模式，部署用 server 模式
- **状态存储**：SQLite（session + 跨会话弱点）
- **编排**：纯 async Python —— 没用 LangChain 运行时，没用 LangGraph
- **UI**：Streamlit（单页，两个 tab）

五个 agent，全部 `async`：**Parser → Matcher → Improver → Rewriter → Interviewer**。数据契约和匹配算法见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 快速开始

```powershell
git clone <repo-url>
cd talent-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 配置 DeepSeek API key
cp .env.example .env
# 编辑 .env：填 LLM_API_KEY=sk-...

# 一次性索引本地项目（添加新项目时重跑）
talent-index

# 启动 UI
talent-ui
# → http://localhost:8501
```

或者用 CLI：

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:TQDM_DISABLE="1"
talent-match --jd data/sample_jd.txt --intent full_loop
```

`--intent` 可选值：`match_only`、`improve_only`、`resume_only`、`interview_only`、`full_loop`。

## 匹配算法

`weighted_score = 0.7 × must_coverage + 0.3 × plus_coverage`

JD 没有 plus-skills 时，权重全部回落到 must。这样可以把「只命中 Python」和「命中 Python + RAG + AWS」区分开，避免所有项目都被压成 100%。

## 配置

环境变量（除 `LLM_API_KEY` 外都可选）：

```bash
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
EMBED_MODEL=BAAI/bge-small-zh-v1.5
EMBED_DEVICE=cpu
QDRANT_URL=                                 # 空 = 本地文件模式
QDRANT_LOCAL_PATH=./data/qdrant_storage
PROJECTS_ROOT=a:/VScode/Code/Projects
INDEX_EXCLUDE=["talent-agent",".git","node_modules",".venv"]
STATE_DB=./data/state.sqlite
```

## 部署

腾讯云 VPS 部署（Qdrant Docker + Streamlit 容器 + Caddy 反代）见 [docs/DEPLOY.md](docs/DEPLOY.md)。

## License

Apache-2.0
