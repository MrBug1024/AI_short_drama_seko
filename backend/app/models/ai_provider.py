"""AI 服务商配置"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AIProvider(Base):
    """AI 服务商（OpenAI/豆包/百炼/自定义等）"""
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 显示名
    provider_type: Mapped[str] = mapped_column(String(32), default="openai_compatible")
    # openai_compatible / doubao / aliyun_bailian / zhipu / custom

    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_key: Mapped[str] = mapped_column(String(500), default="")

    # 支持的模型
    text_model: Mapped[str] = mapped_column(String(100), default="")
    image_model: Mapped[str] = mapped_column(String(100), default="")
    video_model: Mapped[str] = mapped_column(String(100), default="")
    audio_model: Mapped[str] = mapped_column(String(100), default="")

    # 元数据
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否内置
    priority: Mapped[int] = mapped_column(Integer, default=50)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    # 状态
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_status: Mapped[str] = mapped_column(String(32), default="unknown")  # ok/failed/unknown

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())