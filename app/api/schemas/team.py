import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberAdd(BaseModel):
    profile_id: uuid.UUID
    role: str = "member"


class TeamMemberOut(BaseModel):
    team_id: uuid.UUID
    profile_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberUpdate(BaseModel):
    role: Literal["admin", "member"]


class TeamWithMembers(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
    members: list[TeamMemberOut]

    model_config = {"from_attributes": True}
