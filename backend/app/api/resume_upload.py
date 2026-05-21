"""Resume file upload and parsing endpoint."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.core.rate_limit import enforce_rate
from app.models.user import User
from app.services.resume_parser import ParsedResume, parse_resume

router = APIRouter()

_MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}


class ResumeParseOut(BaseModel):
    filename: str
    parsed: ParsedResume


@router.post("/parse", response_model=ResumeParseOut)
async def upload_and_parse_resume(
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> ResumeParseOut:
    # Each call triggers an LLM request — limit like other LLM endpoints.
    await enforce_rate(user.id, "llm", max_requests=10, window_seconds=60)
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unsupported file type: .{ext} (allowed: {', '.join(_ALLOWED_EXTENSIONS)})",
        )

    content = await file.read()
    if len(content) > _MAX_RESUME_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (max 10MB)")

    parsed = await parse_resume(content, file.filename)
    return ResumeParseOut(filename=file.filename, parsed=parsed)
