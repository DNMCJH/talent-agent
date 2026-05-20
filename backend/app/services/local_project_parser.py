"""Parse uploaded local project files (zip) into a ProjectDoc."""

from __future__ import annotations

import io
import os
import zipfile
from collections import Counter

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


async def parse_uploaded_project(content: bytes, filename: str) -> ProjectDoc:
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ValueError("Uploaded file is not a valid zip archive")

    zf = zipfile.ZipFile(io.BytesIO(content))
    names = zf.namelist()

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

    total = sum(lang_bytes.values()) or 1
    languages = {lang: round(b / total, 3) for lang, b in lang_bytes.most_common(10)}
    stack = list(languages.keys())

    if signals.get("pyproject") or signals.get("requirements"):
        if "Python" not in stack:
            stack.append("Python")
    if signals.get("package_json") and not any(s in stack for s in ("JavaScript", "TypeScript")):
        stack.append("JavaScript")

    project_name = filename.rsplit(".", 1)[0] if "." in filename else filename

    topics_raw = await call_llm(
        system="Extract up to 8 topic keywords for this project. Return only a comma-separated list.",
        user_message=(
            f"Project: {project_name}\nLanguages: {list(languages)}\n"
            f"Files: {sample_files[:8]}\nREADME excerpt:\n{readme_text[:2000]}"
        ),
        max_tokens=120,
    )
    topics = [t.strip() for t in topics_raw.split(",") if t.strip()][:8]

    deployment_signal = bool(signals.get("dockerfile") or signals.get("docker_compose"))

    return ProjectDoc(
        name=project_name,
        path=f"upload://{filename}",
        readme=readme_text,
        stack=stack,
        languages=languages,
        topics=topics,
        has_dockerfile=bool(signals.get("dockerfile")),
        has_tests=has_tests,
        deployment_signal=deployment_signal,
        complexity_loc=total_loc,
        sample_files=sample_files[:10],
    )
