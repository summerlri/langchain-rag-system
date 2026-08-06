"""
FastAPI 依赖注入 — 认证和权限校验

FastAPI 的依赖注入(Depends)机制允许我们将认证逻辑从业务代码中解耦。
每个 API 路由只需声明 current_user: User = Depends(get_current_user)，
框架会自动执行 JWT 解析和用户查询，路由函数中拿到的已经是验证通过的 User 对象。

认证链路:
  ① HTTPBearer 提取请求头中的 Bearer Token
  ② decode_access_token 解析 JWT → payload
  ③ 用 payload.sub(user_id) 查询数据库 → User 对象
  ④ 检查 is_active 状态
  ⑤ 返回 User(路由中可直接使用)

为什么 auto_error=False?
  默认 HTTPBearer(auto_error=True) 会在没有 Token 时自动返回 401。
  设为 False 后 credentials 为 None，我们可以自己控制错误信息的措辞。
  这样可以把"未提供 Token"和"Token 无效"区分开，方便前端显示不同的提示。
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.database import get_db
from backend.core.security import decode_access_token
from backend.models.user import User

# auto_error=False: 没有 Token 时不自动抛异常，改为返回 None，由我们手动处理
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 JWT Token 中解析当前登录用户 → 注入到路由函数中。

    这是整个认证系统的"守门员": 所有需要登录的 API 都通过这个函数验证身份。
    对每一次请求都会:
      ① 提取 Bearer Token → ② 解析 JWT → ③ 查数据库 → ④ 检查账户状态

    失败时逐步返回不同的 401 信息，帮助前端调试:
      "未提供认证令牌" → 前端自动跳转登录页
      "令牌无效或已过期" → 前端刷新 Token 或要求重新登录
      "用户不存在" → Token 有效但用户已被删除(极少数情况)
    """
    # ① 提取 Token — 从 HTTP 请求头 Authorization: Bearer <token>
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
        )

    # ② 解析 JWT — 验证签名和过期时间
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
        )

    # ③ 提取用户 ID — sub 是 JWT 标准字段，存储 user.id
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌格式错误")

    # ④ 查数据库 — 确保用户在 Token 签发后没有被删除
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    # ⑤ 检查账户状态 — 软删除/封禁的用户即使 Token 有效也拒绝访问
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已被禁用")

    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    要求当前用户是管理员，否则返回 403。

    这是 get_current_user 的增强版: 先执行普通认证，再额外检查 is_admin 字段。
    用于知识库管理、文档上传等需要管理员权限的接口。

    为什么用 403 而不是 401?
      HTTP 语义: 401 = 未认证(请登录), 403 = 已认证但权限不足(登录了但没有管理员权限)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
