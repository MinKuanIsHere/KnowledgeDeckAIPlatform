# KnowledgeDeck Auth Design

Date: 2026-04-25

## Purpose

Define the authentication and account management foundation for KnowledgeDeck Phase 1. All other MVP features (personal RAG, chat history, slide generation) depend on `user_id` for data isolation, so auth must land before those features. This spec covers user accounts, password handling, JWT issuance, login/logout audit, and CLI-based admin tooling. It excludes self-signup, password reset email flows, refresh tokens, token revocation, and admin web UI — those are deferred to later phases.

## Confirmed Decisions

- Account creation is admin-only. There is no public registration endpoint. The first admin account is auto-seeded on FastAPI startup from `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` environment variables (idempotent: existing emails are not overwritten).
- Authentication uses stateless JWT with HS256 signing.
- Access tokens have an 8-hour TTL (480 minutes). There is no refresh token, no sliding expiry, and no server-side revocation list.
- Email is the unique user identifier. Stored as `CITEXT` for case-insensitive comparison.
- Logout is record-only (writes `logout_at` to the latest open `login_logs` row). The token remains valid until expiry; this is an accepted MVP limitation given the 8-hour TTL.
- Admin user creation in MVP is CLI-only (`python -m app.cli`). Admin web UI is deferred to Phase 4.
- The frontend stores the JWT in `localStorage`. Bearer header is attached via an axios request interceptor. The frontend uses Zustand for the auth store.
- Passwords are hashed with argon2id via `argon2-cffi`.
- `login_logs` only records successful logins (with `logout_at` updated on logout). Failed login attempts and rate limiting are out of MVP scope.
- Roles are modeled as a single `user_role` enum column (`user` / `admin`) on the `users` table. A separate `roles` / `user_roles` table is deferred to Phase 5 group permissions.

## Scope

### In Scope

- `users` and `login_logs` PostgreSQL tables, including Alembic initial migration.
- Argon2id password hashing and verification.
- JWT encode/decode with HS256.
- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` endpoints.
- `get_current_user` and `get_current_admin` FastAPI dependencies.
- `python -m app.cli` commands: `create-user`, `list-users`, `set-active`, `reset-password`.
- FastAPI startup hook that seeds the first admin from environment variables.
- Frontend `/login` page (shadcn/ui form), Zustand auth store with `localStorage` persistence, axios interceptor (Bearer attach + 401 redirect), and a client-side `<AuthGuard>` wrapper for protected routes.
- Backend and frontend test coverage as defined in the testing section.
- Updates to `.env.example` and `docker-compose.yml` (entrypoint runs `alembic upgrade head` before uvicorn).

### Out of Scope

| Item | Deferred to |
|---|---|
| Self-registration / `/auth/register` | Not in MVP |
| Email verification / activation emails | Not in MVP |
| Password reset email flow | Phase 4 (CLI `reset-password` covers admin needs) |
| Refresh tokens / automatic renewal | Phase 5 security hardening |
| Token revocation / Redis blocklist | Phase 5 |
| Login failure rate limit / account lockout | Phase 4 security hardening (short term: reverse proxy) |
| Multi-factor authentication (TOTP, email OTP) | Phase 5+ |
| OAuth / SSO (Google, Microsoft, SAML) | Phase 5+ |
| Multi-device session management UI | Phase 4 |
| Fine-grained permissions (`roles`, `user_roles`, `permissions` tables) | Phase 5 |
| Teams / organizations | Phase 5 |
| Admin user management web UI | Phase 4 |
| Password strength rules | Phase 4 (CLI prints a warning earlier) |
| Full audit log of all auth events beyond login/logout | Phase 4 |
| i18n architecture decisions and language switcher UI | Separate i18n design spec |

## Architecture

### Backend Modules

```
backend/app/
├── core/
│   ├── config.py           [modify] Add jwt_access_token_minutes default 480;
│   │                                add initial_admin_email / initial_admin_password
│   └── security.py         [new] argon2 hash/verify; JWT encode/decode
├── db/
│   ├── __init__.py         [new]
│   ├── base.py             [new] SQLAlchemy declarative base, async engine, session factory
│   ├── models.py           [new] User, LoginLog
│   └── migrations/         [new] Alembic env.py + versions/
├── api/
│   ├── auth.py             [new] /auth/login, /auth/logout, /auth/me
│   └── deps.py             [new] get_current_user, get_current_admin
├── services/
│   └── auth_service.py     [new] authenticate, open_login_log, close_login_log
├── cli.py                  [new] Typer CLI: create-user, list-users, set-active, reset-password
└── startup.py              [new] FastAPI startup hook: seed initial admin from env
```

### Frontend Modules

```
frontend/
├── lib/
│   ├── api.ts              [new] axios instance, Bearer interceptor, 401 handler
│   └── auth-store.ts       [new] Zustand store with persist middleware (localStorage)
├── components/
│   └── AuthGuard.tsx       [new] Client component, redirects to /login when no token
├── app/
│   ├── login/page.tsx      [new] Login form
│   ├── (protected)/        [new] Route group wrapped in AuthGuard
│   │   └── layout.tsx      [new] Wraps children in AuthGuard
│   └── layout.tsx          [modify] Add Zustand provider boundary if needed
```

### New Dependencies

**Backend:**
- `sqlalchemy>=2.0`
- `psycopg[binary]>=3.2` (async PostgreSQL driver)
- `alembic>=1.13`
- `argon2-cffi>=23.1`
- `pyjwt>=2.9`
- `email-validator>=2.2`
- `typer>=0.12`

**Frontend:**
- `axios>=1.7`
- `zustand>=5.0`

## Data Model

### SQL Schema

```sql
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TYPE user_role AS ENUM ('user', 'admin');

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           CITEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    role            user_role NOT NULL DEFAULT 'user',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);

CREATE TABLE login_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    login_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    logout_at       TIMESTAMPTZ NULL,
    ip_address      INET NOT NULL,
    user_agent      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_login_logs_user_login ON login_logs(user_id, login_at DESC);
CREATE INDEX idx_login_logs_open_session ON login_logs(user_id) WHERE logout_at IS NULL;
```

### ORM Definitions

`backend/app/db/models.py` defines:

- `UserRole` enum (`user`, `admin`).
- `User` mapped class for the `users` table.
- `LoginLog` mapped class for the `login_logs` table.

Field types use SQLAlchemy 2.0 typed `Mapped[...]` syntax. `User.email` uses the `CITEXT` type via `sqlalchemy.dialects.postgresql.CITEXT`. `LoginLog.ip_address` uses `sqlalchemy.dialects.postgresql.INET`.

### Design Notes

- `is_active=false` users cannot log in (returns 403 `account_disabled`). Tokens issued before deactivation remain valid until expiry; this matches the stateless JWT model.
- Soft delete (`deleted_at`) is intentionally omitted. MVP uses `is_active=false` for "disabled" and never hard deletes.
- `users.email` uses `CITEXT` so login does not need application-level lowercasing. The initial migration must `CREATE EXTENSION citext`.

## API Endpoints

### `POST /auth/login`

Public. Accepts JSON `{ "email": "...", "password": "..." }`.

Success (200):

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": { "id": 7, "email": "user@example.com", "role": "user" }
}
```

Side effect: insert one row into `login_logs` with the request's IP and `User-Agent`.

Failure responses:

- `401 invalid_credentials` — email not found or password mismatch.
- `403 account_disabled` — user found but `is_active = false`.
- `422` — pydantic validation error (missing field, invalid email format).

### `POST /auth/logout`

Requires `Authorization: Bearer <token>`. No request body.

Success (204): empty body. Side effect: update the most recent `login_logs` row for this user where `logout_at IS NULL`, setting `logout_at = now()`. If multiple open rows exist (multi-device), only the most recent by `login_at` is closed.

Failure: `401 invalid_token` for missing, malformed, expired, or signature-invalid tokens. Expired tokens are not exempted — frontend interceptors will route the user back to login.

### `GET /auth/me`

Requires `Authorization: Bearer <token>`. Returns the current user.

Success (200):

```json
{
  "id": 7,
  "email": "user@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2026-04-25T10:00:00Z"
}
```

Failure responses:

- `401 invalid_token` — token missing/expired/invalid signature.
- `401 user_not_found` — token decodes successfully but `users.id` no longer exists (defensive case; not expected in MVP).
- `403 account_disabled` — token valid but user has been deactivated.

### JWT Payload

```json
{
  "sub": "7",
  "email": "user@example.com",
  "role": "user",
  "iat": 1745568000,
  "exp": 1745596800
}
```

`sub` is the stringified `user.id`. `role` is included for fast admin-route gating, but `get_current_admin` still re-queries the database to confirm `is_active` and current role.

### Auth Dependencies

`get_current_user(authorization: str = Header(...)) -> User` resolves the bearer token, decodes the JWT, loads the user from PostgreSQL, and verifies `is_active`. Raises `HTTPException` for each failure code above.

`get_current_admin(user: User = Depends(get_current_user)) -> User` raises `403 admin_required` when `user.role != UserRole.ADMIN`.

All future protected endpoints (chat, knowledge bases, slides) will declare `current_user: User = Depends(get_current_user)`.

## CLI Tool

`backend/app/cli.py` is implemented with Typer. Invoked as `python -m app.cli <command>`.

```bash
python -m app.cli create-user user@example.com [--password <pwd>] [--admin]
python -m app.cli list-users
python -m app.cli set-active user@example.com [--inactive]
python -m app.cli reset-password user@example.com [--password <pwd>]
```

When `--password` is omitted, the CLI prompts interactively (input is not echoed and is not retained in shell history). The CLI prints a warning when the chosen password is shorter than 8 characters but does not refuse the operation.

`list-users` prints `id, email, role, is_active, created_at`.

`set-active` defaults to enabling. `--inactive` disables.

## First Admin Bootstrap

`backend/app/startup.py` registers a FastAPI startup hook:

1. Read `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` from settings.
2. If either is unset or empty, return without action.
3. Open a database session, look up `users` by `email = INITIAL_ADMIN_EMAIL`.
4. If a row exists, log `seed_skipped existing_admin=<email>` and return without modification.
5. Otherwise, insert a new user with `role = admin`, `is_active = true`, and the argon2id hash of `INITIAL_ADMIN_PASSWORD`.
6. Log `seed_created admin=<email>`.

Invariants:

- Idempotent: restarting the container does not duplicate users or change existing passwords.
- Both env vars must be present for seeding to proceed; this prevents accidental seeding in CI or staging when only one variable is set.
- Operators are expected to rotate the initial password via `python -m app.cli reset-password` after first login and to clear the env vars on subsequent deployments.

`.env.example` adds:

```env
INITIAL_ADMIN_EMAIL=admin@knowledgedeck.local
INITIAL_ADMIN_PASSWORD=change-me-on-first-deploy
```

## Database Migrations

Alembic configuration lives at `backend/app/db/migrations/`. The initial migration:

1. `CREATE EXTENSION IF NOT EXISTS citext`.
2. Create `user_role` enum.
3. Create `users` table with all columns and indexes.
4. Create `login_logs` table with all columns and indexes.

The backend container's entrypoint runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080`. The worker container does not run migrations; it depends on the backend service to have completed startup.

## Frontend Flow

### Axios Instance and Interceptors (`lib/api.ts`)

The shared `api` axios instance reads `NEXT_PUBLIC_API_BASE_URL`. A request interceptor reads the current token from the Zustand store and attaches `Authorization: Bearer <token>`. A response interceptor catches 401 responses, calls `clearSession()`, and redirects the browser to `/login` (unless already on `/login`).

### Auth Store (`lib/auth-store.ts`)

Implemented with Zustand plus the `persist` middleware backed by `localStorage`. The store holds `token: string | null` and `user: User | null`. It exposes `setSession(token, user)` and `clearSession()`. The persisted key is `knowledgedeck-auth`.

### Login Page (`app/login/page.tsx`)

Client component. Renders an email + password form built with shadcn/ui (`Form`, `Input`, `Button`). Submission posts to `/auth/login`. On success, calls `setSession(access_token, user)` and routes to `/`. On failure, maps the response `detail` to an i18n message key:

- `invalid_credentials` → `auth.error.invalid_credentials`
- `account_disabled` → `auth.error.account_disabled`
- network or other → `auth.error.network`

The form does not surface whether the email exists; the same message is used for "email not found" and "wrong password".

### Protected Route Guard

Because the JWT lives in `localStorage`, Next.js middleware running on the server cannot see it. Server-side guards are not viable for this storage choice. Instead, protected routes live under `app/(protected)/` and that group's `layout.tsx` wraps children in a client `<AuthGuard>` component:

1. On mount, read `token` from the Zustand store.
2. If absent, `router.replace('/login')` and render `null`.
3. If present, call `GET /auth/me` once. On success, render children. On failure, `clearSession()` and redirect.

This means a first-render flash on protected pages is expected before the redirect or content shows; this is an accepted MVP trade-off for the localStorage strategy.

### Logout Flow

User clicks logout → `POST /auth/logout` (success or failure both proceed) → `clearSession()` → `router.push('/login')`.

## Error Handling and Error Codes

The backend returns machine-readable error codes (not human strings). The frontend maps codes to localized text via i18n keys.

| Scenario | HTTP | `detail` | Frontend handling |
|---|---|---|---|
| Field validation error | 422 | pydantic default | Show field-level errors |
| Email not found / wrong password | 401 | `invalid_credentials` | `t('auth.error.invalid_credentials')` |
| User disabled | 403 | `account_disabled` | `t('auth.error.account_disabled')` |
| Token missing/expired/invalid | 401 | `invalid_token` | Interceptor clears session and routes to /login |
| User deleted (defensive) | 401 | `user_not_found` | Interceptor clears session and routes to /login |
| Non-admin on admin endpoint | 403 | `admin_required` | `t('auth.error.admin_required')` |
| Internal server error | 500 | `internal_error` | `t('common.error.internal')` |

A FastAPI `app.exception_handler` centralizes the response shape. Stack traces are never exposed to clients.

The set of error codes above forms a stable contract. Frontend i18n keys are owned by the future i18n design spec; the backend will not return human-readable error text.

## Security Invariants

1. **Timing-attack mitigation in login:** when the supplied email does not exist, the login handler still executes argon2 verification against a fixed dummy hash so total response time is comparable to a real password mismatch.
2. **JWT secret:** production deployments must override `JWT_SECRET_KEY`. The `Settings` model already enforces `min_length=8`. Operators are advised to use at least 32 random bytes (e.g., `openssl rand -hex 32`).
3. **Password strength:** MVP does not enforce a minimum length. The CLI prints a warning for passwords shorter than 8 characters. Phase 4 will introduce enforced rules.
4. **HTTPS:** Docker Compose does not include TLS. Production deployments terminate TLS at a reverse proxy (nginx, Caddy, etc.). README documents this expectation.
5. **CORS:** the backend permits the configured `NEXT_PUBLIC_APP_URL` origin, with `allow_credentials=False` (no cookies are used), `allow_methods=["*"]`, `allow_headers=["Authorization", "Content-Type"]`.
6. **Brute-force resistance:** MVP does not implement rate limiting. Operators rely on the reverse proxy's rate-limit module until Phase 4 adds in-app limits.
7. **Token contents:** never include sensitive data in JWT claims. Only `sub`, `email`, `role`, `iat`, `exp` are emitted.
8. **Argon2 parameters:** start with `argon2-cffi` defaults (memory_cost 65536 KiB, time_cost 3, parallelism 4). Re-tune in Phase 4 if profiling on the deployment hardware indicates verification time outside the 100–500 ms range.

## Testing Strategy

### Backend (`pytest` + `pytest-asyncio`)

- `tests/test_security.py` — argon2 hash/verify round-trip; verify rejects wrong password; JWT encode then decode returns the same claims; expired JWT raises; tampered signature raises.
- `tests/test_auth_login.py` — successful login returns 200 with token and writes a `login_logs` row; wrong password returns 401 `invalid_credentials`; non-existent email returns 401 `invalid_credentials` and still takes comparable time (assert via call to `argon2.verify` with dummy hash, mocked); inactive user returns 403 `account_disabled`; email is case-insensitive (`User@Example.com` and `user@example.com` map to the same row).
- `tests/test_auth_logout.py` — logout returns 204 and updates `logout_at` on the most recent open row; logout with multiple open rows only closes the most recent; logout with no open row is a no-op (still 204); expired token returns 401 `invalid_token`.
- `tests/test_auth_me.py` — valid token returns 200 with current user fields; expired token returns 401; deactivated user returns 403; unknown `sub` returns 401 `user_not_found`.
- `tests/test_deps.py` — `get_current_user` rejects missing header, wrong scheme, malformed token, expired token, deactivated user; `get_current_admin` rejects user role.
- `tests/test_seed_admin.py` — both env vars set and email absent → user created with admin role; email already exists → no change; only one env var set → no action; both empty strings → no action.
- `tests/test_cli.py` — `create-user` with explicit password; `create-user` with `--admin`; `list-users`; `set-active --inactive` then back to active; `reset-password` updates hash and verifies with new password.

Tests run against a real PostgreSQL instance via `testcontainers-python` so `CITEXT`, `INET`, and the `user_role` enum behave identically to production.

### Frontend (`vitest` + React Testing Library)

- `lib/auth-store.test.ts` — `setSession` and `clearSession` update state; persistence reads back from `localStorage`.
- `lib/api.test.ts` — interceptor attaches `Authorization` header when token is present; 401 response triggers `clearSession()` and a redirect (mock `window.location`).
- `app/login/page.test.tsx` — submitting valid credentials calls the API, calls `setSession`, and navigates; failure response shows the corresponding i18n key (assert on the key passed to `t()`).
- `components/AuthGuard.test.tsx` — renders nothing and redirects when no token; renders children after `GET /auth/me` succeeds; clears session and redirects when `GET /auth/me` returns 401.

### End-to-End Smoke Test

A scripted manual verification documented in the README:

1. `docker compose up postgres backend` — Alembic migrates and seed runs.
2. `curl -X POST http://localhost:8080/auth/login -d '{"email":"$INITIAL_ADMIN_EMAIL","password":"$INITIAL_ADMIN_PASSWORD"}'` — returns a token.
3. `curl http://localhost:8080/auth/me -H "Authorization: Bearer $TOKEN"` — returns admin user.
4. `curl -X POST http://localhost:8080/auth/logout -H "Authorization: Bearer $TOKEN"` — returns 204; `logout_at` populated in `login_logs`.
5. The same token still works on `/auth/me` (expected behavior; logout is record-only).
6. After expiry (or with `JWT_ACCESS_TOKEN_MINUTES=1` for fast verification), `/auth/me` returns 401.

## Open Items

- i18n architecture (library choice, language detection, switcher UI, key naming) is owned by a forthcoming i18n design spec. This auth spec only fixes the error code contract.
- Argon2 parameters are inherited from `argon2-cffi` defaults; re-tune in Phase 4 once profiling on the deployment hardware confirms verification time.
- The CLI uses Typer; if Typer is rejected during implementation review, fall back to FastAPI's bundled `argparse`-style approach without changing the command surface.
- Testcontainers PostgreSQL pulls a Docker image during test runs; if the CI environment does not allow Docker-in-Docker, fall back to a session-scoped local Postgres fixture managed via `pytest-postgresql`.
