"""Parse resume files (PDF/DOCX) into structured data via text extraction + LLM."""

from __future__ import annotations

import asyncio
import io

from pydantic import BaseModel

from app.core.llm import call_llm_structured


class _ResumeFields(BaseModel):
    """LLM output schema — the fields the model actually extracts.

    Excludes raw_text: that is the source document itself, filled by code,
    not something the LLM should generate.
    """

    name: str = ""
    email: str = ""
    phone: str = ""
    education: list[dict[str, str]] = []
    experience: list[dict[str, str]] = []
    skills: list[str] = []
    projects: list[dict[str, str]] = []


class ParsedResume(_ResumeFields):
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
    parts: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]

    # Table-layout resumes — common in Chinese templates — put nearly all
    # content inside tables, which doc.paragraphs does not cover. Without this
    # such resumes parse out near-empty.
    for table in doc.tables:
        for row in table.rows:
            # row.cells repeats merged cells; dedupe while keeping order.
            seen: list[str] = []
            for cell in row.cells:
                text = cell.text.strip()
                if text and text not in seen:
                    seen.append(text)
            if seen:
                parts.append(" | ".join(seen))

    return "\n".join(parts)


_PARSE_SYSTEM = """You are a resume parser. Extract structured information from the resume text the user provides.

Field guidance:
- name: candidate's full name
- email: email address (empty string if not found)
- phone: phone number (empty string if not found)
- education: array of objects with {school, degree, major, period}
- experience: array of objects with {company, role, period, description}
- skills: array of skill strings
- projects: array of objects with {name, description, tech_stack, highlights}

Use empty strings or empty arrays for anything the resume does not mention; do not invent details."""


async def parse_resume(content: bytes, filename: str) -> ParsedResume:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # PDF/DOCX extraction is synchronous CPU/IO — offload so a large file does
    # not block the event loop (production runs a single uvicorn worker).
    if ext == "pdf":
        raw_text = await asyncio.to_thread(extract_text_from_pdf, content)
    elif ext in ("docx", "doc"):
        raw_text = await asyncio.to_thread(extract_text_from_docx, content)
    else:
        raw_text = content.decode("utf-8", errors="replace")

    if not raw_text.strip():
        return ParsedResume(raw_text="(empty document)")

    # 12k chars comfortably covers a 2-3 page resume — including table-layout
    # ones whose cell joins inflate the character count.
    truncated = raw_text[:12000]

    # Forced function-calling guarantees a schema-shaped reply — no prose
    # preamble or markdown fence can break parsing the way the old hand-rolled
    # JSON extraction did.
    try:
        fields = await call_llm_structured(_PARSE_SYSTEM, truncated, _ResumeFields, provider="claude")
    except Exception:
        # A failed parse must not lose the document — return raw_text so the
        # caller can still store it and the user can edit fields manually.
        return ParsedResume(raw_text=raw_text[:6000])

    return ParsedResume(**fields.model_dump(), raw_text=raw_text[:6000])
