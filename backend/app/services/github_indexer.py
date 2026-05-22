"""Fetch project metadata from a GitHub URL via the REST API (no local clone).

This is the SaaS replacement for the local-filesystem `indexer.scan_project`.
We trade depth (no source-file LOC walk) for breadth (any public repo, no disk needed).
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.llm import call_llm
from app.schemas.agent_models import ProjectDoc

_GITHUB_API = "https://api.github.com"

# Shared topic-tagging prompt (also used by local_project_parser).
TOPIC_SYSTEM = """You tag software projects with the technical topics a recruiter would search for.

Return ONLY a comma-separated list of up to 8 topics. No prose, no numbering.

A good topic is one of:
- a domain or problem area — "recommendation system", "real-time chat", "computer vision"
- a framework, platform, or notable tool — "FastAPI", "React", "PostgreSQL", "Redis"
- an architecture or engineering pattern — "microservices", "event-driven", "REST API", "CI/CD"

Do NOT return:
- bare programming languages (Python, Go, ...) — those are tracked separately
- vague words — "software", "app", "code", "project", "backend", "tool"

Use the engineering signals provided (Docker, CI/CD, etc.) as topics when present.
Prefer specific over generic. If unsure, return fewer topics rather than padding.

Example output: RAG, vector search, FastAPI, LLM, Docker, REST API"""

# Backwards-compatible alias kept in case anything imports the lowercase name.
_TOPIC_SYSTEM = TOPIC_SYSTEM

_GITHUB_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?(?:[#?].*)?$",
    re.IGNORECASE,
)


def parse_github_url(url: str) -> tuple[str, str]:
    m = _GITHUB_URL_RE.match(url.strip())
    if not m:
        raise ValueError(f"Not a valid GitHub repository URL: {url!r}")
    return m.group(1), m.group(2)


async def _gh_get(client: httpx.AsyncClient, path: str, **kwargs: Any) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    headers.setdefault("Accept", "application/vnd.github+json")
    headers.setdefault("X-GitHub-Api-Version", "2022-11-28")
    return await client.get(f"{_GITHUB_API}{path}", headers=headers, **kwargs)


async def _fetch_readme(client: httpx.AsyncClient, owner: str, repo: str) -> str:
    r = await _gh_get(
        client,
        f"/repos/{owner}/{repo}/readme",
        headers={"Accept": "application/vnd.github.raw"},
    )
    if r.status_code == 200:
        return r.text[:8000]
    return ""


async def _fetch_languages(client: httpx.AsyncClient, owner: str, repo: str) -> dict[str, float]:
    r = await _gh_get(client, f"/repos/{owner}/{repo}/languages")
    if r.status_code != 200:
        return {}
    counts: dict[str, int] = r.json()
    total = sum(counts.values()) or 1
    return {lang: round(n / total, 3) for lang, n in counts.items()}


async def _fetch_signals(client: httpx.AsyncClient, owner: str, repo: str) -> dict[str, bool]:
    """Probe a few known config files to detect stack + deployment signals."""
    paths_to_probe = {
        "dockerfile": "Dockerfile",
        "docker_compose": "docker-compose.yml",
        "gh_actions": ".github/workflows",
        "k8s": "k8s",
        "tests_dir": "tests",
        "pyproject": "pyproject.toml",
        "requirements": "requirements.txt",
        "package_json": "package.json",
        "cargo": "Cargo.toml",
        "go_mod": "go.mod",
    }
    results: dict[str, bool] = {}
    for key, path in paths_to_probe.items():
        r = await _gh_get(client, f"/repos/{owner}/{repo}/contents/{path}")
        results[key] = r.status_code == 200
    return results


def _build_stack(languages: dict[str, float], signals: dict[str, bool]) -> list[str]:
    stack: list[str] = []
    # Languages reported by GitHub — most-used first
    for lang, _frac in sorted(languages.items(), key=lambda kv: kv[1], reverse=True):
        stack.append(lang)
    # Framework / tool hints from file presence
    if signals.get("pyproject") or signals.get("requirements"):
        if "Python" not in stack:
            stack.append("Python")
    if signals.get("package_json") and not any(s in stack for s in ("JavaScript", "TypeScript")):
        stack.append("JavaScript")
    if signals.get("cargo") and "Rust" not in stack:
        stack.append("Rust")
    if signals.get("go_mod") and "Go" not in stack:
        stack.append("Go")
    return list(dict.fromkeys(stack))


async def scan_github_repo(url: str, *, token: str | None = None) -> ProjectDoc:
    """Pull metadata for a public GitHub repo. `token` enables higher rate limit
    and access to private repos owned/granted by the caller."""
    owner, repo = parse_github_url(url)
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        meta_r = await _gh_get(client, f"/repos/{owner}/{repo}")
        if meta_r.status_code == 404:
            raise ValueError(f"GitHub repo not found or private without auth: {owner}/{repo}")
        meta_r.raise_for_status()
        meta = meta_r.json()

        readme = await _fetch_readme(client, owner, repo)
        languages = await _fetch_languages(client, owner, repo)
        signals = await _fetch_signals(client, owner, repo)

    stack = _build_stack(languages, signals)
    deployment_signal = signals.get("dockerfile") or signals.get("docker_compose") \
        or signals.get("gh_actions") or signals.get("k8s") or False

    signal_desc = ", ".join(k for k, v in {
        "Docker": signals.get("dockerfile") or signals.get("docker_compose"),
        "CI/CD": signals.get("gh_actions"),
        "Kubernetes": signals.get("k8s"),
        "automated tests": signals.get("tests_dir"),
    }.items() if v) or "none detected"

    topics_raw = await call_llm(
        system=_TOPIC_SYSTEM,
        user_message=(
            f"Project name: {repo}\n"
            f"Languages: {list(languages)}\n"
            f"Engineering signals: {signal_desc}\n"
            f"Description: {meta.get('description') or '(none)'}\n"
            f"README excerpt:\n{readme[:3000]}"
        ),
        max_tokens=120,
        temperature=0.0,
    )
    topics = [t.strip() for t in topics_raw.split(",") if t.strip()][:8]
    # GitHub-declared topics are often more reliable than LLM guesses for well-tagged repos.
    for gh_topic in (meta.get("topics") or [])[:8]:
        if gh_topic not in topics:
            topics.append(gh_topic)
    topics = topics[:8]

    return ProjectDoc(
        name=repo,
        path=f"github://{owner}/{repo}",
        readme=readme,
        stack=stack,
        languages=languages,
        topics=topics,
        last_commit_date=meta.get("pushed_at") or "",
        commit_count=0,  # exact count is expensive on GitHub API; left zero
        has_dockerfile=bool(signals.get("dockerfile")),
        has_tests=bool(signals.get("tests_dir")),
        deployment_signal=bool(deployment_signal),
        complexity_loc=int(sum((meta.get("size") or 0,))),  # repo size in KB, used as a rough proxy
    )
