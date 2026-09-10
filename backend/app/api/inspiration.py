"""灵感广场 API - 作品发布/浏览/点赞/复刻"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.inspiration import Inspiration
from app.models.project import Project
from app.models.character import Character
from app.models.scene import Scene
from app.models.shot import Shot
from app.models.script import Script

router = APIRouter()


@router.get("/inspirations")
async def list_inspirations(
    category: str = "",
    keyword: str = "",
    tag: str = "",
    featured: bool = False,
    limit: int = Query(30, ge=1, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """浏览灵感广场作品"""
    stmt = select(Inspiration).where(Inspiration.published == True)
    if category:
        stmt = stmt.where(Inspiration.category == category)
    if featured:
        stmt = stmt.where(Inspiration.is_featured == True)
    if keyword:
        stmt = stmt.where(Inspiration.title.contains(keyword))
    stmt = stmt.order_by(desc(Inspiration.is_featured), desc(Inspiration.view_count), desc(Inspiration.created_at))
    stmt = stmt.limit(limit).offset(offset)

    items = (await db.execute(stmt)).scalars().all()

    # 补充项目信息
    out = []
    for item in items:
        proj = (await db.execute(select(Project).where(Project.id == item.project_id))).scalar_one_or_none()
        d = {
            "id": item.id,
            "project_id": item.project_id,
            "title": item.title or (proj.name if proj else ""),
            "description": item.description,
            "cover_url": item.cover_url or (proj.cover_url if proj else ""),
            "video_url": item.video_url,
            "category": item.category,
            "tags": item.tags or [],
            "view_count": item.view_count,
            "like_count": item.like_count,
            "fork_count": item.fork_count,
            "is_featured": item.is_featured,
            "source_skill": item.source_skill,
            "art_style": item.art_style or (proj.art_style if proj else ""),
            "created_at": item.created_at.isoformat() if item.created_at else "",
        }
        if tag and tag not in (item.tags or []):
            continue
        out.append(d)

    total = (await db.execute(
        select(func.count(Inspiration.id)).where(Inspiration.published == True)
    )).scalar() or 0

    return {"items": out, "total": total}


@router.post("/inspirations")
async def publish_inspiration(
    project_id: int,
    title: str = "",
    description: str = "",
    cover_url: str = "",
    video_url: str = "",
    category: str = "drama",
    tags: List[str] = [],
    db: AsyncSession = Depends(get_db),
):
    """发布作品到灵感广场"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")

    insp = Inspiration(
        project_id=project_id,
        title=title or proj.name,
        description=description,
        cover_url=cover_url or proj.cover_url,
        video_url=video_url,
        category=category,
        tags=tags,
        published=True,
        source_skill="",
        art_style=proj.art_style,
    )
    db.add(insp)
    await db.commit()
    await db.refresh(insp)
    return {"id": insp.id, "ok": True}


@router.post("/inspirations/{iid}/like")
async def like_inspiration(iid: int, db: AsyncSession = Depends(get_db)):
    """点赞作品"""
    insp = (await db.execute(select(Inspiration).where(Inspiration.id == iid))).scalar_one_or_none()
    if not insp:
        raise HTTPException(404, "作品不存在")
    insp.like_count = (insp.like_count or 0) + 1
    await db.commit()
    return {"ok": True, "like_count": insp.like_count}


@router.post("/inspirations/{iid}/view")
async def view_inspiration(iid: int, db: AsyncSession = Depends(get_db)):
    """增加浏览数"""
    insp = (await db.execute(select(Inspiration).where(Inspiration.id == iid))).scalar_one_or_none()
    if insp:
        insp.view_count = (insp.view_count or 0) + 1
        await db.commit()
    return {"ok": True}


@router.post("/inspirations/{iid}/fork")
async def fork_inspiration(iid: int, db: AsyncSession = Depends(get_db)):
    """复刻作品到自己的项目"""
    insp = (await db.execute(select(Inspiration).where(Inspiration.id == iid))).scalar_one_or_none()
    if not insp:
        raise HTTPException(404, "作品不存在")

    # 复制源项目作为新项目
    src_proj = (await db.execute(select(Project).where(Project.id == insp.project_id))).scalar_one_or_none()
    if not src_proj:
        raise HTTPException(404, "源项目不存在")

    new_proj = Project(
        name=f"{src_proj.name}（复刻）",
        description=src_proj.description,
        prompt=src_proj.prompt,
        art_style=src_proj.art_style,
        target_episodes=src_proj.target_episodes,
        status="draft",
    )
    db.add(new_proj)
    await db.flush()
    await db.refresh(new_proj)

    # 复制角色
    src_chars = (await db.execute(select(Character).where(Character.project_id == src_proj.id))).scalars().all()
    for c in src_chars:
        nc = Character(
            project_id=new_proj.id,
            name=c.name,
            alias=c.alias,
            age=c.age,
            gender=c.gender,
            role=c.role,
            appearance=c.appearance,
            outfit=c.outfit,
            personality=c.personality,
        )
        db.add(nc)

    # 复制场景
    src_scenes = (await db.execute(select(Scene).where(Scene.project_id == src_proj.id))).scalars().all()
    for s in src_scenes:
        ns = Scene(
            project_id=new_proj.id,
            name=s.name,
            location=s.location,
            time_of_day=s.time_of_day,
            weather=s.weather,
            mood=s.mood,
            description=s.description,
        )
        db.add(ns)

    # 复制剧本
    src_scripts = (await db.execute(select(Script).where(Script.project_id == src_proj.id))).scalars().all()
    for sc in src_scripts:
        ns = Script(
            project_id=new_proj.id,
            version=sc.version,
            title=sc.title,
            logline=sc.logline,
            content=sc.content,
            meta=sc.meta,
        )
        db.add(ns)

    await db.commit()

    # 更新 fork 计数
    insp.fork_count = (insp.fork_count or 0) + 1
    await db.commit()

    return {"ok": True, "new_project_id": new_proj.id}


@router.delete("/inspirations/{iid}")
async def unpublish_inspiration(iid: int, db: AsyncSession = Depends(get_db)):
    """下架作品"""
    insp = (await db.execute(select(Inspiration).where(Inspiration.id == iid))).scalar_one_or_none()
    if not insp:
        raise HTTPException(404, "作品不存在")
    insp.published = False
    await db.commit()
    return {"ok": True}


@router.get("/inspirations/featured")
async def get_featured(db: AsyncSession = Depends(get_db)):
    """获取精选作品"""
    stmt = select(Inspiration).where(
        Inspiration.published == True,
        Inspiration.is_featured == True,
    ).order_by(desc(Inspiration.view_count)).limit(10)
    items = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "cover_url": i.cover_url,
            "category": i.category,
            "view_count": i.view_count,
            "like_count": i.like_count,
        }
        for i in items
    ]