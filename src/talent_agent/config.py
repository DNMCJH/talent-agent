from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"

    qdrant_url: str = ""  # empty = local file mode (no server needed)
    qdrant_api_key: str = ""
    qdrant_local_path: str = "./data/qdrant_storage"
    qdrant_collection_projects: str = "projects"
    qdrant_collection_jds: str = "jds"

    projects_root: str = "a:/VScode/Code/Projects"
    index_exclude: list[str] = ["talent-agent", ".git", "node_modules", ".venv"]

    state_db: str = "./data/state.sqlite"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
