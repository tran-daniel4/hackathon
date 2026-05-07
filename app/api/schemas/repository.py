import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RepositoryCreate(BaseModel):
    name: str
    url: str


class RepositoryOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    componentsCount: int = Field(alias="components_count")
    lastUpdated: datetime = Field(alias="updated_at")

    model_config = {"from_attributes": True, "populate_by_name": True}
