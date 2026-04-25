import asyncio

import httpx

from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knowledgedeck_backend"}


def test_ready_endpoint_returns_ready() -> None:
    async def request_ready() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/ready")

    response = asyncio.run(request_ready())

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
