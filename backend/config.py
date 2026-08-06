"""
应用配置管理 — 使用 pydantic-settings 自动加载 .env 环境变量

配置优先级(从高到低):
  环境变量(OS ENV) > .env 文件 > 默认值(代码中的 = 号右侧值)

pydantic-settings 会自动:
  ① 读取项目根目录的 .env 文件
  ② 将值映射到 Settings 类的字段
  ③ 做类型转换(str→int, str→list[str])

@lru_cache() 的作用:
  确保 get_settings() 在整个进程中只创建一次 Settings 实例。
  如果每次都 new Settings(), 会重复读取 .env 文件, 浪费 I/O。
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """
    集中管理所有应用配置, 一处定义, 处处使用。

    分组设计:
      - 百炼 API:    模型和认证
      - 数据库:      文件路径(本地部署无需远程连接)
      - JWT:         认证加密
      - 服务端口:    前后端端口(避免冲突)
      - 文档限制:    上传安全性
    """

    # ========== 百炼 API — 阿里云 DashScope 平台的 LLM + Embedding 服务 ==========
    # 注意: 代码中的默认值是占位符，实际值应从 .env 读取
    # ⚠️ 生产环境必须确保 .env 已配置且 .gitignore 中有 .env
    dashscope_api_key: str = "sk-xxxxxxxxxxxx"
    qwen_model: str = "qwen-plus"           # 性价比之选: qwen-plus(智能) > qwen-turbo(速度)
    embedding_model: str = "text-embedding-v2"  # 1536 维输出向量

    # ========== 本地数据库 ==========
    # SQLite: 单文件数据库, 零配置, 适合中小规模部署
    # aiosqlite: SQLite 的异步驱动(配合 SQLAlchemy async engine)
    database_url: str = "sqlite+aiosqlite:///./data/rag.db"
    chroma_persist_dir: str = "./data/chroma"  # ChromaDB 向量数据持久化路径
    upload_dir: str = "./data/uploads"          # 用户上传文件存储
    cache_dir: str = "./data/cache"             # diskcache 磁盘缓存

    # ========== JWT 配置 ==========
    # ⚠️ jwt_secret_key 必须修改!!! 用 python -c "import secrets; print(secrets.token_urlsafe(64))" 生成
    jwt_secret_key: str = "change-this-to-a-random-string-in-production"
    # 为什么是 1440 分钟(24小时)?
    #   太短(1小时) → 用户频繁被踢出, 体验差
    #   太长(7天)   → Token 泄露后攻击者有 7 天窗口期
    #   24 小时     → 电商场景的合理平衡点, 一天工作结束后自动过期
    jwt_access_token_expire_minutes: int = 1440

    # ========== 服务端口 ==========
    backend_port: int = 8000    # FastAPI 后端端口
    frontend_port: int = 5173   # Vite 开发服务器默认端口, 用于 CORS 白名单

    # ========== 文档上传限制 ==========
    max_upload_size_mb: int = 20  # 20MB: 足够上传大型产品手册 PDF, 防止恶意上传撑爆磁盘
    allowed_file_types: list[str] = ["pdf", "docx", "xlsx", "txt", "csv", "md"]
    # 为什么没有 .ppt? PowerPoint 不适合知识库(文字提取质量差)
    # 为什么有 .md?   开发者可能用 Markdown 编写产品文档, 免转换直接入库

    # pydantic-settings 配置: 告诉它去哪里读取 .env 文件
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    """
    获取 Settings 单例(全进程共享一个实例)。

    用法:
      from backend.config import get_settings
      settings = get_settings()
      print(settings.dashscope_api_key)

    @lru_cache 保证只初始化一次, 所有调用点拿到的是同一个对象,
    修改 Settings 后可以通过 get_settings.cache_clear() 强制刷新。
    """
    return Settings()
