"""会员订阅 / 积分 / 模型目录 / 画风库 API"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.membership import (
    Membership, UserCredits, CreditTransaction,
    ModelCatalog, ArtStyleLibrary,
)
from app.models.project import Project
from app.models.episode import Episode

router = APIRouter()


# ============== 会员计划 ==============

@router.get("/memberships")
async def list_memberships(db: AsyncSession = Depends(get_db)):
    """获取所有会员计划（4 级：免费/标准/高级/企业）"""
    stmt = select(Membership).order_by(Membership.sort_order)
    items = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": m.id,
            "tier": m.tier,
            "name": m.name,
            "description": m.description,
            "monthly_price": m.monthly_price,
            "yearly_price": m.yearly_price,
            "monthly_credits": m.monthly_credits,
            "daily_login_credits": m.daily_login_credits,
            "max_episodes": m.max_episodes,
            "max_shots_per_gen": m.max_shots_per_gen,
            "hd_video": m.hd_video,
            "remove_watermark": m.remove_watermark,
            "priority_queue": m.priority_queue,
            "team_collaboration": m.team_collaboration,
            "vip_support": m.vip_support,
            "badge": m.badge,
        }
        for m in items
    ]


# ============== 用户积分 ==============

async def _get_or_create_credits(db: AsyncSession, user_id: int = 0) -> UserCredits:
    cred = (await db.execute(select(UserCredits).where(UserCredits.user_id == user_id))).scalar_one_or_none()
    if not cred:
        cred = UserCredits(user_id=user_id, credits=100.0, tier="free")
        db.add(cred)
        await db.commit()
        await db.refresh(cred)
    return cred


@router.get("/credits")
async def get_credits(db: AsyncSession = Depends(get_db)):
    """获取当前用户积分"""
    cred = await _get_or_create_credits(db)
    return {
        "credits": cred.credits,
        "tier": cred.tier,
        "total_used": cred.total_used,
        "total_earned": cred.total_earned,
        "signin_streak": cred.signin_streak,
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
    }


@router.post("/credits/signin")
async def daily_signin(db: AsyncSession = Depends(get_db)):
    """每日签到送积分"""
    cred = await _get_or_create_credits(db)

    # 获取会员等级对应的每日积分
    mem = (await db.execute(select(Membership).where(Membership.tier == cred.tier))).scalar_one_or_none()
    daily_credits = mem.daily_login_credits if mem else 10

    now = datetime.utcnow()
    if cred.last_signin_at:
        delta = now - cred.last_signin_at
        if delta.days < 1 and delta.seconds < 86400:
            # 今天已签到
            return {"ok": False, "msg": "今日已签到", "credits": cred.credits, "streak": cred.signin_streak}

        if delta.days <= 2:
            cred.signin_streak = (cred.signin_streak or 0) + 1
        else:
            cred.signin_streak = 1
    else:
        cred.signin_streak = 1

    # 连续签到加成（最高 7 天 + 50%）
    bonus = min(cred.signin_streak, 7) * 0.1
    amount = int(daily_credits * (1 + bonus))

    cred.credits += amount
    cred.total_earned += amount
    cred.last_signin_at = now

    tx = CreditTransaction(
        user_id=cred.user_id,
        tx_type="signin",
        amount=amount,
        description=f"每日签到（连续 {cred.signin_streak} 天）",
    )
    db.add(tx)
    await db.commit()

    return {
        "ok": True,
        "credits": cred.credits,
        "earned": amount,
        "streak": cred.signin_streak,
        "msg": f"签到成功！获得 {amount} 积分",
    }


@router.post("/credits/spend")
async def spend_credits(
    amount: float,
    description: str = "",
    related_task_id: Optional[int] = None,
    related_project_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """消耗积分（内部 API）"""
    cred = await _get_or_create_credits(db)
    if cred.credits < amount:
        raise HTTPException(400, f"积分不足，需要 {amount}，当前 {cred.credits}")
    cred.credits -= amount
    cred.total_used += amount

    tx = CreditTransaction(
        user_id=cred.user_id,
        tx_type="generation",
        amount=-amount,
        description=description,
        related_task_id=related_task_id,
        related_project_id=related_project_id,
    )
    db.add(tx)
    await db.commit()
    return {"ok": True, "credits": cred.credits}


@router.post("/credits/upgrade")
async def upgrade_membership(
    tier: str,
    duration_months: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """升级会员（模拟支付）"""
    cred = await _get_or_create_credits(db)

    mem = (await db.execute(select(Membership).where(Membership.tier == tier))).scalar_one_or_none()
    if not mem:
        raise HTTPException(404, "会员计划不存在")

    cred.tier = tier
    cred.credits += mem.monthly_credits * duration_months
    cred.expires_at = datetime.utcnow() + timedelta(days=30 * duration_months)
    cred.total_earned += mem.monthly_credits * duration_months

    tx = CreditTransaction(
        user_id=cred.user_id,
        tx_type="purchase",
        amount=mem.monthly_credits * duration_months,
        description=f"开通 {mem.name} {duration_months} 个月",
    )
    db.add(tx)
    await db.commit()
    return {"ok": True, "credits": cred.credits, "tier": tier}


@router.get("/credits/transactions")
async def list_transactions(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """积分流水"""
    cred = await _get_or_create_credits(db)
    stmt = select(CreditTransaction).where(
        CreditTransaction.user_id == cred.user_id
    ).order_by(desc(CreditTransaction.created_at)).limit(limit)
    items = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": t.id,
            "type": t.tx_type,
            "amount": t.amount,
            "description": t.description,
            "created_at": t.created_at.isoformat(),
        }
        for t in items
    ]


# ============== 模型目录 ==============

@router.get("/models")
async def list_models(
    model_type: str = "",
    vendor: str = "",
    db: AsyncSession = Depends(get_db),
):
    """模型目录 - 聚合模型（Seedance/可灵/即梦/万相/Nano Banana/Midjourney 等）"""
    stmt = select(ModelCatalog).where(ModelCatalog.enabled == True)
    if model_type:
        stmt = stmt.where(ModelCatalog.model_type == model_type)
    if vendor:
        stmt = stmt.where(ModelCatalog.vendor == vendor)
    stmt = stmt.order_by(desc(ModelCatalog.is_recommended), ModelCatalog.sort_order)
    items = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "vendor": m.vendor,
            "icon": m.icon,
            "model_type": m.model_type,
            "description": m.description,
            "features": m.features or [],
            "specs": m.specs or {},
            "credits_per_second": m.credits_per_second,
            "credits_per_image": m.credits_per_image,
            "is_premium": m.is_premium,
            "is_recommended": m.is_recommended,
        }
        for m in items
    ]


# ============== 画风库 ==============

@router.get("/art-styles")
async def list_art_styles(
    category: str = "",
    db: AsyncSession = Depends(get_db),
):
    """画风库 - 模仿 Seko 画风库"""
    stmt = select(ArtStyleLibrary).where(ArtStyleLibrary.enabled == True)
    if category:
        stmt = stmt.where(ArtStyleLibrary.category == category)
    stmt = stmt.order_by(desc(ArtStyleLibrary.is_new), ArtStyleLibrary.sort_order)
    items = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "category": a.category,
            "description": a.description,
            "visual_prompt": a.visual_prompt,
            "cover_url": a.cover_url,
            "tags": a.tags or [],
            "is_new": a.is_new,
        }
        for a in items
    ]


# ============== 业务查询 ==============

@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """首页仪表盘数据"""
    from app.models.generation_task import GenerationTask
    from app.models.inspiration import Inspiration

    project_count = (await db.execute(select(func.count(Project.id)))).scalar() or 0
    task_count = (await db.execute(select(func.count(GenerationTask.id)))).scalar() or 0
    task_running = (await db.execute(
        select(func.count(GenerationTask.id)).where(
            GenerationTask.status.in_(["pending", "running"])
        )
    )).scalar() or 0
    episode_count = (await db.execute(select(func.count(Episode.id)))).scalar() or 0
    inspiration_count = (await db.execute(
        select(func.count(Inspiration.id)).where(Inspiration.published == True)
    )).scalar() or 0

    cred = await _get_or_credits(db)
    return {
        "projects": project_count,
        "episodes": episode_count,
        "tasks": task_count,
        "tasks_running": task_running,
        "inspirations": inspiration_count,
        "credits": cred.credits,
        "tier": cred.tier,
    }


from sqlalchemy import func  # noqa
async def _get_or_credits(db: AsyncSession) -> UserCredits:
    return await _get_or_create_credits(db)