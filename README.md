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
