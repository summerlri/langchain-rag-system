"""
SQLite 数据库连接和会话管理
"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.config import get_settings

settings = get_settings()

# 创建异步引擎，SQLite WAL 模式提升并发写入性能
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_size=5,
    max_overflow=10,
)


# ═══════════════════════════════════════════════════════════════
# 关键：每个新连接都要设置这些 PRAGMA
# SQLite 在 WAL 模式下支持"一写多读"并发，但没有 busy_timeout
# 的话遇到锁会立刻报错（SQLITE_BUSY），设了之后会等待而不是放弃
# ═══════════════════════════════════════════════════════════════
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """每个数据库连接建立时都执行这些 PRAGMA"""
    cursor = dbapi_connection.cursor()
    # WAL 模式：允许读写并发（文件级持久，设一次即可，但每个连接都设也没副作用）
    cursor.execute("PRAGMA journal_mode=WAL")
    # busy_timeout：遇到锁等 5 秒，而不是立刻报 SQLITE_BUSY 错误
    cursor.execute("PRAGMA busy_timeout=5000")
    # synchronous=NORMAL：WAL 模式下安全且性能更高（减少 fsync 次数）
    cursor.execute("PRAGMA synchronous=NORMAL")
    # 外键约束
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 异步会话工厂
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """依赖注入：获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """创建所有表 + 启用 WAL 模式"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite WAL 模式 — 读写并发
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
