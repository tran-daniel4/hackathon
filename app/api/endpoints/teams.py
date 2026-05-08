import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.session import get_db
from models.profile import Profile
from models.team import Team
from models.team_member import TeamMember
from schemas.team import TeamCreate, TeamMemberAdd, TeamMemberOut, TeamMemberUpdate, TeamOut, TeamWithMembers

router = APIRouter(prefix="/teams", tags=["teams"])


async def _require_member(db: AsyncSession, team_id: uuid.UUID, profile_id: uuid.UUID) -> TeamMember:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.profile_id == profile_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this team")
    return member


@router.get("", response_model=list[TeamOut])
async def list_teams(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeamOut]:
    result = await db.execute(
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.profile_id == current_user.id)
        .order_by(Team.created_at.desc())
    )
    teams = result.scalars().all()
    return [TeamOut.model_validate(t) for t in teams]


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamOut:
    team = Team(id=uuid.uuid4(), name=body.name)
    db.add(team)

    member = TeamMember(team_id=team.id, profile_id=current_user.id, role="admin")
    db.add(member)

    await db.commit()
    await db.refresh(team)
    return TeamOut.model_validate(team)


@router.get("/{team_id}", response_model=TeamWithMembers)
async def get_team(
    team_id: uuid.UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamWithMembers:
    await _require_member(db, team_id, current_user.id)

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    members_result = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id)
    )
    members = members_result.scalars().all()

    return TeamWithMembers(
        id=team.id,
        name=team.name,
        created_at=team.created_at,
        updated_at=team.updated_at,
        members=[TeamMemberOut.model_validate(m) for m in members],
    )


@router.post("/{team_id}/members", response_model=TeamMemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: uuid.UUID,
    body: TeamMemberAdd,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberOut:
    await _require_member(db, team_id, current_user.id)

    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.profile_id == body.profile_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Profile is already a member")

    member = TeamMember(team_id=team_id, profile_id=body.profile_id, role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return TeamMemberOut.model_validate(member)


@router.patch("/{team_id}/members/{profile_id}", response_model=TeamMemberOut)
async def update_member_role(
    team_id: uuid.UUID,
    profile_id: uuid.UUID,
    body: TeamMemberUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberOut:
    await _require_member(db, team_id, current_user.id)

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.profile_id == profile_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    member.role = body.role
    await db.commit()
    await db.refresh(member)
    return TeamMemberOut.model_validate(member)


@router.delete("/{team_id}/members/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: uuid.UUID,
    profile_id: uuid.UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_member(db, team_id, current_user.id)

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.profile_id == profile_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await db.delete(member)
    await db.commit()


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_member(db, team_id, current_user.id)

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    await db.delete(team)
    await db.commit()
