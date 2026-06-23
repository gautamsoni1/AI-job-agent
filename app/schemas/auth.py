from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    phone: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("first_name", "last_name", "email", "phone", mode="before")
    @classmethod
    def trim_register_fields(cls, v):
        return v.strip() if isinstance(v, str) else v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, v):
        return v.strip() if isinstance(v, str) else v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, v):
        return v.strip() if isinstance(v, str) else v


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("token", "new_password", mode="before")
    @classmethod
    def trim_reset_fields(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("current_password", "new_password", mode="before")
    @classmethod
    def trim_password_fields(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    experience_years: int
    preferred_roles: list[str]
    preferred_locations: list[str]
    skills: list[str]
    is_verified: bool
    is_active: bool


class UpdateUserRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    experience_years: int | None = None
    preferred_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    skills: list[str] | None = None
