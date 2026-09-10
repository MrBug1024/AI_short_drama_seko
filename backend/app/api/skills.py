"""技能市场 API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.skill import Skill
from app.schemas.task import SkillOut

router = APIRouter()


@router.get("/skills", response_model=List[SkillOut])
async def list_skills(
    installed_only: bool = False,
    category: str = "",
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Skill).order_by(Skill.sort_order)
    if installed_only:
        stmt = stmt.where(Skill.installed == True)
    if category:
        stmt = stmt.where(Skill.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/skills/{sid}")
async def toggle_skill(sid: int, installed: bool, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "技能不存在")
    s.installed = installed
    await db.commit()
    await db.refresh(s)
    return SkillOut.model_validate(s)


@router.post("/skills/{sid}/use")
async def record_skill_usage(sid: int, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "技能不存在")
    s.usage_count = (s.usage_count or 0) + 1
    await db.commit()
    return SkillOut.model_validate(s)