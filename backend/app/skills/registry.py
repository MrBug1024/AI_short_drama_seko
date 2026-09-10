"""技能注册表 - 内置技能模板

每个技能是一组预设的 prompt + 节点配置 + 流程模板
"""
from typing import List, Dict, Any


# 8 个内置技能，对应 Seko 调研中的核心场景
BUILTIN_SKILLS: List[Dict[str, Any]] = [
    {
        "code": "drama_story",
        "name": "短剧故事",
        "description": "5 步生成完整短剧：创意→分镜→角色→场景→视频",
        "icon": "🎬",
        "category": "drama",
        "sort_order": 1,
        "template": {
            "steps": ["idea", "outline", "characters", "scenes", "shots", "video"],
            "default_art_style": "电影质感",
            "estimated_minutes": 5,
        },
    },
    {
        "code": "comic_drama",
        "name": "AI 漫画剧",
        "description": "漫画风格短剧，适合抖音/红果漫剧平台",
        "icon": "📚",
        "category": "comic",
        "sort_order": 2,
        "template": {
            "steps": ["idea", "outline", "characters", "panels", "shots", "video"],
            "default_art_style": "日漫/漫画分镜",
            "estimated_minutes": 3,
        },
    },
    {
        "code": "knowledge_short",
        "name": "知识科普短片",
        "description": "把任意知识主题变成 1-3 分钟科普短片",
        "icon": "📖",
        "category": "knowledge",
        "sort_order": 3,
        "template": {
            "steps": ["topic", "outline", "narration", "shots", "video"],
            "default_art_style": "扁平插画/科普动画",
            "estimated_minutes": 3,
        },
    },
    {
        "code": "ecommerce_ad",
        "name": "电商广告",
        "description": "上传商品素材，自动生成多版本产品广告",
        "icon": "🛒",
        "category": "ecommerce",
        "sort_order": 4,
        "template": {
            "steps": ["product", "hook", "shots", "video", "variants"],
            "default_art_style": "高质感商品广告",
            "estimated_minutes": 4,
        },
    },
    {
        "code": "character_2nd",
        "name": "角色二创",
        "description": "导入已有 IP 角色形象，保持一致生成二创内容",
        "icon": "🎭",
        "category": "drama",
        "sort_order": 5,
        "template": {
            "steps": ["character_import", "idea", "shots", "video"],
            "default_art_style": "保持参考图风格",
            "estimated_minutes": 3,
        },
    },
    {
        "code": "translate_dub",
        "name": "出海剧转绘",
        "description": "导入外语视频，自动转绘为本地化分镜+翻译配音",
        "icon": "🌍",
        "category": "translate",
        "sort_order": 6,
        "template": {
            "steps": ["video_import", "audio_separate", "translate", "storyboard", "shoot", "video"],
            "default_art_style": "原片风格保持",
            "estimated_minutes": 8,
        },
    },
    {
        "code": "microdrama_series",
        "name": "微短剧连续剧",
        "description": "支持 100 集连续剧情，角色跨集一致性",
        "icon": "📺",
        "category": "drama",
        "sort_order": 7,
        "template": {
            "steps": ["series_plan", "episode_outline", "characters", "scenes", "shots", "video"],
            "default_art_style": "剧集统一风格",
            "estimated_minutes": 30,
            "enable_long_context": True,
        },
    },
    {
        "code": "anim_motion",
        "name": "动效动画",
        "description": "适用于 MG 动画/表情包/二创短视频",
        "icon": "✨",
        "category": "animation",
        "sort_order": 8,
        "template": {
            "steps": ["style", "script", "shots", "video"],
            "default_art_style": "MG 动效/表情包",
            "estimated_minutes": 3,
        },
    },
]


async def ensure_default_skills(db):
    """启动时确保默认技能入库"""
    from sqlalchemy import select
    from app.models.skill import Skill

    existing = (await db.execute(select(Skill.code))).scalars().all()
    existing_set = set(existing)

    for s in BUILTIN_SKILLS:
        if s["code"] not in existing_set:
            db.add(Skill(
                code=s["code"],
                name=s["name"],
                description=s["description"],
                icon=s["icon"],
                category=s["category"],
                sort_order=s["sort_order"],
                template=s["template"],
                installed=True,
                is_builtin=True,
            ))
    await db.commit()