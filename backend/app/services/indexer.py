"""Project indexer: scan local projects, extract metadata, embed, upsert to Qdrant."""

from __future__ import annotations

from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from app.core.config import settings
from app.core.llm import call_llm
from app.schemas.agent_models import ProjectDoc


def _read_readme(project_path: Path) -> str:
    for name in ["README.md", "README_CN.md", "readme.md"]:
        readme = project_path / name
        if readme.exists():
            text = readme.read_text(encoding="utf-8", errors="ignore")
            return text[:8000]
    for md in project_path.glob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        return text[:8000]
    return ""


def _detect_stack(project_path: Path) -> list[str]:
    stack = []

    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        stack.append("Python")
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        for lib in ["fastapi", "flask", "django", "langchain", "torch", "tensorflow",
                    "streamlit", "anthropic", "openai", "qdrant", "celery", "sqlalchemy"]:
            if lib in content.lower():
                stack.append(lib)

    requirements = project_path / "requirements.txt"
    if requirements.exists() and "Python" not in stack:
        stack.append("Python")
        content = requirements.read_text(encoding="utf-8", errors="ignore")
        for lib in ["fastapi", "flask", "django", "langchain", "torch", "tensorflow",
                    "streamlit", "anthropic", "openai", "qdrant"]:
            if lib in content.lower():
                stack.append(lib)

    pkg_json = project_path / "package.json"
    if pkg_json.exists():
        stack.append("JavaScript/TypeScript")
        content = pkg_json.read_text(encoding="utf-8", errors="ignore")
        for lib in ["react", "vue", "next", "express", "nest", "tailwind"]:
            if lib in content.lower():
                stack.append(lib)

    cargo = project_path / "Cargo.toml"
    if cargo.exists():
        stack.append("Rust")

    go_mod = project_path / "go.mod"
    if go_mod.exists():
        stack.append("Go")

    return list(dict.fromkeys(stack))


def _git_facts(project_path: Path) -> tuple[str, int]:
    try:
        repo = Repo(project_path)
        commits = list(repo.iter_commits(max_count=100))
        if commits:
            last_date = commits[0].committed_datetime.isoformat()
            return last_date, len(commits)
    except (InvalidGitRepositoryError, Exception):
        pass
    return "", 0


def _detect_signals(project_path: Path) -> tuple[bool, bool, bool]:
    has_dockerfile = (project_path / "Dockerfile").exists() or (project_path / "dockerfile").exists()
    has_tests = (project_path / "tests").is_dir() or any(project_path.rglob("*_test.py"))

    deployment_signal = (
        has_dockerfile
        or (project_path / "docker-compose.yml").exists()
        or (project_path / "docker-compose.yaml").exists()
        or (project_path / ".github" / "workflows").is_dir()
        or (project_path / "k8s").is_dir()
    )
    return has_dockerfile, has_tests, deployment_signal


def _count_loc(project_path: Path) -> int:
    import contextlib

    total = 0
    extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp"}
    for f in project_path.rglob("*"):
        if f.suffix in extensions and ".venv" not in str(f) and "node_modules" not in str(f):
            with contextlib.suppress(OSError, PermissionError):
                total += sum(1 for _ in f.open(encoding="utf-8", errors="ignore"))
    return total


async def scan_project(project_path: Path) -> ProjectDoc:
    readme = _read_readme(project_path)
    stack = _detect_stack(project_path)
    last_commit, commit_count = _git_facts(project_path)
    has_dockerfile, has_tests, deployment_signal = _detect_signals(project_path)
    loc = _count_loc(project_path)

    topics_raw = await call_llm(
        system="Extract up to 8 topic keywords from this project description. Return only a comma-separated list of keywords, nothing else.",
        user_message=f"Project: {project_path.name}\nStack: {stack}\nREADME:\n{readme[:2000]}",
        max_tokens=100,
    )
    topics = [t.strip() for t in topics_raw.split(",") if t.strip()][:8]

    return ProjectDoc(
        name=project_path.name,
        path=str(project_path),
        readme=readme,
        stack=stack,
        topics=topics,
        last_commit_date=last_commit,
        commit_count=commit_count,
        has_dockerfile=has_dockerfile,
        has_tests=has_tests,
        deployment_signal=deployment_signal,
        complexity_loc=loc,
    )


async def scan_all_projects() -> list[ProjectDoc]:
    root = Path(settings.projects_root)
    exclude = set(settings.index_exclude)
    projects = []

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in exclude or entry.name.startswith("."):
            continue
        doc = await scan_project(entry)
        if doc.readme or doc.stack:
            projects.append(doc)

    return projects
