# KnowledgeDeck Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first testable KnowledgeDeck project scaffold with backend settings, model client contracts, health checks, frontend shell, and Docker Compose service definitions.

**Architecture:** Create a monorepo with `backend/`, `frontend/`, and deployment files at the repository root. The backend exposes a minimal FastAPI app with typed settings and OpenAI-compatible chat/embedding clients. The frontend starts as a Next.js app shell that can later grow into the Open WebUI/Perplexity-style chat interface.

**Tech Stack:** FastAPI, Pydantic Settings, httpx, pytest, Next.js, TypeScript, Tailwind CSS, shadcn/ui-compatible layout, Docker Compose, PostgreSQL, Redis, Qdrant, MinIO, vLLM.

---

## Scope

This plan intentionally implements only the scaffold and core contracts. It does not implement auth, database migrations, RAG ingestion, chat persistence, PPTX generation, or real UI workflows.

## File Structure

- Create `backend/pyproject.toml`: backend package metadata, runtime dependencies, and test dependencies.
- Create `backend/app/main.py`: FastAPI application factory and health route registration.
- Create `backend/app/api/health.py`: health and readiness endpoints.
- Create `backend/app/core/config.py`: typed settings loaded from environment variables.
- Create `backend/app/services/model_clients.py`: OpenAI-compatible chat and embedding client contracts.
- Create `backend/tests/test_config.py`: settings tests.
- Create `backend/tests/test_health.py`: API health tests.
- Create `backend/tests/test_model_clients.py`: request-format tests using a mock transport.
- Create `frontend/package.json`: frontend scripts and dependencies.
- Create `frontend/next.config.ts`: Next.js configuration.
- Create `frontend/tsconfig.json`: TypeScript configuration.
- Create `frontend/app/layout.tsx`: application root layout.
- Create `frontend/app/page.tsx`: initial app shell.
- Create `frontend/app/globals.css`: Tailwind base styling.
- Create `frontend/tailwind.config.ts`: Tailwind configuration.
- Create `frontend/postcss.config.js`: PostCSS configuration.
- Create `.env.example`: documented non-secret environment configuration.
- Create `docker-compose.yml`: service definitions using `knowledgedeck_*` container names.
- Create `backend/Dockerfile`: backend container image.
- Create `frontend/Dockerfile`: frontend container image.
- Modify `.gitignore`: ensure local runtime and dependency artifacts stay untracked.
- Create `README.md`: local development entry point.

---

### Task 1: Backend Package Skeleton

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/health.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knowledgedeck_backend"}


def test_ready_endpoint_returns_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
```

- [ ] **Step 2: Add backend package metadata**

Create `backend/pyproject.toml`:

```toml
[project]
name = "knowledgedeck-backend"
version = "0.1.0"
description = "FastAPI backend for KnowledgeDeck AI Platform"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "pydantic-settings>=2.4.0",
    "uvicorn[standard]>=0.30.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Create the health router**

Create `backend/app/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "knowledgedeck_backend"}


@router.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}
```

- [ ] **Step 4: Create the FastAPI app factory**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeDeck API", version="0.1.0")
    app.include_router(health_router)
    return app


app = create_app()
```

Create empty package files:

```python
# backend/app/__init__.py
```

```python
# backend/app/api/__init__.py
```

```python
# backend/tests/__init__.py
```

- [ ] **Step 5: Run the backend health tests**

Run:

```bash
cd backend
python -m pytest tests/test_health.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests/test_health.py backend/tests/__init__.py
git commit -m "feat: scaffold backend health API"
```

---

### Task 2: Typed Backend Settings

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing settings tests**

Create `backend/tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Implement typed settings**

Create `backend/app/core/config.py`:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KnowledgeDeck"
    environment: str = "local"
    api_prefix: str = "/api"

    jwt_secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60

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
```

Create `backend/app/core/__init__.py`:

```python
from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
```

- [ ] **Step 3: Run settings tests**

Run:

```bash
cd backend
python -m pytest tests/test_config.py -v
```

Expected: both tests pass.

- [ ] **Step 4: Run all backend tests**

Run:

```bash
cd backend
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core backend/tests/test_config.py
git commit -m "feat: add typed backend settings"
```

---

### Task 3: OpenAI-Compatible Model Clients

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/model_clients.py`
- Create: `backend/tests/test_model_clients.py`

- [ ] **Step 1: Write failing model client tests**

Create `backend/tests/test_model_clients.py`:

```python
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
```

- [ ] **Step 2: Add pytest asyncio dependency**

Modify `backend/pyproject.toml` dev dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
]
```

- [ ] **Step 3: Implement model clients**

Create `backend/app/services/model_clients.py`:

```python
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
```

Create `backend/app/services/__init__.py`:

```python
from app.services.model_clients import ChatModelClient, EmbeddingClient

__all__ = ["ChatModelClient", "EmbeddingClient"]
```

- [ ] **Step 4: Run model client tests**

Run:

```bash
cd backend
python -m pytest tests/test_model_clients.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Run all backend tests**

Run:

```bash
cd backend
python -m pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/services backend/tests/test_model_clients.py
git commit -m "feat: add OpenAI-compatible model clients"
```

---

### Task 4: Environment And Docker Compose Scaffold

**Files:**
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Modify: `.gitignore`

- [ ] **Step 1: Write `.env.example` with safe placeholders**

Create `.env.example`:

```env
COMPOSE_PROJECT_NAME=knowledgedeck
GPU_DEVICE=0

POSTGRES_DB=knowledgedeck
POSTGRES_USER=knowledgedeck
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck

REDIS_URL=redis://knowledgedeck_redis:6379/0
QDRANT_URL=http://knowledgedeck_qdrant:6333
MINIO_ENDPOINT=knowledgedeck_minio:9000
MINIO_ACCESS_KEY=change-me
MINIO_SECRET_KEY=change-me
MINIO_BUCKET=knowledgedeck

JWT_SECRET_KEY=change-me-change-before-deploy
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_MINUTES=60

LLM_BASE_URL=http://knowledgedeck_vllm_chat:8000/v1
LLM_API_KEY=local-dev-key
LLM_MODEL=google/gemma-4-E4B-it
VLLM_CHAT_PORT=8000
VLLM_CHAT_GPU_MEMORY_UTILIZATION=0.70
VLLM_CHAT_MAX_MODEL_LEN=16384

EMBEDDING_BASE_URL=http://knowledgedeck_vllm_embedding:8001/v1
EMBEDDING_API_KEY=local-dev-key
EMBEDDING_MODEL=BAAI/bge-m3
VLLM_EMBEDDING_PORT=8001
VLLM_EMBEDDING_GPU_MEMORY_UTILIZATION=0.22
VLLM_EMBEDDING_MAX_MODEL_LEN=8192
```

- [ ] **Step 2: Add backend Dockerfile**

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

COPY app ./app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 3: Add frontend Dockerfile**

Create `frontend/Dockerfile`:

```dockerfile
FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
```

- [ ] **Step 4: Add Docker Compose services**

Create `docker-compose.yml`:

```yaml
services:
  frontend:
    container_name: knowledgedeck_frontend
    build:
      context: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8080
    depends_on:
      - backend

  backend:
    container_name: knowledgedeck_backend
    build:
      context: ./backend
    ports:
      - "8080:8080"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
      - qdrant
      - minio

  worker:
    container_name: knowledgedeck_worker
    build:
      context: ./backend
    command: ["python", "-m", "app.worker"]
    env_file:
      - .env
    depends_on:
      - redis
      - postgres
      - qdrant
      - minio

  postgres:
    container_name: knowledgedeck_postgres
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-knowledgedeck}
      POSTGRES_USER: ${POSTGRES_USER:-knowledgedeck}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change-me}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    container_name: knowledgedeck_redis
    image: redis:7-alpine
    ports:
      - "6379:6379"

  qdrant:
    container_name: knowledgedeck_qdrant
    image: qdrant/qdrant:v1.12.1
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  minio:
    container_name: knowledgedeck_minio
    image: minio/minio:RELEASE.2024-10-13T13-34-11Z
    command: ["server", "/data", "--console-address", ":9001"]
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-change-me}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-change-me}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  vllm_chat:
    container_name: knowledgedeck_vllm_chat
    image: vllm/vllm-openai:gemma4
    profiles: ["gpu"]
    ipc: host
    environment:
      NVIDIA_VISIBLE_DEVICES: ${GPU_DEVICE:-0}
    ports:
      - "${VLLM_CHAT_PORT:-8000}:8000"
    volumes:
      - hf_cache:/root/.cache/huggingface
    command:
      - --model
      - ${LLM_MODEL:-google/gemma-4-E4B-it}
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --gpu-memory-utilization
      - ${VLLM_CHAT_GPU_MEMORY_UTILIZATION:-0.70}
      - --max-model-len
      - ${VLLM_CHAT_MAX_MODEL_LEN:-16384}
      - --limit-mm-per-prompt
      - image=0,audio=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  vllm_embedding:
    container_name: knowledgedeck_vllm_embedding
    image: vllm/vllm-openai:latest
    profiles: ["gpu"]
    ipc: host
    environment:
      NVIDIA_VISIBLE_DEVICES: ${GPU_DEVICE:-0}
    ports:
      - "${VLLM_EMBEDDING_PORT:-8001}:8000"
    volumes:
      - hf_cache:/root/.cache/huggingface
    command:
      - --model
      - ${EMBEDDING_MODEL:-BAAI/bge-m3}
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --gpu-memory-utilization
      - ${VLLM_EMBEDDING_GPU_MEMORY_UTILIZATION:-0.22}
      - --max-model-len
      - ${VLLM_EMBEDDING_MAX_MODEL_LEN:-8192}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  postgres_data:
  qdrant_data:
  minio_data:
  hf_cache:
```

- [ ] **Step 5: Ensure `.gitignore` covers generated artifacts**

Modify `.gitignore` so it contains:

```gitignore
.env
.env.*
!.env.example

__pycache__/
*.pyc
.pytest_cache/

node_modules/
.next/
dist/
build/

.venv/
venv/

data/
uploads/
storage/
minio/
postgres/
qdrant/
redis/

.DS_Store
```

- [ ] **Step 6: Validate Compose configuration without starting services**

Run:

```bash
docker compose --env-file .env.example config
```

Expected: command exits successfully and rendered container names all start with `knowledgedeck_`.

- [ ] **Step 7: Commit**

```bash
git add .env.example docker-compose.yml backend/Dockerfile frontend/Dockerfile .gitignore
git commit -m "feat: add docker compose scaffold"
```

---

### Task 5: Frontend App Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`

- [ ] **Step 1: Add frontend package metadata**

Create `frontend/package.json`:

```json
{
  "name": "knowledgedeck-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --hostname 0.0.0.0",
    "build": "next build",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@types/node": "^22.7.4",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.1",
    "autoprefixer": "^10.4.20",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "next": "^15.0.0",
    "postcss": "^8.4.47",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "tailwind-merge": "^2.5.4",
    "tailwindcss": "^3.4.14",
    "typescript": "^5.6.3"
  },
  "devDependencies": {}
}
```

- [ ] **Step 2: Add Next.js and TypeScript config**

Create `frontend/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{"name": "next"}],
    "paths": {"@/*": ["./*"]}
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Add Tailwind config**

Create `frontend/tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        border: "hsl(var(--border))",
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))"
      }
    }
  },
  plugins: []
};

export default config;
```

Create `frontend/postcss.config.js`:

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {}
  }
};
```

- [ ] **Step 4: Add root layout and global styles**

Create `frontend/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: 210 20% 98%;
  --foreground: 222 47% 11%;
  --border: 214 32% 91%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
}

body {
  background: hsl(var(--background));
  color: hsl(var(--foreground));
}
```

Create `frontend/app/layout.tsx`:

```typescript
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KnowledgeDeck",
  description: "AI chat, RAG, and editable PPTX generation platform"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 5: Add initial app shell**

Create `frontend/app/page.tsx`:

```typescript
import { FileText, MessageSquare, Presentation, Search } from "lucide-react";

const navItems = [
  { label: "Chat", icon: MessageSquare },
  { label: "Knowledge", icon: Search },
  { label: "Documents", icon: FileText },
  { label: "Slides", icon: Presentation }
];

export default function Home() {
  return (
    <main className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 border-r border-border bg-white/80 px-4 py-5 md:block">
        <div className="mb-6 text-lg font-semibold">KnowledgeDeck</div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <button
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              key={item.label}
              type="button"
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <section className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border bg-white/80 px-4">
          <div className="text-sm font-medium">Chat</div>
          <div className="text-xs text-muted-foreground">Model: Gemma 4 E4B</div>
        </header>
        <div className="flex flex-1 items-center justify-center px-4">
          <div className="w-full max-w-3xl">
            <h1 className="mb-3 text-2xl font-semibold">Ask KnowledgeDeck</h1>
            <div className="rounded-lg border border-border bg-white p-3 shadow-sm">
              <textarea
                className="min-h-28 w-full resize-none bg-transparent text-sm outline-none"
                placeholder="Ask a question or describe the presentation you want to create..."
              />
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">RAG ready scaffold</span>
                <button className="rounded-md bg-foreground px-3 py-2 text-sm text-white" type="button">
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 6: Install frontend dependencies and typecheck**

Run:

```bash
cd frontend
npm install
npm run typecheck
```

Expected: dependencies install and typecheck passes.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat: scaffold frontend app shell"
```

---

### Task 6: README And Final Verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Add README**

Create `README.md`:

```markdown
# KnowledgeDeck AI Platform

KnowledgeDeck is an internal AI platform for LLM chat, personal RAG knowledge bases, citation-based answers, and editable PPTX generation.

## Branches

- `main`: stable branch.
- `dev`: active development branch.
- Feature branches should branch from `dev`.

## Local Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Run backend tests:

```bash
cd backend
python -m pytest -v
```

Run frontend typecheck:

```bash
cd frontend
npm run typecheck
```

Validate Docker Compose:

```bash
docker compose --env-file .env.example config
```

Start non-GPU infrastructure:

```bash
docker compose --env-file .env up postgres redis qdrant minio backend frontend
```

Start with GPU model services:

```bash
docker compose --profile gpu --env-file .env up
```

## Secret Safety

Never commit `.env`, API keys, tokens, passwords, private keys, or model credentials. Use `.env.example` with placeholder values only.
```

- [ ] **Step 2: Run backend tests**

Run:

```bash
cd backend
python -m pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 3: Run frontend typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: typecheck passes.

- [ ] **Step 4: Validate Docker Compose**

Run:

```bash
docker compose --env-file .env.example config
```

Expected: Compose renders successfully.

- [ ] **Step 5: Check Git status**

Run:

```bash
git status --short --branch
```

Expected: only intended changes are present before commit, or clean after commit.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: add project setup guide"
```

- [ ] **Step 7: Push dev branch**

```bash
git push origin dev
```

Expected: `dev` branch updates on GitHub.

---

## Self-Review

- Spec coverage: This plan covers the scaffold, endpoint configuration, container naming convention, single-GPU vLLM defaults, backend client abstractions, and frontend shell required before feature implementation. Auth, RAG ingestion, chat persistence, PPTX generation, and admin features are intentionally deferred to later plans.
- Placeholder scan: No task contains `TBD`, `TODO`, `implement later`, or unspecified test instructions.
- Type consistency: Settings names, environment variables, model client method names, and Docker service names are consistent across tasks.
