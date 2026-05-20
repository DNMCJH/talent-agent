from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, interview, match, projects, quiz, resume, resume_upload
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.embedder import embed_text
    embed_text("warmup")
    yield


app = FastAPI(title="talent-agent API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(match.router, prefix="/match", tags=["match"])
app.include_router(interview.router, prefix="/interview", tags=["interview"])
app.include_router(resume.router, prefix="/resume", tags=["resume"])
app.include_router(resume_upload.router, prefix="/resume-upload", tags=["resume-upload"])
app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
