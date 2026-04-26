# KnowledgeDeck AI Platform

KnowledgeDeck is an internal AI platform for LLM chat, personal RAG knowledge bases, citation-based answers, and editable PPTX generation.

## Branches

- `main`: stable branch.
- `dev`: active development branch.
- Feature branches should branch from `dev`.

## Local Setup

**First, copy the example environment file** — every Docker Compose command below requires `.env` to exist (the `backend` and `worker` services declare `env_file: - .env`):

```bash
cp .env.example .env
```

Edit `.env` to set your `INITIAL_USER_USERNAME` / `INITIAL_USER_PASSWORD` (these seed the first admin user on `docker compose up`; defaults are `admin` / `admin` for local dev).

Run backend tests (uses testcontainers — requires a running Docker daemon):

```bash
cd backend
python -m pytest -v
```

Run frontend tests + typecheck (Node 18.18+ required for Next 15):

```bash
cd frontend
npm test
npm run typecheck
```

Validate Docker Compose configuration (requires the `cp` step above):

```bash
docker compose --env-file .env.example config
```

Start non-GPU infrastructure:

```bash
docker compose up postgres redis qdrant minio backend frontend
```

Start with GPU model services:

```bash
docker compose --profile gpu up
```

After containers are up, log in at http://localhost:3000/login with the credentials you set in `INITIAL_USER_*`. To add more users, run:

```bash
docker compose run --rm backend python -m app.cli create-user <username>
```

## Secret Safety

Never commit `.env`, API keys, tokens, passwords, private keys, or model credentials. Use `.env.example` with placeholder values only.
