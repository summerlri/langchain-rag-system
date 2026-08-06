"""
用户模型
"""
import uuid
from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, is_admin={self.is_admin})>"
