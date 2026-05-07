from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models.profile import Profile
from schemas.auth import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Profile = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
