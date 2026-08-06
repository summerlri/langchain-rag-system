"""
认证 API — 注册、登录、修改密码
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.models.user import User
from backend.core.security import hash_password, verify_password, create_access_token
from backend.core.deps import get_current_user
from backend.core.exceptions import BadRequestException, NotFoundException
from backend.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    ChangePasswordRequest, UserInfoResponse,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == req.username))
    existing = result.scalar_one_or_none()
    if existing:
        raise BadRequestException("用户名已存在")

    # 创建用户
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        is_admin=0,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()

    # 生成 Token
    access_token = create_access_token(data={"sub": user.id, "username": user.username})
    return TokenResponse(
        access_token=access_token,
        username=user.username,
        is_admin=bool(user.is_admin),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise BadRequestException("用户名或密码错误")

    if not user.is_active:
        raise BadRequestException("账户已被禁用，请联系管理员")

    access_token = create_access_token(data={"sub": user.id, "username": user.username})
    return TokenResponse(
        access_token=access_token,
        username=user.username,
        is_admin=bool(user.is_admin),
    )


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码"""
    if not verify_password(req.old_password, current_user.hashed_password):
        raise BadRequestException("原密码错误")

    current_user.hashed_password = hash_password(req.new_password)
    current_user.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.flush()
    return {"message": "密码修改成功"}


@router.get("/me", response_model=UserInfoResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserInfoResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email or "",
        is_admin=bool(current_user.is_admin),
        created_at=current_user.created_at,
    )
