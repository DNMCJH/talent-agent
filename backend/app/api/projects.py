from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.project import Project
from app.models.user import User

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


@router.post("/import/github", response_model=ProjectOut, status_code=status.HTTP_202_ACCEPTED)
async def import_github(
    body: ImportGitHubIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    # TODO: enqueue GitHub fetch + analysis + index; for now persist a stub row
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "github import pipeline pending")


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    await session.delete(project)
    await session.commit()
