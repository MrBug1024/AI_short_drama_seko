"""项目管理 API"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.project import Project
from app.models.episode import Episode
from app.models.character import Character
from app.models.scene import Scene
from app.models.shot import Shot
from app.models.generation_task import GenerationTask
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectListOut,
    EpisodeCreate, EpisodeUpdate, EpisodeOut,
)
from app.services.creation import creation_service

router = APIRouter()


async def _enrich_project(db: AsyncSession, project: Project) -> ProjectOut:
    """补充项目的统计字段"""
    ep_count = (await db.execute(
        select(func.count(Episode.id)).where(Episode.project_id == project.id)
    )).scalar() or 0
    ch_count = (await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project.id)
    )).scalar() or 0
    sc_count = (await db.execute(
        select(func.count(Scene.id)).where(Scene.project_id == project.id)
    )).scalar() or 0
    sh_count = (await db.execute(
        select(func.count(Shot.id)).where(Shot.project_id == project.id)
    )).scalar() or 0
    tk_count = (await db.execute(
        select(func.count(GenerationTask.id)).where(GenerationTask.project_id == project.id)
    )).scalar() or 0
    tk_pending = (await db.execute(
        select(func.count(GenerationTask.id)).where(
            GenerationTask.project_id == project.id,
            GenerationTask.status.in_(["pending", "running"]),
        )
    )).scalar() or 0

    out = ProjectOut.model_validate(project)
    out.episode_count = ep_count
    out.character_count = ch_count
    out.scene_count = sc_count
    out.shot_count = sh_count
    out.task_count = tk_count
    out.task_pending = tk_pending
    return out


@router.get("/projects", response_model=ProjectListOut)
async def list_projects(
    keyword: str = "",
    status: str = "",
    limit: int = Query(50, ge=1, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Project).order_by(desc(Project.updated_at))
    if keyword:
        stmt = stmt.where(Project.name.contains(keyword))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    projects = result.scalars().all()

    total = (await db.execute(select(func.count(Project.id)))).scalar() or 0
    enriched = [await _enrich_project(db, p) for p in projects]
    return ProjectListOut(items=enriched, total=total)


@router.post("/projects", response_model=ProjectOut)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(**data.model_dump(exclude={"skill_code"}))
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _enrich_project(db, project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    return await _enrich_project(db, project)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    await db.commit()
    await db.refresh(project)
    return await _enrich_project(db, project)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    await db.delete(project)
    await db.commit()
    return {"ok": True}


# ============== 创作流程 ==============

@router.post("/projects/{project_id}/create")
async def start_creation(
    project_id: int,
    prompt: str = "",
    art_style: str = "",
    skill_code: str = "drama_story",
    db: AsyncSession = Depends(get_db),
):
    """启动 7 步创作流程"""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    use_prompt = prompt or project.prompt
    if not use_prompt:
        raise HTTPException(400, "请输入创意描述")

    return await creation_service.run_full_flow(db, project, use_prompt, art_style, skill_code)


@router.post("/projects/{project_id}/refine")
async def refine_step(
    project_id: int,
    step: str,
    user_prompt: str,
    target_type: str = "",
    target_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """对单个步骤进行优化（如「重新生成剧本」「修改角色外观」）"""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    return await creation_service.refine_step(db, project, step, user_prompt, target_type, target_id)


# ============== Episodes ==============

@router.get("/projects/{project_id}/episodes", response_model=List[EpisodeOut])
async def list_episodes(project_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Episode).where(Episode.project_id == project_id).order_by(Episode.episode_no)
    result = await db.execute(stmt)
    eps = result.scalars().all()

    out = []
    for ep in eps:
        sc = (await db.execute(
            select(func.count(Shot.id)).where(Shot.episode_id == ep.id)
        )).scalar() or 0
        item = EpisodeOut.model_validate(ep)
        item.shot_count = sc
        out.append(item)
    return out


@router.post("/projects/{project_id}/episodes", response_model=EpisodeOut)
async def create_episode(project_id: int, data: EpisodeCreate, db: AsyncSession = Depends(get_db)):
    # 自动计算 episode_no
    max_no = (await db.execute(
        select(func.max(Episode.episode_no)).where(Episode.project_id == project_id)
    )).scalar() or 0

    ep = Episode(project_id=project_id, episode_no=max_no + 1, **data.model_dump())
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return EpisodeOut.model_validate(ep)


@router.patch("/episodes/{episode_id}", response_model=EpisodeOut)
async def update_episode(episode_id: int, data: EpisodeUpdate, db: AsyncSession = Depends(get_db)):
    ep = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not ep:
        raise HTTPException(404, "剧集不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(ep, k, v)
    await db.commit()
    await db.refresh(ep)
    return EpisodeOut.model_validate(ep)


@router.delete("/episodes/{episode_id}")
async def delete_episode(episode_id: int, db: AsyncSession = Depends(get_db)):
    ep = (await db.execute(select(Episode).where(Episode.id == episode_id))).scalar_one_or_none()
    if not ep:
        raise HTTPException(404, "剧集不存在")
    await db.delete(ep)
    await db.commit()
    return {"ok": True}