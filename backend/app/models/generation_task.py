"""生成任务队列 - 异步任务追踪"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class GenerationTask(Base):
    """生成任务（图/视频/音频/TTS/字幕/口型同步等）"""
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 任务类型
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # script / character_portrait / scene_image / prop_image / shot_image / shot_video / tts / lipsync / bgm / audio_separator / storyboard

    # 目标实体
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("shots.id", ondelete="SET NULL"), nullable=True, index=True)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    prop_id: Mapped[int | None] = mapped_column(ForeignKey("props.id", ondelete="SET NULL"), nullable=True)

    # 任务状态机：pending → running → success/failed/cancelled
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    phase: Mapped[str] = mapped_column(String(64), default="")  # 阶段标签

    # 输入参数
    prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)

    # 输出
    output_url: Mapped[str] = mapped_column(String(500), default="")
    output_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    error_msg: Mapped[str] = mapped_column(Text, default="")

    # AI provider 信息
    provider_name: Mapped[str] = mapped_column(String(64), default="")
    model_name: Mapped[str] = mapped_column(String(64), default="")
    external_task_id: Mapped[str] = mapped_column(String(128), default="")  # 外部 API 任务 ID

    # 计费
    estimated_credits: Mapped[float] = mapped_column(Float, default=0)
    actual_credits: Mapped[float] = mapped_column(Float, default=0)

    # 时长
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", back_populates="tasks")