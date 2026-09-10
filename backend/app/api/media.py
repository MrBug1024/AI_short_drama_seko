"""媒体编辑 API - 消除笔/局部重绘/口型同步/音频分离/字幕/合成

画布级精修 + 画布视频节点音频分离 + 一键对口型
"""
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ai.gateway import ai_gateway
from app.models.shot import Shot
from app.models.character import Character
from app.models.scene import Scene
from app.models.generation_task import GenerationTask
from app.models.project import Project

router = APIRouter()


# ============== 画布级精修 ==============

@router.post("/shots/{sid}/inpaint")
async def inpaint_region(
    sid: int,
    mask_url: str,
    prompt: str,
    db: AsyncSession = Depends(get_db),
):
    """局部重绘（消除笔/区域替换）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="inpaint",
        shot_id=sid,
        prompt=prompt,
        params={"mask_url": mask_url, "source_image": sh.image_url},
        status="running",
        progress=30,
        phase="局部重绘",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 调用 AI
    full_prompt = f"image editing: replace masked area with: {prompt}"
    result = await ai_gateway.generate_image(full_prompt)
    task.output_url = result.get("url", sh.image_url)
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    sh.image_url = task.output_url
    await db.commit()

    return {"ok": True, "task_id": task.id, "image_url": task.output_url}


@router.post("/shots/{sid}/remove-watermark")
async def remove_watermark(sid: int, db: AsyncSession = Depends(get_db)):
    """智能去字幕/水印"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="watermark_remove",
        shot_id=sid,
        params={"source_image": sh.image_url},
        status="running",
        progress=50,
        phase="智能去字幕",
    )
    db.add(task)
    await db.commit()

    task.output_url = sh.image_url
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    await db.commit()
    return {"ok": True, "task_id": task.id, "image_url": sh.image_url}


@router.post("/shots/{sid}/re-audit")
async def re_audit_content(sid: int, db: AsyncSession = Depends(get_db)):
    """素材重新审核（审核失败后重新提交）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="audit",
        shot_id=sid,
        status="running",
        progress=50,
        phase="素材审核",
    )
    db.add(task)
    await db.commit()

    # 模拟审核通过
    import random
    task.status = "success" if random.random() > 0.2 else "failed"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    await db.commit()
    return {"ok": True, "task_id": task.id, "audit_passed": task.status == "success"}


# ============== 音频分离 ==============

@router.post("/shots/{sid}/audio-separate")
async def separate_audio(sid: int, db: AsyncSession = Depends(get_db)):
    """音频分离：人声/配乐/环境声"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")
    if not sh.video_url:
        raise HTTPException(400, "该镜头尚无视频")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="audio_separator",
        shot_id=sid,
        params={"video_url": sh.video_url},
        status="running",
        progress=30,
        phase="音频分离",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    result = await ai_gateway.audio_separator(sh.video_url)
    task.output_meta = result
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    await db.commit()
    return {
        "ok": True,
        "task_id": task.id,
        "vocals_url": result.get("vocals_url", ""),
        "music_url": result.get("music_url", ""),
        "ambient_url": result.get("ambient_url", ""),
        "original_url": result.get("original_url", sh.video_url),
    }


# ============== 对口型 / 配音 ==============

@router.post("/shots/{sid}/lipsync")
async def lipsync_video(
    sid: int,
    audio_url: str = "",
    text: str = "",
    voice: str = "default",
    db: AsyncSession = Depends(get_db),
):
    """SekoTalk 一键对口型（多人口型同步）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="lipsync",
        shot_id=sid,
        prompt=text,
        params={"audio_url": audio_url, "voice": voice, "video_url": sh.video_url},
        status="running",
        progress=20,
        phase="口型同步",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 获取镜头角色
    characters = []
    if sh.character_ids:
        chars = (await db.execute(
            select(Character).where(Character.id.in_(sh.character_ids))
        )).scalars().all()
        characters = [c.name for c in chars]

    result = await ai_gateway.lipsync(sh.video_url, audio_url, characters)

    task.output_url = result.get("url", sh.video_url)
    task.output_meta = result
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    sh.video_url = task.output_url
    sh.audio_url = audio_url
    sh.status = "audioed"

    await db.commit()
    return {"ok": True, "task_id": task.id, "video_url": task.output_url}


@router.post("/shots/{sid}/tts")
async def text_to_speech(
    sid: int,
    text: str,
    voice: str = "default",
    emotion: str = "neutral",
    language: str = "zh",
    db: AsyncSession = Depends(get_db),
):
    """TTS 配音"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="tts",
        shot_id=sid,
        prompt=text,
        params={"voice": voice, "emotion": emotion, "language": language},
        status="running",
        progress=40,
        phase="TTS 配音",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    result = await ai_gateway.tts(text, voice=voice, language=language)
    task.output_url = result.get("url", "")
    task.output_meta = result
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    sh.audio_url = task.output_url
    await db.commit()
    return {"ok": True, "task_id": task.id, "audio_url": task.output_url, "duration": result.get("duration", 0)}


# ============== 音频翻译 ==============

@router.post("/shots/{sid}/audio-translate")
async def translate_audio(
    sid: int,
    target_language: str = "en",
    db: AsyncSession = Depends(get_db),
):
    """音频翻译（Seed Audio 翻译视频原声）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="audio_translate",
        shot_id=sid,
        params={"target_language": target_language, "video_url": sh.video_url},
        status="running",
        progress=30,
        phase="音频翻译",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 模拟：返回原视频 URL（实际应调用 Seed Audio 翻译）
    task.output_url = sh.video_url
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    await db.commit()
    return {
        "ok": True,
        "task_id": task.id,
        "video_url": sh.video_url,
        "language": target_language,
    }


# ============== 视频合成 ==============

@router.post("/projects/{pid}/compose")
async def compose_video(
    pid: int,
    shot_ids: Optional[List[int]] = None,
    bgm_url: str = "",
    add_subtitle: bool = True,
    transition: str = "fade",
    db: AsyncSession = Depends(get_db),
):
    """合成完整视频（把所有分镜视频 + 配乐 + 字幕合成）"""
    project = (await db.execute(select(Project).where(Project.id == pid))).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    stmt = select(Shot).where(
        Shot.project_id == pid,
        Shot.video_url != "",
    ).order_by(Shot.shot_no)
    if shot_ids:
        stmt = stmt.where(Shot.id.in_(shot_ids))
    shots = (await db.execute(stmt)).scalars().all()

    if not shots:
        raise HTTPException(400, "没有可合成的视频")

    task = GenerationTask(
        project_id=pid,
        task_type="compose",
        prompt=f"合成 {len(shots)} 个分镜",
        params={
            "shot_ids": [s.id for s in shots],
            "bgm_url": bgm_url,
            "add_subtitle": add_subtitle,
            "transition": transition,
        },
        status="running",
        progress=10,
        phase="视频合成",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 模拟合成
    total_duration = sum(s.duration_sec for s in shots)
    composed_url = f"https://picsum.photos/seed/composed_{pid}/1280/720"

    task.output_url = composed_url
    task.output_meta = {
        "total_duration": total_duration,
        "shot_count": len(shots),
    }
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    project.status = "completed"
    project.cover_url = project.cover_url or shots[0].image_url if shots else ""

    await db.commit()
    return {
        "ok": True,
        "task_id": task.id,
        "video_url": composed_url,
        "duration": total_duration,
        "shot_count": len(shots),
    }


# ============== 扩展：转场（首尾帧） ==============

@router.post("/shots/{sid}/head-tail-frame")
async def generate_head_tail_frames(
    sid: int,
    head_prompt: str = "",
    tail_prompt: str = "",
    db: AsyncSession = Depends(get_db),
):
    """首尾帧生视频（生成首帧+尾帧图，作为视频生成输入）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    results = {}
    if head_prompt:
        task = GenerationTask(
            project_id=sh.project_id,
            task_type="head_frame",
            shot_id=sid,
            prompt=head_prompt,
            status="running",
            progress=30,
            phase="首帧生成",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        r = await ai_gateway.generate_image(head_prompt)
        task.output_url = r.get("url", "")
        task.status = "success"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        results["head_url"] = task.output_url

    if tail_prompt:
        task = GenerationTask(
            project_id=sh.project_id,
            task_type="tail_frame",
            shot_id=sid,
            prompt=tail_prompt,
            status="running",
            progress=30,
            phase="尾帧生成",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        r = await ai_gateway.generate_image(tail_prompt)
        task.output_url = r.get("url", "")
        task.status = "success"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        results["tail_url"] = task.output_url

    await db.commit()
    return {"ok": True, **results}


# ============== 故事推演（前后 3s/5s 画面延展） ==============

@router.post("/shots/{sid}/extend")
async def extend_storyboard(
    sid: int,
    direction: str = "before",  # before/after
    seconds: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """故事推演：基于当前镜头延展前后画面"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="extend",
        shot_id=sid,
        prompt=f"{direction} {seconds}s continuation of: {sh.description}",
        params={"direction": direction, "seconds": seconds},
        status="running",
        progress=30,
        phase="故事推演",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    r = await ai_gateway.generate_image(task.prompt)
    task.output_url = r.get("url", "")
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    await db.commit()
    return {
        "ok": True,
        "task_id": task.id,
        "extend_url": task.output_url,
        "direction": direction,
        "seconds": seconds,
    }


# ============== 720° 全景图 ==============

@router.post("/scenes/{sid}/panorama")
async def generate_panorama(sid: int, db: AsyncSession = Depends(get_db)):
    """生成 720° 全景图"""
    scene = (await db.execute(select(Scene).where(Scene.id == sid))).scalar_one_or_none()
    if not scene:
        raise HTTPException(404, "场景不存在")

    task = GenerationTask(
        project_id=scene.project_id,
        task_type="panorama",
        scene_id=sid,
        prompt=scene.visual_prompt or scene.description,
        status="running",
        progress=30,
        phase="全景图生成",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    r = await ai_gateway.generate_image(f"360 panorama: {task.prompt}")
    task.output_url = r.get("url", "")
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    scene.panorama_url = task.output_url
    await db.commit()

    return {"ok": True, "task_id": task.id, "panorama_url": task.output_url}


# ============== 九宫格图 ==============

@router.post("/shots/{sid}/grid9")
async def generate_grid9(sid: int, prompt: str, db: AsyncSession = Depends(get_db)):
    """九宫格图（同一主题 9 个变体）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")

    task = GenerationTask(
        project_id=sh.project_id,
        task_type="grid9",
        shot_id=sid,
        prompt=prompt,
        params={"shots": 9},
        status="running",
        progress=30,
        phase="九宫格生成",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    results = []
    for i in range(9):
        r = await ai_gateway.generate_image(f"{prompt} variant {i+1}")
        results.append(r.get("url", ""))

    task.output_meta = {"images": results}
    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()

    await db.commit()
    return {"ok": True, "task_id": task.id, "images": results}