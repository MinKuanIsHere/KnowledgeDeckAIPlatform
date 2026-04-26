import re
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User

# Bounded to PostgreSQL BIGINT range (max 9_223_372_036_854_775_807, 19 digits)
# and rejects leading zeros / id=0 so over-long values surface as 401, not 500.
_TOKEN_RE = re.compile(r"^u_([1-9]\d{0,18})$")


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    token = authorization.split(" ", 1)[1]
    match = _TOKEN_RE.match(token)
    if not match:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    user_id = int(match.group(1))
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    return user
