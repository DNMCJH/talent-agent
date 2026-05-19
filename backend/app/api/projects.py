from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.services import vector_store
from app.services.embedder import embed_text, project_doc_to_text
from app.services.github_indexer import parse_github_url, scan_github_repo

router = APIRouter()


class ProjectOut(BaseModel):
    id: int
    name: str
    source: str
    github_url: str | None = None
    analysis_depth: str

    model_config = {"from_attributes": True}


class ImportGitHubIn(BaseModel):
    github_url: str
    analysis_depth: str = "medium"  # 'medium' | 'heavy'


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectOut]:
    result = await session.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    )
    return [ProjectOut.model_validate(p) for p in result.scalars()]


@router.post("/import/github", response_model=ProjectOut)
async def import_github(
    body: ImportGitHubIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Synchronously fetch GitHub metadata, embed, persist. Returns 200 with the project row.

    Synchronous (not background) for Phase 1 — fetch + embed is < 5s for typical repos.
    Move to Redis/Celery if it grows to multiple LLM passes."""
    try:
        owner, repo = parse_github_url(body.github_url)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    # Dedup: refuse a re-import if this user already owns this repo.
    existing = await session.execute(
        select(Project).where(
            Project.user_id == user.id, Project.github_url == body.github_url
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this repository is already imported"
        )

    try:
        doc = await scan_github_repo(body.github_url, token=settings.github_token or None)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"github fetch failed: {e}") from e

    project = Project(
        user_id=user.id,
        name=repo,
        source="github",
        github_url=body.github_url,
        analysis_depth=body.analysis_depth,
        doc=doc.model_dump(),
    )
    session.add(project)
    await session.flush()  # populate project.id

    text = project_doc_to_text(doc.name, doc.readme, doc.stack, doc.topics)
    vector = embed_text(text)
    await vector_store.ensure_projects_collection(vector_size=len(vector))
    point_id = await vector_store.upsert_project(
        user_id=user.id,
        project_id=project.id,
        vector=vector,
        payload={"name": doc.name, "stack": doc.stack, "topics": doc.topics},
    )
    project.qdrant_point_id = point_id
    await session.commit()
    await session.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    try:
        await vector_store.delete_project(user_id=user.id, project_id=project.id)
    except Exception:
        pass
    await session.delete(project)
    await session.commit()


class GitHubUserReposIn(BaseModel):
    username: str


class RepoOut(BaseModel):
    full_name: str
    html_url: str
    description: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    pushed_at: str | None = None


@router.post("/repos/github-user", response_model=list[RepoOut])
async def list_github_user_repos(
    body: GitHubUserReposIn,
    user: User = Depends(get_current_user),
) -> list[RepoOut]:
    """Fetch public repos for a GitHub username using server-side token."""
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api.github.com/users/{body.username}/repos",
            params={"sort": "pushed", "per_page": 100, "type": "owner"},
            headers=headers,
        )
    if resp.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"GitHub user '{body.username}' not found")
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitHub API error: {resp.status_code}")
    repos = resp.json()
    return [RepoOut(**{k: r.get(k) for k in RepoOut.model_fields}) for r in repos if not r.get("fork")]
