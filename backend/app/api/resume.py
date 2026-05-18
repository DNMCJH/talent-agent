from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class ResumeIn(BaseModel):
    project_id: int
    jd_hash: str


@router.post("")
async def generate_resume(body: ResumeIn) -> dict[str, str]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "resume generation pending")
