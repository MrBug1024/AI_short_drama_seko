"""镜头/分镜模型"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Shot(Base):
    """镜头（分镜）：画面|构图|运镜|台词|时长"""
    __tablename__ = "shots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True, index=True)

    shot_no: Mapped[int] = mapped_column(Integer, default=1)
    shot_code: Mapped[str] = mapped_column(String(32), default="")  # 镜头编号 SC01/SC02

    # 画面描述
    description: Mapped[str] = mapped_column(Text, default="")
    composition: Mapped[str] = mapped_column(String(64), default="")  # 构图：九宫格/中心/对称等
    camera_movement: Mapped[str] = mapped_column(String(64), default="")  # 运镜：推/拉/摇/移/跟
    camera_angle: Mapped[str] = mapped_column(String(64), default="")  # 角度：平视/俯视/仰视

    # 角色/场景
    character_ids: Mapped[list] = mapped_column(JSON, default=list)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id"), nullable=True)
    prop_ids: Mapped[list] = mapped_column(JSON, default=list)

    # 台词/字幕
    dialogue: Mapped[str] = mapped_column(Text, default="")
    narration: Mapped[str] = mapped_column(Text, default="")
    subtitle: Mapped[str] = mapped_column(Text, default="")

    # 时长
    duration_sec: Mapped[float] = mapped_column(Integer, default=5)

    # 视觉 prompt（用于生图/生视频）
    visual_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")

    # 生成的媒体 URL
    image_url: Mapped[str] = mapped_column(String(500), default="")
    video_url: Mapped[str] = mapped_column(String(500), default="")
    audio_url: Mapped[str] = mapped_column(String(500), default="")

    # 角色一致性引用
    character_refs: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/imaging/videod/audioed/done/failed

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    episode = relationship("Episode", back_populates="shots")