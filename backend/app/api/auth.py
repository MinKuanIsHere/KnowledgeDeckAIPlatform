from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.db.models import User
from app.services.auth_service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserSummary(BaseModel):
    id: int
    username: str


class LoginResponse(BaseModel):
    token: str
    user: UserSummary


class MeResponse(BaseModel):
    id: int
    username: str
    created_at: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> LoginResponse:
    user = await authenticate(session, body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    return LoginResponse(
        token=f"u_{user.id}",
        user=UserSummary(id=user.id, username=user.username),
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at.isoformat(),
    )
