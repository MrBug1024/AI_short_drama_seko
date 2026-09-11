"""生成分镜视频 prompt：根据 Shot + 关联 Scene/Characters + 项目剧本 拼装完整提示

设计目标：避免 AI 视频模型只看到一句空泛的 shot_code 而胡乱发挥，
把分镜描述、构图、运镜、角色外貌、场景氛围、镜头时长都翻译成一段可执行的画面语言。

调用方式：
    text, meta = await build_shot_video_prompt(db, project_id, shot_id, fallback_title="SC01")
    ai_gateway.generate_video(prompt=text, ...)
"""
from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.shot import Shot
from app.models.scene import Scene
from app.models.character import Character
from app.models.project import Project


def _clean(s: Optional[str], default: str = "") -> str:
    if not s:
        return default
    s = str(s).strip()
    return s


def _short(s: str, n: int = 80) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


async def _load_shot_context(db: AsyncSession, shot: Shot) -> Dict[str, Any]:
    """加载 shot 的完整语境：scene + characters + project"""
    ctx: Dict[str, Any] = {
        "scene": None,
        "characters": [],
        "project": None,
    }
    # 关联场景
    if shot.scene_id:
        sc = (await db.execute(select(Scene).where(Scene.id == shot.scene_id))).scalar_one_or_none()
        if sc:
            ctx["scene"] = {
                "name": _clean(sc.name),
                "location": _clean(sc.location),
                "time_of_day": _clean(sc.time_of_day),
                "weather": _clean(sc.weather),
                "mood": _clean(getattr(sc, "mood", "")),
                "description": _clean(getattr(sc, "description", "")),
            }
    # 关联角色
    char_ids = shot.character_ids or []
    if char_ids:
        rows = (await db.execute(select(Character).where(Character.id.in_(char_ids)))).scalars().all()
        for c in rows:
            ctx["characters"].append({
                "name": _clean(c.name),
                "alias": _clean(c.alias),
                "age": c.age if isinstance(c.age, int) and c.age > 0 else None,
                "gender": _clean(c.gender),
                "role": _clean(c.role),
                "appearance": _clean(getattr(c, "appearance", "")),
                "personality": _clean(getattr(c, "personality", "")),
                "costume": _clean(getattr(c, "costume", "")),
            })
    # 项目
    p = (await db.execute(select(Project).where(Project.id == shot.project_id))).scalar_one_or_none()
    if p:
        ctx["project"] = {
            "name": _clean(p.name),
            "description": _clean(getattr(p, "description", "")),
            "art_style": _clean(getattr(p, "art_style", "")),
            "genre": _clean(getattr(p, "genre", "")),
        }
    return ctx


def _compose_video_prompt(
    shot: Shot,
    scene: Optional[Dict[str, Any]],
    characters: List[Dict[str, Any]],
    project: Optional[Dict[str, Any]],
) -> str:
    """根据 shot + 关联上下文拼装最终 prompt

    顺序（AI 模型对中段最敏感）：
      1. 艺术风格 / 项目主题
      2. 场景氛围（时间/天气/地点）
      3. 角色外貌（按出现顺序）
      4. 分镜动作/画面
      5. 构图 + 运镜 + 镜头角度
      6. 台词/旁白（参考）
      7. 时长
    """
    parts: List[str] = []

    # 1. 风格
    style_bits: List[str] = []
    if project:
        if project.get("art_style"):
            style_bits.append(project["art_style"])
        elif project.get("genre"):
            style_bits.append(f"{project['genre']} 风格")
    style_bits.append("电影质感")
    style_bits.append("高动态范围")
    parts.append(f"风格：{ '，'.join(style_bits) }。")

    # 2. 场景
    if scene:
        scene_desc_bits = []
        if scene.get("location"):
            scene_desc_bits.append(f"地点「{scene['location']}」")
        if scene.get("name") and scene["name"] != scene.get("location"):
            scene_desc_bits.append(f"（{scene['name']}）")
        if scene.get("time_of_day"):
            scene_desc_bits.append(f"{scene['time_of_day']}")
        if scene.get("weather"):
            scene_desc_bits.append(f"{scene['weather']}")
        if scene.get("mood"):
            scene_desc_bits.append(f"氛围{scene['mood']}")
        if scene_desc_bits:
            parts.append("场景：" + "，".join(scene_desc_bits) + "。")
        if scene.get("description"):
            parts.append(f"环境细节：{ _short(scene['description'], 120) }。")

    # 3. 角色
    if characters:
        char_lines = []
        for c in characters[:4]:  # 最多 4 人，避免 prompt 过长
            name = c["name"] or c["alias"] or "人物"
            demo_bits: List[str] = []
            if c.get("gender"):
                demo_bits.append(c["gender"])
            if c.get("age"):
                demo_bits.append(f"{c['age']}岁")
            demo_str = f"，{'，'.join(demo_bits)}" if demo_bits else ""
            head = f"{name}{demo_str}"

            body_bits: List[str] = []
            # 仅在 appearance 不含数字年龄时才补充 "X 岁"
            appearance = c.get("appearance") or ""
            if appearance and c.get("age") and f"{c['age']}岁" not in appearance:
                body_bits.append(f"{c['age']}岁")
            if appearance:
                body_bits.append(appearance)
            if c.get("costume"):
                body_bits.append(f"穿着 {c['costume']}")
            if c.get("role"):
                body_bits.append(f"身份：{c['role']}")
            body = "，".join(body_bits)

            line = head + (f"，{body}" if body else "")
            char_lines.append(line)
        parts.append("出场角色：" + "；".join(char_lines) + "。")

    # 4. 分镜主体（核心）
    desc = _clean(shot.description) or _clean(shot.visual_prompt)
    if not desc:
        desc = "一个简短的电影场景"
    parts.append(f"画面：{desc}。")

    # 5. 构图 + 运镜 + 角度
    tech_bits = []
    if shot.composition:
        tech_bits.append(f"{shot.composition}构图")
    if shot.camera_movement:
        tech_bits.append(f"{shot.camera_movement}运镜")
    if shot.camera_angle:
        tech_bits.append(f"{shot.camera_angle}")
    if tech_bits:
        parts.append("镜头：" + "，".join(tech_bits) + "。")

    # 6. 台词/旁白（AI 不直接生成声音，但有助于画面氛围）
    if shot.dialogue:
        parts.append(f"台词参考：「{_short(shot.dialogue, 60)}」")
    if shot.narration:
        parts.append(f"旁白参考：「{_short(shot.narration, 60)}」")

    # 7. 负面提示
    neg = _clean(shot.negative_prompt)
    if neg:
        parts.append(f"避免：{neg}。")

    # 拼接 → 单段流畅文本
    full = " ".join(parts)

    # 末尾时长提醒（视频模型有时按字数匹配时长）
    dur = shot.duration_sec or 5
    parts.append(f"时长 {int(dur)} 秒。")
    full = " ".join(parts)

    return full


async def build_shot_video_prompt(
    db: AsyncSession,
    project_id: int,
    shot_id: int,
    fallback_title: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """主入口：返回 (rich_prompt, meta)

    meta 包含 shot_code / scene_name / character_names / 项目名，
    方便写回 GenerationTask.params 给前端展示。
    """
    shot = (await db.execute(
        select(Shot).where(Shot.id == shot_id, Shot.project_id == project_id)
    )).scalar_one_or_none()

    if not shot:
        # 没找到 shot：返回兜底
        return (fallback_title or "a cinematic scene"), {"shot_id": shot_id, "shot_missing": True}

    ctx = await _load_shot_context(db, shot)
    prompt = _compose_video_prompt(shot, ctx["scene"], ctx["characters"], ctx["project"])

    meta = {
        "shot_id": shot.id,
        "shot_code": _clean(shot.shot_code),
        "shot_no": shot.shot_no,
        "scene_name": (ctx["scene"] or {}).get("name") or (ctx["scene"] or {}).get("location") or "",
        "character_names": [c["name"] for c in ctx["characters"] if c.get("name")],
        "duration_sec": int(shot.duration_sec or 5),
        "has_visual_prompt": bool(_clean(shot.visual_prompt)),
        "composition": _clean(shot.composition),
        "camera_movement": _clean(shot.camera_movement),
        "camera_angle": _clean(shot.camera_angle),
    }
    logger.info(
        f"video_prompt shot#{shot.id} {shot.shot_code} → "
        f"{len(prompt)} chars (scene={meta['scene_name']!r}, chars={meta['character_names']})"
    )
    return prompt, meta
