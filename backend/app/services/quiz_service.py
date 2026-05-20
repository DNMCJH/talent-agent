"""Quiz question bank and AI-powered self-test service.

Seed questions are loaded from a static bank. The LLM can generate new questions
on demand based on category and difficulty. User answers are scored by the LLM.
"""
from __future__ import annotations

import json
import random
from typing import Any

from app.core.llm import call_llm

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
# Each entry: {category, difficulty, question, hint, company_tags}
SEED_QUESTIONS: list[dict[str, Any]] = [
    {"id": "f1", "category": "foundations", "difficulty": "mid", "question": "What is generative AI, and how is it different from predictive ML?", "hint": "Think about output distributions vs fixed labels.", "company_tags": ["OpenAI", "Google DeepMind", "NVIDIA"]},
    {"id": "f2", "category": "foundations", "difficulty": "mid", "question": "Explain self-attention in a transformer and why it matters for LLMs.", "hint": "Q/K/V projections, quadratic complexity, long-range dependencies.", "company_tags": ["Anthropic", "Cohere", "Hugging Face"]},
    {"id": "f3", "category": "foundations", "difficulty": "mid", "question": "What are tokens and why does tokenization matter for LLM applications?", "hint": "BPE, cost, multilingual, context window.", "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "f4", "category": "foundations", "difficulty": "senior", "question": "Compare autoregressive decoding with diffusion-based generation.", "hint": "Sequential vs iterative refinement, latency, quality.", "company_tags": ["Google DeepMind", "Stability AI"]},
    {"id": "f5", "category": "foundations", "difficulty": "senior", "question": "What is the scaling hypothesis and what are its practical limits?", "hint": "Chinchilla, data walls, diminishing returns.", "company_tags": ["Anthropic", "OpenAI"]},
    {"id": "r1", "category": "rag", "difficulty": "mid", "question": "Walk me through a production RAG pipeline end-to-end.", "hint": "Chunking → embedding → retrieval → reranking → generation → citation.", "company_tags": ["Pinecone", "Cohere", "Microsoft"]},
    {"id": "r2", "category": "rag", "difficulty": "mid", "question": "How do you evaluate RAG quality? What metrics matter?", "hint": "Faithfulness, relevance, recall@k, answer correctness.", "company_tags": ["Anthropic", "LangChain"]},
    {"id": "r3", "category": "rag", "difficulty": "senior", "question": "When would you choose RAG over fine-tuning, and vice versa?", "hint": "Freshness, cost, hallucination control, domain specificity.", "company_tags": ["OpenAI", "Google"]},
    {"id": "r4", "category": "rag", "difficulty": "mid", "question": "What chunking strategies exist and how do you pick one?", "hint": "Fixed-size, semantic, recursive, document-aware.", "company_tags": ["Pinecone", "Weaviate"]},
    {"id": "r5", "category": "rag", "difficulty": "senior", "question": "How do you handle multi-hop questions in RAG?", "hint": "Query decomposition, iterative retrieval, chain-of-thought.", "company_tags": ["Microsoft", "Anthropic"]},
    {"id": "a1", "category": "agent", "difficulty": "mid", "question": "What is an AI agent and how does it differ from a chain?", "hint": "Autonomy, tool use, planning loop, state.", "company_tags": ["OpenAI", "LangChain", "Anthropic"]},
    {"id": "a2", "category": "agent", "difficulty": "senior", "question": "How do you prevent an agent from going off-rails in production?", "hint": "Guardrails, budget limits, human-in-the-loop, sandboxing.", "company_tags": ["Anthropic", "OpenAI"]},
    {"id": "a3", "category": "agent", "difficulty": "mid", "question": "Describe the ReAct pattern and when you'd use it.", "hint": "Reason + Act loop, observation, tool calling.", "company_tags": ["Google DeepMind", "LangChain"]},
    {"id": "ma1", "category": "multi_agent", "difficulty": "senior", "question": "When would you use multiple agents vs a single agent with many tools?", "hint": "Separation of concerns, context limits, specialization.", "company_tags": ["Microsoft", "CrewAI"]},
    {"id": "ma2", "category": "multi_agent", "difficulty": "senior", "question": "How do you handle coordination and communication between agents?", "hint": "Message passing, shared state, orchestrator pattern.", "company_tags": ["AutoGen", "LangGraph"]},
    {"id": "p1", "category": "prompting", "difficulty": "mid", "question": "What is chain-of-thought prompting and when does it help?", "hint": "Step-by-step reasoning, math/logic tasks, few-shot examples.", "company_tags": ["Google", "OpenAI"]},
    {"id": "p2", "category": "prompting", "difficulty": "mid", "question": "How do you structure a system prompt for a production application?", "hint": "Role, constraints, output format, examples, guardrails.", "company_tags": ["Anthropic", "OpenAI"]},
    {"id": "t1", "category": "tools_mcp", "difficulty": "mid", "question": "How does function calling / tool use work in modern LLMs?", "hint": "Schema definition, model selection, execution, result injection.", "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "t2", "category": "tools_mcp", "difficulty": "senior", "question": "What is MCP (Model Context Protocol) and what problem does it solve?", "hint": "Standardized tool interface, server/client, resource discovery.", "company_tags": ["Anthropic"]},
    {"id": "m1", "category": "memory", "difficulty": "mid", "question": "What memory strategies exist for LLM applications?", "hint": "Buffer, summary, vector store, entity memory, conversation window.", "company_tags": ["LangChain", "OpenAI"]},
    {"id": "e1", "category": "evaluation", "difficulty": "senior", "question": "How do you evaluate an LLM application in production?", "hint": "Online vs offline, LLM-as-judge, human eval, A/B testing.", "company_tags": ["Anthropic", "Google"]},
    {"id": "s1", "category": "safety", "difficulty": "mid", "question": "What are common LLM security risks and how do you mitigate them?", "hint": "Prompt injection, data leakage, jailbreaks, output validation.", "company_tags": ["Anthropic", "OWASP"]},
    {"id": "ft1", "category": "fine_tuning", "difficulty": "mid", "question": "When should you fine-tune vs use prompting + RAG?", "hint": "Style/format, latency, cost, data availability.", "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "sd1", "category": "system_design", "difficulty": "senior", "question": "Design a real-time AI customer support system.", "hint": "Routing, RAG, escalation, latency, caching, fallback.", "company_tags": ["Intercom", "Zendesk"]},
    {"id": "sd2", "category": "system_design", "difficulty": "senior", "question": "How would you build a code review agent?", "hint": "Diff parsing, context retrieval, multi-file understanding, feedback format.", "company_tags": ["GitHub", "Anthropic"]},
    {"id": "cl1", "category": "cost_latency", "difficulty": "mid", "question": "What strategies reduce LLM inference cost in production?", "hint": "Caching, model routing, batching, shorter prompts, smaller models.", "company_tags": ["OpenAI", "Anthropic"]},
    {"id": "b1", "category": "behavioral", "difficulty": "mid", "question": "Tell me about a time you debugged a non-deterministic AI system.", "hint": "Reproduction, logging, seed control, statistical testing.", "company_tags": ["Any"]},
]


SCORE_PROMPT = """你是一位 AI 工程面试评分官。评估候选人对以下面试题的回答。

题目：{question}
分类：{category}
难度：{difficulty}

候选人回答：
{answer}

返回 JSON：
{{
  "score": 1-10 (1=完全错误, 5=基本合格, 7=良好, 9=优秀, 10=完美),
  "summary": "一句话总评（中文）",
  "key_points_hit": ["答到的关键点"],
  "key_points_missed": ["遗漏的关键点"],
  "suggestion": "一句改进建议（中文）"
}}

评分标准：5分=知道概念但缺乏深度，7分=有具体例子和trade-off分析，9分=能举一反三+实际经验。"""


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

    raw = await call_llm(
        system=SCORE_PROMPT.format(
            question=q["question"],
            category=q["category"],
            difficulty=q["difficulty"],
            answer=answer,
        ),
        user_message=answer,
        max_tokens=400,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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

