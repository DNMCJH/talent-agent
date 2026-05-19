from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # Embedding
    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"

    # Qdrant (multi-tenant via payload filter on user_id)
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_collection_projects: str = "projects"
    qdrant_collection_jds: str = "jds"

    # Postgres (users, projects, sessions, weaknesses)
    postgres_dsn: str = "postgresql+asyncpg://talent:talent@postgres:5432/talent"

    # Redis (session cache, rate limit)
    redis_url: str = "redis://redis:6379/0"

    # GitHub OAuth (verified on the API; UI uses NextAuth.js)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_token: str = ""

    # API
    api_cors_origins: list[str] = ["http://localhost:3000"]
    api_secret: str = "dev-secret-change-me"  # JWT signing for session tokens

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
