"""无限画布：节点 + 连线"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class CanvasNode(Base):
    """画布节点：角色/场景/道具/分镜/视频节点"""
    __tablename__ = "canvas_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 节点类型
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # character / scene / prop / shot / video / script / generation / audio_separator / storyboard

    # 关联实体 ID
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 显示标题
    title: Mapped[str] = mapped_column(String(200), default="")

    # 画布位置
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)

    # 缩略图
    thumbnail_url: Mapped[str] = mapped_column(String(500), default="")

    # 节点状态
    status: Mapped[str] = mapped_column(String(32), default="draft")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="canvas_nodes")
    outgoing_edges = relationship(
        "CanvasEdge",
        foreign_keys="CanvasEdge.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "CanvasEdge",
        foreign_keys="CanvasEdge.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )


class CanvasEdge(Base):
    """画布连线：节点之间的引用/依赖关系"""
    __tablename__ = "canvas_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    source_id: Mapped[int] = mapped_column(ForeignKey("canvas_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("canvas_nodes.id", ondelete="CASCADE"), nullable=False, index=True)

    # 连线类型：reference（参考）/dependency（依赖）/sequence（流程）
    edge_type: Mapped[str] = mapped_column(String(32), default="reference")

    # 标签（可选）
    label: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="canvas_edges")
    source = relationship("CanvasNode", foreign_keys=[source_id], back_populates="outgoing_edges")
    target = relationship("CanvasNode", foreign_keys=[target_id], back_populates="incoming_edges")