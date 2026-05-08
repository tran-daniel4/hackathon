from fastapi import APIRouter, Depends

from core.deps import get_current_user
from db.session import get_db
from models.profile import Profile
from schemas.auth import UpdateProfileRequest, UserResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Profile = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    body: UpdateProfileRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the currently authenticated user's profile."""
    current_user.full_name = body.full_name
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
