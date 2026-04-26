from app.core.config import Settings


def test_settings_defaults_match_local_development() -> None:
    settings = Settings()

    assert settings.app_name == "KnowledgeDeck"
    assert settings.environment == "local"
    assert settings.llm_base_url == "http://knowledgedeck_vllm_chat:8000/v1"
    assert settings.llm_model == "google/gemma-4-E4B-it"
    assert settings.embedding_base_url == "http://knowledgedeck_vllm_embedding:8001/v1"
    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.gpu_device == "0"
    assert settings.database_url == (
        "postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck"
    )
    assert settings.initial_user_username == ""
    assert settings.initial_user_password == ""


def test_settings_accept_endpoint_overrides() -> None:
    settings = Settings(
        llm_base_url="https://models.example.test/v1",
        llm_api_key="test-key",
        llm_model="custom-chat",
        embedding_base_url="https://embeddings.example.test/v1",
        embedding_api_key="embedding-key",
        embedding_model="custom-embedding",
    )

    assert settings.llm_base_url == "https://models.example.test/v1"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_model == "custom-chat"
    assert settings.embedding_base_url == "https://embeddings.example.test/v1"
    assert settings.embedding_api_key == "embedding-key"
    assert settings.embedding_model == "custom-embedding"


def test_settings_accept_initial_user_overrides() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        initial_user_username="admin",
        initial_user_password="admin-password",
    )

    assert settings.database_url == "postgresql+psycopg://test:test@localhost:5432/test"
    assert settings.initial_user_username == "admin"
    assert settings.initial_user_password == "admin-password"


def test_settings_expose_minio_fields(monkeypatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("MINIO_ENDPOINT", "knowledgedeck_minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "k")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("MINIO_BUCKET", "kd-test")
    s = Settings()
    assert s.minio_endpoint == "knowledgedeck_minio:9000"
    assert s.minio_access_key == "k"
    assert s.minio_secret_key == "s"
    assert s.minio_bucket == "kd-test"
    assert s.max_upload_bytes == 52_428_800
