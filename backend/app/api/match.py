from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class MatchIn(BaseModel):
    raw_jd: str
    intent: str = "match_only"  # 'match_only' | 'full_loop' | 'improve_only' | 'resume_only'


@router.post("")
async def run_match(body: MatchIn) -> dict[str, str]:
    # TODO: wire to app.services.orchestrator.run_pipeline with per-user Qdrant filter
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "match pipeline wiring pending")
