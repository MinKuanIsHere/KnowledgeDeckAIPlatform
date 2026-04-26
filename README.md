# KnowledgeDeck AI Platform

An internal AI platform for streaming chat, personal RAG knowledge bases with citation-based answers, and conversational PPTX deck generation. Self-hosted: vLLM for inference, Qdrant for vectors, Presenton for slide rendering — no third-party API keys required.

---

## Features

### 🗂️ Knowledge Bases (KB)

- Per-user, named collections of documents.
- Upload supports **TXT, PDF, CS, MD, DOCX, PPTX** (50 MB cap each).
- Files are parsed → chunked → embedded → indexed with **hybrid (dense + BM25) retrieval** out of the box.
- Soft-delete with `deleted_at`; vectors are cleaned from Qdrant on file delete.
- UI: drag-and-drop multi-file + folder upload, sortable file list (by upload time / size / type).

### 💬 Chat

- Multi-turn conversational chat against the configured LLM (default: `Gemma 4 E4B` via vLLM).
- Optional RAG grounding: tick **Use RAG** + pick KBs → answers cite the exact files used.
- Server-Sent Events for token-level streaming.
- Markdown rendering with copy-to-clipboard, persistent session history (rename / delete sidebar).

### 🎯 Slide Maker

- Conversational deck planning: the LLM asks clarifying questions, proposes a markdown outline, iterates until you confirm.
- On confirmation (`[OUTLINE_READY]` marker), automatically renders a PPTX via Presenton.
- 4 visual templates: `general`, `modern`, `standard`, `swift` (LLM picks based on your tone preference; can be overridden).
- Same RAG pipeline as Chat — slides can be grounded in your KB documents.
- Render result + Download button persists in the chat history; iterate and re-render anytime.

### 📊 Dashboard

- At-a-glance counts of KBs, files, chats, and decks.
- Brief feature descriptions for each module.

---

## Architecture

```
                              ┌─────────────────┐
                              │  Next.js 15     │
                              │  App Router     │
                              │  (frontend)     │
                              └────────┬────────┘
                                       │ HTTPS / SSE
                              ┌────────▼────────┐
                              │  FastAPI        │
                              │  (backend)      │
                              └─┬───────────┬───┘
                                │           │
   ┌────────────────────────────┼───────────┼──────────────────┐
   │                            │           │                  │
┌──▼──────┐   ┌─────────┐  ┌────▼────┐ ┌────▼────┐  ┌──────────▼──┐
│ vLLM    │   │ vLLM    │  │ vLLM    │ │ Qdrant  │  │  MinIO       │
│ chat    │   │ embed   │  │ rerank  │ │ vectors │  │  (originals  │
│ Gemma   │   │ bge-m3  │  │ bge-r-v2│ │  hybrid │  │   + PPTX)    │
└─────────┘   └─────────┘  └─────────┘ └─────────┘  └──────────────┘
                                                ┌──────────────┐
                                                │  Postgres    │
                                                │  (metadata)  │
                                                └──────────────┘
                                                ┌──────────────┐
                                                │  Presenton   │
                                                │  (PPTX gen)  │
                                                └──────────────┘
```

**RAG retrieval pipeline** (every chat / slide turn that opts in):

```
query → [rewriter (chat only)] → embed dense + sparse (parallel)
     → Qdrant prefetch top-40×2 → RRF fusion top-20
     → cross-encoder rerank → threshold filter → top-5 context
```

The retrieval module ([`backend/app/services/rag.py`](backend/app/services/rag.py)) is a single function shared by chat and slide maker — same hybrid search, same reranker, same threshold. Differences between the two surfaces live in the LLM prompt and in *which* query string is fed into RAG.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 15, React 18, Tailwind, Zustand, react-markdown |
| Backend | FastAPI, SQLAlchemy 2.0 async, Pydantic, Alembic |
| LLM | vLLM (OpenAI-compatible) — default Google Gemma 4 E4B |
| Embedding | vLLM serving BAAI/bge-m3 (1024-d dense) |
| Sparse | fastembed `Qdrant/bm25` (in-process) |
| Reranker | vLLM `--runner pooling --convert classify` serving BAAI/bge-reranker-v2-m3 |
| Vectors | Qdrant 1.12+ with named vectors + RRF fusion |
| Object store | MinIO (S3-compatible) |
| Database | Postgres 16 |
| Slide rendering | Presenton (`ghcr.io/presenton/presenton`) |

---

## Quick Start

**Prerequisites**: Docker + Docker Compose + an NVIDIA GPU (for vLLM containers; CPU-only fallback isn't bundled).

### 1. Clone + bootstrap env

```bash
git clone <this-repo>
cd KnowledgeDeckAIPlatform
cp .env.example .env
```

Open `.env` and at minimum set:
- `INITIAL_USER_USERNAME=admin`
- `INITIAL_USER_PASSWORD=<choose-one>`
- `CORS_ORIGINS=http://localhost:3000` (or `http://<your-host>:3000` if accessing remotely)

Defaults work for everything else (Qdrant / MinIO / vLLM / Presenton credentials are local-only).

### 2. Bring up the stack

**Without GPU services** (Postgres / Qdrant / MinIO / Presenton / backend / frontend only — useful for iterating UI, but Chat / RAG / Slides won't work):

```bash
docker compose up postgres qdrant minio presenton backend frontend
```

**Full stack with GPU** (recommended):

```bash
docker compose --profile gpu up -d
```

First run pulls the vLLM image (~9 GB) and downloads three models on first request: Gemma 4 E4B (~8 GB), bge-m3 (~2 GB), bge-reranker-v2-m3 (~570 MB). Subsequent runs are fast.

### 3. Log in

Open http://localhost:3000/login (or `http://<host>:3000/login` for remote access) and authenticate with the credentials from step 1.

To create more users:

```bash
docker compose run --rm backend python -m app.cli create-user <username>
```

### 4. Smoke test

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your-password>"}' \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")

# What model is configured?
curl -s http://localhost:8080/llm/info -H "Authorization: Bearer $TOKEN"

# Health
curl -s http://localhost:8080/ready
```

---

## Configuration

Everything lives in `.env`. Grouped:

### LLM (chat + slide maker share the same model)

| Variable | Default | Notes |
|---|---|---|
| `LLM_BASE_URL` | `http://knowledgedeck_vllm_chat:8000/v1` | OpenAI-compatible endpoint. Anything that serves `/v1/chat/completions` works (vLLM, OpenAI, Together, etc.). |
| `LLM_MODEL` | `google/gemma-4-E4B-it` | Sent in request body — must match the endpoint's served model. |
| `LLM_MODEL_LABEL` | `Gemma 4 E4B` | Display name in Chat / Slide Maker header. Decoupled from `LLM_MODEL`. |
| `LLM_API_KEY` | `local-dev-key` | Bearer key. For local vLLM any non-empty string works. |
| `VLLM_CHAT_GPU_MEMORY_UTILIZATION` | `0.70` | vLLM workspace fraction. Lower = less VRAM, smaller KV cache. |
| `VLLM_CHAT_MAX_MODEL_LEN` | `16384` | Max context tokens. |

**To swap LLM**: edit the four `LLM_*` vars, then `docker compose up -d --build backend`. If you're swapping the bundled vLLM container's model too, also update `docker-compose.yml`'s `vllm_chat` service (`--model` arg + `VLLM_CHAT_*` env). Hard-reload the browser to pick up the new label.

### Embeddings + RAG retrieval

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 1024-d dense embedding model. |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder reranker. |
| `RAG_DENSE_TOP_K` | `20` | How many candidates Qdrant returns before rerank. |
| `RAG_FINAL_TOP_K` | `5` | How many chunks survive into the prompt. |
| `RAG_MIN_SCORE` | `0.30` | Dense cosine threshold (early filter). |
| `RAG_RERANK_MIN_SCORE` | `0.10` | Cross-encoder threshold (post-rerank filter). |

### GPU placement

All three vLLM services default to `GPU_DEVICE=0` (single-GPU mode). To split across GPUs, set per-service overrides — see `.env.example`.

### Other services

`MINIO_*`, `QDRANT_URL`, `PRESENTON_*`, and `DATABASE_URL` all have local-network defaults that work out of the box.

---

## API Summary

All endpoints (except `/health`, `/ready`, `/auth/login`) require `Authorization: Bearer <token>`. Token comes from `POST /auth/login`.

### Auth

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/login` | `{username, password}` → `{token, user}`. |
| `GET` | `/auth/me` | Current user from token. |

### Knowledge Bases & Files

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/knowledge-bases` | List user's KBs. |
| `POST` | `/knowledge-bases` | Create `{name, description?}`. |
| `PATCH` | `/knowledge-bases/{kb_id}` | Rename. |
| `DELETE` | `/knowledge-bases/{kb_id}` | Soft-delete (cascades to files + vectors). |
| `GET` | `/knowledge-bases/{kb_id}/files` | List files in a KB. |
| `POST` | `/knowledge-bases/{kb_id}/files` | Multipart upload. Synchronous: parse + chunk + embed + index inline. Returns `{status: indexed \| failed, ...}`. |
| `DELETE` | `/knowledge-bases/{kb_id}/files/{file_id}` | Soft-delete file + remove vectors. |

Accepted file formats: **txt, pdf, cs, md, docx, pptx**. 50 MB cap. Format is validated by extension + magic bytes (PDF: `%PDF`; OOXML: `PK\x03\x04`; text formats: UTF-8 + null-byte check).

### Chat

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/chat/sessions` | List user's chat sessions. |
| `POST` | `/chat/sessions` | Create empty session. Title auto-derived from first message. |
| `GET` | `/chat/sessions/{session_id}` | Session detail with full message history. |
| `PATCH` | `/chat/sessions/{session_id}` | Rename. |
| `DELETE` | `/chat/sessions/{session_id}` | Soft-delete. |
| `POST` | `/chat/stream` | SSE: `{session_id, message, use_rag, kb_ids}` → token / citations / done events. |

### Slide Maker

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/slide-sessions` | List user's slide decks. |
| `POST` | `/slide-sessions` | Create empty session. |
| `GET` | `/slide-sessions/{id}` | Session detail with messages + render status. |
| `PATCH` | `/slide-sessions/{id}` | Rename. |
| `DELETE` | `/slide-sessions/{id}` | Soft-delete. |
| `POST` | `/slide-sessions/{id}/stream` | SSE planner conversation (same shape as chat stream). The `done` event includes `outline_ready: bool` — when true, the frontend auto-triggers `/render`. |
| `POST` | `/slide-sessions/{id}/render` | Build PPTX via Presenton from the latest `[OUTLINE_READY]` outline. Returns the persisted assistant message containing `[RENDERED:N]` or `[RENDER_FAILED:N]` markers. |
| `GET` | `/slide-sessions/{id}/download` | Stream the rendered .pptx file. |

### LLM Info

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/llm/info` | `{label, model_id}` for the header display. |

### Admin / Maintenance

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/admin/rag-reindex` | Drops the Qdrant collection and re-ingests every non-deleted file from MinIO. Used after RAG-pipeline changes (e.g., schema migrations). Returns `{reindexed, failed, skipped, failed_files[]}`. **Destructive — requires login.** |

### Health

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness. |
| `GET` | `/ready` | Readiness — checks DB + storage. |

---

## Development

### Repo Layout

```
backend/
  app/
    api/            ← FastAPI routers, one file per domain (auth, files, chat, ...)
    services/       ← Business logic (rag, chat_service, slide_chat_service, ingestion, ...)
    db/             ← SQLAlchemy models + Alembic migrations
    core/           ← Settings (Pydantic)
  tests/            ← pytest + testcontainers
  requirements.txt

frontend/
  app/              ← Next.js 15 App Router (routes)
    (protected)/    ← Auth-gated routes (chat, KB, slides, dashboard)
    login/
  components/       ← Reusable UI (ChatInput, DropUpload, AuthGuard, ...)
  lib/              ← API clients + Zustand stores

docker-compose.yml  ← All services (postgres, qdrant, minio, vllm × 3, presenton, backend, frontend)
.env.example        ← Documented config template
docs/superpowers/   ← Design specs and implementation plans
```

### Running Tests

Backend (uses testcontainers for real Postgres + MinIO):

```bash
cd backend
python -m pytest -v
```

Frontend (vitest + tsc):

```bash
cd frontend
npm test
npm run typecheck
```

### Validating compose config without starting anything

```bash
docker compose --env-file .env.example config
```

---

## Branching Workflow

- `main`: stable.
- `dev`: active development.
- Feature work branches from `dev`.
- Don't commit directly to `main` unless explicitly requested.

---

## Secret Safety

Never commit `.env`, API keys, tokens, passwords, private keys, or model credentials. Use `.env.example` with placeholder values only. Pre-commit hooks: TBD.
