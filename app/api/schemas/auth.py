import uuid
from datetime import datetime
from pydantic import BaseModel

class UserResponse(BaseModel):
    """Returned by /me."""
    id: uuid.UUID
    email: str
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
