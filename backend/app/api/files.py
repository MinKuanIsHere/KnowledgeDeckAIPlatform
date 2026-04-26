import io

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.base import get_db
from app.db.models import FileStatus, KnowledgeBase, KnowledgeFile, User
from app.services import file_service
from app.services.object_storage import get_minio_client

router = APIRouter(prefix="/knowledge-bases", tags=["files"])

# Module-level so tests can monkeypatch a smaller value.
MAX_UPLOAD_BYTES = get_settings().max_upload_bytes


class FileOut(BaseModel):
    id: int
    knowledge_base_id: int
    filename: str
    extension: str
    size_bytes: int
    status: str
    status_error: str | None = None
    created_at: str


def _content_type_for(extension: str) -> str:
    return {
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "cs": "text/x-csharp; charset=utf-8",
    }[extension]


async def _load_owned_kb(
    session: AsyncSession, *, owner_user_id: int, kb_id: int
) -> KnowledgeBase:
    kb = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="kb_not_found")
    return kb


@router.post(
    "/{kb_id}/files", response_model=FileOut, status_code=status.HTTP_201_CREATED
)
async def upload_file(
    kb_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FileOut:
    kb = await _load_owned_kb(session, owner_user_id=user.id, kb_id=kb_id)

    try:
        extension = file_service.validate_extension(file.filename or "")
    except file_service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code)

    try:
        data, sha256, size = await file_service.stream_into_buffer(
            file, MAX_UPLOAD_BYTES
        )
    except file_service.ValidationError as e:
        # `stream_into_buffer` only raises file_too_large.
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=e.code)

    try:
        file_service.validate_content(extension, data[:1024])
    except file_service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code)

    duplicate = await session.scalar(
        select(KnowledgeFile.id).where(
            KnowledgeFile.knowledge_base_id == kb.id,
            KnowledgeFile.filename == file.filename,
            KnowledgeFile.deleted_at.is_(None),
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="duplicate_filename")

    row = KnowledgeFile(
        knowledge_base_id=kb.id,
        owner_user_id=user.id,
        filename=file.filename,
        extension=extension,
        size_bytes=size,
        content_sha256=sha256,
        storage_key="",  # placeholder — updated after we know the id
        status=FileStatus.UPLOADED,
    )
    session.add(row)
    await session.flush()
    row.storage_key = f"kb/{kb.id}/files/{row.id}/original.{extension}"

    try:
        await get_minio_client().put_object(
            row.storage_key,
            io.BytesIO(data),
            size,
            _content_type_for(extension),
        )
    except Exception:
        await session.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="storage_error"
        )

    await session.commit()
    await session.refresh(row)

    return FileOut(
        id=row.id,
        knowledge_base_id=row.knowledge_base_id,
        filename=row.filename,
        extension=row.extension,
        size_bytes=row.size_bytes,
        status=row.status.value,
        status_error=row.status_error,
        created_at=row.created_at.isoformat(),
    )
