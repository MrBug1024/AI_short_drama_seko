"""无限画布 API - 节点/连线"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.canvas import CanvasNode, CanvasEdge
from app.models.shot import Shot
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

    # 为分镜节点富化视频地址（前端据此显示"视频就绪/可预览"状态）
    shot_ref_ids = [n.ref_id for n in nodes if n.node_type == "shot" and n.ref_id]
    video_by_shot = {}
    if shot_ref_ids:
        shots = (await db.execute(
            select(Shot).where(Shot.id.in_(shot_ref_ids))
        )).scalars().all()
        video_by_shot = {s.id: s.video_url for s in shots if s.video_url}

    out_nodes = []
    for n in nodes:
        item = CanvasNodeOut.model_validate(n)
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