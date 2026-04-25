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
