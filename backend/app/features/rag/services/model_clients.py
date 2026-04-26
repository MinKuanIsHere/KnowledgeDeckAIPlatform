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


class RerankClient:
    """Cross-encoder client for vLLM `--task=score`.

    vLLM exposes `POST /v1/score` with body `{model, text_1, text_2}`.
    We pass the query as text_1 (string) and the candidate passages as
    text_2 (list of strings). The response shape is
    `{"data": [{"index": i, "score": f}, ...]}`. Higher score = more
    relevant. We resort by score descending so callers see best-first.
    """

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

    async def score(
        self, query: str, passages: Sequence[str]
    ) -> list[tuple[int, float]]:
        """Returns list of (original_index, score), sorted by score desc."""
        if not passages:
            return []
        payload = {
            "model": self._model,
            "text_1": query,
            "text_2": list(passages),
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._http_client is not None:
            response = await self._http_client.post(
                f"{self._base_url}/score", json=payload, headers=headers
            )
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/score", json=payload, headers=headers
                )
        response.raise_for_status()
        data = response.json().get("data", [])
        # Be defensive — some vLLM versions return `index`, others rely on
        # positional ordering. Fall back to enumerate if `index` is missing.
        out: list[tuple[int, float]] = []
        for i, row in enumerate(data):
            idx = row.get("index", i)
            score = float(row.get("score", 0.0))
            out.append((idx, score))
        out.sort(key=lambda t: t[1], reverse=True)
        return out
