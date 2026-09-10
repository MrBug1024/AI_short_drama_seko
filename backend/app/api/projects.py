"""项目管理 API"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.project import Project
from app.models.episode import Episode
from app.models.character import Character
from app.models.scene import Scene
from app.models.shot import Shot
from app.models.generation_task import GenerationTask
from app.models.user import User
from app.api.auth import get_current_user, get_current_user_optional
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectListOut,
    EpisodeCreate, EpisodeUpdate, EpisodeOut,
)
from app.services.creation import creation_service

router = APIRouter()


def _ensure_can_access(project: Project, current: User):
    """检查当前用户对项目有访问权：公开（owner_id NULL）项目所有人可读；
    私有项目仅 owner 可访问。"""
    if project.owner_id is None:
        return  # 公开项目，匿名/任意登录用户可访问
    if current is None or current.id != project.owner_id:
        raise HTTPException(status_code=403, detail="无权访问该项目")


def _ensure_can_modify(project: Project, current: User):
    """仅 owner 可修改/删除/创作；公开项目也仅 owner 可改（兼容历史）。"""
    if project.owner_id is None:
        # 公开项目：未绑定 owner，绑定当前用户后才能改
        return
    if current.id != project.owner_id:
        raise HTTPException(status_code=403, detail="无权操作该项目")


async def _enrich_project(db: AsyncSession, project: Project) -> ProjectOut:
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
    current: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    # 可见性：未登录 → 只看公开项目（owner_id IS NULL）
    #         登录   → 看自己的 + 公开项目
    if current is None:
        visibility = Project.owner_id.is_(None)
    else:
        visibility = or_(Project.owner_id == current.id, Project.owner_id.is_(None))

    stmt = select(Project).where(visibility).order_by(desc(Project.updated_at))
    if keyword:
        stmt = stmt.where(Project.name.contains(keyword), visibility)
    if status:
        stmt = stmt.where(Project.status == status, visibility)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    projects = result.scalars().all()

    total = (await db.execute(
        select(func.count(Project.id)).where(visibility)
    )).scalar() or 0
    enriched = [await _enrich_project(db, p) for p in projects]
    return ProjectListOut(items=enriched, total=total)


@router.post("/projects", response_model=ProjectOut)
async def create_project(
    data: ProjectCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(**data.model_dump(exclude={"skill_code"}))
    project.owner_id = current.id
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _enrich_project(db, project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    current: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    _ensure_can_access(project, current)
    return await _enrich_project(db, project)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    _ensure_can_modify(project, current)

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    await db.commit()
    await db.refresh(project)
    return await _enrich_project(db, project)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    _ensure_can_modify(project, current)
    await db.delete(project)
    await db.commit()
    return {"ok": True}


# ============== 创作流程 ==============

class StartCreationBody(BaseModel):
    """启动 7 步创作流程的请求体（用 body 避免长 prompt 触发 431）"""
    prompt: str = Field("", description="创意描述/灵感正文")
    art_style: str = Field("", description="美术风格")
    skill_code: str = Field("drama_story", description="创作技能")


@router.post("/projects/{project_id}/create")
async def start_creation(
    project_id: int,
    current: User = Depends(get_current_user),
    body: Optional[StartCreationBody] = None,
    prompt: str = "",
    art_style: str = "",
    skill_code: str = "drama_story",
    db: AsyncSession = Depends(get_db),
):
    """启动 7 步创作流程

    同时支持两种入参：
    - 旧 query 形式：?prompt=...（保留兼容）
    - 新 body 形式：{"prompt":"..."}（推荐，避免 431）
    body 优先于 query；body 与 query 都没传则回退 project.prompt。
    """
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    _ensure_can_modify(project, current)
    # 如果项目还没有 owner，顺手绑定到当前用户（兼容历史公开项目）
    if project.owner_id is None:
        project.owner_id = current.id

    use_prompt = ""
    use_style = ""
    use_skill = "drama_story"
    if body:
        use_prompt = body.prompt or ""
        use_style = body.art_style or ""
        use_skill = body.skill_code or "drama_story"
    if not use_prompt:
        use_prompt = prompt or project.prompt
    if not use_style:
        use_style = art_style or project.art_style or ""
    if not use_skill or use_skill == "drama_story":
        if skill_code:
            use_skill = skill_code

    if not use_prompt:
        raise HTTPException(400, "请输入创意描述")

    return await creation_service.run_full_flow(db, project, use_prompt, use_style, use_skill)


@router.post("/projects/{project_id}/refine")
async def refine_step(
    project_id: int,
    step: str,
    user_prompt: str,
    target_type: str = "",
    target_id: Optional[int] = None,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对单个步骤进行优化（如「重新生成剧本」「修改角色外观」）"""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")
    _ensure_can_modify(project, current)
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