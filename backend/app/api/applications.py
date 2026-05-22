from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.application import Application
from app.models.user import User

router = APIRouter()

VALID_STATUS = {"saved", "applied", "interviewing", "offer", "rejected"}


class ApplicationOut(BaseModel):
    id: int
    company: str
    role: str
    status: str
    link: str | None = None
    notes: str = ""


class ApplicationIn(BaseModel):
    company: str
    role: str
    status: str = "saved"
    link: str | None = None
    notes: str = ""


class ApplicationPatch(BaseModel):
    company: str | None = None
    role: str | None = None
    status: str | None = None
    link: str | None = None
    notes: str | None = None


def _to_out(a: Application) -> ApplicationOut:
    return ApplicationOut(
        id=a.id, company=a.company, role=a.role,
        status=a.status, link=a.link, notes=a.notes,
    )


async def _own(app_id: int, user: User, session: AsyncSession) -> Application:
    row = await session.get(Application, app_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "application not found")
    return row


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationOut]:
    rows = await session.execute(
        select(Application)
        .where(Application.user_id == user.id)
        .order_by(Application.updated_at.desc())
    )
    return [_to_out(a) for a in rows.scalars()]


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    if body.status not in VALID_STATUS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid status")
    if not body.company.strip() or not body.role.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "company and role are required")
    row = Application(
        user_id=user.id,
        company=body.company.strip(),
        role=body.role.strip(),
        status=body.status,
        link=body.link or None,
        notes=body.notes,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.patch("/{app_id}", response_model=ApplicationOut)
async def update_application(
    app_id: int,
    body: ApplicationPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    row = await _own(app_id, user, session)
    if body.status is not None:
        if body.status not in VALID_STATUS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid status")
        row.status = body.status
    if body.company is not None:
        row.company = body.company.strip()
    if body.role is not None:
        row.role = body.role.strip()
    if body.link is not None:
        row.link = body.link or None
    if body.notes is not None:
        row.notes = body.notes
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _own(app_id, user, session)
    await session.delete(row)
    await session.commit()
