"""用户模型 - 邮箱+密码的本地账号"""
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    """本地用户：邮箱登录 + bcrypt 密码"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 角色：普通用户 / 管理员
    role: Mapped[str] = mapped_column(String(32), default="user")

    # 状态：active / disabled
    status: Mapped[str] = mapped_column(String(32), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联项目
    projects = relationship("Project", back_populates="owner", cascade="")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"