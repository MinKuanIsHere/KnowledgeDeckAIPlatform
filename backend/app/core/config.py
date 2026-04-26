from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KnowledgeDeck"
    environment: str = "local"
    api_prefix: str = "/api"

    database_url: str = (
        "postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck"
    )

    initial_user_username: str = ""
    initial_user_password: str = ""

    # Comma-separated list of allowed CORS origins (e.g.
    # "http://localhost:3000,http://192.168.1.102:3000"). Empty = no CORS
    # middleware attached. Used by the browser when the frontend host
    # differs from the backend host (cross-origin requests).
    cors_origins: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    minio_endpoint: str = "knowledgedeck_minio:9000"
    minio_access_key: str = "change-me"
    minio_secret_key: str = "change-me"
    minio_bucket: str = "knowledgedeck"
    minio_secure: bool = False  # MVP runs MinIO over plain HTTP inside the compose network

    # 50 MiB hard cap on a single file upload.
    max_upload_bytes: int = 52_428_800

    llm_base_url: str = "http://knowledgedeck_vllm_chat:8000/v1"
    llm_api_key: str = "local-dev-key"
    llm_model: str = "google/gemma-4-E4B-it"

    embedding_base_url: str = "http://knowledgedeck_vllm_embedding:8001/v1"
    embedding_api_key: str = "local-dev-key"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024  # BAAI/bge-m3 outputs 1024-dim vectors

    qdrant_url: str = "http://knowledgedeck_qdrant:6333"
    qdrant_collection: str = "knowledgedeck"

    # Presenton (PPTX rendering) — runs as a separate compose service. The
    # shared volume mounted at presenton_data_root lets backend read PPTX
    # files Presenton wrote without proxying via HTTP.
    presenton_url: str = "http://knowledgedeck_presenton:80"
    presenton_username: str = "admin"
    presenton_password: str = "change-me-please"
    presenton_data_root: str = "/presenton_data"

    # Chunking knobs (character-based, simple). Bigger overlap reduces
    # mid-sentence cuts at the cost of more vectors per file.
    chunk_chars: int = 1200
    chunk_overlap: int = 150

    gpu_device: str = "0"
    vllm_chat_gpu_memory_utilization: float = 0.70
    vllm_chat_max_model_len: int = 16384
    vllm_embedding_gpu_memory_utilization: float = 0.22
    vllm_embedding_max_model_len: int = 8192


@lru_cache
def get_settings() -> Settings:
    return Settings()
