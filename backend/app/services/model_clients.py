from collections.abc import Sequence
from typing import Any

import httpx


class ChatModelClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._http_client = http_client

    async def create_chat_completion(
        self,
        messages: Sequence[dict[str, str]],
        stream: bool,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": list(messages),
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        return await self._post_json("/chat/completions", payload)

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._http_client is not None:
            response = await self._http_client.post(f"{self._base_url}{path}", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self._base_url}{path}", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


class EmbeddingClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._http_client = http_client

    async def create_embeddings(self, texts: Sequence[str]) -> dict[str, Any]:
        payload = {"model": self._model, "input": list(texts)}
        headers = {"Authorization": f"Bearer {self._api_key}"}

        if self._http_client is not None:
            response = await self._http_client.post(f"{self._base_url}/embeddings", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self._base_url}/embeddings", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
