"""设计工作台 API - 角色多视图设计稿 / AI 优化 / 角色关系

对标主流短剧平台的设计能力：
- 角色：先"设计"（生成多视图设计稿：正面/侧面/背面/表情/特写），用户确认后再用于分镜生成
- 剧本/场景/分镜：支持 AI 优化改写（保持结构，按用户要求调整）
- 角色关系：恋人/仇人/亲子等关系定义，画布可连线展示
"""
import json
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ai.gateway import ai_gateway
from app.ai import prompts as P
from app.models.project import Project
from app.models.script import Script
from app.models.character import Character, CharacterRelation
from app.models.scene import Scene
from app.models.shot import Shot
from app.models.canvas import CanvasNode
from app.models.generation_task import GenerationTask
from app.schemas.asset import RelationCreate, RelationUpdate, RelationOut

router = APIRouter()


def _strip_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


async def _parse_json(content: str) -> Dict[str, Any]:
    """解析 LLM 返回的 JSON（多级容错）

    1. 剥代码围栏
    2. 直接 json.loads
    3. 截取首个 {...} 再试
    4. 修复尾逗号（,} / ,]）再试
    5. 修复字符串值内未转义的英文双引号再试
    """
    s = _strip_fences(content)
    candidates = [s]
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        candidates.append(s[start:end + 1])

    for cand in candidates:
        try:
            return json.loads(cand)
        except Exception:
            pass

    # 修复尾逗号
    import re as _re
    for cand in list(candidates):
        fixed = _re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            return json.loads(fixed)
        except Exception:
            pass
        candidates.append(fixed)

    # 修复字符串值内未转义的英文双引号：
    # 形如 "description":"xxx "quoted" yyy" → 把值内部的 " 替换为中文引号
    def _fix_inner_quotes(text: str) -> str:
        out = []
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == '"':
                # 找到字符串结束引号：向后扫描，若下一个非空白是 , } ] : 则视为合法结束
                j = i + 1
                while j < n:
                    if text[j] == '\\':
                        j += 2
                        continue
                    if text[j] == '"':
                        k = j + 1
                        while k < n and text[k] in ' \t\r\n':
                            k += 1
                        if k >= n or text[k] in ',}]:':
                            break
                        # 内部引号 → 替换为中文引号
                        text = text[:j] + '\u201d' + text[j + 1:]
                        n = len(text)
                        j += 1
                        continue
                    j += 1
                out.append(text[i:j + 1])
                i = j + 1
            else:
                out.append(ch)
                i += 1
        return "".join(out)

    for cand in list(candidates):
        try:
            return json.loads(_fix_inner_quotes(cand))
        except Exception:
            continue

    raise ValueError("无法解析 AI 返回的 JSON")


async def _sync_node_thumbnail(db: AsyncSession, project_id: int, node_type: str,
                               ref_id: int, thumbnail_url: str, title: str = ""):
    """实体图更新后同步画布节点缩略图"""
    node = (await db.execute(
        select(CanvasNode).where(
            CanvasNode.project_id == project_id,
            CanvasNode.node_type == node_type,
            CanvasNode.ref_id == ref_id,
        )
    )).scalars().first()
    if node:
        node.thumbnail_url = thumbnail_url
        if title:
            node.title = title


# ============== 角色设计稿（多视图） ==============

@router.post("/characters/{cid}/design-sheet")
async def generate_character_design_sheet(
    cid: int,
    views: str = "closeup,front,side,expression",
    db: AsyncSession = Depends(get_db),
):
    """生成角色设计稿：多视图（正面/侧面/背面/表情/特写）

    参考专业角色设计流程：先出设计稿供用户确认/修改，再投入分镜生成。
    并发调用图片模型，所有视图共享同一"外貌锚点"保证一致性。
    """
    ch = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "角色不存在")
    project = (await db.execute(select(Project).where(Project.id == ch.project_id))).scalar_one_or_none()
    art_style = project.art_style if project else ""

    view_list = [v.strip() for v in views.split(",") if v.strip() in P.CHARACTER_VIEW_PROMPTS]
    if not view_list:
        view_list = ["closeup"]

    char_dict = {
        "name": ch.name, "alias": ch.alias, "age": ch.age, "gender": ch.gender,
        "appearance": ch.appearance, "outfit": ch.outfit,
    }

    task = GenerationTask(
        project_id=ch.project_id,
        task_type="character_design",
        character_id=cid,
        prompt=P.character_anchor(char_dict),
        params={"views": view_list},
        status="running",
        progress=10,
        phase="角色设计稿生成",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    started = datetime.utcnow()

    async def gen_view(view: str):
        prompt = P.build_character_prompt(char_dict, art_style, view)
        r = await ai_gateway.generate_image(
            prompt,
            negative_prompt=P.CHARACTER_NEGATIVE,
            width=1024, height=1024,
            # 已有主参考图时作为参考，强化一致性
            reference_images=[ch.portrait_url] if ch.portrait_url else None,
        )
        return view, r.get("url", "")

    results = await asyncio.gather(*[gen_view(v) for v in view_list], return_exceptions=True)

    view_images = dict(ch.view_images or {})
    ok_count = 0
    for res in results:
        if isinstance(res, Exception):
            continue
        view, url = res
        if url:
            view_images[view] = url
            ok_count += 1

    if ok_count == 0:
        task.status = "failed"
        task.error_msg = "所有视图生成失败，请检查图片模型配置"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(502, "角色设计稿生成失败：图片模型未返回有效结果")

    # 主参考图：优先特写 > 正面
    portrait = view_images.get("closeup") or view_images.get("front") or ch.portrait_url
    ch.view_images = view_images
    ch.portrait_url = portrait
    if portrait and portrait not in (ch.reference_images or []):
        ch.reference_images = list(ch.reference_images or []) + [portrait]

    task.status = "success"
    task.progress = 100
    task.output_url = portrait
    task.duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    task.finished_at = datetime.utcnow()
    await db.commit()

    await _sync_node_thumbnail(db, ch.project_id, "character", cid, portrait, ch.name)
    await db.commit()

    return {"ok": True, "task_id": task.id, "view_images": view_images, "portrait_url": portrait}


@router.post("/characters/{cid}/generate-view")
async def generate_character_view(
    cid: int,
    view: str = "closeup",
    extra_prompt: str = "",
    db: AsyncSession = Depends(get_db),
):
    """重新生成角色的单个视图（用户不满意某个视角时单独重roll）"""
    ch = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "角色不存在")
    if view not in P.CHARACTER_VIEW_PROMPTS:
        raise HTTPException(400, f"不支持的视图类型：{view}")
    project = (await db.execute(select(Project).where(Project.id == ch.project_id))).scalar_one_or_none()

    char_dict = {
        "name": ch.name, "alias": ch.alias, "age": ch.age, "gender": ch.gender,
        "appearance": ch.appearance, "outfit": ch.outfit,
    }
    prompt = P.build_character_prompt(char_dict, project.art_style if project else "", view, extra_prompt)

    task = GenerationTask(
        project_id=ch.project_id, task_type="character_design", character_id=cid,
        prompt=prompt, params={"view": view}, status="running", progress=30, phase=f"角色视图生成（{P.CHARACTER_VIEW_LABELS.get(view, view)}）",
    )
    db.add(task)
    await db.commit()

    r = await ai_gateway.generate_image(
        prompt, negative_prompt=P.CHARACTER_NEGATIVE,
        reference_images=[ch.portrait_url] if ch.portrait_url else None,
    )
    url = r.get("url", "")
    if not url:
        task.status = "failed"
        task.error_msg = r.get("error", "生成失败")
        await db.commit()
        raise HTTPException(502, f"图片生成失败：{task.error_msg}")

    view_images = dict(ch.view_images or {})
    view_images[view] = url
    ch.view_images = view_images
    if view in ("closeup", "front"):
        ch.portrait_url = url
    task.status = "success"
    task.progress = 100
    task.output_url = url
    task.finished_at = datetime.utcnow()
    await db.commit()

    await _sync_node_thumbnail(db, ch.project_id, "character", cid, ch.portrait_url, ch.name)
    await db.commit()
    return {"ok": True, "view": view, "url": url, "view_images": view_images, "portrait_url": ch.portrait_url}


# ============== AI 优化：角色 / 场景 / 分镜 / 剧本 ==============

@router.post("/characters/{cid}/optimize")
async def optimize_character(
    cid: int,
    requirement: str,
    db: AsyncSession = Depends(get_db),
):
    """AI 优化角色设定（按用户要求改写外貌/服装/性格等，落库并返回新设定）"""
    ch = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "角色不存在")

    current = {
        "name": ch.name, "alias": ch.alias, "age": ch.age, "gender": ch.gender,
        "role": ch.role, "appearance": ch.appearance, "outfit": ch.outfit,
        "personality": ch.personality, "backstory": ch.backstory,
    }
    user_prompt = f"当前角色设定：\n{json.dumps(current, ensure_ascii=False, indent=2)}\n\n修改要求：{requirement}"

    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": P.OPTIMIZE_SYSTEM_PROMPTS["character"]},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True, temperature=0.7,
    )
    try:
        data = await _parse_json(result["content"])
    except Exception as e:
        raise HTTPException(502, f"AI 返回格式错误：{e}")

    for k in ("name", "alias", "gender", "role", "appearance", "outfit", "personality", "backstory"):
        if data.get(k):
            setattr(ch, k, str(data[k]))
    if data.get("age"):
        try:
            ch.age = int(data["age"])
        except (ValueError, TypeError):
            pass
    await db.commit()
    await db.refresh(ch)

    await _sync_node_thumbnail(db, ch.project_id, "character", cid, ch.portrait_url, ch.name)
    await db.commit()
    return {"ok": True, "character": {
        "id": ch.id, "name": ch.name, "alias": ch.alias, "age": ch.age, "gender": ch.gender,
        "role": ch.role, "appearance": ch.appearance, "outfit": ch.outfit,
        "personality": ch.personality, "backstory": ch.backstory,
    }}


@router.post("/scenes/{sid}/optimize")
async def optimize_scene(
    sid: int,
    requirement: str,
    db: AsyncSession = Depends(get_db),
):
    """AI 优化场景设定"""
    sc = (await db.execute(select(Scene).where(Scene.id == sid))).scalar_one_or_none()
    if not sc:
        raise HTTPException(404, "场景不存在")

    current = {
        "name": sc.name, "location": sc.location, "time_of_day": sc.time_of_day,
        "weather": sc.weather, "mood": sc.mood, "description": sc.description,
        "visual_prompt": sc.visual_prompt,
    }
    user_prompt = f"当前场景设定：\n{json.dumps(current, ensure_ascii=False, indent=2)}\n\n修改要求：{requirement}"

    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": P.OPTIMIZE_SYSTEM_PROMPTS["scene"]},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True, temperature=0.7,
    )
    try:
        data = await _parse_json(result["content"])
    except Exception as e:
        raise HTTPException(502, f"AI 返回格式错误：{e}")

    for k in ("name", "location", "time_of_day", "weather", "mood", "description", "visual_prompt"):
        if data.get(k):
            setattr(sc, k, str(data[k]))
    await db.commit()
    await db.refresh(sc)

    await _sync_node_thumbnail(db, sc.project_id, "scene", sid, sc.panorama_url, sc.name)
    await db.commit()
    return {"ok": True, "scene": current | {
        "id": sc.id, "name": sc.name, "location": sc.location, "time_of_day": sc.time_of_day,
        "weather": sc.weather, "mood": sc.mood, "description": sc.description,
        "visual_prompt": sc.visual_prompt,
    }}


@router.post("/scenes/{sid}/generate-image")
async def generate_scene_image(
    sid: int,
    extra_prompt: str = "",
    db: AsyncSession = Depends(get_db),
):
    """生成/重roll 场景概念图（用专业场景 prompt，而不是场景名）"""
    sc = (await db.execute(select(Scene).where(Scene.id == sid))).scalar_one_or_none()
    if not sc:
        raise HTTPException(404, "场景不存在")
    project = (await db.execute(select(Project).where(Project.id == sc.project_id))).scalar_one_or_none()

    scene_dict = {
        "name": sc.name, "location": sc.location, "time_of_day": sc.time_of_day,
        "weather": sc.weather, "mood": sc.mood, "description": sc.description,
        "visual_prompt": sc.visual_prompt,
    }
    prompt = P.build_scene_prompt(scene_dict, project.art_style if project else "", extra_prompt)

    task = GenerationTask(
        project_id=sc.project_id, task_type="scene_image", scene_id=sid,
        prompt=prompt, status="running", progress=30, phase="场景图生成",
    )
    db.add(task)
    await db.commit()

    r = await ai_gateway.generate_image(prompt, negative_prompt=P.SCENE_NEGATIVE, width=1280, height=720)
    url = r.get("url", "")
    if not url:
        task.status = "failed"
        task.error_msg = r.get("error", "生成失败")
        await db.commit()
        raise HTTPException(502, f"图片生成失败：{task.error_msg}")

    sc.panorama_url = url
    if url not in (sc.reference_images or []):
        sc.reference_images = list(sc.reference_images or []) + [url]
    task.status = "success"
    task.progress = 100
    task.output_url = url
    task.finished_at = datetime.utcnow()
    await db.commit()

    await _sync_node_thumbnail(db, sc.project_id, "scene", sid, url, sc.name)
    await db.commit()
    return {"ok": True, "task_id": task.id, "panorama_url": url}


@router.post("/shots/{sid}/optimize")
async def optimize_shot(
    sid: int,
    requirement: str,
    db: AsyncSession = Depends(get_db),
):
    """AI 优化分镜（画面/构图/运镜/台词），带上下文（场景+角色）"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
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

    current = {
        "shot_code": sh.shot_code, "description": sh.description,
        "composition": sh.composition, "camera_movement": sh.camera_movement,
        "camera_angle": sh.camera_angle, "dialogue": sh.dialogue,
        "duration_sec": sh.duration_sec, "visual_prompt": sh.visual_prompt,
    }
    context = {
        "scene": {"name": scene.name, "description": scene.description} if scene else None,
        "characters": [{"name": c.name, "appearance": c.appearance, "outfit": c.outfit} for c in chars],
    }
    user_prompt = (
        f"镜头上下文：\n{json.dumps(context, ensure_ascii=False)}\n\n"
        f"当前镜头设定：\n{json.dumps(current, ensure_ascii=False, indent=2)}\n\n"
        f"修改要求：{requirement}"
    )

    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": P.OPTIMIZE_SYSTEM_PROMPTS["shot"]},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True, temperature=0.7,
    )
    try:
        data = await _parse_json(result["content"])
    except Exception as e:
        raise HTTPException(502, f"AI 返回格式错误：{e}")

    for k in ("description", "composition", "camera_movement", "camera_angle", "dialogue", "visual_prompt"):
        if data.get(k):
            setattr(sh, k, str(data[k]))
    if data.get("duration_sec"):
        try:
            sh.duration_sec = float(data["duration_sec"])
        except (ValueError, TypeError):
            pass
    await db.commit()
    await db.refresh(sh)

    await _sync_node_thumbnail(
        db, sh.project_id, "shot", sid, sh.image_url,
        f"{sh.shot_code} {sh.description[:12]}",
    )
    await db.commit()
    return {"ok": True, "shot": {
        "id": sh.id, "shot_code": sh.shot_code, "description": sh.description,
        "composition": sh.composition, "camera_movement": sh.camera_movement,
        "camera_angle": sh.camera_angle, "dialogue": sh.dialogue,
        "duration_sec": sh.duration_sec, "visual_prompt": sh.visual_prompt,
    }}


@router.post("/shots/{sid}/generate-image")
async def generate_shot_image(
    sid: int,
    extra_prompt: str = "",
    db: AsyncSession = Depends(get_db),
):
    """生成/重roll 分镜图：使用专业 prompt（角色锚点+场景+镜头语言+画风）

    这是修复"生成不相干风景照"的关键入口：不再拿镜头标题当 prompt。
    """
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "镜头不存在")
    project = (await db.execute(select(Project).where(Project.id == sh.project_id))).scalar_one_or_none()

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
            "weather": scene.weather, "description": scene.description, "visual_prompt": scene.visual_prompt,
        }
    prompt = P.build_shot_prompt(shot_dict, chars, scene_dict,
                                 project.art_style if project else "", extra_prompt)
    negative = P.build_shot_negative(shot_dict, len(chars))

    # 角色参考图（图生图强化一致性）
    ref_images = [c.portrait_url for c in chars if c.portrait_url][:2]

    task = GenerationTask(
        project_id=sh.project_id, task_type="shot_image", shot_id=sid,
        prompt=prompt, negative_prompt=negative,
        status="running", progress=30, phase="分镜图生成",
    )
    db.add(task)
    await db.commit()

    started = datetime.utcnow()
    r = await ai_gateway.generate_image(
        prompt, negative_prompt=negative, width=1280, height=720,
        reference_images=ref_images or None,
    )
    url = r.get("url", "")
    if not url:
        task.status = "failed"
        task.error_msg = r.get("error", "生成失败")
        task.finished_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(502, f"图片生成失败：{task.error_msg}")

    sh.image_url = url
    sh.status = "imaged"
    task.status = "success"
    task.progress = 100
    task.output_url = url
    task.duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    task.finished_at = datetime.utcnow()
    await db.commit()

    await _sync_node_thumbnail(db, sh.project_id, "shot", sid, url,
                               f"{sh.shot_code} {sh.description[:12]}")
    await db.commit()
    return {"ok": True, "task_id": task.id, "image_url": url}


@router.post("/projects/{project_id}/optimize-script")
async def optimize_script(
    project_id: int,
    requirement: str,
    db: AsyncSession = Depends(get_db),
):
    """AI 优化整部短剧剧本：按用户要求改写，生成新版本 Script 并同步实体

    与"重新创作"不同：保留现有角色/场景/分镜结构，只做增量修改。
    """
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "项目不存在")

    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    if not script:
        raise HTTPException(400, "该项目还没有剧本，请先创作")

    task = GenerationTask(
        project_id=project_id, task_type="script_optimize",
        status="running", progress=20, phase="剧本 AI 优化", prompt=requirement[:200],
    )
    db.add(task)
    await db.commit()

    meta_str = json.dumps(script.meta or {}, ensure_ascii=False)
    if len(meta_str) > 12000:
        meta_str = meta_str[:12000]
    user_prompt = (
        f"现有剧本结构化数据（JSON）：\n{meta_str}\n\n"
        f"修改要求：{requirement}\n\n"
        f"请输出优化后的完整 JSON（保持原有字段结构：logline/art_style/characters/scenes/props/shots）。"
    )

    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": P.OPTIMIZE_SYSTEM_PROMPTS["script"]},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True, temperature=0.7, max_tokens=8192,
    )
    try:
        data = await _parse_json(result["content"])
    except Exception as e:
        task.status = "failed"
        task.error_msg = str(e)
        await db.commit()
        raise HTTPException(502, f"AI 返回格式错误：{e}")

    # 写入新版本剧本（旧版本保留，可回溯）
    from app.services.creation import creation_service
    new_script = Script(
        project_id=project_id,
        version=(script.version or 1) + 1,
        title=data.get("title", script.title),
        logline=data.get("logline", script.logline),
        content=creation_service._format_script_md(data),
        raw_text=script.raw_text,
        meta=data,
        source_task_id=str(task.id),
    )
    db.add(new_script)

    # 同步实体：按名称匹配更新，新增的创建，不再删除已有图片资产
    await _sync_script_entities(db, project, data)

    task.status = "success"
    task.progress = 100
    task.finished_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "task_id": task.id, "version": new_script.version, "data": data}


async def _sync_script_entities(db: AsyncSession, project: Project, data: Dict[str, Any]):
    """剧本优化后同步角色/场景/道具/分镜（按名称增量更新，不删已有资产图）"""
    # 角色
    existing_chars = {c.name: c for c in (await db.execute(
        select(Character).where(Character.project_id == project.id))).scalars().all()}
    char_map: Dict[str, int] = {}
    for c in data.get("characters", []):
        name = c.get("name", "")
        if not name:
            continue
        if name in existing_chars:
            ch = existing_chars[name]
            for k in ("alias", "gender", "role", "appearance", "outfit", "personality"):
                if c.get(k):
                    setattr(ch, k, str(c[k]))
            if c.get("age"):
                try:
                    ch.age = int(c["age"])
                except (ValueError, TypeError):
                    pass
            char_map[name] = ch.id
        else:
            ch = Character(
                project_id=project.id, name=name, alias=c.get("alias", ""),
                age=int(c.get("age") or 0), gender=c.get("gender", ""), role=c.get("role", ""),
                appearance=c.get("appearance", ""), outfit=c.get("outfit", ""),
                personality=c.get("personality", ""),
            )
            db.add(ch)
            await db.flush()
            char_map[name] = ch.id
            existing_chars[name] = ch

    # 场景
    existing_scenes = {s.name: s for s in (await db.execute(
        select(Scene).where(Scene.project_id == project.id))).scalars().all()}
    scene_map: Dict[str, int] = {}
    for s in data.get("scenes", []):
        name = s.get("name", "")
        if not name:
            continue
        if name in existing_scenes:
            sc = existing_scenes[name]
            for k in ("location", "time_of_day", "weather", "mood", "description", "visual_prompt"):
                if s.get(k):
                    setattr(sc, k, str(s[k]))
            scene_map[name] = sc.id
        else:
            sc = Scene(
                project_id=project.id, name=name, location=s.get("location", ""),
                time_of_day=s.get("time_of_day", "day"), weather=s.get("weather", ""),
                mood=s.get("mood", ""), description=s.get("description", ""),
                visual_prompt=s.get("visual_prompt", ""),
            )
            db.add(sc)
            await db.flush()
            scene_map[name] = sc.id
            existing_scenes[name] = sc

    # 分镜：按 shot_code 匹配更新，新镜头追加
    existing_shots = {sh.shot_code: sh for sh in (await db.execute(
        select(Shot).where(Shot.project_id == project.id))).scalars().all()}
    for i, sh_data in enumerate(data.get("shots", [])):
        code = sh_data.get("shot_code", f"SC{i + 1:02d}")
        char_ids = [char_map[n] for n in sh_data.get("character_names", []) if n in char_map]
        scene_id = scene_map.get(sh_data.get("scene_name", ""))
        if code in existing_shots:
            sh = existing_shots[code]
            for k in ("description", "composition", "camera_movement", "camera_angle", "dialogue"):
                if sh_data.get(k):
                    setattr(sh, k, str(sh_data[k]))
            if sh_data.get("duration_sec"):
                try:
                    sh.duration_sec = float(sh_data["duration_sec"])
                except (ValueError, TypeError):
                    pass
            if sh_data.get("visual_prompt"):
                sh.visual_prompt = str(sh_data["visual_prompt"])
            if char_ids:
                sh.character_ids = char_ids
            if scene_id:
                sh.scene_id = scene_id
        else:
            sh = Shot(
                project_id=project.id, shot_no=len(existing_shots) + 1, shot_code=code,
                description=sh_data.get("description", ""),
                composition=sh_data.get("composition", ""),
                camera_movement=sh_data.get("camera_movement", ""),
                camera_angle=sh_data.get("camera_angle", ""),
                dialogue=sh_data.get("dialogue", ""),
                duration_sec=float(sh_data.get("duration_sec") or 5),
                visual_prompt=sh_data.get("visual_prompt") or sh_data.get("description", ""),
                scene_id=scene_id, character_ids=char_ids,
            )
            db.add(sh)
            await db.flush()
            existing_shots[code] = sh
    await db.flush()


# ============== 角色关系 ==============

@router.get("/projects/{project_id}/relations", response_model=List[RelationOut])
async def list_relations(project_id: int, db: AsyncSession = Depends(get_db)):
    rels = (await db.execute(
        select(CharacterRelation).where(CharacterRelation.project_id == project_id)
    )).scalars().all()
    chars = {c.id: c.name for c in (await db.execute(
        select(Character).where(Character.project_id == project_id))).scalars().all()}
    out = []
    for r in rels:
        item = RelationOut.model_validate(r)
        item.from_name = chars.get(r.from_character_id, "")
        item.to_name = chars.get(r.to_character_id, "")
        out.append(item)
    return out


@router.post("/projects/{project_id}/relations", response_model=RelationOut)
async def create_relation(project_id: int, data: RelationCreate, db: AsyncSession = Depends(get_db)):
    rel = CharacterRelation(project_id=project_id, **data.model_dump())
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    item = RelationOut.model_validate(rel)
    for cid, attr in ((rel.from_character_id, "from_name"), (rel.to_character_id, "to_name")):
        ch = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
        setattr(item, attr, ch.name if ch else "")
    return item


@router.patch("/relations/{rid}", response_model=RelationOut)
async def update_relation(rid: int, data: RelationUpdate, db: AsyncSession = Depends(get_db)):
    rel = (await db.execute(select(CharacterRelation).where(CharacterRelation.id == rid))).scalar_one_or_none()
    if not rel:
        raise HTTPException(404, "关系不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rel, k, v)
    await db.commit()
    await db.refresh(rel)
    return RelationOut.model_validate(rel)


@router.delete("/relations/{rid}")
async def delete_relation(rid: int, db: AsyncSession = Depends(get_db)):
    rel = (await db.execute(select(CharacterRelation).where(CharacterRelation.id == rid))).scalar_one_or_none()
    if not rel:
        raise HTTPException(404, "关系不存在")
    await db.delete(rel)
    await db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/relations/auto-generate")
async def auto_generate_relations(project_id: int, db: AsyncSession = Depends(get_db)):
    """AI 自动设计角色关系（基于剧本与角色列表）"""
    chars = list((await db.execute(
        select(Character).where(Character.project_id == project_id))).scalars().all())
    if len(chars) < 2:
        raise HTTPException(400, "至少需要 2 个角色才能生成关系")

    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()

    char_dicts = [{"name": c.name, "role": c.role, "personality": c.personality} for c in chars]
    user_prompt = P.build_relation_prompt(
        char_dicts,
        logline=script.logline if script else "",
        script_md=script.content if script else "",
    )

    result = await ai_gateway.chat(
        messages=[
            {"role": "system", "content": P.OPTIMIZE_SYSTEM_PROMPTS["relation"]},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True, temperature=0.7,
    )
    try:
        data = await _parse_json(result["content"])
    except Exception as e:
        raise HTTPException(502, f"AI 返回格式错误：{e}")

    char_by_name = {c.name: c.id for c in chars}
    for c in chars:
        if c.alias:
            char_by_name[c.alias] = c.id

    # 清空旧关系重建
    await db.execute(delete(CharacterRelation).where(CharacterRelation.project_id == project_id))

    created = []
    for r in data.get("relations", []):
        fid = char_by_name.get(r.get("from", ""))
        tid = char_by_name.get(r.get("to", ""))
        if not fid or not tid or fid == tid:
            continue
        rel = CharacterRelation(
            project_id=project_id, from_character_id=fid, to_character_id=tid,
            relation_type=r.get("type", ""), description=r.get("description", ""),
        )
        db.add(rel)
        created.append(r)
    await db.commit()
    return {"ok": True, "count": len(created), "relations": created}


# ============== AI 补充空白字段（不重写已有内容） ==============

async def _script_ctx_for(db: AsyncSession, project_id: int):
    """取项目最新剧本的上下文（文本+梗概）"""
    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    return (script.content if script else "") or "", (script.logline if script else "") or ""


@router.post("/characters/{cid}/enrich")
async def enrich_character_endpoint(cid: int, db: AsyncSession = Depends(get_db)):
    """AI 补充单角色的空白字段（appearance/outfit/personality/backstory/alias）。

    不重写已有内容，仅填充空字段。
    """
    ch = (await db.execute(select(Character).where(Character.id == cid))).scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "角色不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    script_text, logline = await _script_ctx_for(db, ch.project_id)
    before = dict(
        appearance=ch.appearance, outfit=ch.outfit,
        personality=ch.personality, backstory=ch.backstory, alias=ch.alias,
    )
    await _enrich["enrich_character"](db, ch, script_text, logline)
    await db.refresh(ch)
    after = dict(
        appearance=ch.appearance, outfit=ch.outfit,
        personality=ch.personality, backstory=ch.backstory, alias=ch.alias,
    )
    filled = [k for k in before if not (before[k] or "").strip() and (after[k] or "").strip()]
    return {"ok": True, "filled": filled, "character": {
        "id": ch.id, "name": ch.name, "alias": ch.alias, "age": ch.age, "gender": ch.gender,
        "role": ch.role, "appearance": ch.appearance, "outfit": ch.outfit,
        "personality": ch.personality, "backstory": ch.backstory,
    }}


@router.post("/scenes/{sid}/enrich")
async def enrich_scene_endpoint(sid: int, db: AsyncSession = Depends(get_db)):
    """AI 补充单场景的空白字段。"""
    sc = (await db.execute(select(Scene).where(Scene.id == sid))).scalar_one_or_none()
    if not sc:
        raise HTTPException(404, "场景不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    script_text, logline = await _script_ctx_for(db, sc.project_id)
    before = dict(
        location=sc.location, time_of_day=sc.time_of_day, weather=sc.weather,
        mood=sc.mood, description=sc.description, visual_prompt=sc.visual_prompt,
    )
    await _enrich["enrich_scene"](db, sc, script_text, logline)
    await db.refresh(sc)
    after = dict(
        location=sc.location, time_of_day=sc.time_of_day, weather=sc.weather,
        mood=sc.mood, description=sc.description, visual_prompt=sc.visual_prompt,
    )
    filled = [k for k in before if not (before[k] or "").strip() and (after[k] or "").strip()]
    return {"ok": True, "filled": filled, "scene": {
        "id": sc.id, "name": sc.name, "location": sc.location, "time_of_day": sc.time_of_day,
        "weather": sc.weather, "mood": sc.mood, "description": sc.description,
        "visual_prompt": sc.visual_prompt,
    }}


@router.post("/shots/{sid}/enrich")
async def enrich_shot_endpoint(sid: int, db: AsyncSession = Depends(get_db)):
    """AI 补充单分镜的空白字段。"""
    sh = (await db.execute(select(Shot).where(Shot.id == sid))).scalar_one_or_none()
    if not sh:
        raise HTTPException(404, "分镜不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    proj = (await db.execute(select(Project).where(Project.id == sh.project_id))).scalar_one_or_none()
    art_style = proj.art_style if proj else ""
    script_text, logline = await _script_ctx_for(db, sh.project_id)
    before = dict(
        composition=sh.composition, camera_movement=sh.camera_movement,
        camera_angle=sh.camera_angle, dialogue=sh.dialogue, narration=sh.narration,
        visual_prompt=sh.visual_prompt,
    )
    await _enrich["enrich_shot"](db, sh, script_text, logline, art_style)
    await db.refresh(sh)
    after = dict(
        composition=sh.composition, camera_movement=sh.camera_movement,
        camera_angle=sh.camera_angle, dialogue=sh.dialogue, narration=sh.narration,
        visual_prompt=sh.visual_prompt,
    )
    filled = [k for k in before if not (before[k] or "").strip() and (after[k] or "").strip()]
    return {"ok": True, "filled": filled, "shot": {
        "id": sh.id, "shot_code": sh.shot_code, "description": sh.description,
        "composition": sh.composition, "camera_movement": sh.camera_movement,
        "camera_angle": sh.camera_angle, "dialogue": sh.dialogue, "narration": sh.narration,
        "duration_sec": sh.duration_sec, "visual_prompt": sh.visual_prompt,
    }}


@router.post("/projects/{project_id}/enrich-all")
async def enrich_project_endpoint(project_id: int, db: AsyncSession = Depends(get_db)):
    """项目级兜底扫描：逐个 AI 补充所有空白字段。

    用于：用户升级画风、剧本优化后统一对齐、初始化后补救。
    可能耗时（取决于实体数量 × LLM 响应时间）。
    """
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    enriched = await _enrich["enrich_project_entities"](db, project_id)
    total = enriched["characters"] + enriched["scenes"] + enriched["shots"]
    return {"ok": True, "enriched": enriched, "total": total}


# ============== 批量补全端点 ==============

@router.post("/projects/{project_id}/enrich-characters")
async def enrich_characters_batch(project_id: int, db: AsyncSession = Depends(get_db)):
    """批量补全项目所有角色的空白字段。"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    from app.services.entity_enrichment import CHARACTER_FIELDS, _missing_fields

    # 取最新剧本
    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    script_text = (script.content if script else "") or ""
    script_logline = (script.logline if script else "") or ""

    chars = list((await db.execute(
        select(Character).where(Character.project_id == project_id)
    )).scalars().all())

    enriched = 0
    fields_summary: Dict[str, int] = {}
    for ch in chars:
        missing = _missing_fields(ch, CHARACTER_FIELDS)
        if not missing:
            continue
        before = set(_missing_fields(ch, CHARACTER_FIELDS))
        await _enrich["enrich_character"](db, ch, script_text, script_logline)
        await db.refresh(ch)
        after = set(_missing_fields(ch, CHARACTER_FIELDS))
        filled = before - after
        if filled:
            enriched += 1
            for f in filled:
                fields_summary[f] = fields_summary.get(f, 0) + 1
    return {"ok": True, "enriched": enriched, "total": len(chars), "fields": fields_summary}


@router.post("/projects/{project_id}/enrich-scenes")
async def enrich_scenes_batch(project_id: int, db: AsyncSession = Depends(get_db)):
    """批量补全项目所有场景的空白字段。"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    from app.services.entity_enrichment import SCENE_FIELDS, _missing_fields

    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    script_text = (script.content if script else "") or ""
    script_logline = (script.logline if script else "") or ""

    scenes = list((await db.execute(
        select(Scene).where(Scene.project_id == project_id)
    )).scalars().all())

    enriched = 0
    fields_summary: Dict[str, int] = {}
    for sc in scenes:
        missing = _missing_fields(sc, SCENE_FIELDS)
        if not missing:
            continue
        before = set(_missing_fields(sc, SCENE_FIELDS))
        await _enrich["enrich_scene"](db, sc, script_text, script_logline)
        await db.refresh(sc)
        after = set(_missing_fields(sc, SCENE_FIELDS))
        filled = before - after
        if filled:
            enriched += 1
            for f in filled:
                fields_summary[f] = fields_summary.get(f, 0) + 1
    return {"ok": True, "enriched": enriched, "total": len(scenes), "fields": fields_summary}


@router.post("/projects/{project_id}/enrich-shots")
async def enrich_shots_batch(project_id: int, db: AsyncSession = Depends(get_db)):
    """批量补全项目所有分镜的空白字段。"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")
    from app.services.entity_enrichment import entity_enrichment as _enrich
    from app.services.entity_enrichment import SHOT_FIELDS, _missing_fields

    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    script_text = (script.content if script else "") or ""
    script_logline = (script.logline if script else "") or ""
    art_style = proj.art_style or ""

    shots = list((await db.execute(
        select(Shot).where(Shot.project_id == project_id)
    )).scalars().all())

    enriched = 0
    fields_summary: Dict[str, int] = {}
    for sh in shots:
        missing = _missing_fields(sh, SHOT_FIELDS)
        if not missing:
            continue
        before = set(_missing_fields(sh, SHOT_FIELDS))
        await _enrich["enrich_shot"](db, sh, script_text, script_logline, art_style)
        await db.refresh(sh)
        after = set(_missing_fields(sh, SHOT_FIELDS))
        filled = before - after
        if filled:
            enriched += 1
            for f in filled:
                fields_summary[f] = fields_summary.get(f, 0) + 1
    return {"ok": True, "enriched": enriched, "total": len(shots), "fields": fields_summary}


# ============== 批量生成（数量参数） ==============

@router.post("/projects/{project_id}/batch-generate-characters")
async def batch_generate_characters(
    project_id: int,
    body: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
):
    """批量生成角色（按剧本上下文推断并创建 N 个新角色）。

    body: {count?: int=3, focus?: str=''}
    - count: 要生成的角色数量，默认 3
    - focus: 可选的创作方向（如「家庭成员」「职场同事」）
    """
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")

    count = max(1, min(int(body.get("count", 3)), 10))
    focus = str(body.get("focus") or "").strip()

    # 取最新剧本
    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    script_text = (script.content if script else "") or ""
    script_logline = (script.logline if script else "") or ""

    # 已存在的角色名（避免重名）
    existing = list((await db.execute(
        select(Character).where(Character.project_id == project_id)
    )).scalars().all())
    existing_names = [c.name for c in existing if c.name]

    system = (
        "你是专业角色设计师。基于剧本上下文，生成符合剧情且与现有角色不重名的新角色。\n"
        "输出 JSON：{\"characters\": [Character, ...]}\n"
        "Character 字段：name(必填), alias, age(1-150 正整数), gender(男/女), "
        "role(主角/配角/反派/路人), appearance, outfit, personality, backstory\n"
        "要求：\n"
        "1. age 必须是 1-150 之间的正整数\n"
        "2. 名字、性格、外貌、背景与剧本逻辑强相关\n"
        "3. appearance 必须是可直接生图的具体视觉描述（发型发色/脸型/五官/体型/标志性特征）\n"
        "4. 字符串内禁止英文双引号 \" 和反斜杠 \\，需要引用时用中文「」\n"
        "5. 只输出合法 JSON\n"
    )
    user_payload = {
        "logline": script_logline,
        "script_snippet": script_text[:3000],
        "existing_character_names": existing_names,
        "focus": focus or "无特别要求",
        "count": count,
    }
    user = f"生成 {count} 个新角色：\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n请只返回 JSON。"

    try:
        result = await ai_gateway.chat(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            json_mode=True,
            temperature=0.85,
        )
    except Exception as e:
        logger.error(f"批量生成角色 LLM 失败: {e}")
        raise HTTPException(500, f"AI 调用失败: {e}")

    data = await _parse_json((result or {}).get("content", ""))
    new_chars = data.get("characters") or []
    if not isinstance(new_chars, list) or not new_chars:
        return {"ok": False, "created": 0, "items": [], "message": "AI 未返回有效角色"}

    created = []
    for item in new_chars[:count]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name in existing_names:
            continue
        existing_names.append(name)
        ch = Character(
            project_id=project_id,
            name=name,
            alias=str(item.get("alias", "")).strip()[:200],
            age=_coerce_int(item.get("age", 0)) or 0,
            gender=_norm_gender(item.get("gender", "")),
            role=_norm_role(item.get("role", "配角")),
            appearance=str(item.get("appearance", "")).strip(),
            outfit=str(item.get("outfit", "")).strip(),
            personality=str(item.get("personality", "")).strip(),
            backstory=str(item.get("backstory", "")).strip(),
        )
        # age 兜底为 0 时尝试根据角色名/role 推个合理值
        if not ch.age or ch.age < 1:
            ch.age = 30  # 兜底
        db.add(ch)
        created.append(ch)
    if created:
        await db.commit()
        for c in created:
            await db.refresh(c)
    return {
        "ok": True,
        "created": len(created),
        "items": [
            {
                "id": c.id, "name": c.name, "age": c.age, "gender": c.gender,
                "role": c.role, "alias": c.alias,
            } for c in created
        ],
    }


@router.post("/projects/{project_id}/batch-generate-scenes")
async def batch_generate_scenes(
    project_id: int,
    body: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
):
    """批量生成场景（按剧本上下文推断并创建 N 个新场景）。

    body: {count?: int=3, focus?: str=''}
    """
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "项目不存在")

    count = max(1, min(int(body.get("count", 3)), 10))
    focus = str(body.get("focus") or "").strip()

    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    script_text = (script.content if script else "") or ""
    script_logline = (script.logline if script else "") or ""

    existing = list((await db.execute(
        select(Scene).where(Scene.project_id == project_id)
    )).scalars().all())
    existing_names = [s.name for s in existing if s.name]

    system = (
        "你是专业场景概念设计师。基于剧本上下文，生成符合剧情且与现有场景不重名的新场景。\n"
        "输出 JSON：{\"scenes\": [Scene, ...]}\n"
        "Scene 字段：name(必填), location, time_of_day(day/night/dawn/dusk), weather, "
        "mood, description(空间布局/关键物件/光线来源/色彩基调), visual_prompt(可直接生图)\n"
        "要求：\n"
        "1. 场景必须服务于剧情\n"
        "2. description 与 visual_prompt 都要详细、可直接生图\n"
        "3. 字符串内禁止英文双引号 \" 和反斜杠 \\，需要引用时用中文「」\n"
        "4. 只输出合法 JSON\n"
    )
    user_payload = {
        "logline": script_logline,
        "script_snippet": script_text[:3000],
        "existing_scene_names": existing_names,
        "focus": focus or "无特别要求",
        "count": count,
    }
    user = f"生成 {count} 个新场景：\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n请只返回 JSON。"

    try:
        result = await ai_gateway.chat(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            json_mode=True,
            temperature=0.85,
        )
    except Exception as e:
        logger.error(f"批量生成场景 LLM 失败: {e}")
        raise HTTPException(500, f"AI 调用失败: {e}")

    data = await _parse_json((result or {}).get("content", ""))
    new_scenes = data.get("scenes") or []
    if not isinstance(new_scenes, list) or not new_scenes:
        return {"ok": False, "created": 0, "items": [], "message": "AI 未返回有效场景"}

    created = []
    for item in new_scenes[:count]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name in existing_names:
            continue
        existing_names.append(name)
        sc = Scene(
            project_id=project_id,
            name=name,
            location=str(item.get("location", "")).strip(),
            time_of_day=str(item.get("time_of_day", "")).strip(),
            weather=str(item.get("weather", "")).strip(),
            mood=str(item.get("mood", "")).strip(),
            description=str(item.get("description", "")).strip(),
            visual_prompt=str(item.get("visual_prompt", "")).strip() or str(item.get("description", "")).strip(),
        )
        db.add(sc)
        created.append(sc)
    if created:
        await db.commit()
        for s in created:
            await db.refresh(s)
    return {
        "ok": True,
        "created": len(created),
        "items": [
            {
                "id": s.id, "name": s.name, "location": s.location,
                "time_of_day": s.time_of_day, "weather": s.weather,
            } for s in created
        ],
    }


# ============== 工具函数 ==============

def _coerce_int(v: Any) -> Optional[int]:
    """安全地把任意值转 int，失败或 0/负数/超范围返回 None"""
    try:
        n = int(v)
    except Exception:
        return None
    if n < 1 or n > 150:
        return None
    return n


def _norm_gender(v: Any) -> str:
    """规范化 gender 字段"""
    g = str(v or "").strip()
    if g.lower() in ("male", "m"):
        return "男"
    if g.lower() in ("female", "f"):
        return "女"
    if g in ("男", "女", "其他"):
        return g
    return ""


def _norm_role(v: Any) -> str:
    """规范化 role 字段"""
    r = str(v or "").strip()
    mapping = {
        "protagonist": "主角", "supporting": "配角",
        "antagonist": "反派", "extra": "路人",
    }
    return mapping.get(r.lower(), r) if r else "配角"
