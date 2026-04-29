import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.security import decode_token
from db.session import get_db
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decodes the Bearer token from the Authorization header,
    validates it, and returns the matching User from the database.
    Raises 401 if the token is missing, invalid, expired, or the user
    no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)

        if payload.get("type") != "access":
            raise credentials_exception

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user
