"""分镜关系修复服务：自动给孤儿 shot 补 scene_id 和 character_ids

触发场景：
- 历史项目创建时 AI 返回缺字段
- 用户编辑剧本后重新解析，scene_name 没匹配上
- 任何 scene_id=None 或 character_ids=[] 的 shot

修复策略（按优先级）：
1. 关键词匹配：shot.description 中出现「场景名 / 场景 location」→ 关联 scene
2. 关键词匹配：shot.description/dialogue 中出现「角色名 / 别名」→ 关联 character
3. 兜底：scene_id 设为项目第一个场景，character_ids 设为主角
"""
from __future__ import annotations
import re
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from loguru import logger

from app.models.shot import Shot
from app.models.scene import Scene
from app.models.character import Character


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())


async def _load_scene_map(db: AsyncSession, project_id: int) -> Dict[str, int]:
    """name + location + description 关键词都映射到 scene id"""
    rows = (await db.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
    m: Dict[str, int] = {}
    for s in rows:
        if s.name:
            m[_norm(s.name)] = s.id
        if s.location:
            m[_norm(s.location)] = s.id
        # 从 description 抽取 2 字以上名词短语作关键词
        if s.description:
            for kw in _extract_keywords(s.description):
                if kw not in m:
                    m[kw] = s.id
    return m


# 场景描述里高频出现的有用名词（可扩展）
_KW_STOP = {
    "的", "了", "是", "在", "和", "有", "一", "个", "上", "下", "里", "外", "前", "后", "中",
    "着", "着", "把", "被", "让", "给", "从", "到", "为", "与", "及", "或", "并", "而",
    "画面", "可见", "显示", "出现", "透出", "洒落", "洒满", "悬挂", "依山", "依", "尽",
}


def _extract_keywords(text: str) -> List[str]:
    """从描述里抽 2-4 字关键词（中文 n-gram）"""
    import re
    # 清理标点
    cleaned = re.sub(r"[，。、；：？！《》（）()…—\-,.!?]", " ", text)
    out = []
    # 2-4 字 n-gram
    for n in (3, 2):
        for i in range(len(cleaned) - n + 1):
            seg = cleaned[i:i + n].strip()
            if not seg or seg in _KW_STOP:
                continue
            # 至少含一个汉字
            if not any("\u4e00" <= ch <= "\u9fff" for ch in seg):
                continue
            out.append(seg)
    # 去重保序
    seen = set()
    dedup = []
    for k in out:
        if k not in seen:
            seen.add(k)
            dedup.append(k)
    return dedup[:30]  # 每个场景最多 30 个关键词


async def _load_character_map(db: AsyncSession, project_id: int) -> Dict[str, int]:
    """name + alias 都映射到 character id"""
    rows = (await db.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
    m: Dict[str, int] = {}
    for c in rows:
        if c.name:
            m[_norm(c.name)] = c.id
        if c.alias:
            m[_norm(c.alias)] = c.id
    return m


async def repair_project_shots(db: AsyncSession, project_id: int, *, dry_run: bool = False) -> Dict[str, Any]:
    """扫描并修复项目所有孤儿 shot

    Returns: {"scanned": N, "fixed_scene": N, "fixed_characters": N, "details": [...]}
    """
    # 1. 加载场景/角色映射
    scene_map = await _load_scene_map(db, project_id)
    char_map = await _load_character_map(db, project_id)

    # 2. 加载孤儿 shot
    stmt = select(Shot).where(Shot.project_id == project_id)
    all_shots = (await db.execute(stmt.order_by(Shot.shot_no))).scalars().all()
    orphans = [s for s in all_shots if s.scene_id is None or not (s.character_ids or [])]

    if not orphans:
        return {"scanned": len(all_shots), "fixed_scene": 0, "fixed_characters": 0, "details": []}

    # 3. 兜底值：第一个场景 + 主角（role=主角 or 第一个角色）
    fallback_scene_id = next(iter(scene_map.values()), None) if scene_map else None
    main_char_id = None
    chars = (await db.execute(
        select(Character).where(Character.project_id == project_id).order_by(Character.id)
    )).scalars().all()
    for c in chars:
        if c.role and "主角" in c.role:
            main_char_id = c.id
            break
    if not main_char_id and chars:
        main_char_id = chars[0].id

    # 4. 关键词匹配（按名称长度倒序，避免「林」匹配到「林远」前先匹配到「林母」）
    sorted_scene_keys = sorted(scene_map.keys(), key=len, reverse=True)
    sorted_char_keys = sorted(char_map.keys(), key=len, reverse=True)

    fixed_scene = 0
    fixed_char = 0
    details: List[Dict[str, Any]] = []

    for shot in orphans:
        text = _norm((shot.description or "") + (shot.dialogue or "") + (shot.narration or ""))

        # 场景修复
        new_scene_id = shot.scene_id
        if new_scene_id is None:
            for key in sorted_scene_keys:
                if key and key in text:
                    new_scene_id = scene_map[key]
                    break
            if new_scene_id is None and fallback_scene_id:
                new_scene_id = fallback_scene_id
            if new_scene_id != shot.scene_id:
                shot.scene_id = new_scene_id
                fixed_scene += 1

        # 角色修复
        new_char_ids = list(shot.character_ids or [])
        if not new_char_ids:
            for key in sorted_char_keys:
                if key and key in text:
                    cid = char_map[key]
                    if cid not in new_char_ids:
                        new_char_ids.append(cid)
            if not new_char_ids and main_char_id:
                new_char_ids = [main_char_id]
            if new_char_ids != (shot.character_ids or []):
                shot.character_ids = new_char_ids
                fixed_char += 1

        details.append({
            "shot_id": shot.id,
            "shot_code": shot.shot_code,
            "scene_id": shot.scene_id,
            "character_ids": shot.character_ids,
            "desc_preview": (shot.description or "")[:60],
        })

    if not dry_run:
        await db.commit()

    logger.info(
        f"[shot_repair] project#{project_id}: scanned={len(all_shots)} "
        f"orphans={len(orphans)} fixed_scene={fixed_scene} fixed_char={fixed_char}"
    )
    return {
        "scanned": len(all_shots),
        "orphans": len(orphans),
        "fixed_scene": fixed_scene,
        "fixed_characters": fixed_char,
        "details": details,
    }
