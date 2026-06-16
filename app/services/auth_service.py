import secrets
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext

from app.config import get_settings
from app.core.exceptions import UnauthorizedException, ConflictException, NotFoundException
from app.core.security import create_access_token, create_refresh_token
from app.repositories.user_repo import UserRepository

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    async def register(self, first_name: str, last_name: str, email: str, password: str, phone: str = "") -> dict:
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ConflictException("Email already registered")

        verification_token = secrets.token_urlsafe(32)
        user_doc = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email.lower(),
            "hashed_password": self.hash_password(password),
            "phone": phone,
            "experience_years": 0,
            "preferred_roles": [],
            "preferred_locations": [],
            "skills": [],
            "is_verified": False,
            "is_active": True,
            "verification_token": verification_token,
            "refresh_tokens": [],
            "last_login": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        user_id = await self.user_repo.insert(user_doc)
        return {"user_id": user_id, "verification_token": verification_token, "email": email}

    async def verify_email(self, token: str) -> bool:
        user = await self.user_repo.find_by_verification_token(token)
        if not user:
            raise NotFoundException("Invalid or expired verification token")
        await self.user_repo.verify_email(str(user["_id"]))
        return True

    async def login(self, email: str, password: str) -> dict:
        user = await self.user_repo.find_by_email(email)
        if not user:
            raise UnauthorizedException("Invalid credentials")
        if not self.verify_password(password, user["hashed_password"]):
            raise UnauthorizedException("Invalid credentials")
        if not user.get("is_active", True):
            raise UnauthorizedException("Account is deactivated")

        user_id = str(user["_id"])
        access_token = create_access_token({"sub": user_id, "email": user["email"]})
        refresh_token = create_refresh_token({"sub": user_id})

        await self.user_repo.store_refresh_token(user_id, refresh_token)
        await self.user_repo.update_last_login(user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user_id,
            "email": user["email"],
            "first_name": user["first_name"],
            "is_verified": user.get("is_verified", False),
        }

    async def refresh_tokens(self, user_id: str, refresh_token: str) -> dict:
        is_valid = await self.user_repo.is_refresh_token_valid(user_id, refresh_token)
        if not is_valid:
            raise UnauthorizedException("Invalid refresh token")

        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")

        await self.user_repo.revoke_refresh_token(user_id, refresh_token)

        new_access = create_access_token({"sub": user_id, "email": user["email"]})
        new_refresh = create_refresh_token({"sub": user_id})
        await self.user_repo.store_refresh_token(user_id, new_refresh)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }

    async def logout(self, user_id: str, refresh_token: str) -> bool:
        return await self.user_repo.revoke_refresh_token(user_id, refresh_token)

    async def forgot_password(self, email: str) -> Optional[str]:
        user = await self.user_repo.find_by_email(email)
        if not user:
            return None
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=1)
        await self.user_repo.set_reset_token(str(user["_id"]), token, expires)
        return token

    async def reset_password(self, token: str, new_password: str) -> bool:
        user = await self.user_repo.find_by_reset_token(token)
        if not user:
            raise NotFoundException("Invalid or expired reset token")
        hashed = self.hash_password(new_password)
        user_id = str(user["_id"])
        await self.user_repo.update_password(user_id, hashed)
        await self.user_repo.clear_reset_token(user_id)
        return True

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        if not self.verify_password(current_password, user["hashed_password"]):
            raise UnauthorizedException("Current password is incorrect")
        hashed = self.hash_password(new_password)
        return await self.user_repo.update_password(user_id, hashed)