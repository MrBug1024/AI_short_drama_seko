"""角色/场景/道具/分镜 CRUD API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.character import Character
from app.models.scene import Scene
from app.models.prop import Prop
from app.models.shot import Shot
from app.schemas.asset import (
    CharacterCreate, CharacterUpdate, CharacterOut,
    SceneCreate, SceneUpdate, SceneOut,
    PropCreate, PropUpdate, PropOut,
    ShotCreate, ShotUpdate, ShotOut,
)

router = APIRouter()


# ============== Character ==============

@router.get("/projects/{project_id}/characters", response_model=List[CharacterOut])
async def list_characters(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Character).where(Character.project_id == project_id).order_by(Character.id)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/characters", response_model=CharacterOut)
async def create_character(project_id: int, data: CharacterCreate, db: AsyncSession = Depends(get_db)):
    c = Character(project_id=project_id, **data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@router.patch("/characters/{cid}", response_model=CharacterOut)
async def update_character(cid: int, data: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "角色不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return c


@router.delete("/characters/{cid}")
async def delete_character(cid: int, db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "角色不存在")
    await db.delete(c)
    await db.commit()
    return {"ok": True}


# ============== Scene ==============

@router.get("/projects/{project_id}/scenes", response_model=List[SceneOut])
async def list_scenes(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.id)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/scenes", response_model=SceneOut)
async def create_scene(project_id: int, data: SceneCreate, db: AsyncSession = Depends(get_db)):
    s = Scene(project_id=project_id, **data.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@router.patch("/scenes/{sid}", response_model=SceneOut)
async def update_scene(sid: int, data: SceneUpdate, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Scene).where(Scene.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "场景不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return s


@router.delete("/scenes/{sid}")
async def delete_scene(sid: int, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Scene).where(Scene.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "场景不存在")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


# ============== Prop ==============

@router.get("/projects/{project_id}/props", response_model=List[PropOut])
async def list_props(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Prop).where(Prop.project_id == project_id).order_by(Prop.id)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/props", response_model=PropOut)
async def create_prop(project_id: int, data: PropCreate, db: AsyncSession = Depends(get_db)):
    p = Prop(project_id=project_id, **data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@router.patch("/props/{pid}", response_model=PropOut)
async def update_prop(pid: int, data: PropUpdate, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(Prop).where(Prop.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "道具不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


@router.delete("/props/{pid}")
async def delete_prop(pid: int, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(Prop).where(Prop.id == pid))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "道具不存在")
    await db.delete(p)
    await db.commit()
    return {"ok": True}


# ============== Shot ==============

@router.get("/projects/{project_id}/shots", response_model=List[ShotOut])
async def list_shots(
    project_id: int,
    episode_id: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_no)
    if episode_id:
        stmt = stmt.where(Shot.episode_id == episode_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/projects/{project_id}/shots", response_model=ShotOut)
async def create_shot(project_id: int, data: ShotCreate, db: AsyncSession = Depends(get_db)):
    sh = Shot(project_id=project_id, **data.model_dump())
    db.add(sh)
    await db.commit()
    await db.refresh(sh)
    return sh


@router.patch("/shots/{sid}", response_model=ShotOut)
async def update_shot(sid: int, data: ShotUpdate, db: AsyncSession = Depends(get_db)):
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sh, k, v)
    await db.commit()
    await db.refresh(sh)
    return sh


@router.delete("/shots/{sid}")
async def delete_shot(sid: int, db: AsyncSession = Depends(get_db)):
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")
    await db.delete(sh)
    await db.commit()
    return {"ok": True}