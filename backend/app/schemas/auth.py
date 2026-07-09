from pydantic import BaseModel, EmailStr, Field

from app.schemas.users import UserRead


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, description="Username or email address.")
    password: str = Field(min_length=8, max_length=256)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

