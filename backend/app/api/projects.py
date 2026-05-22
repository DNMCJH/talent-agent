import logging
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.rate_limit import enforce_rate
from app.models.project import Project
from app.models.user import User
from app.schemas.agent_models import ProjectDoc
from app.services import vector_store
from app.services.embedder import embed_text_async, embed_texts_async, project_doc_to_text
from app.services.github_indexer import parse_github_url, scan_github_repo
from app.services.local_project_parser import parse_uploaded_project

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-user limit for import endpoints — each does GitHub I/O and/or embedding.
_IMPORT_RATE = dict(max_requests=20, window_seconds=60)


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
    # Optional: the caller's GitHub OAuth access token. Required to import
    # private repos because the server-side PAT only covers a fixed scope.
    github_token: str | None = None


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
    await enforce_rate(user.id, "import", **_IMPORT_RATE)
    try:
        owner, repo = parse_github_url(body.github_url)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    existing = await session.execute(
        select(Project).where(
            Project.user_id == user.id, Project.github_url == body.github_url
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this repository is already imported"
        )

    # Prefer the user's OAuth access token (covers their private repos);
    # fall back to the server PAT for public repos when the user hasn't
    # linked GitHub yet (email-registered users importing a public URL).
    gh_token = body.github_token or settings.github_token or None
    try:
        doc = await scan_github_repo(body.github_url, token=gh_token)
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
    await session.flush()

    try:
        text = project_doc_to_text(doc.name, doc.readme, doc.stack, doc.topics)
        vector = await embed_text_async(text)
        await vector_store.ensure_projects_collection(vector_size=len(vector))
        point_id = await vector_store.upsert_project(
            user_id=user.id,
            project_id=project.id,
            vector=vector,
            payload={"name": doc.name, "stack": doc.stack, "topics": doc.topics},
        )
        project.qdrant_point_id = point_id
    except Exception as e:
        await session.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"embed failed: {e}") from e

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
        # Postgres row still gets removed; log so the orphaned vector can be
        # reconciled instead of silently lingering in match results.
        logger.error(
            "qdrant delete failed for project %s (user %s) — vector orphaned",
            project.id, user.id, exc_info=True,
        )
    await session.delete(project)
    await session.commit()


class GitHubUserReposIn(BaseModel):
    username: str
    github_token: str | None = None


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
    """Fetch repos for a GitHub username. With user OAuth token, private
    repos are included too; otherwise falls back to the server PAT and only
    public repos are returned."""
    # Validate the username before interpolating it into the API path —
    # GitHub usernames are alphanumeric + single hyphens, ≤39 chars. This
    # rejects path-traversal and injection attempts in the URL.
    username = body.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}", username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid GitHub username")
    headers = {"Accept": "application/vnd.github+json"}
    tok = body.github_token or settings.github_token
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "pushed", "per_page": 100, "type": "owner"},
            headers=headers,
        )
    if resp.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"GitHub user '{username}' not found")
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitHub API error: {resp.status_code}")
    repos = resp.json()
    return [RepoOut(**{k: r.get(k) for k in RepoOut.model_fields}) for r in repos if not r.get("fork")]


_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


async def _persist_project(
    *,
    user: User,
    session: AsyncSession,
    doc: ProjectDoc,
    source: str,
    github_url: str | None = None,
    analysis_depth: str = "medium",
) -> Project:
    """Create a Project row + embed it in Qdrant. Used by upload/manual/resume importers."""
    project = Project(
        user_id=user.id,
        name=doc.name,
        source=source,
        github_url=github_url,
        analysis_depth=analysis_depth,
        doc=doc.model_dump(),
    )
    session.add(project)
    await session.flush()

    try:
        text = project_doc_to_text(doc.name, doc.readme, doc.stack, doc.topics)
        vector = await embed_text_async(text)
        await vector_store.ensure_projects_collection(vector_size=len(vector))
        point_id = await vector_store.upsert_project(
            user_id=user.id,
            project_id=project.id,
            vector=vector,
            payload={"name": doc.name, "stack": doc.stack, "topics": doc.topics},
        )
        project.qdrant_point_id = point_id
    except Exception as e:
        await session.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"embed failed: {e}") from e

    await session.commit()
    await session.refresh(project)
    return project


@router.post("/import/upload", response_model=ProjectOut)
async def import_upload(
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    await enforce_rate(user.id, "import", **_IMPORT_RATE)
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no file provided")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (max 50MB)")

    try:
        doc = await parse_uploaded_project(content, file.filename)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e

    project = await _persist_project(user=user, session=session, doc=doc, source="upload")
    return ProjectOut.model_validate(project)


class ManualProjectIn(BaseModel):
    name: str
    description: str = ""
    stack: list[str] = []
    topics: list[str] = []
    highlights: list[str] = []
    repo_url: str | None = None
    has_dockerfile: bool = False
    has_tests: bool = False
    deployment_signal: bool = False


def _split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.replace("、", ",").replace("，", ",").split(",") if x.strip()]


def _resume_readme(description: str, highlights: list[str]) -> str:
    parts: list[str] = []
    if description:
        parts.append(description.strip())
    if highlights:
        parts.append("\n".join(f"- {h}" for h in highlights if h.strip()))
    return "\n\n".join(parts)


@router.post("/import/manual", response_model=ProjectOut)
async def import_manual(
    body: ManualProjectIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    await enforce_rate(user.id, "import", **_IMPORT_RATE)
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "project name is required")

    existing = await session.execute(
        select(Project).where(Project.user_id == user.id, Project.name == name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"a project named '{name}' already exists")

    doc = ProjectDoc(
        name=name,
        path=f"manual://{name}",
        readme=_resume_readme(body.description, body.highlights),
        stack=body.stack,
        topics=body.topics,
        has_dockerfile=body.has_dockerfile,
        has_tests=body.has_tests,
        deployment_signal=body.deployment_signal,
    )
    project = await _persist_project(
        user=user, session=session, doc=doc, source="manual", github_url=body.repo_url
    )
    return ProjectOut.model_validate(project)


class ResumeProjectItem(BaseModel):
    name: str | None = None
    description: str | None = None
    tech_stack: str | None = None  # comma-separated string from LLM
    highlights: str | None = None


class ImportFromResumeIn(BaseModel):
    projects: list[ResumeProjectItem]


class ImportFromResumeOut(BaseModel):
    imported: list[ProjectOut]
    skipped: list[dict[str, str]]  # [{name, reason}]


@router.post("/import/from-resume", response_model=ImportFromResumeOut)
async def import_from_resume(
    body: ImportFromResumeIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ImportFromResumeOut:
    """Bulk-create Project rows from a parsed resume's project list. Each becomes a
    `source='manual'` project so the matcher and interviewer can use them like any other."""
    await enforce_rate(user.id, "import", **_IMPORT_RATE)
    imported: list[ProjectOut] = []
    skipped: list[dict[str, str]] = []

    existing_names = {
        n for (n,) in (
            await session.execute(select(Project.name).where(Project.user_id == user.id))
        ).all()
    }

    valid_docs: list[ProjectDoc] = []
    valid_items_idx: list[int] = []

    for i, item in enumerate(body.projects):
        raw_name = (item.name or "").strip()
        if not raw_name:
            skipped.append({"name": "(unnamed)", "reason": "missing name"})
            continue
        if raw_name in existing_names:
            skipped.append({"name": raw_name, "reason": "already exists"})
            continue

        stack = _split_csv(item.tech_stack or "")
        highlights = [h for h in (item.highlights or "").split("\n") if h.strip()]
        doc = ProjectDoc(
            name=raw_name,
            path=f"resume://{raw_name}",
            readme=_resume_readme(item.description or "", highlights),
            stack=stack,
            topics=stack[:5],
        )
        valid_docs.append(doc)
        valid_items_idx.append(i)
        existing_names.add(raw_name)

    if not valid_docs:
        return ImportFromResumeOut(imported=imported, skipped=skipped)

    texts = [project_doc_to_text(d.name, d.readme, d.stack, d.topics) for d in valid_docs]
    vectors = await embed_texts_async(texts)
    await vector_store.ensure_projects_collection(vector_size=len(vectors[0]))

    for doc, vector in zip(valid_docs, vectors):
        project = Project(
            user_id=user.id,
            name=doc.name,
            source="manual",
            github_url=None,
            analysis_depth="medium",
            doc=doc.model_dump(),
        )
        session.add(project)
        await session.flush()
        try:
            point_id = await vector_store.upsert_project(
                user_id=user.id,
                project_id=project.id,
                vector=vector,
                payload={"name": doc.name, "stack": doc.stack, "topics": doc.topics},
            )
            project.qdrant_point_id = point_id
            imported.append(ProjectOut.model_validate(project))
        except Exception:
            # Drop the flushed row — committing it would leave a project with
            # qdrant_point_id=None that match search can never surface.
            logger.error("resume import upsert failed for %r", doc.name, exc_info=True)
            await session.delete(project)
            skipped.append({"name": doc.name, "reason": "embed/upsert failed"})

    await session.commit()
    return ImportFromResumeOut(imported=imported, skipped=skipped)

