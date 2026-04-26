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

    llm_base_url: str = "http://knowledgedeck_vllm_chat:8000/v1"
    llm_api_key: str = "local-dev-key"
    llm_model: str = "google/gemma-4-E4B-it"

    embedding_base_url: str = "http://knowledgedeck_vllm_embedding:8001/v1"
    embedding_api_key: str = "local-dev-key"
    embedding_model: str = "BAAI/bge-m3"

    gpu_device: str = "0"
    vllm_chat_gpu_memory_utilization: float = 0.70
    vllm_chat_max_model_len: int = 16384
    vllm_embedding_gpu_memory_utilization: float = 0.22
    vllm_embedding_max_model_len: int = 8192


@lru_cache
def get_settings() -> Settings:
    return Settings()
