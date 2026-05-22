"""Quiz question bank and AI-powered self-test service.

Seed questions are loaded from a static bank. The LLM can generate new questions
on demand based on category and difficulty. User answers are scored by the LLM.
"""
from __future__ import annotations

import json
import random
from typing import Any

from pydantic import BaseModel

from app.core.llm import call_llm, call_llm_structured


class QuizScore(BaseModel):
    """Structured scoring result for a quiz answer."""

    score: int = 5  # 1-10
    summary: str = ""
    key_points_hit: list[str] = []
    key_points_missed: list[str] = []
    suggestion: str = ""

CATEGORIES = [
    "foundations",
    "rag",
    "agent",
    "multi_agent",
    "prompting",
    "tools_mcp",
    "memory",
    "evaluation",
    "safety",
    "fine_tuning",
    "system_design",
    "cost_latency",
    "behavioral",
]

CATEGORY_LABELS_ZH = {
    "foundations": "基础",
    "rag": "RAG",
    "agent": "Agent",
    "multi_agent": "多智能体",
    "prompting": "Prompting",
    "tools_mcp": "工具 & MCP",
    "memory": "记忆",
    "evaluation": "评估",
    "safety": "安全",
    "fine_tuning": "微调",
    "system_design": "系统设计",
    "cost_latency": "成本与延迟",
    "behavioral": "行为面",
}

# Seed question bank — extracted from the 42-question GenAI/Agentic interview set.
# Each entry: {category, difficulty, question, hint, key_points, company_tags}
# key_points are the reference-answer points the LLM scorer checks the answer
# against — without them scoring is unanchored and drifts run to run.
SEED_QUESTIONS: list[dict[str, Any]] = [
    {"id": "f1", "category": "foundations", "difficulty": "mid", "question": "What is generative AI, and how is it different from predictive ML?", "hint": "Think about output distributions vs fixed labels.", "key_points": ["Generative models learn the data distribution and sample new content; predictive ML maps inputs to fixed labels/values", "Generative output is open-ended (text, image, code); predictive output is a class or number", "Generative models are typically self-supervised on unlabeled data; predictive ML is usually supervised on labeled data"], "company_tags": ["OpenAI", "Google DeepMind", "NVIDIA"]},
    {"id": "f2", "category": "foundations", "difficulty": "mid", "question": "Explain self-attention in a transformer and why it matters for LLMs.", "hint": "Q/K/V projections, quadratic complexity, long-range dependencies.", "key_points": ["Each token is projected into Query, Key, Value vectors; attention weights = softmax(QK^T/sqrt(d))", "Lets every token directly attend to every other token, capturing long-range dependencies without recurrence", "Fully parallelizable across the sequence (unlike RNNs), enabling efficient training at scale", "Cost is quadratic in sequence length — the main scaling bottleneck for long context"], "company_tags": ["Anthropic", "Cohere", "Hugging Face"]},
    {"id": "f3", "category": "foundations", "difficulty": "mid", "question": "What are tokens and why does tokenization matter for LLM applications?", "hint": "BPE, cost, multilingual, context window.", "key_points": ["Tokens are sub-word units (often BPE/byte-level) — the actual unit the model reads and bills on", "API cost and context-window limits are counted in tokens, not characters or words", "Tokenization is uneven across languages — non-English text often costs more tokens per word", "Bad tokenization affects number handling, code, and rare words"], "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "f4", "category": "foundations", "difficulty": "senior", "question": "Compare autoregressive decoding with diffusion-based generation.", "hint": "Sequential vs iterative refinement, latency, quality.", "key_points": ["Autoregressive generates one token at a time conditioned on previous tokens — inherently sequential", "Diffusion starts from noise and iteratively denoises the whole output — parallel over positions but multi-step", "AR dominates text (causal structure fits); diffusion dominates images/audio", "Trade-offs: AR latency scales with output length; diffusion latency scales with number of denoising steps"], "company_tags": ["Google DeepMind", "Stability AI"]},
    {"id": "f5", "category": "foundations", "difficulty": "senior", "question": "What is the scaling hypothesis and what are its practical limits?", "hint": "Chinchilla, data walls, diminishing returns.", "key_points": ["Scaling hypothesis: loss improves predictably with more compute, data, and parameters (scaling laws)", "Chinchilla showed compute-optimal training needs data scaled with parameters — many models were under-trained", "Practical limits: finite high-quality data ('data wall'), compute cost, energy, diminishing returns", "Capabilities are emergent/unpredictable per-task even when aggregate loss is predictable"], "company_tags": ["Anthropic", "OpenAI"]},
    {"id": "r1", "category": "rag", "difficulty": "mid", "question": "Walk me through a production RAG pipeline end-to-end.", "hint": "Chunking → embedding → retrieval → reranking → generation → citation.", "key_points": ["Ingestion: load docs, chunk them, embed chunks, store vectors + metadata in a vector DB", "Query time: embed the query, retrieve top-k chunks (often + metadata filtering)", "Optional rerank step to improve precision of the retrieved set", "Generation: stuff retrieved context into the prompt; produce answer with citations", "Production concerns: caching, evaluation, freshness/re-indexing, handling no-result cases"], "company_tags": ["Pinecone", "Cohere", "Microsoft"]},
    {"id": "r2", "category": "rag", "difficulty": "mid", "question": "How do you evaluate RAG quality? What metrics matter?", "hint": "Faithfulness, relevance, recall@k, answer correctness.", "key_points": ["Retrieval metrics: recall@k / precision@k / MRR — did we fetch the right chunks", "Generation metrics: faithfulness/groundedness (answer supported by context, no hallucination)", "Answer relevance and answer correctness vs ground truth", "Methods: LLM-as-judge, golden datasets, human eval; evaluate retrieval and generation separately to localize failures"], "company_tags": ["Anthropic", "LangChain"]},
    {"id": "r3", "category": "rag", "difficulty": "senior", "question": "When would you choose RAG over fine-tuning, and vice versa?", "hint": "Freshness, cost, hallucination control, domain specificity.", "key_points": ["RAG for knowledge that is large, changing, or needs citations/freshness — update the index, not the model", "Fine-tuning for style, format, tone, or behavior the model should internalize", "RAG gives traceability and easier knowledge updates; fine-tuning gives lower latency and no retrieval dependency", "They are complementary — many production systems fine-tune for behavior and use RAG for facts"], "company_tags": ["OpenAI", "Google"]},
    {"id": "r4", "category": "rag", "difficulty": "mid", "question": "What chunking strategies exist and how do you pick one?", "hint": "Fixed-size, semantic, recursive, document-aware.", "key_points": ["Fixed-size (with overlap), recursive/separator-based, semantic, and document-structure-aware chunking", "Overlap preserves context across chunk boundaries", "Chunk size trades retrieval precision (small) against context completeness (large)", "Pick based on document structure and query type; validate empirically with retrieval metrics"], "company_tags": ["Pinecone", "Weaviate"]},
    {"id": "r5", "category": "rag", "difficulty": "senior", "question": "How do you handle multi-hop questions in RAG?", "hint": "Query decomposition, iterative retrieval, chain-of-thought.", "key_points": ["Single-shot retrieval fails — the answer requires chaining facts across documents", "Query decomposition: break the question into sub-questions, retrieve for each", "Iterative/agentic retrieval: retrieve, reason, then retrieve again based on intermediate findings", "Techniques like HyDE, graph-based retrieval, or self-querying; trade latency for accuracy"], "company_tags": ["Microsoft", "Anthropic"]},
    {"id": "a1", "category": "agent", "difficulty": "mid", "question": "What is an AI agent and how does it differ from a chain?", "hint": "Autonomy, tool use, planning loop, state.", "key_points": ["A chain is a fixed, predetermined sequence of steps", "An agent decides its own next action in a loop based on observations — control flow is dynamic", "Agents use tools, maintain state, and decide when to stop", "Trade-off: agents are flexible but less predictable and harder to debug/bound"], "company_tags": ["OpenAI", "LangChain", "Anthropic"]},
    {"id": "a2", "category": "agent", "difficulty": "senior", "question": "How do you prevent an agent from going off-rails in production?", "hint": "Guardrails, budget limits, human-in-the-loop, sandboxing.", "key_points": ["Hard limits: max steps/iterations, token/cost budget, timeouts to stop infinite loops", "Tool-level guardrails: scoped permissions, sandboxing, allowlists, validation of tool inputs/outputs", "Human-in-the-loop approval for high-risk or irreversible actions", "Observability: logging, tracing every step; output validation and monitoring/alerting"], "company_tags": ["Anthropic", "OpenAI"]},
    {"id": "a3", "category": "agent", "difficulty": "mid", "question": "Describe the ReAct pattern and when you'd use it.", "hint": "Reason + Act loop, observation, tool calling.", "key_points": ["ReAct interleaves Reasoning (thought) and Acting (tool call) in a loop", "Cycle: Thought → Action → Observation → repeat until done", "The explicit reasoning trace improves tool selection and makes behavior debuggable", "Use it for tasks needing external info or multi-step tool use; overkill for simple single-shot tasks"], "company_tags": ["Google DeepMind", "LangChain"]},
    {"id": "ma1", "category": "multi_agent", "difficulty": "senior", "question": "When would you use multiple agents vs a single agent with many tools?", "hint": "Separation of concerns, context limits, specialization.", "key_points": ["Multiple agents when subtasks need different specialization, prompts, or even models", "Helps when one agent's context window can't hold all tools/instructions", "Separation of concerns: each agent is simpler, easier to test and reason about", "Costs: coordination overhead, latency, more failure modes — don't over-split; a single agent is simpler when tools are related"], "company_tags": ["Microsoft", "CrewAI"]},
    {"id": "ma2", "category": "multi_agent", "difficulty": "senior", "question": "How do you handle coordination and communication between agents?", "hint": "Message passing, shared state, orchestrator pattern.", "key_points": ["Orchestrator/supervisor pattern: a coordinator routes tasks and aggregates results", "Communication via message passing or a shared state/blackboard", "Define clear interfaces/handoff contracts between agents", "Handle failures, deadlocks, and infinite hand-off loops; bound total steps/cost"], "company_tags": ["AutoGen", "LangGraph"]},
    {"id": "p1", "category": "prompting", "difficulty": "mid", "question": "What is chain-of-thought prompting and when does it help?", "hint": "Step-by-step reasoning, math/logic tasks, few-shot examples.", "key_points": ["CoT asks the model to produce intermediate reasoning steps before the final answer", "Helps on multi-step reasoning: math, logic, planning — gives the model 'space to think'", "Triggered by few-shot reasoning examples or simply 'think step by step'", "Costs more tokens/latency; modern reasoning models do this internally"], "company_tags": ["Google", "OpenAI"]},
    {"id": "p2", "category": "prompting", "difficulty": "mid", "question": "How do you structure a system prompt for a production application?", "hint": "Role, constraints, output format, examples, guardrails.", "key_points": ["Define role/persona and the task clearly", "Specify constraints, guardrails, and what NOT to do", "Specify exact output format (schema/JSON) and give few-shot examples", "Handle edge cases explicitly; keep it versioned and test prompt changes like code"], "company_tags": ["Anthropic", "OpenAI"]},
    {"id": "t1", "category": "tools_mcp", "difficulty": "mid", "question": "How does function calling / tool use work in modern LLMs?", "hint": "Schema definition, model selection, execution, result injection.", "key_points": ["You provide tool/function schemas (name, description, JSON-schema parameters)", "The model decides whether to call a tool and emits structured arguments", "Your code executes the tool — the model does not run it itself", "The result is fed back into the conversation; the model continues or answers"], "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "t2", "category": "tools_mcp", "difficulty": "senior", "question": "What is MCP (Model Context Protocol) and what problem does it solve?", "hint": "Standardized tool interface, server/client, resource discovery.", "key_points": ["MCP is an open standard for connecting LLM apps to tools and data sources", "Client/server architecture: MCP servers expose tools, resources, and prompts", "Solves the M×N integration problem — one protocol instead of bespoke integrations per app per tool", "Enables reuse and discovery of capabilities across different LLM clients"], "company_tags": ["Anthropic"]},
    {"id": "m1", "category": "memory", "difficulty": "mid", "question": "What memory strategies exist for LLM applications?", "hint": "Buffer, summary, vector store, entity memory, conversation window.", "key_points": ["Short-term: conversation buffer or sliding window of recent turns", "Summary memory: compress old turns into a running summary to save context", "Long-term: vector-store retrieval of past interactions/facts", "Entity/structured memory tracks specific facts; choice trades context cost vs recall fidelity"], "company_tags": ["LangChain", "OpenAI"]},
    {"id": "e1", "category": "evaluation", "difficulty": "senior", "question": "How do you evaluate an LLM application in production?", "hint": "Online vs offline, LLM-as-judge, human eval, A/B testing.", "key_points": ["Offline: golden/eval datasets run on every change (regression testing)", "Online: A/B tests, user feedback signals, production monitoring", "LLM-as-judge for scalable scoring; human eval for ground truth and calibration", "Task-specific metrics + tracing; watch for drift and prompt/model regressions"], "company_tags": ["Anthropic", "Google"]},
    {"id": "s1", "category": "safety", "difficulty": "mid", "question": "What are common LLM security risks and how do you mitigate them?", "hint": "Prompt injection, data leakage, jailbreaks, output validation.", "key_points": ["Prompt injection (esp. indirect, via retrieved/tool content) — separate untrusted input, least-privilege tools", "Data leakage of secrets/PII — scrub inputs, restrict what the model can access", "Jailbreaks bypassing guardrails — layered defenses, system-prompt hardening", "Always validate/sanitize model output before acting on it; never trust it blindly"], "company_tags": ["Anthropic", "OWASP"]},
    {"id": "ft1", "category": "fine_tuning", "difficulty": "mid", "question": "When should you fine-tune vs use prompting + RAG?", "hint": "Style/format, latency, cost, data availability.", "key_points": ["Try prompting + RAG first — cheaper, faster to iterate, no training data needed", "Fine-tune for consistent style/format/tone, narrow tasks, or to shorten long prompts", "Fine-tuning needs a quality labeled dataset and ongoing maintenance as base models update", "RAG for knowledge/facts; fine-tuning for behavior — they are not mutually exclusive"], "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "sd1", "category": "system_design", "difficulty": "senior", "question": "Design a real-time AI customer support system.", "hint": "Routing, RAG, escalation, latency, caching, fallback.", "key_points": ["Intent classification/routing; RAG over knowledge base and account/order data", "Escalation path to humans for low confidence or sensitive issues", "Latency: streaming responses, caching common answers, smaller/faster models where possible", "Reliability: fallbacks, guardrails, logging; evaluation and feedback loop for quality"], "company_tags": ["Intercom", "Zendesk"]},
    {"id": "sd2", "category": "system_design", "difficulty": "senior", "question": "How would you build a code review agent?", "hint": "Diff parsing, context retrieval, multi-file understanding, feedback format.", "key_points": ["Parse the diff; retrieve surrounding/related code for cross-file context", "Check correctness, style, security, tests; ground comments on specific lines", "Structured, actionable feedback; avoid noise — prioritize and dedupe", "Integrate with PR workflow (CI, inline comments); evaluate precision to keep developer trust"], "company_tags": ["GitHub", "Anthropic"]},
    {"id": "cl1", "category": "cost_latency", "difficulty": "mid", "question": "What strategies reduce LLM inference cost in production?", "hint": "Caching, model routing, batching, shorter prompts, smaller models.", "key_points": ["Model routing — use small/cheap models for easy requests, large only when needed", "Caching: exact-match and semantic caching, plus prompt caching of shared prefixes", "Prompt compression — shorter system prompts and context", "Batching, streaming for perceived latency, and capping max output tokens"], "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "b1", "category": "behavioral", "difficulty": "mid", "question": "Tell me about a time you debugged a non-deterministic AI system.", "hint": "Reproduction, logging, seed control, statistical testing.", "key_points": ["Concrete situation with a real non-deterministic failure", "Approach: logging/tracing inputs+outputs, fixing seed/temperature to reproduce", "Statistical/aggregate testing rather than relying on a single run", "Clear outcome and a lesson learned (STAR-style structure)"], "company_tags": ["Any"]},
]


SCORE_PROMPT = """你是一位 AI 工程面试评分官。评估候选人对以下面试题的回答。

题目：{question}
分类：{category}
难度：{difficulty}

参考答案要点（评分锚点 —— 候选人答到越多、越深入，分数越高）：
{key_points}

候选人回答：
{answer}

评分规则：
- score 1-10：1=完全错误或答非所问，5=覆盖部分要点但缺乏深度，7=覆盖大部分要点且有具体例子或 trade-off 分析，9=覆盖全部要点并能举一反三/结合实际经验，10=完美。
- key_points_hit / key_points_missed：对照上面的参考答案要点逐条判断，命中的放 hit，遗漏的放 missed。
- summary：一句话中文总评。suggestion：一句中文改进建议。
- 只依据回答的实际内容评分，不要因回答简短或冗长本身加减分。"""


GENERATE_PROMPT = """生成一道 AI 工程面试题。

分类：{category}
难度：{difficulty}
语言：中文题目 + 英文关键术语

返回 JSON：
{{
  "question": "题目文本",
  "hint": "一句提示（帮助候选人打开思路）",
  "key_points": ["参考答案要点1", "参考答案要点2", "参考答案要点3"]
}}

要求：
- 题目应该考察实际工程能力，不是纯理论背诵
- 难度 mid = 1-2年经验能答，senior = 需要实际项目经验
- 不要和以下已有题目重复：{existing_questions}"""


def get_questions(
    category: str | None = None,
    difficulty: str | None = None,
    count: int = 5,
) -> list[dict[str, Any]]:
    pool = SEED_QUESTIONS
    if category:
        pool = [q for q in pool if q["category"] == category]
    if difficulty:
        pool = [q for q in pool if q["difficulty"] == difficulty]
    if len(pool) <= count:
        return pool
    return random.sample(pool, count)


async def score_answer(question_id: str, answer: str) -> dict[str, Any]:
    q = next((q for q in SEED_QUESTIONS if q["id"] == question_id), None)
    if not q:
        return {"score": 0, "summary": "题目未找到", "key_points_hit": [], "key_points_missed": [], "suggestion": ""}

    key_points = q.get("key_points") or []
    key_points_block = "\n".join(f"- {kp}" for kp in key_points) or "（本题无参考要点，按通用标准评分）"

    # Structured output: forced function-calling guarantees a schema-shaped
    # reply, so a chatty model can't break scoring the way raw json.loads did.
    try:
        result = await call_llm_structured(
            system=SCORE_PROMPT.format(
                question=q["question"],
                category=q["category"],
                difficulty=q["difficulty"],
                key_points=key_points_block,
            ),
            user_message=f"候选人回答：\n{answer}",
            output_schema=QuizScore,
            max_tokens=600,
        )
        return result.model_dump()
    except Exception:
        return {"score": 5, "summary": "评分解析失败", "key_points_hit": [], "key_points_missed": [], "suggestion": ""}


async def generate_question(category: str, difficulty: str = "mid") -> dict[str, Any]:
    existing = [q["question"] for q in SEED_QUESTIONS if q["category"] == category][:5]
    raw = await call_llm(
        system=GENERATE_PROMPT.format(
            category=category,
            difficulty=difficulty,
            existing_questions="; ".join(existing),
        ),
        user_message=f"Generate a {difficulty} question for category: {category}",
        max_tokens=300,
    )
    try:
        result = json.loads(raw)
        result["id"] = f"gen_{category}_{random.randint(1000, 9999)}"
        result["category"] = category
        result["difficulty"] = difficulty
        result["company_tags"] = []
        return result
    except json.JSONDecodeError:
        return {
            "id": f"gen_fallback_{random.randint(1000, 9999)}",
            "category": category,
            "difficulty": difficulty,
            "question": "生成失败，请重试",
            "hint": "",
            "company_tags": [],
        }

