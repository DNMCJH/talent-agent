"""Parse uploaded local project files (zip) into a ProjectDoc."""

from __future__ import annotations

import asyncio
import io
import os
import zipfile
from collections import Counter
from typing import Any

from app.core.llm import call_llm
from app.schemas.agent_models import ProjectDoc

_LANG_EXTENSIONS: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".jsx": "JavaScript", ".java": "Java",
    ".go": "Go", ".rs": "Rust", ".c": "C", ".cpp": "C++",
    ".h": "C", ".hpp": "C++", ".cs": "C#", ".rb": "Ruby",
    ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
    ".scala": "Scala", ".vue": "Vue", ".dart": "Dart",
}

_SIGNAL_FILES = {
    "Dockerfile": "dockerfile",
    "docker-compose.yml": "docker_compose",
    "docker-compose.yaml": "docker_compose",
    "pyproject.toml": "pyproject",
    "requirements.txt": "requirements",
    "package.json": "package_json",
    "Cargo.toml": "cargo",
    "go.mod": "go_mod",
}

_IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", ".idea", ".vscode",
}


_MAX_UNCOMPRESSED_SIZE = 200 * 1024 * 1024  # 200 MB
_MAX_FILE_COUNT = 5000


def _scan_zip(content: bytes, filename: str) -> dict[str, Any]:
    """Synchronous zip extraction + static analysis.

    Run via asyncio.to_thread — reading a large archive would otherwise block
    the event loop for the whole worker.
    """
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ValueError("Uploaded file is not a valid zip archive")

    zf = zipfile.ZipFile(io.BytesIO(content))
    names = zf.namelist()

    total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > _MAX_UNCOMPRESSED_SIZE:
        raise ValueError(f"Archive too large when extracted ({total_uncompressed // 1024 // 1024}MB > 200MB limit)")
    if len(names) > _MAX_FILE_COUNT:
        raise ValueError(f"Archive contains too many files ({len(names)} > {_MAX_FILE_COUNT} limit)")

    lang_bytes: Counter[str] = Counter()
    signals: dict[str, bool] = {}
    readme_text = ""
    sample_files: list[str] = []
    has_tests = False
    total_loc = 0

    for name in names:
        parts = name.replace("\\", "/").split("/")
        if any(p in _IGNORE_DIRS for p in parts):
            continue

        basename = os.path.basename(name)

        if basename.lower().startswith("readme") and not readme_text:
            try:
                readme_text = zf.read(name).decode("utf-8", errors="replace")[:8000]
            except Exception:
                pass
            continue

        if basename in _SIGNAL_FILES:
            signals[_SIGNAL_FILES[basename]] = True

        if "test" in name.lower() or "spec" in name.lower():
            has_tests = True

        ext = os.path.splitext(basename)[1].lower()
        if ext in _LANG_EXTENSIONS:
            try:
                size = zf.getinfo(name).file_size
            except Exception:
                size = 0
            lang_bytes[_LANG_EXTENSIONS[ext]] += size
            total_loc += size // 40  # rough LOC estimate
            if len(sample_files) < 10:
                sample_files.append(name)

    # No README — fall back to source excerpts so the LLM has something
    # concrete to characterize the project from, instead of just a file list.
    source_excerpt = ""
    if not readme_text and sample_files:
        chunks: list[str] = []
        for name in sample_files[:5]:
            try:
                text = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            chunks.append(f"# {name}\n{text[:1200]}")
        source_excerpt = "\n\n".join(chunks)[:6000]

    total = sum(lang_bytes.values()) or 1
    languages = {lang: round(b / total, 3) for lang, b in lang_bytes.most_common(10)}
    stack = list(languages.keys())

    if signals.get("pyproject") or signals.get("requirements"):
        if "Python" not in stack:
            stack.append("Python")
    if signals.get("package_json") and not any(s in stack for s in ("JavaScript", "TypeScript")):
        stack.append("JavaScript")

    project_name = filename.rsplit(".", 1)[0] if "." in filename else filename

    return {
        "project_name": project_name,
        "filename": filename,
        "readme_text": readme_text,
        "source_excerpt": source_excerpt,
        "stack": stack,
        "languages": languages,
        "sample_files": sample_files,
        "has_tests": has_tests,
        "total_loc": total_loc,
        "signals": signals,
    }


async def parse_uploaded_project(content: bytes, filename: str) -> ProjectDoc:
    scan = await asyncio.to_thread(_scan_zip, content, filename)
    signals: dict[str, bool] = scan["signals"]

    if scan["readme_text"]:
        context_label = "README excerpt"
        context_body = scan["readme_text"][:2000]
    else:
        context_label = "Source excerpt"
        context_body = scan["source_excerpt"][:2000]

    topics_raw = await call_llm(
        system="Extract up to 8 topic keywords for this project. Return only a comma-separated list.",
        user_message=(
            f"Project: {scan['project_name']}\nLanguages: {list(scan['languages'])}\n"
            f"Files: {scan['sample_files'][:8]}\n{context_label}:\n{context_body}"
        ),
        max_tokens=120,
    )
    topics = [t.strip() for t in topics_raw.split(",") if t.strip()][:8]

    deployment_signal = bool(signals.get("dockerfile") or signals.get("docker_compose"))

    return ProjectDoc(
        name=scan["project_name"],
        path=f"upload://{filename}",
        readme=scan["readme_text"],
        stack=scan["stack"],
        languages=scan["languages"],
        topics=topics,
        has_dockerfile=bool(signals.get("dockerfile")),
        has_tests=scan["has_tests"],
        deployment_signal=deployment_signal,
        complexity_loc=scan["total_loc"],
        sample_files=scan["sample_files"][:10],
    )
