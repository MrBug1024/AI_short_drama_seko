"""技能市场 - 可安装的插件/技能"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Skill(Base):
    """技能：一组预定义的创作流程（如「出海剧转绘」「知识科普短剧」等）"""
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 唯一标识
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    # 类别：drama/knowledge/ecommerce/animation/comic/translate

    # 模板（prompt 模板 + 节点预设）
    template: Mapped[dict] = mapped_column(JSON, default=dict)

    # 安装状态
    installed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)

    # 排序
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())