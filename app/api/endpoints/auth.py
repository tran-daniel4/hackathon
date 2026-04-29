import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis import get_redis
from core.deps import get_current_user
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from db.session import get_db
from models.user import User
from schemas.auth import (
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Redis key prefix for blocklisted refresh token JTIs
_BLOCKLIST_PREFIX = "refresh_blocklist:"


def _blocklist_key(jti: str) -> str:
    return f"{_BLOCKLIST_PREFIX}{jti}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a new user account and return a token pair."""
    # 1. Check email not already taken
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # 2. Hash password and insert user
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 3. Issue token pair
    user_id = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password using the OAuth2 password flow.
    The 'username' field in the form is treated as the email address.
    """
    # 1. Look up user by email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    # 2. Verify password — same error for missing user or wrong password to prevent enumeration
    if user is None or not verify_password(form_data.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Issue token pair
    user_id = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    redis: Redis = Depends(get_redis),
) -> None:
    """
    Invalidate a refresh token by adding its JTI to the Redis blocklist.
    The TTL is set to match the token's remaining lifetime.
    """
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        # Token is already invalid — treat as success
        return

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a refresh token")

    jti: str = payload["jti"]
    exp: int = payload["exp"]
    now = int(__import__("time").time())
    ttl = max(exp - now, 1)

    await redis.setex(_blocklist_key(jti), ttl, "1")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is immediately blocklisted (token rotation).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    jti: str = payload["jti"]

    # 1. Check blocklist
    if await redis.exists(_blocklist_key(jti)):
        raise credentials_exception

    # 2. Verify user still exists
    user_id: str = payload["sub"]
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    if result.scalar_one_or_none() is None:
        raise credentials_exception

    # 3. Blocklist the used refresh token (token rotation — one-time use)
    exp: int = payload["exp"]
    now = int(__import__("time").time())
    ttl = max(exp - now, 1)
    await redis.setex(_blocklist_key(jti), ttl, "1")

    # 4. Issue new token pair
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
