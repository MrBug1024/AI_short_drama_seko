"""剧本模型 - 多版本管理"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Script(Base):
    """剧本：一个项目可有多个版本（V1, V2...）"""
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    title: Mapped[str] = mapped_column(String(200), default="")
    logline: Mapped[str] = mapped_column(Text, default="")  # 一句话故事
    content: Mapped[str] = mapped_column(Text, default="")  # 完整剧本 Markdown
    raw_text: Mapped[str] = mapped_column(Text, default="")  # 原始输入

    # 结构化数据（场景列表、人物列表、分镜列表 JSON）
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    # 任务追踪
    source_task_id: Mapped[str] = mapped_column(String(64), default="")  # 对应的 AI 任务 ID

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="scripts")