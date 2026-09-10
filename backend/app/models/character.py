"""角色模型 - 角色一致性控制（SekoIDX 占位）"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Character(Base):
    """角色：参考图+特征描述，保证跨集一致性"""
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), default="")
    alias: Mapped[str] = mapped_column(String(200), default="")  # 别名/化名
    age: Mapped[int] = mapped_column(Integer, default=0)
    gender: Mapped[str] = mapped_column(String(16), default="")
    role: Mapped[str] = mapped_column(String(32), default="")  # 主角/配角/反派

    # 视觉特征
    appearance: Mapped[str] = mapped_column(Text, default="")  # 外貌描述
    outfit: Mapped[str] = mapped_column(Text, default="")  # 服装
    personality: Mapped[str] = mapped_column(Text, default="")  # 性格
    backstory: Mapped[str] = mapped_column(Text, default="")  # 背景故事

    # 参考图（SekoIDX 负参考图技术）
    reference_images: Mapped[list] = mapped_column(JSON, default=list)  # 图片 URL 列表
    portrait_url: Mapped[str] = mapped_column(String(500), default="")  # 主参考图

    # 角色设计多视图：{"front":url,"side":url,"back":url,"expression":url,"closeup":url}
    view_images: Mapped[dict] = mapped_column(JSON, default=dict)

    # 角色一致性标识（用于跨集同步）
    consistency_key: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="characters")


class CharacterRelation(Base):
    """角色关系：恋人/仇人/亲子等，用于画布关系连线与剧情一致性"""
    __tablename__ = "character_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    from_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    to_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)

    relation_type: Mapped[str] = mapped_column(String(32), default="")  # 恋人/仇人/亲子/朋友...
    description: Mapped[str] = mapped_column(Text, default="")  # 关系描述与戏剧张力

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())