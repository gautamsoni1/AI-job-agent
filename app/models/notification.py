from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class NotificationDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    title: str
    message: str
    type: str = "info"  # info | success | warning | error
    is_read: bool = False
    action_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True