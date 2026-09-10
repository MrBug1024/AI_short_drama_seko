"""项目模型 - 一个短剧项目对应一个 AI 创作工程"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Project(Base):
    """项目：对应一次完整的短剧创作任务"""
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(String(500), default="")

    # 归属用户（NULL = 匿名/历史遗留项目，所有用户可见）
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # 创作状态
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/creating/processing/completed/failed
    art_style: Mapped[str] = mapped_column(String(64), default="realistic")  # 美术风格
    target_episodes: Mapped[int] = mapped_column(Integer, default=1)
    target_duration_sec: Mapped[int] = mapped_column(Integer, default=60)

    # 原始创意 prompt
    prompt: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联关系
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
    props = relationship("Prop", back_populates="project", cascade="all, delete-orphan")
    canvas_nodes = relationship("CanvasNode", back_populates="project", cascade="all, delete-orphan")
    canvas_edges = relationship("CanvasEdge", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("GenerationTask", back_populates="project", cascade="all, delete-orphan")

    # 用户归属
    owner = relationship("User", back_populates="projects")