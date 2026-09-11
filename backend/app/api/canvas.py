"""无限画布 API - 节点/连线"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.canvas import CanvasNode, CanvasEdge
from app.models.shot import Shot
from app.models.character import Character
from app.models.scene import Scene
from app.schemas.task import (
    CanvasNodeCreate, CanvasNodeUpdate, CanvasNodeOut,
    CanvasEdgeCreate, CanvasEdgeOut, CanvasSnapshot,
)

router = APIRouter()


@router.get("/projects/{project_id}/canvas", response_model=CanvasSnapshot)
async def get_canvas(project_id: int, db: AsyncSession = Depends(get_db)):
    nodes = (await db.execute(
        select(CanvasNode).where(CanvasNode.project_id == project_id)
    )).scalars().all()
    edges = (await db.execute(
        select(CanvasEdge).where(CanvasEdge.project_id == project_id)
    )).scalars().all()

    # 收集 ref_id → 实体的映射（角色 / 场景 / 分镜）
    char_ids = [n.ref_id for n in nodes if n.node_type == "character" and n.ref_id]
    scene_ids = [n.ref_id for n in nodes if n.node_type == "scene" and n.ref_id]
    shot_ids = [n.ref_id for n in nodes if n.node_type == "shot" and n.ref_id]

    name_by_char: dict[int, dict] = {}
    if char_ids:
        for c in (await db.execute(select(Character).where(Character.id.in_(char_ids)))).scalars().all():
            name_by_char[c.id] = {"name": c.name or "", "alias": c.alias or ""}

    name_by_scene: dict[int, dict] = {}
    if scene_ids:
        for s in (await db.execute(select(Scene).where(Scene.id.in_(scene_ids)))).scalars().all():
            name_by_scene[s.id] = {"name": s.name or "", "location": s.location or ""}

    shot_by_id: dict[int, Shot] = {}
    video_by_shot: dict[int, str] = {}
    if shot_ids:
        shots = (await db.execute(select(Shot).where(Shot.id.in_(shot_ids)))).scalars().all()
        for s in shots:
            shot_by_id[s.id] = s
            if s.video_url:
                video_by_shot[s.id] = s.video_url

    out_nodes = []
    for n in nodes:
        item = CanvasNodeOut.model_validate(n)

        # 角色节点：把名字/别名回填到 title；额外信息进 meta（前端可展示）
        if n.node_type == "character" and n.ref_id in name_by_char:
            info = name_by_char[n.ref_id]
            if not item.title:
                item.title = info["name"] or info["alias"] or "未命名角色"
            item.meta = {
                **(item.meta or {}),
                "name": info["name"],
                "alias": info["alias"],
            }

        # 场景节点：把场景名 + 地点回填
        elif n.node_type == "scene" and n.ref_id in name_by_scene:
            info = name_by_scene[n.ref_id]
            if not item.title:
                item.title = info["name"] or info["location"] or "未命名场景"
            item.meta = {
                **(item.meta or {}),
                "name": info["name"],
                "location": info["location"],
            }

        # 分镜节点：title 优先用 shot_code + 描述摘要；meta 携带完整描述便于卡片显示
        elif n.node_type == "shot" and n.ref_id in shot_by_id:
            sh = shot_by_id[n.ref_id]
            extra_meta: dict = {
                "shot_code": sh.shot_code or "",
                "description": sh.description or "",
                "composition": sh.composition or "",
                "camera_movement": sh.camera_movement or "",
            }
            if not item.title:
                item.title = sh.shot_code or f"SC{sh.shot_no:02d}"
            item.meta = {**(item.meta or {}), **extra_meta}

        # 视频 URL 富化（分镜）
        if n.node_type == "shot" and n.ref_id in video_by_shot:
            item.meta = {**(item.meta or {}), "video_url": video_by_shot[n.ref_id]}

        out_nodes.append(item)

    return CanvasSnapshot(
        nodes=out_nodes,
        edges=[CanvasEdgeOut.model_validate(e) for e in edges],
    )


@router.post("/projects/{project_id}/canvas/nodes", response_model=CanvasNodeOut)
async def create_node(project_id: int, data: CanvasNodeCreate, db: AsyncSession = Depends(get_db)):
    node = CanvasNode(project_id=project_id, **data.model_dump())
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


@router.patch("/canvas/nodes/{nid}", response_model=CanvasNodeOut)
async def update_node(nid: int, data: CanvasNodeUpdate, db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(CanvasNode).where(CanvasNode.id == nid))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "节点不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(node, k, v)
    await db.commit()
    await db.refresh(node)
    return node


@router.delete("/canvas/nodes/{nid}")
async def delete_node(nid: int, db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(CanvasNode).where(CanvasNode.id == nid))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "节点不存在")
    # 先删相关连线
    await db.execute(delete(CanvasEdge).where(
        (CanvasEdge.source_id == nid) | (CanvasEdge.target_id == nid)
    ))
    await db.delete(node)
    await db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/canvas/edges", response_model=CanvasEdgeOut)
async def create_edge(project_id: int, data: CanvasEdgeCreate, db: AsyncSession = Depends(get_db)):
    # 校验源/目标存在
    src = (await db.execute(select(CanvasNode).where(CanvasNode.id == data.source_id))).scalar_one_or_none()
    tgt = (await db.execute(select(CanvasNode).where(CanvasNode.id == data.target_id))).scalar_one_or_none()
    if not src or not tgt:
        raise HTTPException(400, "源节点或目标节点不存在")

    edge = CanvasEdge(project_id=project_id, **data.model_dump())
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


@router.delete("/canvas/edges/{eid}")
async def delete_edge(eid: int, db: AsyncSession = Depends(get_db)):
    edge = (await db.execute(select(CanvasEdge).where(CanvasEdge.id == eid))).scalar_one_or_none()
    if not edge:
        raise HTTPException(404, "连线不存在")
    await db.delete(edge)
    await db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/canvas/repair-shot-relations")
async def repair_shot_relations(project_id: int, db: AsyncSession = Depends(get_db)):
    """批量修复孤儿 shot（scene_id=None 或 character_ids=[]）的关联关系

    用于 AI 返回字段缺失、apply-to-canvas 旧版本等历史问题。
    """
    from app.services.shot_repair import repair_project_shots

    result = await repair_project_shots(db, project_id=project_id)
    return result