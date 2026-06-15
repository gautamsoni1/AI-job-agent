"""
Auth API Endpoints — Registration, Login, Token Refresh, Password Management
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_refresh_token
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest,
    ChangePasswordRequest, UserResponse, UpdateUserRequest
)

router = APIRouter()


def get_auth_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db))


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    svc = get_auth_service(db)
    result = await svc.register(
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        password=body.password,
        phone=body.phone or "",
    )
    email_svc = EmailService()
    background_tasks.add_task(
        email_svc.send_verification_email,
        result["email"],
        body.first_name,
        result["verification_token"],
    )
    return {"success": True, "message": "Registration successful. Check your email to verify.", "user_id": result["user_id"]}


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    svc = get_auth_service(db)
    await svc.verify_email(token)
    return {"success": True, "message": "Email verified successfully."}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    svc = get_auth_service(db)
    result = await svc.login(body.email, body.password)
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(body: RefreshRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        payload = decode_refresh_token(body.refresh_token)
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Invalid refresh token")
    except Exception:
        raise UnauthorizedError("Invalid refresh token")
    svc = get_auth_service(db)
    return await svc.refresh_tokens(user_id, body.refresh_token)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    svc = get_auth_service(db)
    await svc.logout(str(current_user["_id"]), body.refresh_token)
    return {"success": True, "message": "Logged out successfully."}


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    svc = get_auth_service(db)
    email_svc = EmailService()
    repo = UserRepository(db)
    token = await svc.forgot_password(body.email)
    if token:
        user = await repo.find_by_email(body.email)
        if user:
            background_tasks.add_task(
                email_svc.send_password_reset_email,
                body.email,
                user.get("first_name", ""),
                token,
            )
    return {"success": True, "message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    svc = get_auth_service(db)
    await svc.reset_password(body.token, body.new_password)
    return {"success": True, "message": "Password reset successfully."}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    svc = get_auth_service(db)
    await svc.change_password(str(current_user["_id"]), body.current_password, body.new_password)
    return {"success": True, "message": "Password changed successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user["_id"]),
        first_name=current_user.get("first_name", ""),
        last_name=current_user.get("last_name", ""),
        email=current_user.get("email", ""),
        phone=current_user.get("phone"),
        experience_years=current_user.get("experience_years", 0),
        preferred_roles=current_user.get("preferred_roles", []),
        preferred_locations=current_user.get("preferred_locations", []),
        skills=current_user.get("skills", []),
        is_verified=current_user.get("is_verified", False),
        is_active=current_user.get("is_active", True),
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UpdateUserRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from datetime import datetime
    repo = UserRepository(db)
    update_data = body.model_dump(exclude_none=True)
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await repo.update(str(current_user["_id"]), update_data)
    updated = await repo.get_by_id(str(current_user["_id"]))
    return UserResponse(
        id=str(updated["_id"]),
        first_name=updated.get("first_name", ""),
        last_name=updated.get("last_name", ""),
        email=updated.get("email", ""),
        phone=updated.get("phone"),
        experience_years=updated.get("experience_years", 0),
        preferred_roles=updated.get("preferred_roles", []),
        preferred_locations=updated.get("preferred_locations", []),
        skills=updated.get("skills", []),
        is_verified=updated.get("is_verified", False),
        is_active=updated.get("is_active", True),
    )