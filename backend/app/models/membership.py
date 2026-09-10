"""会员订阅/积分系统模型 - 类似 Seko 订阅计划"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func, JSON, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Membership(Base):
    """会员计划 - 模仿 Seko 四级订阅"""
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # free / standard / pro / enterprise

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    # 价格
    monthly_price: Mapped[float] = mapped_column(Float, default=0)  # CNY
    yearly_price: Mapped[float] = mapped_column(Float, default=0)

    # 积分配额
    monthly_credits: Mapped[int] = mapped_column(Integer, default=0)
    daily_login_credits: Mapped[int] = mapped_column(Integer, default=10)

    # 功能限制
    max_episodes: Mapped[int] = mapped_column(Integer, default=1)  # 多剧集最大集数
    max_shots_per_gen: Mapped[int] = mapped_column(Integer, default=30)  # 一键最多生成分镜
    hd_video: Mapped[bool] = mapped_column(Boolean, default=False)
    remove_watermark: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_queue: Mapped[bool] = mapped_column(Boolean, default=False)
    team_collaboration: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_support: Mapped[bool] = mapped_column(Boolean, default=False)

    # 优先级排序
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    badge: Mapped[str] = mapped_column(String(32), default="")  # 最受欢迎/推荐

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserCredits(Base):
    """用户积分账户"""
    __tablename__ = "user_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, unique=True)  # 默认单用户 0

    # 当前积分
    credits: Mapped[float] = mapped_column(Float, default=100.0)  # 新用户赠送 100 积分

    # 会员等级
    tier: Mapped[str] = mapped_column(String(32), default="free")

    # 累计统计
    total_used: Mapped[float] = mapped_column(Float, default=0)
    total_earned: Mapped[float] = mapped_column(Float, default=0)

    # 上次签到
    last_signin_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signin_streak: Mapped[int] = mapped_column(Integer, default=0)

    # 会员到期
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CreditTransaction(Base):
    """积分流水"""
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # 变动类型
    tx_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # signin / purchase / generation / refund / invite / admin

    # 数量（正=增加，负=消耗）
    amount: Mapped[float] = mapped_column(Float, default=0)

    # 描述
    description: Mapped[str] = mapped_column(String(200), default="")

    # 关联
    related_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class ModelCatalog(Base):
    """模型目录 - 模仿 Seko 模型聚合（Seedance/可灵/即梦/万相/Nano Banana 等）"""
    __tablename__ = "model_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # 显示名
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    vendor: Mapped[str] = mapped_column(String(32), default="")  # doubao/kling/wan/qwen/midjourney/nano_banana 等
    icon: Mapped[str] = mapped_column(String(32), default="")

    # 类型
    model_type: Mapped[str] = mapped_column(String(32), default="video")  # image/video/audio/text
    # image / video / audio / text / multimodal

    # 能力描述
    description: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[list] = mapped_column(JSON, default=list)  # ["首帧生视频", "参考生视频", "唇形同步"...]
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"max_duration": 30, "resolution": "1080P", "aspect_ratios": ["16:9", "9:16"]}

    # 计费（积分/秒 或 积分/张）
    credits_per_second: Mapped[float] = mapped_column(Float, default=0)
    credits_per_image: Mapped[float] = mapped_column(Float, default=0)

    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否付费模型

    # 推荐
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ArtStyleLibrary(Base):
    """画风库 - 模仿 Seko 画风库（国风漫剧/真人古风/超现实奇幻/3D 现代/怪谈漫画）"""
    __tablename__ = "art_styles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="realistic")
    # realistic / anime / guofeng / comic / sci-fi / fantasy / horror / 3d

    description: Mapped[str] = mapped_column(Text, default="")
    visual_prompt: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(String(500), default="")

    tags: Mapped[list] = mapped_column(JSON, default=list)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())