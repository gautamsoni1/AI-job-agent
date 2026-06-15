"""
User MongoDB Document Model
"""
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field, EmailStr


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if not ObjectId.is_valid(str(v)):
            raise ValueError("Invalid ObjectId")
        return str(v)


class UserDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    first_name: str
    last_name: str
    email: str
    hashed_password: str
    phone: Optional[str] = None
    experience_years: int = 0
    preferred_roles: list[str] = []
    preferred_locations: list[str] = []
    skills: list[str] = []
    is_verified: bool = False
    is_active: bool = True
    is_admin: bool = False
    verification_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    refresh_tokens: list[str] = []
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True