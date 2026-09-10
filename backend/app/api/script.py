"""剧本解析与高级生成 API

模仿 Seko 的「剧本解析能力全面优化」：
- 支持旁白解说/剧情剧本/分镜表三种格式
- 自动识别角色/道具/场景
- 提取分镜+台词+音效+镜头时长
"""
import json
import re
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ai.gateway import ai_gateway
from app.models.project import Project
from app.models.script import Script
from app.models.character import Character
from app.models.scene import Scene
from app.models.prop import Prop
from app.models.shot import Shot
from app.models.canvas import CanvasNode
from app.models.generation_task import GenerationTask
from app.services.creation import creation_service

router = APIRouter()


PARSE_SCRIPT_PROMPT = """你是一个专业的剧本解析 Agent，能识别三种格式：
1. **旁白解说**：包含「旁白：」「画面：」字段
2. **剧情剧本**：标准剧本格式（场景+角色+台词+动作）
3. **分镜表**：以 SC01/SC02/SC03 编号开头的分镜表

请将输入解析为 JSON：
{
    "format": "narration|drama|storyboard",
    "title": "剧名",
    "logline": "一句话故事",
    "characters": [{"name": "角色", "role": "主角/配角"}],
    "scenes": [{"name": "场景", "location": "地点", "time": "时间"}],
    "props": [{"name": "道具", "category": "类别"}],
    "shots": [
        {
            "shot_code": "SC01",
            "description": "画面描述",
            "camera": "运镜方式",
            "dialogue": "台词（若有）",
            "narration": "旁白（若有）",
            "duration_sec": 5
        }
    ]
}

严格要求：
1. 只输出合法 JSON，不要任何 markdown 标记
2. 镜头时长 3-8 秒
3. 中文输出
4. 保持原剧本的剧情和节奏，不要增删内容
"""


class ParseScriptBody(BaseModel):
    """解析剧本请求体 - 用 body 传长文本，避免 431 Request Header Fields Too Large"""
    script_text: str = Field(..., min_length=10, description="完整剧本文本（旁白/剧情/分镜表）")
    format_hint: str = Field("auto", description="格式提示：auto/narration/drama/storyboard")


@router.post("/projects/{project_id}/parse-script")
async def parse_script(
    project_id: int,
    body: ParseScriptBody,
    db: AsyncSession = Depends(get_db),
):
    """解析用户上传的剧本（旁白/剧情/分镜表三种格式）

    重要修复：原来用 query 传脚本，剧本太长时会被 HTTP 客户端拒绝（431 错误）。
    现改为 JSON body 接收，无大小限制（除服务端 nginx/反代之外）。
    """
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    script_text = body.script_text
    format_hint = body.format_hint

    task = GenerationTask(
        project_id=project_id,
        task_type="script_parse",
        status="running",
        progress=30,
        phase="剧本解析",
        prompt=script_text[:200],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 调用 LLM 解析
    user_prompt = f"剧本格式提示：{format_hint}\n\n剧本内容：\n{script_text}"
    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": PARSE_SCRIPT_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
        temperature=0.5,
    )

    try:
        data = json.loads(result["content"])
    except Exception as e:
        task.status = "failed"
        task.error_msg = f"解析失败：{e}"
        await db.commit()
        return {"ok": False, "error": str(e), "raw": result["content"][:500]}

    # 写入数据库 - 单版本覆盖：删除旧脚本版本后再写入新版本
    from app.models.script import Script as ScriptModel
    old_scripts = (await db.execute(
        select(ScriptModel).where(ScriptModel.project_id == project_id)
    )).scalars().all()
    for old in old_scripts:
        await db.delete(old)
    await db.flush()

    script = Script(
        project_id=project_id,
        version=1,
        title=data.get("title", project.name),
        logline=data.get("logline", ""),
        content=script_text,
        meta=data,
        source_task_id=str(task.id),
    )
    db.add(script)

    # 角色
    char_map = {}
    for c in data.get("characters", []):
        existing = (await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.name == c.get("name", ""),
            )
        )).scalar_one_or_none()
        if existing:
            char_map[c.get("name", "")] = existing.id
            continue
        character = Character(
            project_id=project_id,
            name=c.get("name", ""),
            role=c.get("role", ""),
        )
        db.add(character)
        await db.flush()
        char_map[c.get("name", "")] = character.id

    # 场景
    scene_map = {}
    for s in data.get("scenes", []):
        existing = (await db.execute(
            select(Scene).where(
                Scene.project_id == project_id,
                Scene.name == s.get("name", ""),
            )
        )).scalar_one_or_none()
        if existing:
            scene_map[s.get("name", "")] = existing.id
            continue
        scene = Scene(
            project_id=project_id,
            name=s.get("name", ""),
            location=s.get("location", ""),
            time_of_day=s.get("time", "day"),
            description=s.get("description", ""),
        )
        db.add(scene)
        await db.flush()
        scene_map[s.get("name", "")] = scene.id

    # 道具
    for p in data.get("props", []):
        prop = Prop(
            project_id=project_id,
            name=p.get("name", ""),
            category=p.get("category", ""),
        )
        db.add(prop)

    # 镜头（关键！）
    for idx, sh in enumerate(data.get("shots", []), 1):
        shot = Shot(
            project_id=project_id,
            shot_no=idx,
            shot_code=sh.get("shot_code", f"SC{idx:02d}"),
            description=sh.get("description", ""),
            camera_movement=sh.get("camera", ""),
            dialogue=sh.get("dialogue", ""),
            narration=sh.get("narration", ""),
            duration_sec=sh.get("duration_sec", 5),
            visual_prompt=sh.get("description", ""),
        )
        db.add(shot)

    project.status = "draft"
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()
    await db.commit()

    shot_count = len(data.get("shots", []))
    char_count = len(data.get("characters", []))
    scene_count = len(data.get("scenes", []))

    return {
        "ok": True,
        "task_id": task.id,
        "script_id": script.id,
        "format": data.get("format", format_hint),
        "shot_count": shot_count,
        "character_count": char_count,
        "scene_count": scene_count,
    }


@router.post("/projects/{project_id}/multi-episode-split")
async def split_multi_episode(
    project_id: int,
    total_episodes: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """把项目拆分为多剧集（自动分配剧情到每一集）"""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()

    if not script:
        raise HTTPException(400, "请先创建剧本")

    task = GenerationTask(
        project_id=project_id,
        task_type="episode_split",
        status="running",
        progress=20,
        phase="多剧集拆分",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 让 AI 把剧本拆成 N 集
    prompt = f"""把以下剧本大纲拆分为 {total_episodes} 集短剧。

剧本梗概：{script.logline}
剧本内容：{script.content[:2000]}

输出 JSON：
{{
    "episodes": [
        {{"episode_no": 1, "title": "第1集标题", "synopsis": "本集梗概（100字内）", "key_events": ["事件1", "事件2"]}},
        ...
    ]
}}

要求：
- 每集剧情连贯
- 每集梗概不超过 100 字
- 保持原作剧情走向
"""
    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": "你是专业的短剧编剧，擅长分集编排。"},
            {"role": "user", "content": prompt},
        ],
        json_mode=True,
        temperature=0.6,
    )

    try:
        data = json.loads(result["content"])
    except Exception as e:
        task.status = "failed"
        task.error_msg = str(e)
        await db.commit()
        return {"ok": False, "error": str(e)}

    # 写入剧集
    from app.models.episode import Episode

    # 清空旧剧集
    old_eps = (await db.execute(select(Episode).where(Episode.project_id == project_id))).scalars().all()
    for ep in old_eps:
        await db.delete(ep)
    await db.flush()

    for e in data.get("episodes", []):
        ep = Episode(
            project_id=project_id,
            episode_no=e.get("episode_no", 1),
            title=e.get("title", ""),
            synopsis=e.get("synopsis", ""),
            status="draft",
        )
        db.add(ep)

    project.target_episodes = total_episodes
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()
    await db.commit()

    return {
        "ok": True,
        "task_id": task.id,
        "episodes": data.get("episodes", []),
        "total": len(data.get("episodes", [])),
    }


async def _run_batch_images_bg(project_id: int, task_ids: List[int]):
    """后台逐个生成分镜图：每完成一个立即 commit，前端轮询可渐进看到效果"""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        tasks = (await db.execute(
            select(GenerationTask).where(GenerationTask.id.in_(task_ids)).order_by(GenerationTask.id)
        )).scalars().all()

        for task in tasks:
            task.status = "running"
            task.progress = 30
            await db.commit()

            # 参考图：该分镜出场角色的主视图
            sh = (await db.execute(select(Shot).where(Shot.id == task.shot_id))).scalar_one_or_none()
            ref_images = []
            if sh:
                chars = (await db.execute(
                    select(Character).where(Character.id.in_(sh.character_ids or [-1]))
                )).scalars().all()
                ref_images = [c.portrait_url for c in chars if c.portrait_url][:2]

            try:
                result = await ai_gateway.generate_image(
                    task.prompt,
                    negative_prompt=task.negative_prompt,
                    width=1280, height=720,
                    model=task.model_name or None,
                    reference_images=ref_images or None,
                )
            except Exception as e:
                result = {"url": "", "error": str(e)}

            task.output_url = result.get("url", "")
            task.model_name = result.get("model", task.model_name)
            task.status = "success" if task.output_url else "failed"
            if not task.output_url:
                task.error_msg = result.get("error", "图片模型未返回结果")
            task.progress = 100
            task.finished_at = datetime.utcnow()

            # 回填分镜 + 画布节点（立即 commit，前端可见）
            if sh and task.output_url:
                sh.image_url = task.output_url
                sh.status = "imaged"
                node = (await db.execute(
                    select(CanvasNode).where(
                        CanvasNode.project_id == project_id,
                        CanvasNode.node_type == "shot",
                        CanvasNode.ref_id == sh.id,
                    )
                )).scalars().first()
                if node:
                    node.thumbnail_url = task.output_url
                    node.status = ""
            await db.commit()


@router.post("/projects/{project_id}/batch-generate-shot-images")
async def batch_generate_shot_images(
    project_id: int,
    shot_ids: Optional[List[int]] = None,
    image_model: str = "",
    db: AsyncSession = Depends(get_db),
):
    """批量生成分镜图（后台执行：立即返回，逐个生成，前端轮询渐进显示）"""
    import asyncio as _asyncio
    from app.ai import prompts as P
    from app.core.config import settings

    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    stmt = select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_no)
    if shot_ids:
        stmt = stmt.where(Shot.id.in_(shot_ids))
    shots = (await db.execute(stmt)).scalars().all()

    if not shots:
        raise HTTPException(400, "没有可用的分镜")

    # 获取角色和场景，用于构造专业 prompt
    chars = (await db.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
    scenes = (await db.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
    char_by_id = {c.id: c for c in chars}
    scene_by_id = {s.id: s for s in scenes}

    use_model = image_model or settings.IMAGE_MODEL

    # 为每个分镜创建 pending 任务（先落库，前端立刻能看到排队状态）
    task_ids = []
    for sh in shots:
        shot_dict = {
            "description": sh.description, "visual_prompt": sh.visual_prompt,
            "composition": sh.composition, "camera_movement": sh.camera_movement,
            "camera_angle": sh.camera_angle,
        }
        shot_chars = [char_by_id[cid] for cid in (sh.character_ids or []) if cid in char_by_id]
        shot_scene = scene_by_id.get(sh.scene_id)
        scene_dict = None
        if shot_scene:
            scene_dict = {
                "name": shot_scene.name, "location": shot_scene.location,
                "time_of_day": shot_scene.time_of_day, "weather": shot_scene.weather,
                "description": shot_scene.description, "visual_prompt": shot_scene.visual_prompt,
            }
        v_prompt = P.build_shot_prompt(shot_dict, shot_chars, scene_dict, project.art_style)
        v_negative = P.build_shot_negative(shot_dict, len(shot_chars))

        task = GenerationTask(
            project_id=project_id,
            task_type="shot_image",
            shot_id=sh.id,
            prompt=v_prompt,
            negative_prompt=v_negative,
            params={"model": use_model, "art_style": project.art_style},
            status="pending",
            progress=0,
            phase="批量分镜图生成",
            model_name=use_model,
        )
        db.add(task)
        await db.flush()
        task_ids.append(task.id)

        # 画布节点标记 running（前端立即出现加载态）
        node = (await db.execute(
            select(CanvasNode).where(
                CanvasNode.project_id == project_id,
                CanvasNode.node_type == "shot",
                CanvasNode.ref_id == sh.id,
            )
        )).scalars().first()
        if node:
            node.status = "running"

    await db.commit()

    # 后台执行，接口立即返回
    _asyncio.get_event_loop().create_task(_run_batch_images_bg(project_id, task_ids))
    return {"ok": True, "total": len(task_ids), "task_ids": task_ids, "async": True}


async def _run_batch_videos_bg(project_id: int, task_ids: List[int]):
    """后台逐个提交视频生成：每完成一个立即 commit，前端轮询渐进看到"""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        tasks = (await db.execute(
            select(GenerationTask).where(GenerationTask.id.in_(task_ids)).order_by(GenerationTask.id)
        )).scalars().all()

        for task in tasks:
            task.status = "running"
            task.progress = 30
            await db.commit()

            try:
                result = await ai_gateway.generate_video(
                    task.prompt,
                    image_url=task.params.get("image_url", ""),
                    duration=task.params.get("duration", 5),
                )
            except Exception as e:
                result = {"status": "failed", "error": str(e)}

            task.external_task_id = result.get("task_id", "")
            if result.get("status") == "failed":
                task.status = "failed"
                task.error_msg = result.get("error", "视频生成失败")
                task.progress = 100
                task.finished_at = datetime.utcnow()
            elif result.get("video_url"):
                # 同步返回了视频 URL
                task.status = "success"
                task.output_url = result["video_url"]
                task.progress = 100
                task.finished_at = datetime.utcnow()
                sh = (await db.execute(select(Shot).where(Shot.id == task.shot_id))).scalar_one_or_none()
                if sh:
                    sh.video_url = task.output_url
                    sh.status = "videod"
            else:
                # 外部异步任务：保持 running，等轮询 worker 更新
                task.status = "running"
                task.progress = 60
            await db.commit()


@router.post("/projects/{project_id}/batch-generate-shot-videos")
async def batch_generate_shot_videos(
    project_id: int,
    shot_ids: Optional[List[int]] = None,
    video_model: str = "",
    db: AsyncSession = Depends(get_db),
):
    """批量生成分镜视频（后台执行：立即返回，前端轮询渐进显示）"""
    import asyncio as _asyncio
    from app.core.config import settings

    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    stmt = select(Shot).where(
        Shot.project_id == project_id,
        Shot.image_url != "",
    ).order_by(Shot.shot_no)
    if shot_ids:
        stmt = stmt.where(Shot.id.in_(shot_ids))
    shots = (await db.execute(stmt)).scalars().all()

    if not shots:
        raise HTTPException(400, "没有可生成分镜视频的镜头（需要先有分镜图）")

    use_model = video_model or settings.VIDEO_MODEL

    task_ids = []
    for sh in shots:
        v_prompt = sh.visual_prompt or sh.description
        task = GenerationTask(
            project_id=project_id,
            task_type="shot_video",
            shot_id=sh.id,
            prompt=v_prompt,
            params={"model": use_model, "image_url": sh.image_url, "duration": int(sh.duration_sec)},
            status="pending",
            progress=0,
            phase="批量视频生成",
            model_name=use_model,
        )
        db.add(task)
        await db.flush()
        task_ids.append(task.id)

        node = (await db.execute(
            select(CanvasNode).where(
                CanvasNode.project_id == project_id,
                CanvasNode.node_type == "shot",
                CanvasNode.ref_id == sh.id,
            )
        )).scalars().first()
        if node:
            node.status = "running"

    await db.commit()

    _asyncio.get_event_loop().create_task(_run_batch_videos_bg(project_id, task_ids))
    return {"ok": True, "total": len(task_ids), "task_ids": task_ids, "async": True}

# ============== 脚本资源管理（剧本是一等公民，不再是临时资产） ==============

class ScriptUpdateBody(BaseModel):
    """更新剧本的请求体（仅修改文本字段，不改结构化 meta）"""
    title: Optional[str] = None
    logline: Optional[str] = None
    content: Optional[str] = None


@router.get("/projects/{project_id}/scripts")
async def list_project_scripts(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """列出项目的全部脚本版本（按版本倒序）

    用途：
    - 画布『剧本/关系』抽屉读取完整剧本
    - 显示当前应用的版本
    """
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    scripts = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().all()

    return {
        "items": [
            {
                "id": s.id,
                "version": s.version,
                "title": s.title,
                "logline": s.logline,
                "content": s.content,
                "raw_text": s.raw_text,
                "meta": s.meta or {},
                "source_task_id": s.source_task_id,
                "created_at": s.created_at.isoformat() if s.created_at else "",
                "updated_at": s.updated_at.isoformat() if s.updated_at else "",
            }
            for s in scripts
        ],
        "total": len(scripts),
        "current_version": scripts[0].version if scripts else 0,
    }


@router.get("/scripts/{script_id}")
async def get_script(script_id: int, db: AsyncSession = Depends(get_db)):
    """读取完整剧本（完整 Markdown 内容 + 结构化 meta）"""
    script = (await db.execute(
        select(Script).where(Script.id == script_id)
    )).scalar_one_or_none()
    if not script:
        raise HTTPException(404, "剧本不存在")
    return {
        "id": script.id,
        "project_id": script.project_id,
        "version": script.version,
        "title": script.title,
        "logline": script.logline,
        "content": script.content,
        "raw_text": script.raw_text,
        "meta": script.meta or {},
        "source_task_id": script.source_task_id,
        "created_at": script.created_at.isoformat() if script.created_at else "",
        "updated_at": script.updated_at.isoformat() if script.updated_at else "",
    }


@router.patch("/scripts/{script_id}")
async def update_script(
    script_id: int,
    body: ScriptUpdateBody,
    db: AsyncSession = Depends(get_db),
):
    """编辑剧本（标题/梗概/完整内容）；不改结构化 meta（meta 只能由 AI 重新生成覆盖）

    用户改文本后仍可触发『重新应用到画布』生成新角色/场景/分镜。
    """
    script = (await db.execute(
        select(Script).where(Script.id == script_id)
    )).scalar_one_or_none()
    if not script:
        raise HTTPException(404, "剧本不存在")

    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(script, k, v)
    await db.commit()
    await db.refresh(script)
    return {"ok": True, "script_id": script.id, "version": script.version}
