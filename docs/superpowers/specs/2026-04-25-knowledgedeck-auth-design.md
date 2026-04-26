# KnowledgeDeck Auth Design (MVP — Minimal)

Date: 2026-04-25 (revised)

## Purpose

Provide the **bare-minimum login mechanism** needed to identify the current user so downstream MVP features (chat history, personal RAG knowledge base, slide projects) can be scoped per `user_id`. This spec deliberately rejects every security mechanism that is not strictly required to *identify* a user. Phase 4 (Security Hardening) will replace this with hashed passwords, JWT, refresh tokens, audit logs, rate limiting, and API-level admin role enforcement.

This spec supersedes the prior auth design dated 2026-04-25 that called for argon2id, JWT (HS256, 8h TTL), `login_logs` audit table, CITEXT email, timing-attack mitigation, and admin role enforcement. The revised scope below reduces the implementation to roughly 30% of the original surface.

## Confirmed Decisions

- Account creation is admin-only via the CLI. No public registration. The first user is auto-seeded on FastAPI startup from `INITIAL_USER_USERNAME` and `INITIAL_USER_PASSWORD` env vars (idempotent: existing username is not overwritten).
- The user identifier is `username` (plain text, unique). It is **not** an email — no format validation, no uniqueness-via-CITEXT.
- Passwords are stored **as plaintext** in the `users.password` TEXT column. There is no hashing in MVP. This is an explicit, documented MVP risk acceptance for an internal demo platform; production deployments must override this in Phase 4 before any real-user data is loaded.
- Login compares the supplied password to the stored value via direct string equality.
- The session token is the opaque string `u_<user_id>` (e.g., `u_7`). It is sent via `Authorization: Bearer u_<id>`. The token never expires. There is no server-side session store.
- Logout is a pure client-side operation (the frontend clears its local token). There is no `/auth/logout` backend endpoint in MVP.
- The `users` table carries no `is_admin`, no `is_active`, no `last_login_at`, no `created_by`. Just `id`, `username`, `password`, `created_at`. (Add columns in Phase 4 when admin web UI ships.)
- No `login_logs` table, no IP/User-Agent tracking, no rate limiting, no failed-login tracking.
- Frontend stores the token in `localStorage` via Zustand (same pattern previously chosen — unchanged because storage choice is independent of token format).
- Frontend uses axios with a Bearer interceptor + 401 redirect to `/login`, plus a client-side `<AuthGuard>` for protected routes (same pattern previously chosen — unchanged).

## Scope

### In Scope

- `users` table (id, username, password, created_at) and the corresponding Alembic initial migration.
- `POST /auth/login` and `GET /auth/me` endpoints.
- `get_current_user` FastAPI dependency that parses `u_<id>` and loads the user row.
- `python -m app.cli` with one command: `create-user <username> <password>`.
- FastAPI lifespan hook that seeds the first user from env vars.
- Frontend `/login` page (shadcn/ui form), Zustand auth store with `localStorage` persist, axios instance with Bearer + 401 interceptor, `<AuthGuard>` client component for the `(protected)` route group, logout button (pure client-side `clearSession()`).
- Backend and frontend test coverage as defined below.
- Updates to `.env.example` (`INITIAL_USER_USERNAME`, `INITIAL_USER_PASSWORD`) and `docker-compose.yml` (backend entrypoint runs `alembic upgrade head` before uvicorn).

### Out of Scope (Phase 4 Security Hardening, unless noted)

| Item | Deferred to |
|---|---|
| Password hashing (argon2id, bcrypt) | Phase 4 |
| JWT (HS256 or otherwise) | Phase 4 |
| Refresh tokens / token expiry | Phase 4 |
| Token revocation / Redis blocklist | Phase 4 |
| `/auth/logout` backend endpoint | Phase 4 |
| `login_logs` table, IP / User-Agent tracking | Phase 4 |
| Failed-login tracking, rate limiting, account lockout | Phase 4 |
| `is_active` flag (admin disables user) | Phase 4 |
| `is_admin` / role enum at API layer | Phase 4 |
| Admin web UI for user management | Phase 4 |
| Email as identifier; email verification; password reset email | Phase 4+ |
| Multi-factor auth, OAuth/SSO | Phase 5+ |
| Timing-attack mitigation (DUMMY_HASH) | Phase 4 (lands with hashing) |
| i18n architecture (only error code contract is fixed here) | Separate i18n design spec |

## Architecture

### Backend Modules

```
backend/app/
├── core/
│   └── config.py           [modify] Add database_url (already present), initial_user_username, initial_user_password.
│                                    Remove jwt_* fields (none needed in MVP).
├── db/
│   ├── __init__.py         [new] Re-export from base.
│   ├── base.py             [new] DeclarativeBase + lazy async engine + session factory + get_db.
│   ├── models.py           [new] User only.
│   └── migrations/         [new] Alembic config + initial migration.
├── api/
│   ├── auth.py             [new] /auth/login, /auth/me.
│   └── deps.py             [new] get_current_user (parses u_<id>, loads user).
├── services/
│   └── auth_service.py     [new] authenticate(session, username, password) -> User | None
├── cli.py                  [new] Typer: `create-user <username> <password>`.
└── startup.py              [new] FastAPI lifespan: seed initial user from env.
```

### Frontend Modules

```
frontend/
├── lib/
│   ├── api.ts              [new] axios instance + Bearer + 401 redirect.
│   └── auth-store.ts       [new] Zustand + persist(localStorage). Token type is just `string` (the u_<id> value).
├── components/
│   └── AuthGuard.tsx       [new] Calls GET /auth/me on mount; redirects to /login on absent or invalid token.
├── app/
│   ├── login/page.tsx      [new] Username + password form.
│   ├── (protected)/        [new] Route group wrapped in <AuthGuard>.
│   │   ├── layout.tsx      [new]
│   │   └── page.tsx        [moved] Existing chat shell, plus a "Logout" button that calls clearSession().
│   └── layout.tsx          [unchanged]
```

### New Dependencies

**Backend:**
- `sqlalchemy>=2.0`
- `psycopg[binary]>=3.2`
- `alembic>=1.13`
- `typer>=0.12`

(No `argon2-cffi`, no `pyjwt`, no `email-validator`. Removed compared to the prior spec.)

**Frontend:**
- `axios>=1.7`
- `zustand>=5.0`

(Unchanged from prior spec.)

## Data Model

### SQL Schema

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

No CITEXT extension. No enum types. No `login_logs` table. No indexes beyond the `UNIQUE` constraint's implicit btree on `username`.

### ORM Definition

`backend/app/db/models.py` defines only `User` mapping the four columns above. No relationships in MVP (chat sessions, knowledge bases, etc. arrive in their own specs and will reference `User.id`).

### Notes

- Soft delete is not modeled. User deletion in MVP is hard delete via raw SQL or a future admin tool.
- The schema intentionally has room for Phase 4 additions (`password_hash`, `is_admin`, `is_active`, `last_login_at`) without table renames — those will be additive `ALTER TABLE` migrations.

## API Endpoints

### `POST /auth/login`

Public. Accepts JSON `{ "username": "...", "password": "..." }`.

Success (200):

```json
{
  "token": "u_7",
  "user": { "id": 7, "username": "alice" }
}
```

Failure responses:

- `401 invalid_credentials` — username not found or password mismatch (single error code; do not differentiate).
- `422` — pydantic validation error (missing field, empty string).

Side effects: none. No row is written, no log is emitted.

### `GET /auth/me`

Requires `Authorization: Bearer u_<id>`. Returns the current user.

Success (200):

```json
{ "id": 7, "username": "alice", "created_at": "2026-04-25T10:00:00Z" }
```

Failure responses:

- `401 invalid_token` — header absent, malformed (does not match `^u_\d+$`), or the user with that id does not exist.

### Token Format

The token is the literal string `u_` followed by the decimal user id. Example: `u_42`. This is opaque enough to look "tokenish" in transit, while being trivially parseable by `get_current_user`. Anyone who guesses a valid id can impersonate that user — this is a documented MVP risk.

### Auth Dependency

`get_current_user(authorization: Annotated[str | None, Header()] = None, session: AsyncSession = Depends(get_db)) -> User`:

1. If `authorization` missing or does not start with `Bearer u_`, raise `401 invalid_token`.
2. Strip the `Bearer u_` prefix; the remainder must match `\d+`. Otherwise raise `401 invalid_token`.
3. Convert to int, `session.get(User, id)`. If `None`, raise `401 invalid_token`.
4. Return the `User`.

(There is no separate `get_current_admin` in MVP — no API endpoint needs it.)

## CLI Tool

`backend/app/cli.py` is implemented with Typer. Single command:

```bash
python -m app.cli create-user <username> [--password <pwd>]
```

When `--password` is omitted, the CLI prompts interactively (no echo, no shell history). Refuses if `username` already exists.

Phase 4 will add `list-users`, `set-active`, `reset-password`, etc.

## First User Bootstrap

`backend/app/startup.py` registers a FastAPI startup hook (via `lifespan` context manager):

1. Read `INITIAL_USER_USERNAME` and `INITIAL_USER_PASSWORD` from settings.
2. If either is empty, return without action.
3. Open a database session, look up `users` by `username`.
4. If a row exists, log `seed_skipped existing_user=<username>` and return without modification.
5. Otherwise insert the new user with the provided password (verbatim — no hashing) and log `seed_created user=<username>`.

Invariants:

- Idempotent: restarting the container does not duplicate users or change existing passwords.
- Both env vars must be non-empty for seeding to proceed.

`.env.example` adds:

```env
INITIAL_USER_USERNAME=admin
INITIAL_USER_PASSWORD=admin
```

(These plaintext defaults are intentional placeholders for an internal MVP demo. Operators should change them before any non-development use.)

## Database Migrations

Alembic configuration lives at `backend/app/db/migrations/`. The initial migration creates only the `users` table (no extensions, no enums, no `login_logs`). The backend container's entrypoint runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080`.

## Frontend Flow

### Axios Instance and Interceptors (`lib/api.ts`)

The shared `api` axios instance reads `NEXT_PUBLIC_API_BASE_URL`. A request interceptor reads the token from the Zustand store and attaches `Authorization: Bearer <token>`. A response interceptor catches 401, calls `clearSession()`, and routes to `/login` (unless already on `/login`).

### Auth Store (`lib/auth-store.ts`)

Zustand + `persist` middleware backed by `localStorage`. Persisted key `knowledgedeck-auth`. State:

```typescript
type AuthUser = { id: number; username: string };
type AuthState = {
  token: string | null;
  user: AuthUser | null;
  setSession: (token: string, user: AuthUser) => void;
  clearSession: () => void;
};
```

### Login Page (`app/login/page.tsx`)

Client component, shadcn/ui form. Submission posts to `/auth/login`. On success: `setSession(token, user)`, route to `/`. On failure (401): show `auth.error.invalid_credentials` i18n key. On network failure: `auth.error.network`.

### Protected Route Guard

Same client-side pattern as before: protected routes live under `app/(protected)/`, that group's `layout.tsx` wraps children in `<AuthGuard>` which:

1. Reads `token` from Zustand on mount; if absent → `router.replace('/login')`.
2. Calls `GET /auth/me`; on success render children, on failure clear session and redirect.

### Logout

The logout button in the protected layout calls `clearSession()` and routes to `/login`. There is no backend call.

## Error Handling and Error Codes

| Scenario | HTTP | `detail` | Frontend handling |
|---|---|---|---|
| Field validation error | 422 | pydantic default | Show field-level errors |
| Username not found / wrong password | 401 | `invalid_credentials` | `t('auth.error.invalid_credentials')` |
| Token absent / malformed / unknown user | 401 | `invalid_token` | Interceptor clears session, redirects |
| Internal error | 500 | `internal_error` | `t('common.error.internal')` |

Error codes are stable. Frontend i18n key naming lives in the future i18n design spec.

## Security Risk Acknowledgment

This MVP design accepts the following risks **explicitly** and documents the Phase 4 mitigation path:

| Risk | Mitigation Phase |
|---|---|
| Plaintext password storage | Phase 4 — argon2id hashing + migration that reads existing rows and re-hashes |
| Predictable opaque token (`u_<id>`) | Phase 4 — JWT with HS256, signed with `JWT_SECRET_KEY` |
| No token expiry | Phase 4 — 8h access token + refresh flow |
| No login audit | Phase 4 — `login_logs` table + IP/UA capture |
| No rate limiting | Phase 4 — reverse-proxy or in-app limiter |
| No admin role enforcement at API | Phase 4 — `is_admin` column + `get_current_admin` dependency |
| Logout has no server effect | Phase 4 — token revocation list |

Operators deploying this MVP outside an internal trusted network must complete Phase 4 first.

## Testing Strategy

### Backend (`pytest` + `pytest-asyncio`, asyncio_mode=auto)

- `tests/test_auth_service.py` — `authenticate` returns `User` on match, `None` on wrong password, `None` on unknown username; case-sensitive comparison.
- `tests/test_deps.py` — `get_current_user` rejects missing/wrong-scheme/malformed/unknown-id tokens; succeeds for `u_<existing_id>`.
- `tests/test_auth_login.py` — successful login returns 200 with `token == "u_<id>"` and user object; wrong password → 401 `invalid_credentials`; unknown username → 401 `invalid_credentials`; missing field → 422.
- `tests/test_auth_me.py` — valid token → 200 with user fields; missing/malformed/unknown-id → 401 `invalid_token`.
- `tests/test_seed_user.py` — both env vars set + username absent → user created; username already exists → no change; either env var empty → no action.
- `tests/test_cli.py` — `create-user` happy path; rejects existing username.

Tests run against a real PostgreSQL instance via `testcontainers-python` (same pattern as established by Tasks 1-3 prior; the conftest from those tasks is preserved).

### Frontend (`vitest` + React Testing Library)

- `lib/auth-store.test.ts` — `setSession` / `clearSession` / `localStorage` persist round-trip.
- `lib/api.test.ts` — Bearer header attachment when token present; 401 clears session and redirects (unless already on `/login`).
- `components/AuthGuard.test.tsx` — redirects to `/login` when no token; renders children after `/auth/me` succeeds; clears + redirects when `/auth/me` returns 401.
- `app/login/page.test.tsx` — submits credentials, stores session, navigates on success; surfaces `auth.error.invalid_credentials` on 401.

### End-to-End Smoke Test

Documented in README:

1. `docker compose up postgres backend` — Alembic migrates and seed runs.
2. `curl -X POST http://localhost:8080/auth/login -d '{"username":"admin","password":"admin"}' -H "Content-Type: application/json"` — returns `{"token": "u_1", "user": {"id": 1, "username": "admin"}}`.
3. `curl http://localhost:8080/auth/me -H "Authorization: Bearer u_1"` — returns the user.
4. Wrong password → 401 `invalid_credentials`.
5. `Bearer u_999` (nonexistent) → 401 `invalid_token`.

## Open Items

- i18n architecture (library, language detection, switcher UI) is owned by a separate i18n design spec. Only error code keys are fixed here.
- Typer can be swapped for stdlib argparse if its dependency footprint is unwanted; the command surface stays the same.
- testcontainers PostgreSQL pulls a Docker image during test runs; if CI cannot run Docker-in-Docker, fall back to `pytest-postgresql` per the conftest pattern.
