from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class StartInterviewIn(BaseModel):
    project_id: int
    jd_hash: str
    mode: str = "tech"  # 'tech' | 'stress' | 'behavior'


class TurnIn(BaseModel):
    session_id: str
    candidate_message: str


@router.post("/start")
async def start_interview(body: StartInterviewIn) -> dict[str, str]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "interview start pending")


@router.post("/turn")
async def interview_turn(body: TurnIn) -> dict[str, str]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "interview turn pending")
