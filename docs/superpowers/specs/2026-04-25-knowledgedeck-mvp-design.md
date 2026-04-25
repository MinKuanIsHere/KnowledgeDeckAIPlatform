# KnowledgeDeck MVP Design

Date: 2026-04-25

## Purpose

KnowledgeDeck is an internal AI platform for chat, personal RAG knowledge bases, citation-based answers, and editable PPTX generation. The MVP should prove the core workflow end to end before adding advanced admin, template parsing, preview, reranking, and monitoring features.

## Confirmed Decisions

- Authentication uses JWT.
- Frontend uses Next.js, React, TypeScript, Tailwind CSS, and shadcn/ui.
- UI direction follows Open WebUI and Perplexity: compact, chat-first, clean retrieval-oriented screens.
- Backend uses FastAPI.
- Background jobs handle document processing, embedding, and PPTX generation.
- LLM and embedding access must use OpenAI-compatible endpoints.
- Default chat model is `google/gemma-4-E4B-it`.
- Default embedding model is `BAAI/bge-m3`.
- Default local serving uses vLLM.
- Docker Compose includes two vLLM services: one for chat and one for embeddings.
- MVP deployment target is one RTX 4090 24GB GPU, even though the machine has four GPUs.
- All Docker container names use the `knowledgedeck_*` prefix.

## MVP Scope

The MVP includes:

- Login and logout.
- JWT-protected API access.
- Streaming LLM chat.
- Conversation history.
- File upload for PDF, PPTX, and DOCX.
- Document parsing, chunking, embedding, and indexing.
- Personal RAG knowledge base.
- RAG answer generation with citations.
- Citation metadata containing file, chunk, and page or slide number.
- PPTX generation and download.
- Basic RAG management UI.
- Docker Compose deployment.

The MVP excludes:

- Shared admin knowledge bases.
- Fine-grained role and group permissions.
- Hybrid retrieval.
- Reranking.
- Online slide editing.
- Complex PPTX template parsing.
- Citation click-through preview.
- Usage analytics and monitoring dashboards.

## Architecture

The platform is split into these services:

- `knowledgedeck_frontend`: Next.js web UI.
- `knowledgedeck_backend`: FastAPI REST and streaming API.
- `knowledgedeck_worker`: background jobs for document processing and slide generation.
- `knowledgedeck_postgres`: relational metadata store.
- `knowledgedeck_redis`: task queue and cache.
- `knowledgedeck_qdrant`: vector database.
- `knowledgedeck_minio`: object storage for uploads, parsed artifacts, templates, and generated PPTX files.
- `knowledgedeck_vllm_chat`: OpenAI-compatible vLLM chat endpoint.
- `knowledgedeck_vllm_embedding`: OpenAI-compatible vLLM embedding endpoint.

Backend code must depend on internal client abstractions, not directly on vLLM. The two required clients are:

- `ChatModelClient`: calls `/v1/chat/completions` and supports streaming.
- `EmbeddingClient`: calls `/v1/embeddings`.

Both clients read base URL, API key, and model name from environment variables.

## Model Endpoint Configuration

Default `.env` values:

```env
GPU_DEVICE=0

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

The default uses `GPU_DEVICE=0` so both vLLM containers run on a single RTX 4090. The chat context is intentionally limited to 16K tokens. RAG prompts must be compact and should use selected chunks rather than relying on the model's full 128K context window.

If startup fails due to GPU memory pressure, use this fallback:

```env
VLLM_CHAT_GPU_MEMORY_UTILIZATION=0.65
VLLM_CHAT_MAX_MODEL_LEN=8192
VLLM_EMBEDDING_GPU_MEMORY_UTILIZATION=0.18
```

Future deployment may add a `gpu-split` Compose profile that runs chat on GPU 0 and embeddings on GPU 1.

## RAG Flow

Upload flow:

1. User uploads a supported file.
2. Backend stores the original file in MinIO.
3. Backend creates file metadata in PostgreSQL.
4. Backend queues a worker job.
5. Worker parses the document.
6. Worker extracts text plus page or slide metadata where available.
7. Worker chunks the document.
8. Worker calls `EmbeddingClient`.
9. Worker stores vectors and payload metadata in Qdrant.
10. Worker updates processing status in PostgreSQL.

Question flow:

1. User submits a chat message with RAG enabled.
2. Backend embeds the query using `EmbeddingClient`.
3. Backend retrieves top-k chunks from Qdrant with user isolation filters.
4. Backend builds a compact context block with citation metadata.
5. Backend streams the answer through `ChatModelClient`.
6. Backend stores the chat messages and returned citation list.

Citation metadata must include:

- `file_id`
- `file_name`
- `file_type`
- `chunk_id`
- `page_number` when available
- `slide_number` when available
- `chunk_index`
- `text_excerpt`

## PPTX Generation

The LLM does not directly produce a PPTX file. It produces structured slide JSON, and the worker renders the file.

Generation flow:

1. User describes the requested presentation.
2. Backend optionally retrieves RAG context.
3. LLM generates an outline.
4. User confirms or edits the outline.
5. LLM generates slide JSON.
6. Worker renders editable PPTX.
7. Generated PPTX is stored in MinIO.
8. Metadata and version records are stored in PostgreSQL.
9. User downloads the PPTX.

MVP rendering should support:

- Editable titles and text boxes.
- Bullet lists.
- Simple tables.
- Basic layouts.
- Citation notes or references.

Complex PPTX template parsing is postponed. Slide JSON should remain renderer-neutral so the project can start with `python-pptx` and later add a JavaScript `pptxgenjs` renderer if needed.

## Data Isolation

All user-owned records must include `user_id`. RAG retrieval must apply user filters before returning chunks. Admin shared knowledge bases are out of MVP scope, but the schema should leave room for `knowledge_base.scope` values such as `personal` and `shared`.

## API Surface

MVP APIs:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /chat/stream`
- `GET /chat/sessions`
- `GET /chat/sessions/{id}`
- `DELETE /chat/sessions/{id}`
- `POST /knowledge-bases`
- `GET /knowledge-bases`
- `POST /knowledge-bases/{id}/files`
- `GET /knowledge-bases/{id}/files`
- `DELETE /files/{id}`
- `POST /rag/query`
- `POST /slides/projects`
- `POST /slides/generate`
- `GET /slides/projects`
- `GET /slides/projects/{id}`
- `GET /slides/projects/{id}/download`

## Error Handling

- Streaming chat errors must return a visible terminal error event to the frontend.
- File processing failures must update file status with a readable reason.
- Embedding failures must keep the original file and allow retry.
- PPTX generation failures must preserve the slide project request and mark the failed version.
- vLLM endpoint failures must be surfaced as model service unavailable errors.

## Testing Strategy

Backend tests should cover:

- JWT auth and protected routes.
- OpenAI-compatible chat and embedding client request formatting.
- Document chunk metadata creation.
- RAG retrieval permission filtering.
- Citation serialization.
- Slide JSON validation.
- PPTX renderer smoke test.

Frontend tests should cover:

- Login flow.
- Streaming chat rendering.
- RAG toggle and knowledge base selector.
- File upload state display.
- Citation display.
- PPTX generation request and download action.

Integration tests should use mocked model endpoints first. Real vLLM smoke tests can be added separately because they require GPU resources.

## Open Items

- Exact database schema will be defined in the implementation plan.
- Exact document parser libraries will be selected during scaffold design.
- PPTX renderer starts with `python-pptx` unless implementation findings show a blocker.
- Multi-GPU `gpu-split` Compose profile is deferred until the single-GPU MVP is working.
