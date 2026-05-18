"""JD Parser agent: raw JD text -> structured ParsedJD."""

from __future__ import annotations

import hashlib

from app.core.llm import call_llm_structured
from app.schemas.agent_models import ParsedJD

SYSTEM_PROMPT = """You are a JD (Job Description) parser for tech roles. Extract structured information from the raw JD text.

Rules:
- Only extract TECHNICAL skills (programming languages, frameworks, tools, platforms, methodologies). Do NOT include soft skills like "analytical skills", "problem-solving", "communication", "teamwork", "fast-paced environment".
- Normalize skill names (e.g. "LangChain" not "langchain", "Python" not "python", "RAG" not "retrieval-augmented generation")
- Distinguish must-have skills (explicit requirements, mandatory qualifications) from plus/nice-to-have skills (marked with "plus", "preferred", "nice to have", "bonus")
- If a skill appears in a "plus" or "strong plus" sentence, it goes in plus_skills even if it sounds important
- Infer implicit signals: team style (startup vs enterprise), production vs research focus, seniority expectation
- Generate 5-10 keywords optimized for vector search against project descriptions (focus on technical terms)
- Detect language (en/zh) from the JD content
- work_mode: look for keywords like "hybrid", "remote", "onsite", "混合办公", "远程"
"""


async def parse_jd(raw_jd: str) -> ParsedJD:
    jd_hash = hashlib.sha256(raw_jd.encode()).hexdigest()[:12]

    result = await call_llm_structured(
        system=SYSTEM_PROMPT,
        user_message=f"Parse this JD:\n\n{raw_jd}",
        output_schema=ParsedJD,
    )
    result.raw = raw_jd
    result.jd_hash = jd_hash
    return result
