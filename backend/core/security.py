"""
JWT 认证和密码哈希工具

安全设计原则:
  - 密码: bcrypt(通过 passlib) — 自带盐值，每次哈希结果不同，抗彩虹表攻击
  - Token: JWT HS256 — 服务端签名，无需存储 session 状态(无状态认证)
  - 过期: 默认 24 小时 — 平衡了安全和用户体验(不用每天重新登录)
  - 失败静默: decode_access_token 失败返回 None 而非抛异常 → 防止攻击者通过异常差异推断 token 结构

为什么用 JWT 而不是 Session?
  前后端分离架构(Vue + FastAPI)天然适合 JWT:
    - 不依赖服务端 session 存储，水平扩展时不需要 session 共享
    - 前端 HTTP 头传 Authorization: Bearer <token>，简单且标准
    - 缺点: 服务端无法主动吊销单个 token(除非加黑名单机制)，所以过期时间不宜过长

为什么用 bcrypt 而不是 SHA256/argon2?
  bcrypt 是密码哈希领域的"黄金标准"之一:
    - 内建盐值 → 相同密码每次哈希结果不同
    - 计算慢(故意慢) → 暴力破解成本高
    - passlib 自动识别已弃用的哈希算法(deprecated="auto") → 方便未来升级
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from backend.config import get_settings

settings = get_settings()
# CryptContext: passlib 的核心配置对象
# schemes=["bcrypt"] 指定算法
# deprecated="auto" 让 passlib 自动检测旧格式哈希(如以后从 bcrypt 升级到 argon2)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    对密码进行 bcrypt 单向哈希。

    为什么"单向"?
      bcrypt 是故意设计成不可逆的——即使数据库泄露，攻击者也只能暴力破解而无法反转哈希
      拿到原文。这是密码存储的行业标准: 永远不要存储明文密码，也永远不要能"解密"密码。

    每次哈希结果不同(因为随机盐)，所以相同密码调用两次会得到不同的哈希字符串。
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否匹配已存储的哈希值。

    passlib 的 verify 方法会自动从哈希中提取盐值、迭代次数等参数，
    然后用相同参数重新哈希明文并比较。所以不需要额外存储盐值。
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT Access Token。

    参数:
      data:          要编码到 Token 中的数据(至少应包含 "sub": user.id)
      expires_delta: 自定义过期时间，不传则用配置文件中的默认值

    Token 结构(JWT 三段式):
      header.payload.signature
      header:   {"alg": "HS256"}  → 签名算法
      payload:  {"sub": "user-id", "username": "admin", "exp": 时间戳}
      signature: HMAC-SHA256(base64(header) + "." + base64(payload), secret_key)

    为什么用 data.copy()?
      在 JWT payload 中添加 exp 时会修改 dict。copy() 避免污染调用方的原始 data。
    """
    to_encode = data.copy()
    # exp 是 JWT 标准字段，代表过期时间，jose 库会自动校验
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """
    解析 JWT Token，验证签名和过期时间。

    返回值: 成功 → payload dict / 失败(过期/伪造/格式错) → None

    为什么失败返回 None 而不是抛异常?
      安全意识: 对不同类型的失败都返回相同的 None，防止攻击者通过
      返回的错误类型("签名无效" vs "已过期")推断出 token 的内部结构。
      面向调用方(deps.py)来说，None 就代表"没通过认证"，不去区分具体原因。
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
