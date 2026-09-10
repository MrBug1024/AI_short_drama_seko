"""灵感广场作品模型"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Inspiration(Base):
    """灵感广场作品 - 用户可发布自己的创作"""
    __tablename__ = "inspirations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0)  # 预留多用户

    # 作品信息
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(String(500), default="")
    video_url: Mapped[str] = mapped_column(String(500), default="")

    # 标签与分类
    category: Mapped[str] = mapped_column(String(64), default="drama")  # drama/comic/knowledge/animation
    tags: Mapped[list] = mapped_column(JSON, default=list)

    # 统计
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    fork_count: Mapped[int] = mapped_column(Integer, default=0)

    # 状态
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)  # 编辑精选

    # 来源
    source_skill: Mapped[str] = mapped_column(String(64), default="")
    art_style: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())