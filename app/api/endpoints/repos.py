import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis import get_redis
from core.deps import get_current_user
from db.session import get_db
from models.profile import Profile
from models.repository import Repository
from schemas.repository import RepositoryCreate, RepositoryOut

router = APIRouter(prefix="/repos", tags=["repos"])

_CACHE_TTL = 300


def _cache_key(user_id: uuid.UUID) -> str:
    return f"repos:{user_id}"


@router.get("", response_model=list[RepositoryOut])
async def list_repos(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RepositoryOut]:
    redis = get_redis()
    cache_key = _cache_key(current_user.id)

    cached = await redis.get(cache_key)
    if cached:
        return [RepositoryOut.model_validate(item) for item in json.loads(cached)]

    result = await db.execute(
        select(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()
    out = [RepositoryOut.model_validate(r) for r in repos]

    await redis.set(cache_key, json.dumps([o.model_dump(mode="json") for o in out]), ex=_CACHE_TTL)
    return out


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
async def create_repo(
    body: RepositoryCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryOut:
    repo = Repository(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=body.name,
        url=body.url,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    redis = get_redis()
    await redis.delete(_cache_key(current_user.id))

    return RepositoryOut.model_validate(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(
    repo_id: uuid.UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.user_id == current_user.id,
        )
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    await db.delete(repo)
    await db.commit()

    redis = get_redis()
    await redis.delete(_cache_key(current_user.id))
