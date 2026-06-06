import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter()

DATA_ROOT = Path("/app/data") if Path("/app").exists() else Path(__file__).resolve().parents[2] / "data"
DATA_DIR = DATA_ROOT / "integrations"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class OralPracticeResultIn(BaseModel):
    type: str = "oral_practice_sync"
    session_id: str = Field(min_length=1, max_length=64)
    scenario: str = "interview"
    total_turns: int = 0
    total_corrections: int = 0
    avg_pronunciation: float | None = None
    avg_fluency: float | None = None
    avg_accuracy: float | None = None
    common_errors: list[dict] = Field(default_factory=list)
    report: str = ""


@router.post("/oral-practice/result")
async def receive_oral_practice_result(
    body: OralPracticeResultIn,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> dict:
    """Receive a completed SpeakFlow mock interview result.

    This is intentionally internal-token protected and stores an append-only
    event for now. It gives the product a reliable cross-service handoff without
    coupling to Talent Agent's logged-in user session model.
    """
    if not settings.talent_agent_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "integration token is not configured")
    if x_internal_token != settings.talent_agent_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid integration token")

    event = body.model_dump()
    event["received_at"] = datetime.now(UTC).isoformat()

    out_file = DATA_DIR / "oral_practice_results.jsonl"
    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return {"synced": True, "session_id": body.session_id}
