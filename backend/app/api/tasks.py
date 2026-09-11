"""生成任务队列 API"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.ai.gateway import ai_gateway
from app.models.generation_task import GenerationTask
from app.models.shot import Shot
from app.models.character import Character
from app.models.scene import Scene
from app.models.prop import Prop
from app.schemas.task import TaskCreate, TaskOut, TaskListItem

router = APIRouter()


async def _enrich_task(db: AsyncSession, task: GenerationTask) -> TaskListItem:
    item = TaskListItem.model_validate(task)
    # 补充目标标题
    if task.shot_id:
        sh = (await db.execute(select(Shot).where(Shot.id == task.shot_id))).scalar_one_or_none()
        if sh:
            item.shot_code = sh.shot_code
            item.target_title = sh.description or sh.shot_code
    elif task.character_id:
        c = (await db.execute(select(Character).where(Character.id == task.character_id))).scalar_one_or_none()
        if c:
            item.target_title = c.name or c.alias
    elif task.scene_id:
        s = (await db.execute(select(Scene).where(Scene.id == task.scene_id))).scalar_one_or_none()
        if s:
            item.target_title = s.name
    elif task.prop_id:
        p = (await db.execute(select(Prop).where(Prop.id == task.prop_id))).scalar_one_or_none()
        if p:
            item.target_title = p.name
    return item


@router.get("/generation/tasks", response_model=List[TaskListItem])
async def list_tasks(
    project_id: int = 0,
    status: str = "",
    task_type: str = "",
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GenerationTask).order_by(desc(GenerationTask.created_at))
    if project_id:
        stmt = stmt.where(GenerationTask.project_id == project_id)
    if status:
        if status == "running":
            stmt = stmt.where(GenerationTask.status.in_(["pending", "running"]))
        else:
            stmt = stmt.where(GenerationTask.status == status)
    if task_type:
        stmt = stmt.where(GenerationTask.task_type == task_type)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [await _enrich_task(db, t) for t in tasks]


@router.get("/generation/tasks/{task_id}", response_model=TaskListItem)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = (await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    return await _enrich_task(db, task)


@router.post("/projects/{project_id}/generation/image")
async def enqueue_image_generation(
    project_id: int,
    prompt: str = "",
    negative_prompt: str = "",
    shot_id: Optional[int] = None,
    character_id: Optional[int] = None,
    scene_id: Optional[int] = None,
    prop_id: Optional[int] = None,
    view: str = "closeup",
    background: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """提交图片生成任务（同步返回 URL）

    关键修复：当指定了 character_id/scene_id/shot_id 时，不再直接用调用方
    传来的 prompt（以前画布传的是节点标题=角色名，导致生成不相干图片），
    而是基于实体的完整设定构造专业 prompt（外貌锚点+场景+镜头语言+画风）。
    """
    from app.ai import prompts as P

    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    art_style = project.art_style if project else ""

    ref_images: Optional[List[str]] = None
    final_prompt = prompt
    final_negative = negative_prompt

    if character_id:
        ch = (await db.execute(select(Character).where(Character.id == character_id))).scalar_one_or_none()
        if not ch:
            raise HTTPException(404, "角色不存在")
        char_dict = {
            "name": ch.name, "alias": ch.alias, "age": ch.age, "gender": ch.gender,
            "appearance": ch.appearance, "outfit": ch.outfit,
        }
        # prompt 为空或只是角色名时 → 用专业角色 prompt；否则视为用户的额外要求
        extra = "" if (not prompt or prompt.strip() == ch.name) else prompt
        final_prompt = P.build_character_prompt(char_dict, art_style, view, extra)
        final_negative = P.CHARACTER_NEGATIVE
        ref_images = [ch.portrait_url] if ch.portrait_url else None
    elif scene_id:
        sc = (await db.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
        if not sc:
            raise HTTPException(404, "场景不存在")
        scene_dict = {
            "name": sc.name, "location": sc.location, "time_of_day": sc.time_of_day,
            "weather": sc.weather, "mood": sc.mood, "description": sc.description,
            "visual_prompt": sc.visual_prompt,
        }
        extra = "" if (not prompt or prompt.strip() == sc.name) else prompt
        final_prompt = P.build_scene_prompt(scene_dict, art_style, extra)
        final_negative = P.SCENE_NEGATIVE
    elif shot_id:
        sh = (await db.execute(select(Shot).where(Shot.id == shot_id))).scalar_one_or_none()
        if not sh:
            raise HTTPException(404, "镜头不存在")
        scene = None
        if sh.scene_id:
            scene = (await db.execute(select(Scene).where(Scene.id == sh.scene_id))).scalar_one_or_none()
        chars = []
        if sh.character_ids:
            chars = list((await db.execute(
                select(Character).where(Character.id.in_(sh.character_ids))
            )).scalars().all())
        shot_dict = {
            "description": sh.description, "visual_prompt": sh.visual_prompt,
            "composition": sh.composition, "camera_movement": sh.camera_movement,
            "camera_angle": sh.camera_angle,
        }
        scene_dict = None
        if scene:
            scene_dict = {
                "name": scene.name, "location": scene.location, "time_of_day": scene.time_of_day,
                "weather": scene.weather, "description": scene.description,
                "visual_prompt": scene.visual_prompt,
            }
        extra = "" if (not prompt or prompt.strip() == (sh.shot_code or "")) else prompt
        final_prompt = P.build_shot_prompt(shot_dict, chars, scene_dict, art_style, extra)
        final_negative = P.build_shot_negative(shot_dict, len(chars))
        ref_images = [c.portrait_url for c in chars if c.portrait_url][:2] or None

    if not final_prompt:
        raise HTTPException(400, "请提供 prompt 或指定生成目标（角色/场景/分镜）")

    task = GenerationTask(
        project_id=project_id,
        task_type="image",
        shot_id=shot_id,
        character_id=character_id,
        scene_id=scene_id,
        prop_id=prop_id,
        prompt=final_prompt,
        negative_prompt=final_negative,
        status="running",
        progress=20,
        phase="图片生成",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 调用 AI 网关
    started = datetime.utcnow()
    result = await ai_gateway.generate_image(
        final_prompt, final_negative,
        width=1280 if shot_id or scene_id else 1024,
        height=720 if shot_id or scene_id else 1024,
        reference_images=ref_images,
    )
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)

    url = result.get("url", "")
    task.output_url = url
    task.model_name = result.get("model", "")
    task.duration_ms = duration_ms
    task.status = "success" if url else "failed"
    if not url:
        task.error_msg = result.get("error", "图片模型未返回结果")
    task.progress = 100
    task.finished_at = datetime.utcnow()
    await db.commit()

    # 回填到对应实体 + 同步画布节点缩略图
    if url:
        from app.models.canvas import CanvasNode

        async def sync_node(node_type: str, ref_id: int):
            node = (await db.execute(
                select(CanvasNode).where(
                    CanvasNode.project_id == project_id,
                    CanvasNode.node_type == node_type,
                    CanvasNode.ref_id == ref_id,
                )
            )).scalars().first()
            if node:
                node.thumbnail_url = url

        if shot_id:
            sh = (await db.execute(select(Shot).where(Shot.id == shot_id))).scalar_one_or_none()
            if sh:
                sh.image_url = url
                sh.status = "imaged"
            await sync_node("shot", shot_id)
        elif character_id:
            ch = (await db.execute(select(Character).where(Character.id == character_id))).scalar_one_or_none()
            if ch:
                ch.portrait_url = url
                views = dict(ch.view_images or {})
                views[view] = url
                ch.view_images = views
            await sync_node("character", character_id)
        elif scene_id:
            sc = (await db.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
            if sc:
                sc.panorama_url = url
            await sync_node("scene", scene_id)

    await db.commit()
    await db.refresh(task)

    return await _enrich_task(db, task)


@router.post("/projects/{project_id}/generation/video")
async def enqueue_video_generation(
    project_id: int,
    prompt: str = "",
    image_url: str = "",
    duration: int = 5,
    shot_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """提交视频生成任务（异步，返回 task_id）

    自动组装丰富 prompt：
    - 如果传了 shot_id：根据分镜 description/composition/运镜 + 关联场景 + 角色外貌 + 项目风格
      生成多段式画面描述，远比前端传的短 title 准确
    - 没传 shot_id：使用原始 prompt（兜底）
    """
    from app.services.video_prompt_builder import build_shot_video_prompt

    final_prompt = (prompt or "").strip()
    shot_meta: Dict[str, Any] = {}

    if shot_id:
        rich_prompt, shot_meta = await build_shot_video_prompt(
            db, project_id, shot_id, fallback_title=prompt or ""
        )
        # 优先用丰富 prompt；如果用户给的 prompt 比自动的还长且不像 shot_code，保留它作为补充
        if rich_prompt and len(rich_prompt) > len(final_prompt):
            final_prompt = rich_prompt
        # 从 shot 自动取 image_url（如果前端没传）
        if not image_url:
            shot_row = (await db.execute(
                select(Shot).where(Shot.id == shot_id, Shot.project_id == project_id)
            )).scalar_one_or_none()
            if shot_row:
                image_url = shot_row.image_url or ""
                if not duration or duration == 5:
                    duration = int(shot_row.duration_sec or 5)

    task = GenerationTask(
        project_id=project_id,
        task_type="video",
        shot_id=shot_id,
        prompt=final_prompt,
        params={
            "image_url": image_url,
            "duration": duration,
            "raw_prompt": prompt,
            **shot_meta,
        },
        status="running",
        progress=10,
        phase="视频生成",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    result = await ai_gateway.generate_video(final_prompt, image_url, duration)
    task.external_task_id = result.get("task_id", "")
    task.model_name = result.get("model", "")

    if result.get("status") == "failed":
        task.status = "failed"
        task.error_msg = result.get("error", "视频生成失败")
        task.progress = 100
        task.finished_at = datetime.utcnow()
    else:
        task.status = "running"  # 视频生成通常较长，等待轮询

    await db.commit()
    await db.refresh(task)
    return await _enrich_task(db, task)


@router.post("/projects/{project_id}/generation/audio-separate")
async def audio_separate(
    project_id: int,
    video_url: str,
    db: AsyncSession = Depends(get_db),
):
    """音频分离：人声/配乐/环境声"""
    task = GenerationTask(
        project_id=project_id,
        task_type="audio_separator",
        status="running",
        progress=30,
        phase="音频分离",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    result = await ai_gateway.audio_separator(video_url)
    task.output_url = result.get("vocals_url", "")
    task.output_meta = result
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return await _enrich_task(db, task)


@router.post("/projects/{project_id}/generation/lipsync")
async def lipsync(
    project_id: int,
    video_url: str,
    audio_url: str,
    shot_id: Optional[int] = None,
    characters: str = "",  # 逗号分隔的角色名
    db: AsyncSession = Depends(get_db),
):
    """多角色口型同步"""
    char_list = [c.strip() for c in characters.split(",") if c.strip()]
    task = GenerationTask(
        project_id=project_id,
        task_type="lipsync",
        shot_id=shot_id,
        status="running",
        progress=20,
        phase="SekoTalk 口型同步",
        params={"video_url": video_url, "audio_url": audio_url, "characters": char_list},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    result = await ai_gateway.lipsync(video_url, audio_url, char_list)
    task.output_url = result.get("url", video_url)
    task.output_meta = result
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return await _enrich_task(db, task)


@router.post("/generation/tasks/{task_id}/cancel")
async def cancel_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = (await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status in ["pending", "running"]:
        task.status = "cancelled"
        task.finished_at = datetime.utcnow()
        await db.commit()
    return await _enrich_task(db, task)


@router.delete("/generation/tasks/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = (await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "任务不存在")
    await db.delete(task)
    await db.commit()
    return {"ok": True}