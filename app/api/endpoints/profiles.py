from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.session import get_db
from models.profile import Profile
from schemas.auth import UserResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/search", response_model=list[UserResponse])
async def search_profiles(
    email: str = Query(..., min_length=3),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    result = await db.execute(
        select(Profile)
        .where(Profile.email.ilike(f"%{email}%"))
        .limit(10)
    )
    profiles = result.scalars().all()
    return [UserResponse.model_validate(p) for p in profiles]
