from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.core.rate_limit import rate_limit_llm
from app.models.user import User
from app.services.quiz_service import (
    CATEGORIES,
    CATEGORY_LABELS_ZH,
    generate_question,
    get_questions,
    score_answer,
)

router = APIRouter()


class ScoreIn(BaseModel):
    question_id: str
    answer: str


class GenerateIn(BaseModel):
    category: str
    difficulty: str = "mid"


@router.get("/categories")
async def list_categories(user: User = Depends(get_current_user)):
    return [{"id": c, "label_zh": CATEGORY_LABELS_ZH[c]} for c in CATEGORIES]


@router.get("/questions")
async def list_questions(
    category: str | None = None,
    difficulty: str | None = None,
    count: int = 5,
    user: User = Depends(get_current_user),
):
    if category and category not in CATEGORIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown category: {category}")
    return get_questions(category=category, difficulty=difficulty, count=count)


@router.post("/score")
async def score(
    body: ScoreIn,
    user: User = Depends(rate_limit_llm),
):
    if not body.answer.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "answer is empty")
    return await score_answer(body.question_id, body.answer)


@router.post("/generate")
async def generate(
    body: GenerateIn,
    user: User = Depends(rate_limit_llm),
):
    if body.category not in CATEGORIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown category: {body.category}")
    if body.difficulty not in ("mid", "senior"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "difficulty must be mid or senior")
    return await generate_question(body.category, body.difficulty)
