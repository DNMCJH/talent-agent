"""Parse resume files (PDF/DOCX) into structured data via text extraction + LLM."""

from __future__ import annotations

import io
import json
from typing import Any

from pydantic import BaseModel

from app.core.llm import call_llm


class ParsedResume(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    education: list[dict[str, str]] = []
    experience: list[dict[str, str]] = []
    skills: list[str] = []
    projects: list[dict[str, str]] = []
    raw_text: str = ""


def extract_text_from_pdf(content: bytes) -> str:
    import fitz  # pymupdf

    doc = fitz.open(stream=content, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def extract_text_from_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


_PARSE_PROMPT = """You are a resume parser. Extract structured information from the following resume text.

Return a JSON object with these fields:
- name: candidate's full name
- email: email address (empty string if not found)
- phone: phone number (empty string if not found)
- education: array of objects with {school, degree, major, period}
- experience: array of objects with {company, role, period, description}
- skills: array of skill strings
- projects: array of objects with {name, description, tech_stack, highlights}

Resume text:
---
{text}
---

Return ONLY valid JSON, no markdown fences."""


async def parse_resume(content: bytes, filename: str) -> ParsedResume:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        raw_text = extract_text_from_pdf(content)
    elif ext in ("docx", "doc"):
        raw_text = extract_text_from_docx(content)
    else:
        raw_text = content.decode("utf-8", errors="replace")

    if not raw_text.strip():
        return ParsedResume(raw_text="(empty document)")

    truncated = raw_text[:6000]
    prompt = _PARSE_PROMPT.format(text=truncated)

    response = await call_llm(prompt)

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = {}

    return ParsedResume(
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        education=data.get("education", []),
        experience=data.get("experience", []),
        skills=data.get("skills", []),
        projects=data.get("projects", []),
        raw_text=raw_text[:3000],
    )
