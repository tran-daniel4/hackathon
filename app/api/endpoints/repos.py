import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis import get_redis
from core.analysis_service import execute_analysis
from core.deps import get_current_user
from core.repo_loader import get_github_repo_head_sha, is_github_repo_url
from db.session import get_db
from models.profile import Profile
from models.repository import Repository
from models.repository_analysis import RepositoryAnalysis
from schemas.repository import RepositoryCreate, RepositoryOut, RepositoryUpdate

router = APIRouter(prefix="/repos", tags=["repos"])

_CACHE_TTL = 300


class AnalysisSyncRequest(BaseModel):
    github_token: str | None = None


def _repos_cache_key(user_id: uuid.UUID) -> str:
    return f"repos:{user_id}"


def _analysis_cache_key(repo_id: uuid.UUID) -> str:
    return f"repo-analysis:{repo_id}"


def _alerts_cache_key(user_id: uuid.UUID) -> str:
    return f"repo-alerts:{user_id}"


def _repository_payload(repo: Repository) -> dict[str, Any]:
    return RepositoryOut.model_validate(repo).model_dump(mode="json")


@router.get("", response_model=list[RepositoryOut])
async def list_repos(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RepositoryOut]:
    redis = get_redis()
    cache_key = _repos_cache_key(current_user.id)

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


@router.get("/alerts")
async def list_repo_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    redis = get_redis()
    cache_key = _alerts_cache_key(current_user.id)
    cached = await redis.get(cache_key)
    if cached:
        payload = json.loads(cached)
        payload["alerts"] = payload["alerts"][:limit]
        return payload

    repos_result = await db.execute(
        select(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
    )
    repos = repos_result.scalars().all()
    if not repos:
        payload = {"alerts": [], "generated_at": datetime.utcnow().isoformat()}
        await redis.set(cache_key, json.dumps(payload), ex=_CACHE_TTL)
        return payload

    repo_by_id = {repo.id: repo for repo in repos}
    analyses_result = await db.execute(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.repository_id.in_(list(repo_by_id.keys())))
        .where(RepositoryAnalysis.status == "completed")
        .order_by(RepositoryAnalysis.repository_id, desc(RepositoryAnalysis.analyzed_at))
    )
    analyses = analyses_result.scalars().all()

    latest_by_repo: dict[uuid.UUID, RepositoryAnalysis] = {}
    for analysis in analyses:
        latest_by_repo.setdefault(analysis.repository_id, analysis)

    alerts: list[dict[str, Any]] = []
    for repo_id, analysis in latest_by_repo.items():
        repo = repo_by_id.get(repo_id)
        if repo is None:
            continue
        findings = ((analysis.snapshot or {}).get("bottlenecks") or {}).get("findings") or []
        for finding in findings:
            alerts.append({
                "id": f"{repo_id}-{finding.get('id', uuid.uuid4())}",
                "repository": repo.name,
                "repository_id": str(repo.id),
                "severity": finding.get("severity", "low"),
                "type": _activity_type_for_severity(finding.get("severity", "low")),
                "message": finding.get("title", "Untitled alert"),
                "details": finding.get("why") or finding.get("impact"),
                "confidence": finding.get("confidence", 0),
                "analyzed_at": analysis.analyzed_at.isoformat(),
                "branch": analysis.branch,
                "commit_sha": analysis.commit_sha,
            })

    alerts.sort(
        key=lambda alert: (
            -(datetime.fromisoformat(alert["analyzed_at"]).timestamp() if alert.get("analyzed_at") else 0),
            _severity_rank(alert["severity"]),
            -(alert.get("confidence") or 0),
        )
    )

    payload = {
        "alerts": alerts,
        "generated_at": datetime.utcnow().isoformat(),
    }
    await redis.set(cache_key, json.dumps(payload), ex=_CACHE_TTL)
    payload["alerts"] = payload["alerts"][:limit]
    return payload


@router.get("/{repo_id}/analysis/latest")
async def get_latest_repo_analysis(
    repo_id: uuid.UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = await _get_repo_or_404(db, current_user.id, repo_id)
    _ = repo

    redis = get_redis()
    cache_key = _analysis_cache_key(repo_id)
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    analysis = await _get_latest_completed_analysis(db, repo_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved analysis found")

    payload = _serialize_analysis_snapshot(analysis, repo)
    await redis.set(cache_key, json.dumps(payload), ex=_CACHE_TTL)
    return payload


@router.post("/{repo_id}/analysis/sync")
async def sync_repo_analysis(
    repo_id: uuid.UUID,
    body: AnalysisSyncRequest,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = await _get_repo_or_404(db, current_user.id, repo_id)
    latest = await _get_latest_completed_analysis(db, repo_id)

    should_refresh = latest is None
    if latest is not None and is_github_repo_url(repo.url):
        latest_head = get_github_repo_head_sha(
            repo.url,
            branch=latest.branch,
            github_token=body.github_token,
        )
        if latest_head and latest.commit_sha and latest_head != latest.commit_sha:
            should_refresh = True

    if not should_refresh and latest is not None:
        payload = _serialize_analysis_snapshot(latest, repo)
        redis = get_redis()
        await redis.set(_analysis_cache_key(repo_id), json.dumps(payload), ex=_CACHE_TTL)
        return payload

    bundle = await execute_analysis(
        repo_url=repo.url,
        github_token=body.github_token,
    )
    analysis = await _save_repository_analysis(
        db=db,
        repo=repo,
        bundle=bundle,
    )
    payload = _serialize_analysis_snapshot(analysis, repo)

    redis = get_redis()
    await redis.set(_analysis_cache_key(repo_id), json.dumps(payload), ex=_CACHE_TTL)
    await redis.delete(_alerts_cache_key(current_user.id))
    await redis.delete(_repos_cache_key(current_user.id))
    return payload


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
    await redis.delete(_repos_cache_key(current_user.id))
    await redis.delete(_alerts_cache_key(current_user.id))

    return RepositoryOut.model_validate(repo)


@router.patch("/{repo_id}", response_model=RepositoryOut)
async def update_repo(
    repo_id: uuid.UUID,
    body: RepositoryUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryOut:
    repo = await _get_repo_or_404(db, current_user.id, repo_id)
    repo.name = body.name
    await db.commit()
    await db.refresh(repo)

    redis = get_redis()
    await redis.delete(_repos_cache_key(current_user.id))
    await redis.delete(_alerts_cache_key(current_user.id))
    await redis.delete(_analysis_cache_key(repo_id))

    return RepositoryOut.model_validate(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(
    repo_id: uuid.UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = await _get_repo_or_404(db, current_user.id, repo_id)

    await db.delete(repo)
    await db.commit()

    redis = get_redis()
    await redis.delete(_repos_cache_key(current_user.id))
    await redis.delete(_alerts_cache_key(current_user.id))
    await redis.delete(_analysis_cache_key(repo_id))


async def _get_repo_or_404(db: AsyncSession, user_id: uuid.UUID, repo_id: uuid.UUID) -> Repository:
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.user_id == user_id,
        )
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


async def _get_latest_completed_analysis(db: AsyncSession, repo_id: uuid.UUID) -> RepositoryAnalysis | None:
    result = await db.execute(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.repository_id == repo_id)
        .where(RepositoryAnalysis.status == "completed")
        .order_by(desc(RepositoryAnalysis.analyzed_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _save_repository_analysis(
    *,
    db: AsyncSession,
    repo: Repository,
    bundle,
) -> RepositoryAnalysis:
    snapshot = bundle.payload
    repo.components_count = bundle.component_count
    analysis = RepositoryAnalysis(
        id=uuid.uuid4(),
        repository_id=repo.id,
        status="completed",
        source=bundle.source,
        branch=bundle.repo_meta.get("branch"),
        commit_sha=bundle.repo_meta.get("commit_sha"),
        snapshot=snapshot,
        error_message=None,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


def _serialize_analysis_snapshot(analysis: RepositoryAnalysis, repo: Repository) -> dict[str, Any]:
    return {
        "id": str(analysis.id),
        "repository_id": str(analysis.repository_id),
        "status": analysis.status,
        "source": analysis.source,
        "branch": analysis.branch,
        "commit_sha": analysis.commit_sha,
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "repository": _repository_payload(repo),
        **(analysis.snapshot or {}),
    }


def _severity_rank(severity: str) -> int:
    return {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }.get(severity, 4)


def _activity_type_for_severity(severity: str) -> str:
    if severity in {"critical", "high"}:
        return "alert"
    if severity == "medium":
        return "task"
    return "update"
