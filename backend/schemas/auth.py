"""
认证相关 Pydantic 模型
"""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码（6-100位）")
    email: str = Field(default="", max_length=100, description="邮箱（可选）")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)


class UserInfoResponse(BaseModel):
    id: str
    username: str
    email: str
    is_admin: bool
    created_at: str | None = None
