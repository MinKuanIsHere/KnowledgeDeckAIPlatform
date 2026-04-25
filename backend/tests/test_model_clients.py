import json

import httpx
import pytest

from app.services.model_clients import ChatModelClient, EmbeddingClient


@pytest.mark.asyncio
async def test_chat_client_posts_openai_compatible_payload() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "chatcmpl-test", "choices": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ChatModelClient(
            base_url="https://models.example.test/v1",
            api_key="secret",
            model="chat-model",
            http_client=http_client,
        )
        response = await client.create_chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            stream=False,
        )

    assert response == {"id": "chatcmpl-test", "choices": []}
    assert captured["url"] == "https://models.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert captured["payload"] == {
        "model": "chat-model",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    }


@pytest.mark.asyncio
async def test_embedding_client_posts_openai_compatible_payload() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = EmbeddingClient(
            base_url="https://embeddings.example.test/v1",
            api_key="embedding-secret",
            model="embedding-model",
            http_client=http_client,
        )
        response = await client.create_embeddings(["KnowledgeDeck"])

    assert response == {"data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]}
    assert captured["url"] == "https://embeddings.example.test/v1/embeddings"
    assert captured["authorization"] == "Bearer embedding-secret"
    assert captured["payload"] == {
        "model": "embedding-model",
        "input": ["KnowledgeDeck"],
    }
