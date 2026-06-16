"""
FastAPI Dependency Injection
"""
from fastapi import Cookie, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.repositories.user_repo import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_db() -> AsyncIOMotorDatabase:
    return get_database()


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    token = token or access_token
    if not token:
        raise UnauthorizedError("Missing authorization token")

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise UnauthorizedError("Could not validate credentials")
    except JWTError:
        raise UnauthorizedError("Could not validate credentials")

    repo = UserRepository(db)
    user = await repo.find_by_id(user_id)
    if user is None:
        raise UnauthorizedError("Could not validate credentials")
    if not user.get("is_active", True):
        raise UnauthorizedError("Account is deactivated")
    return user


async def get_current_admin(current_user=Depends(get_current_user)):
    if not current_user.get("is_admin", False):
        raise ForbiddenError("Admin access required")
    return current_user
