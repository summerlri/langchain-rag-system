"""
数据库初始化脚本 — 创建表 + 初始化 admin 账户
"""
import asyncio
from datetime import datetime
from sqlalchemy import select
from backend.db.database import async_session, init_db
from backend.models.user import User
from backend.core.security import hash_password


async def seed_admin():
    """初始化管理员账户 admin / 123456"""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        existing = result.scalar_one_or_none()

        if existing:
            print("[WARN] Admin account already exists, skipping creation")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        admin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=hash_password("123456"),
            is_admin=1,
            is_active=1,
            created_at=now,
            updated_at=now,
        )
        session.add(admin)
        await session.commit()
        print("[OK] Admin account created: admin / 123456")


async def main():
    await init_db()
    await seed_admin()


if __name__ == "__main__":
    asyncio.run(main())
