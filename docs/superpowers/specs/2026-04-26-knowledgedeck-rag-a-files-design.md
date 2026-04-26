# KnowledgeDeck RAG Sub-project A — File Upload & Storage

Date: 2026-04-26

## Purpose

Sub-project A delivers the user-facing surface for organizing files into knowledge bases:
create / list / delete a knowledge base, upload / list / delete files within it. Files are
stored verbatim in MinIO with metadata in PostgreSQL. **A does not parse, embed, index, or
queue any background work** — uploaded files sit at `status='uploaded'` and stay there
until Sub-project B introduces the worker. This split keeps the queue / worker / Redis
infrastructure cohesive in B rather than leaving a no-op stub in A.

## Confirmed Decisions

- A is pure CRUD + storage. No Redis, no RQ/Celery, no worker process.
- Knowledge bases are personal-only. Schema does **not** include a `scope` column. When
  Phase 4 adds shared knowledge bases, a single migration will add the column. This
  follows the project rule "don't design for hypothetical future requirements".
- Both knowledge bases and files use soft delete (`deleted_at TIMESTAMPTZ NULL`). MinIO
  objects are not removed on delete; a future cleanup job will reclaim storage. This
  avoids cross-service deletion fragility once B/C/D add Qdrant vectors.
- Single-file upload only (one file per `POST`). Multi-file batch upload is out of scope.
- Duplicate filename within the same knowledge base is **rejected** (409). The user must
  explicitly delete the existing file before re-uploading.
- File size cap: 50 MB single file. No per-KB count cap, no per-user quota.
- Format validation: extension allow-list (`txt`, `pdf`, `cs`) + PDF magic bytes
  (`%PDF-` prefix) + TXT/CS text-likeness check (no NUL byte in first 1 KB and decodable
  as UTF-8). Stricter than extension-only so that B's parsers are not fed garbage.
- Delete URL is nested: `DELETE /knowledge-bases/{id}/files/{file_id}`. The MVP design
  spec's `DELETE /files/{id}` form is superseded — nested is symmetric with POST/GET and
  forces the ownership check through the KB.
- `files.status` enum is defined fully now (`uploaded | parsing | parsed | embedding |
  indexed | failed`) so B/C don't need `ALTER TYPE` migrations.
- MinIO object key layout: `kb/{kb_id}/files/{file_id}/original.{ext}`. B/C/D will add
  sibling artifacts (e.g. `parsed.txt`, `chunks.jsonl`) under the same prefix.
- MinIO client: `minio-py` (official, lightweight). Sync calls wrapped in
  `asyncio.to_thread(...)` to avoid blocking the FastAPI event loop.
- Frontend: two pages — `/knowledge-bases` list and `/knowledge-bases/[id]` detail with
  upload + file list. New "Knowledge Bases" link in the existing protected-shell sidebar.
- Backend tests use **real MinIO** via testcontainers-python (parallel to the existing
  Postgres pattern), not mocks.

## MVP Scope

In:

- `POST /knowledge-bases` — create personal KB.
- `GET /knowledge-bases` — list current user's KBs (with `file_count`).
- `DELETE /knowledge-bases/{id}` — soft-cascade delete KB + its files.
- `POST /knowledge-bases/{id}/files` — single-file multipart upload.
- `GET /knowledge-bases/{id}/files` — list non-deleted files in KB.
- `DELETE /knowledge-bases/{id}/files/{file_id}` — soft-delete single file.
- File format / size / content validation.
- Frontend KB list page, detail page, create dialog, upload card, file list, confirm
  dialogs.

Out (deferred):

- Any parsing, chunking, embedding, indexing — Sub-project B/C.
- Background worker / Redis / RQ — introduced in Sub-project B.
- File download endpoint — added in Sub-project C/D for citation click-through.
- Knowledge base rename (`PATCH /knowledge-bases/{id}`) — Phase 4.
- File reprocess endpoint — added once B/C exist.
- Multi-file batch upload, drag-and-drop, MinIO object cleanup job — Phase 4.
- Pagination on KB list and file list — assumes < 100 KBs / user, < 100 files / KB.
- Shared (admin) KBs — Phase 4.

## Data Model

### Table `knowledge_bases`

| Column          | Type                | Notes                                |
| --------------- | ------------------- | ------------------------------------ |
| `id`            | BIGINT PK           | identity                             |
| `owner_user_id` | BIGINT NOT NULL FK → `users.id`              |
| `name`          | TEXT NOT NULL       | 1–100 chars (enforced API-side)      |
| `description`   | TEXT NULL           | 0–500 chars                          |
| `created_at`    | TIMESTAMPTZ NOT NULL DEFAULT now()           |
| `deleted_at`    | TIMESTAMPTZ NULL    | soft delete sentinel                 |

Indexes:

- `UNIQUE (owner_user_id, name) WHERE deleted_at IS NULL` — partial unique. Allows the
  same owner to recreate a KB with a name they previously soft-deleted.

### Table `files`

| Column              | Type                          | Notes                                       |
| ------------------- | ----------------------------- | ------------------------------------------- |
| `id`                | BIGINT PK                     | identity                                    |
| `knowledge_base_id` | BIGINT NOT NULL FK → `knowledge_bases.id`                                   |
| `owner_user_id`     | BIGINT NOT NULL FK → `users.id` (denormalized for retrieval permission filter in C/D) |
| `filename`          | TEXT NOT NULL                 | original upload filename                    |
| `extension`         | TEXT NOT NULL                 | normalized lowercase: `txt`/`pdf`/`cs`      |
| `size_bytes`        | BIGINT NOT NULL               |                                             |
| `content_sha256`    | TEXT NOT NULL                 | hex digest, used by B for dedupe / retry    |
| `storage_key`       | TEXT NOT NULL                 | MinIO object key                            |
| `status`            | `file_status` NOT NULL DEFAULT `'uploaded'` | enum                          |
| `status_error`      | TEXT NULL                     | populated by B/C/D on `failed`              |
| `created_at`        | TIMESTAMPTZ NOT NULL DEFAULT now()                                          |
| `deleted_at`        | TIMESTAMPTZ NULL              | soft delete                                 |

Indexes:

- `UNIQUE (knowledge_base_id, filename) WHERE deleted_at IS NULL` — enforces
  duplicate-filename rejection.

### Enum `file_status`

`uploaded | parsing | parsed | embedding | indexed | failed`

A only ever writes `uploaded`. The remaining values exist so Sub-projects B and C don't
need `ALTER TYPE` migrations: B will set `parsing` / `parsed` / `failed`, C will set
`embedding` / `indexed` / `failed`.

### Soft-delete cascade

Deleting a KB marks the KB row and every non-deleted child `files` row with
`deleted_at = now()` inside a single transaction. MinIO objects are untouched.

## Storage Layer

- Bucket: value of `MINIO_BUCKET` env (default `knowledgedeck`, already configured).
  Bucket existence is verified / created lazily on first use.
- Object key: `kb/{kb_id}/files/{file_id}/original.{ext}`.
- `extension` is the normalized lowercase suffix (no leading dot).
- B/C/D will write sibling artifacts under the same `kb/{kb_id}/files/{file_id}/` prefix
  (e.g. `parsed.txt`, `chunks.jsonl`).

A new module `app/services/object_storage.py` wraps `minio-py`:

- `MinioClient.put_object(key, data, length, content_type)`
- `MinioClient.delete_object(key)` (unused in A; included for B/C use without API churn)
- `MinioClient.ensure_bucket()` called once at app startup (lifespan).
- All methods are async and internally call `asyncio.to_thread(...)`.

## API

All endpoints require `Authorization: Bearer u_<id>` and resolve the current user via
the existing `get_current_user` dependency. Resources not owned by the current user
return **404** (not 403) to avoid leaking existence.

### `POST /knowledge-bases`

Request:

```json
{ "name": "string (1-100)", "description": "string|null (0-500)" }
```

Response 201:

```json
{ "id": 1, "name": "...", "description": "...", "created_at": "..." }
```

Errors: `409 duplicate_kb_name` if `(owner_user_id, name)` exists among non-deleted rows.

### `GET /knowledge-bases`

Response 200:

```json
[
  {
    "id": 1, "name": "...", "description": "...",
    "file_count": 3,
    "created_at": "..."
  }
]
```

Sort: `created_at DESC`. `file_count` counts non-deleted files in each KB. No pagination.

### `DELETE /knowledge-bases/{id}`

204 on success. 404 if not found or not owned. Soft-cascades KB + child files in one
transaction.

### `POST /knowledge-bases/{id}/files`

`multipart/form-data` with field `file`.

Validation (in order):

1. KB exists, owned by current user, not soft-deleted → else 404 `kb_not_found`.
2. Filename has extension in `{txt, pdf, cs}` (case-insensitive) → else 400
   `invalid_extension`.
3. `Content-Length` header ≤ `52_428_800` (50 MiB). Stream-read also enforces the cap to
   defend against missing / lying headers → else 413 `file_too_large`.
4. While streaming into a temp buffer / spool, compute SHA-256 and total size.
5. Content sniff:
   - `pdf` → first 4 bytes must equal `b"%PDF"`.
   - `txt` / `cs` → first 1 KB must contain no NUL byte AND must decode as UTF-8 strict.
   - Failure → 400 `invalid_content`.
6. Check `(knowledge_base_id, filename)` not present among non-deleted → else 409
   `duplicate_filename`.
7. Insert the `files` row with a placeholder `storage_key` (e.g. empty string),
   `session.flush()` to assign the id without committing, then set
   `storage_key = f"kb/{kb_id}/files/{file_id}/original.{ext}"` on the same row.
8. Upload to MinIO via `MinioClient.put_object(...)`.
9. `session.commit()`.

Atomicity: MinIO PUT failure (or any earlier exception) → SQLAlchemy session rollback,
no orphan row. DB commit failure after a successful MinIO PUT → orphan object (rare;
future cleanup job's responsibility).

Response 201:

```json
{
  "id": 5, "knowledge_base_id": 1,
  "filename": "report.pdf", "extension": "pdf",
  "size_bytes": 12345, "status": "uploaded",
  "created_at": "..."
}
```

### `GET /knowledge-bases/{id}/files`

Response 200:

```json
[
  {
    "id": 5, "filename": "report.pdf", "extension": "pdf",
    "size_bytes": 12345, "status": "uploaded",
    "status_error": null, "created_at": "..."
  }
]
```

Sort: `created_at DESC`. No pagination.

### `DELETE /knowledge-bases/{id}/files/{file_id}`

204 on success. 404 if file is missing, soft-deleted, in a different KB, or KB not owned.
Sets `deleted_at = now()`. MinIO untouched.

### Error response format

Reuses the auth feature's existing shape:

```json
{ "detail": { "code": "duplicate_filename", "message": "..." } }
```

Codes used: `kb_not_found`, `duplicate_kb_name`, `duplicate_filename`,
`invalid_extension`, `invalid_content`, `file_too_large`.

## Frontend

### Routes

Both under the existing `app/(protected)/` group (auth-guarded):

- `app/(protected)/knowledge-bases/page.tsx` — KB list + create dialog + delete confirm.
- `app/(protected)/knowledge-bases/[id]/page.tsx` — single KB: header, upload card, file
  list, delete confirms.

The protected shell sidebar gains a "Knowledge Bases" link above logout.

### Components (`frontend/components/`)

- `KnowledgeBaseList.tsx` — list rendering, "+ New" button, row delete action.
- `KnowledgeBaseCreateDialog.tsx` — `name` (required) + `description` (textarea); shows
  duplicate-name error inline.
- `FileUploadCard.tsx` — `<input type="file" accept=".txt,.pdf,.cs">`, shows selected
  filename + size, Upload button triggers axios POST with `onUploadProgress` driving a
  shadcn `<Progress>` bar; resets on success; surfaces errors via toast.
- `FileList.tsx` — table rows: filename, extension badge, size (human-readable), status
  badge, created_at, delete button. `uploaded` status renders as "Pending processing".
- `ConfirmDeleteDialog.tsx` — wraps shadcn `<AlertDialog>`; reused by KB and file delete.

### API client (`frontend/lib/knowledge-bases.ts`)

```ts
listKnowledgeBases(): Promise<KnowledgeBase[]>
createKnowledgeBase(input): Promise<KnowledgeBase>
deleteKnowledgeBase(id: number): Promise<void>
listFiles(kbId: number): Promise<KnowledgeFile[]>
uploadFile(kbId: number, file: File, onProgress?: (pct: number) => void): Promise<KnowledgeFile>
deleteFile(kbId: number, fileId: number): Promise<void>
```

Reuses `lib/api.ts` axios instance (Bearer auto-attach + 401 redirect already wired).

### Error UX

Backend `detail.code` → English fallback message via an `ERROR_FALLBACKS` map matching
the auth page's pattern:

| code                  | message                                                             |
| --------------------- | ------------------------------------------------------------------- |
| `kb_not_found`        | "Knowledge base not found"                                          |
| `duplicate_kb_name`   | "A knowledge base with this name already exists"                    |
| `duplicate_filename`  | "A file with this name already exists. Delete it first to re-upload." |
| `file_too_large`      | "File exceeds the 50 MB limit"                                      |
| `invalid_extension`   | "Only TXT, PDF, and CS files are supported"                         |
| `invalid_content`     | "File contents do not match the file type"                          |

If the backend supplies a `message`, prefer that; otherwise fall back to the table.

## Testing Strategy

### Backend (`backend/tests/`)

Adds a new fixture `minio_client` using `testcontainers-python`'s MinIO container,
parallel to the existing Postgres fixture. The autouse `_patch_app_storage` fixture
swaps the app's `MinioClient` to point at the testcontainer.

- `test_knowledge_bases.py` — KB CRUD: create / list (with `file_count`) / soft-delete
  cascade (create KB → upload 1 file → delete KB → file is also soft-deleted);
  duplicate-name 409; recreate after soft-delete succeeds; cross-user 404.
- `test_files_upload.py` — happy path; `invalid_extension`; oversized file (size cap);
  PDF without `%PDF-` prefix; TXT with NUL byte; TXT not UTF-8; duplicate filename 409;
  upload to a KB owned by a different user → 404; MinIO PUT failure rolls back the DB
  row (raise inside the patched client and assert no row persists).
- `test_files_list_delete.py` — list excludes soft-deleted; soft-delete returns 204 and
  the file disappears from list; cross-user delete → 404; second delete on already-deleted
  file → 404.

### Frontend

Vitest + React Testing Library + axios-mock-adapter, matching the auth feature setup:

- `KnowledgeBaseList.test.tsx` — empty state, list rendering, "+ New" opens dialog,
  delete confirm flow.
- `KnowledgeBaseCreateDialog.test.tsx` — name-required validation, submit success,
  duplicate-name error rendering.
- `FileUploadCard.test.tsx` — picker reflects selected file, Upload button triggers
  axios call, progress callback updates UI, error surfaces in toast.
- `FileList.test.tsx` — list rendering, status badge mapping, delete confirm flow.
- `lib/knowledge-bases.test.ts` — verifies endpoint URLs and request payloads.

### Manual end-to-end

After Docker compose comes up, the user verifies in a browser at
`http://192.168.1.102:3000`:

1. Login as `admin`.
2. Create a KB, observe it in the list with `file_count = 0`.
3. Upload `sample.pdf` and `sample.cs`; observe progress bar; observe entries with
   status "Pending processing".
4. Delete one file; observe it disappears.
5. Try to upload the same filename again; observe error message.
6. Delete the KB; observe it disappears from the list.
7. (DB inspection) confirm soft-deleted rows still exist with `deleted_at` set.

## Open Items

- Cleanup job to actually remove MinIO objects for soft-deleted files — Phase 4.
- Pagination on KB list and file list — only when usage signals require it.
- Whether `content_sha256` should be exposed via the API — currently internal; B may
  surface it in `GET /files/{id}` once download is implemented.
