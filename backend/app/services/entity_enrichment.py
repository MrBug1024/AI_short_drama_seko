"""实体字段 AI 补充服务

设计目标：
- 解决「剧本解析时字段被空、点开设计面板空空如也」的核心痛点
- 任何写入路径（剧本解析 / 剧本优化 / 手动创建）结束后，自动扫描实体关键字段
- 空字段根据剧本上下文 + 该实体的现有字段，调用 LLM 一次性补齐

调用入口：
- enrich_character(db, character, script_text) - 单角色补全
- enrich_scene(db, scene, script_text) - 单场景补全
- enrich_shot(db, shot, script_text) - 单分镜补全
- enrich_project_entities(db, project) - 一次性扫描项目所有实体（兜底）
"""
import json
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import ai_gateway
from app.models.character import Character
from app.models.scene import Scene
from app.models.shot import Shot
from app.models.script import Script


CHARACTER_FIELDS = ("age", "gender", "role", "appearance", "outfit", "personality", "backstory", "alias")
SCENE_FIELDS = ("location", "time_of_day", "weather", "mood", "description", "visual_prompt")
SHOT_FIELDS = ("composition", "camera_movement", "camera_angle", "dialogue", "narration", "visual_prompt")


def _has_value(v: Any) -> bool:
    """判断字段是否有有效值（非空字符串/0/空列表/None）"""
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return len(v) > 0
    if isinstance(v, (int, float)):
        return v != 0
    return True


def _age_valid(v: Any) -> bool:
    """年龄合法：正整数且在 1~150 之间"""
    try:
        n = int(v)
    except Exception:
        return False
    return 1 <= n <= 150


def _missing_fields(obj: Any, fields: tuple) -> List[str]:
    """返回对象中值为空的字段名列表"""
    missing = []
    for f in fields:
        v = getattr(obj, f, None)
        if not _has_value(v):
            missing.append(f)
    return missing


def _coerce_int(v: Any) -> Optional[int]:
    """安全地把任意值转 int，失败或 0/负数/超范围返回 None"""
    try:
        n = int(v)
    except Exception:
        return None
    if n < 1 or n > 150:
        return None
    return n


async def _call_llm_json(system: str, user: str) -> Dict[str, Any]:
    """调用 LLM 并解析 JSON（多级容错，参考 design.py _parse_json）"""
    try:
        result = await ai_gateway.chat(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            json_mode=True,
            temperature=0.7,
        )
    except Exception as e:
        # gateway 失败时不抛出，避免影响主流程
        logger.warning(f"AI 补充调用失败: {e}")
        return {}

    content = (result or {}).get("content", "")
    if not content:
        return {}

    # 剥代码围栏
    s = content.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    s = s.strip()

    candidates = [s]
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        candidates.append(s[start:end + 1])

    for cand in candidates:
        try:
            return json.loads(cand)
        except Exception:
            pass

    import re as _re
    for cand in list(candidates):
        fixed = _re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            return json.loads(fixed)
        except Exception:
            pass
    logger.warning(f"AI 补充返回非 JSON: {content[:200]}")
    return {}


# ============== 角色补全 ==============

async def enrich_character(
    db: AsyncSession,
    character: Character,
    script_text: str = "",
    script_logline: str = "",
) -> Character:
    """补全角色空白字段。基于剧本上下文 + 角色现有字段推理。"""
    missing = _missing_fields(character, CHARACTER_FIELDS)
    if not missing:
        return character

    # 取该角色在剧本里出现的片段（按名字前后各取 200 字）
    name = character.name or character.alias or ""
    context_snippet = ""
    if name and script_text:
        idx = script_text.find(name)
        if idx != -1:
            start = max(0, idx - 200)
            end = min(len(script_text), idx + 400)
            context_snippet = script_text[start:end]

    system = (
        "你是专业角色设计师。请根据提供的剧本片段和角色已有信息，"
        f"补全角色的缺失字段。输出 JSON 对象，仅包含缺失字段。\n"
        "硬性要求（必须遵守）：\n"
        "1. age 必须是 1-150 之间的正整数，绝对不能是 0 或负数。"
        "   若 user_payload 中 age 为 null 或 0，表示数据库默认未设置，必须从剧本推断并补全\n"
        "2. gender 取值 男/女/其他（中文）。若 user_payload 中 gender 为 null 或空字符串，必须补全\n"
        "3. role 取值 主角/配角/反派/路人 之一（中文）。若为 null/空必须补全\n"
        "4. appearance 必须是可直接生图的具体视觉描述（发型发色/脸型/五官/体型/标志性特征），禁止抽象词\n"
        "5. outfit 具体到款式+颜色\n"
        "6. personality 用 3-5 个关键词\n"
        "7. backstory 50 字以内，说明与剧情冲突相关的关键经历\n"
        "8. alias 若原本没有别名，留空字符串\n"
        "9. 字符串值内禁止使用英文双引号 \" 和反斜杠 \\，需要引用时用中文引号「」\n"
        "10. missing_fields 列表中每个字段都必须出现在返回 JSON 中\n"
        "11. 只输出合法 JSON\n"
    )
    # 把数据库默认值 0 / "" 转成 None，让 LLM 明确知道是"未设置"而不是"已知为0"
    current_age = character.age if _age_valid(character.age) else None
    current_gender = (character.gender or "").strip() or None
    current_role = (character.role or "").strip() or None

    user_payload = {
        "role_name": character.name,
        "role_alias": character.alias,
        "age": current_age,  # null 表示数据库未设置（不要传 0，LLM 会以为是"已知年龄为0"）
        "gender": current_gender,  # null 表示未设置
        "role": current_role,  # null 表示未设置
        "existing_appearance": character.appearance,
        "existing_outfit": character.outfit,
        "existing_personality": character.personality,
        "existing_backstory": character.backstory,
        "logline": script_logline,
        "script_snippet": context_snippet[:1500],
        "missing_fields": list(missing),
        "_reminder": "missing_fields 列表里每个字段都必须出现在返回 JSON 中。"
        "age/gender/role 为 null 时视为未设置，必须根据剧本推断并补全。",
    }
    user = f"补全角色信息：\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n请只返回 JSON。"

    data = await _call_llm_json(system, user)
    if not data:
        return character

    # 兜底：检查关键字段（age/gender/role）是否被返回，没有则重试一次
    critical_missing = [f for f in missing if f in ("age", "gender", "role") and not _has_value(data.get(f))]
    if critical_missing:
        logger.info(f"角色 {character.id} 关键字段 {critical_missing} 首次未返回，重试一次")
        retry_system = (
            system
            + "\n再次强调：用户已明确要求 " + "、".join(critical_missing)
            + " 必须返回，且 age 必须是 1-150 的正整数（不能是 0）。"
        )
        retry_data = await _call_llm_json(retry_system, user)
        if retry_data:
            for k in critical_missing:
                if _has_value(retry_data.get(k)) and not _has_value(data.get(k)):
                    data[k] = retry_data[k]

    changed = False
    for f in missing:
        v = data.get(f)
        if not _has_value(v):
            continue
        # age 必须 1-150（避免 LLM 给 0 / 负数 / 200）
        if f == "age":
            n = _coerce_int(v)
            if n is None:
                logger.warning(f"角色 {character.id} AI 返回的 age={v!r} 不合法，跳过")
                continue
            character.age = n
            changed = True
        elif f == "gender":
            g = str(v).strip()
            if g in ("男", "女", "其他", "male", "female", "other", "M", "F", "m", "f"):
                # 统一存中文
                if g.lower() in ("male", "m"):
                    g = "男"
                elif g.lower() in ("female", "f"):
                    g = "女"
                character.gender = g
                changed = True
            else:
                logger.warning(f"角色 {character.id} AI 返回的 gender={v!r} 不在枚举中，跳过")
        elif f == "role":
            r = str(v).strip()
            if r in ("主角", "配角", "反派", "路人", "protagonist", "supporting", "antagonist", "extra"):
                mapping = {"protagonist": "主角", "supporting": "配角", "antagonist": "反派", "extra": "路人"}
                character.role = mapping.get(r.lower(), r)
                changed = True
            else:
                logger.warning(f"角色 {character.id} AI 返回的 role={v!r} 不在枚举中，跳过")
        else:
            # alias 空字符串是合法值（表示"无别名"），但仅在 LLM 明确给出空串时接受；这里只要非空就用
            setattr(character, f, str(v) if not isinstance(v, (int, list)) else v)
            changed = True
    if changed:
        await db.commit()
        logger.info(f"角色 {character.id} ({character.name}) AI 补充字段：{missing}")
    return character


# ============== 场景补全 ==============

async def enrich_scene(
    db: AsyncSession,
    scene: Scene,
    script_text: str = "",
    script_logline: str = "",
) -> Scene:
    missing = _missing_fields(scene, SCENE_FIELDS)
    if not missing:
        return scene

    name = scene.name or ""
    context_snippet = ""
    if name and script_text:
        idx = script_text.find(name)
        if idx != -1:
            start = max(0, idx - 200)
            end = min(len(script_text), idx + 400)
            context_snippet = script_text[start:end]

    system = (
        "你是场景概念设计师。请根据提供的剧本片段和场景已有信息，"
        "补全场景的缺失字段。输出 JSON 对象，仅包含缺失字段。\n"
        "要求：\n"
        "1. description 包含空间布局/关键物件/光线来源/色彩基调\n"
        "2. visual_prompt 是可直接生图的视觉描述（构图+前景中景背景+光线+色调）\n"
        "3. time_of_day 取值 day/night/dawn/dusk\n"
        "4. 字符串值内禁止使用英文双引号 \" 和反斜杠 \\，需要引用时用中文引号「」\n"
        "5. 只输出合法 JSON\n"
    )
    user_payload = {
        "scene_name": scene.name,
        "existing_location": scene.location,
        "existing_time_of_day": scene.time_of_day,
        "existing_weather": scene.weather,
        "existing_mood": scene.mood,
        "existing_description": scene.description,
        "existing_visual_prompt": scene.visual_prompt,
        "logline": script_logline,
        "script_snippet": context_snippet[:1500],
        "missing_fields": list(missing),
    }
    user = f"补全场景信息：\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n请只返回 JSON。"

    data = await _call_llm_json(system, user)
    if not data:
        return scene

    changed = False
    for f in missing:
        v = data.get(f)
        if _has_value(v):
            setattr(scene, f, str(v))
            changed = True
    if changed:
        await db.commit()
        logger.info(f"场景 {scene.id} ({scene.name}) AI 补充字段：{missing}")
    return scene


# ============== 分镜补全 ==============

async def enrich_shot(
    db: AsyncSession,
    shot: Shot,
    script_text: str = "",
    script_logline: str = "",
    project_art_style: str = "",
) -> Shot:
    missing = _missing_fields(shot, SHOT_FIELDS)
    if not missing:
        return shot

    # 取镜头描述片段
    code = shot.shot_code or ""
    context_snippet = ""
    if code and script_text:
        # 按编号搜索
        idx = script_text.find(code)
        if idx == -1:
            # 按描述搜索
            if shot.description:
                idx = script_text.find(shot.description[:30])
        if idx != -1:
            start = max(0, idx - 200)
            end = min(len(script_text), idx + 400)
            context_snippet = script_text[start:end]

    # 取出该镜头关联的场景和角色
    scene = None
    if shot.scene_id:
        scene = (await db.execute(select(Scene).where(Scene.id == shot.scene_id))).scalar_one_or_none()
    chars = []
    if shot.character_ids:
        chars = list((await db.execute(
            select(Character).where(Character.id.in_(shot.character_ids))
        )).scalars().all())

    system = (
        "你是分镜导演。请根据提供的剧本片段、镜头已有信息、所属场景和出场角色设定，"
        "补全镜头的缺失字段。输出 JSON 对象，仅包含缺失字段。\n"
        "要求：\n"
        "1. composition 用专业构图术语（九宫格/中心/对称/三分法/对角线 等）\n"
        "2. camera_movement 用专业运镜术语（推/拉/摇/移/跟/固定/升/降/环绕/手持）\n"
        "3. camera_angle 格式为「角度+景别」（如：俯视中景/平视特写）\n"
        "4. visual_prompt 是可直接生图的画面描述，必须包含出场角色的外貌特征\n"
        "5. dialogue 若该镜无台词，留空字符串\n"
        "6. narration 若该镜无旁白，留空字符串\n"
        "7. 字符串值内禁止使用英文双引号 \" 和反斜杠 \\，需要引用时用中文引号「」\n"
        "8. 只输出合法 JSON\n"
    )
    user_payload = {
        "shot_code": shot.shot_code,
        "existing_description": shot.description,
        "existing_composition": shot.composition,
        "existing_camera_movement": shot.camera_movement,
        "existing_camera_angle": shot.camera_angle,
        "existing_dialogue": shot.dialogue,
        "existing_narration": shot.narration,
        "existing_visual_prompt": shot.visual_prompt,
        "scene": {
            "name": scene.name if scene else "",
            "location": scene.location if scene else "",
            "time_of_day": scene.time_of_day if scene else "",
            "weather": scene.weather if scene else "",
            "mood": scene.mood if scene else "",
            "description": scene.description if scene else "",
            "visual_prompt": scene.visual_prompt if scene else "",
        } if scene else None,
        "characters": [
            {
                "name": c.name, "appearance": c.appearance, "outfit": c.outfit,
            } for c in chars
        ],
        "logline": script_logline,
        "art_style": project_art_style,
        "script_snippet": context_snippet[:1500],
        "missing_fields": list(missing),
    }
    user = f"补全分镜信息：\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}\n请只返回 JSON。"

    data = await _call_llm_json(system, user)
    if not data:
        return shot

    changed = False
    for f in missing:
        v = data.get(f)
        if _has_value(v):
            setattr(shot, f, str(v))
            changed = True
    if changed:
        await db.commit()
        logger.info(f"分镜 {shot.id} ({shot.shot_code}) AI 补充字段：{missing}")
    return shot


# ============== 项目级别兜底扫描 ==============

async def enrich_project_entities(db: AsyncSession, project_id: int) -> Dict[str, int]:
    """扫描项目所有实体的空白字段，调用 LLM 补充。

    用途：
    - 项目创建完成后兜底（即便 LLM 第一次没填全，也能补救）
    - 用户升级画风/剧本优化后，对齐所有实体
    - 手动触发「AI 重新生成所有空白字段」按钮

    Returns: {"characters": n, "scenes": n, "shots": n} 补充的实体数量
    """
    # 取最新剧本
    script = (await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )).scalars().first()
    script_text = (script.content if script else "") or ""
    script_logline = (script.logline if script else "") or ""

    from app.models.project import Project
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    art_style = proj.art_style if proj else ""

    char_count = 0
    scene_count = 0
    shot_count = 0

    # 角色
    chars = list((await db.execute(
        select(Character).where(Character.project_id == project_id)
    )).scalars().all())
    for ch in chars:
        if _missing_fields(ch, CHARACTER_FIELDS):
            before = set(_missing_fields(ch, CHARACTER_FIELDS))
            await enrich_character(db, ch, script_text, script_logline)
            await db.refresh(ch)
            after = set(_missing_fields(ch, CHARACTER_FIELDS))
            if before - after:
                char_count += 1

    # 场景
    scenes = list((await db.execute(
        select(Scene).where(Scene.project_id == project_id)
    )).scalars().all())
    for sc in scenes:
        if _missing_fields(sc, SCENE_FIELDS):
            before = set(_missing_fields(sc, SCENE_FIELDS))
            await enrich_scene(db, sc, script_text, script_logline)
            await db.refresh(sc)
            after = set(_missing_fields(sc, SCENE_FIELDS))
            if before - after:
                scene_count += 1

    # 分镜
    shots = list((await db.execute(
        select(Shot).where(Shot.project_id == project_id)
    )).scalars().all())
    for sh in shots:
        if _missing_fields(sh, SHOT_FIELDS):
            before = set(_missing_fields(sh, SHOT_FIELDS))
            await enrich_shot(db, sh, script_text, script_logline, art_style)
            await db.refresh(sh)
            after = set(_missing_fields(sh, SHOT_FIELDS))
            if before - after:
                shot_count += 1

    return {"characters": char_count, "scenes": scene_count, "shots": shot_count}


entity_enrichment = {
    "enrich_character": enrich_character,
    "enrich_scene": enrich_scene,
    "enrich_shot": enrich_shot,
    "enrich_project_entities": enrich_project_entities,
}
