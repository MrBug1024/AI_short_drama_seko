"""默认数据初始化 - 会员/模型/画风（模仿 Seko 数据）"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# 4 级会员（模仿 Seko：免费/标准/高级/企业）
DEFAULT_MEMBERSHIPS = [
    {
        "tier": "free",
        "name": "免费会员",
        "description": "体验 Seko 全部核心功能",
        "monthly_price": 0,
        "yearly_price": 0,
        "monthly_credits": 0,
        "daily_login_credits": 10,
        "max_episodes": 1,
        "max_shots_per_gen": 30,
        "hd_video": False,
        "remove_watermark": False,
        "priority_queue": False,
        "team_collaboration": False,
        "vip_support": False,
        "sort_order": 1,
        "badge": "",
    },
    {
        "tier": "standard",
        "name": "标准会员",
        "description": "适合个人创作者持续产出",
        "monthly_price": 39,
        "yearly_price": 374,  # 8 折
        "monthly_credits": 500,
        "daily_login_credits": 20,
        "max_episodes": 10,
        "max_shots_per_gen": 50,
        "hd_video": True,
        "remove_watermark": True,
        "priority_queue": False,
        "team_collaboration": False,
        "vip_support": False,
        "sort_order": 2,
        "badge": "首购优惠",
    },
    {
        "tier": "pro",
        "name": "高级会员",
        "description": "适合内容工作室/MCN 机构",
        "monthly_price": 195,
        "yearly_price": 1872,
        "monthly_credits": 3000,
        "daily_login_credits": 50,
        "max_episodes": 50,
        "max_shots_per_gen": 80,
        "hd_video": True,
        "remove_watermark": True,
        "priority_queue": True,
        "team_collaboration": False,
        "vip_support": False,
        "sort_order": 3,
        "badge": "最受欢迎",
    },
    {
        "tier": "enterprise",
        "name": "企业会员",
        "description": "短剧团队/影视公司定制方案",
        "monthly_price": 0,  # 定制
        "yearly_price": 0,
        "monthly_credits": 0,  # 按需
        "daily_login_credits": 100,
        "max_episodes": 100,
        "max_shots_per_gen": 120,
        "hd_video": True,
        "remove_watermark": True,
        "priority_queue": True,
        "team_collaboration": True,
        "vip_support": True,
        "sort_order": 4,
        "badge": "VIP 定制",
    },
]


# 模型目录（模仿 Seko 聚合模型）
DEFAULT_MODELS = [
    # 视频模型
    {
        "code": "seedance-2.0",
        "name": "Seedance 2.0 满血版",
        "vendor": "doubao",
        "icon": "🎬",
        "model_type": "video",
        "description": "影视级真人剧直出，突破 15s 限制，30 分钟连贯剧情一键生成",
        "features": ["首帧生视频", "尾帧生视频", "参考生视频", "音画同出", "唇形同步"],
        "specs": {"max_duration": 1800, "resolution": "1080P", "aspect_ratios": ["16:9", "9:16", "1:1", "21:9"]},
        "credits_per_second": 8,
        "is_premium": True,
        "is_recommended": True,
        "sort_order": 1,
    },
    {
        "code": "kling-3.0",
        "name": "可灵 3.0",
        "vendor": "kling",
        "icon": "⚡",
        "model_type": "video",
        "description": "分镜切镜灵活性超高，音画同出支持多人，人物演绎更具张力",
        "features": ["首帧", "尾帧", "镜头运动", "多人同出"],
        "specs": {"max_duration": 15, "resolution": "1080P"},
        "credits_per_second": 10,
        "is_recommended": True,
        "sort_order": 2,
    },
    {
        "code": "kling-o3",
        "name": "可灵 O3 院线级原生 4K",
        "vendor": "kling",
        "icon": "✨",
        "model_type": "video",
        "description": "更清晰、更细腻、更真实；电影级质感，文字细节还原",
        "features": ["4K", "院线质感", "文字细节"],
        "specs": {"max_duration": 15, "resolution": "4K"},
        "credits_per_second": 20,
        "is_premium": True,
        "sort_order": 3,
    },
    {
        "code": "vidu-q3",
        "name": "Vidu Q3",
        "vendor": "vidu",
        "icon": "🎞️",
        "model_type": "video",
        "description": "细节表现更优秀，画质与稳定性更进一步",
        "features": ["首尾帧", "文生视频", "图生视频"],
        "specs": {"max_duration": 10, "resolution": "1080P"},
        "credits_per_second": 8,
        "sort_order": 4,
    },
    {
        "code": "vidu-q3-mix",
        "name": "Vidu Q3 Mix",
        "vendor": "vidu",
        "icon": "🎬",
        "model_type": "video",
        "description": "风格复刻更精准，长视频画面衔接更自然",
        "features": ["风格迁移", "长视频"],
        "specs": {"max_duration": 30, "resolution": "1080P"},
        "credits_per_second": 12,
        "sort_order": 5,
    },
    {
        "code": "wan-2.5",
        "name": "通义万相 2.5",
        "vendor": "aliyun",
        "icon": "🌊",
        "model_type": "video",
        "description": "阿里通义万相，影视级中文理解",
        "features": ["文生视频", "图生视频", "运镜"],
        "specs": {"max_duration": 10, "resolution": "1080P"},
        "credits_per_second": 6,
        "sort_order": 6,
    },
    {
        "code": "happyhorse-1.1",
        "name": "Happyhorse 1.1",
        "vendor": "happyhorse",
        "icon": "🐎",
        "model_type": "video",
        "description": "15s 多镜头叙事，电影级画质；真人友好，动作/微表情/对白真实自然",
        "features": ["多镜头", "电影级", "唇形同步", "音画一体"],
        "specs": {"max_duration": 15, "resolution": "1080P"},
        "credits_per_second": 15,
        "is_premium": True,
        "is_recommended": True,
        "sort_order": 7,
    },
    {
        "code": "jimeng-5.0",
        "name": "即梦 5.0",
        "vendor": "doubao",
        "icon": "🌟",
        "model_type": "image",
        "description": "精准掌控创作能力，实时联网检索生图，深刻把握模糊指令",
        "features": ["高清生图", "联网检索", "指令遵循"],
        "specs": {"resolution": "2048", "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"]},
        "credits_per_image": 3,
        "is_recommended": True,
        "sort_order": 1,
    },
    {
        "code": "nano-banana",
        "name": "Nano Banana",
        "vendor": "nano_banana",
        "icon": "🍌",
        "model_type": "image",
        "description": "一致性大师模型 2.0：跨分镜角色一致性最强",
        "features": ["角色一致性", "风格统一"],
        "specs": {"resolution": "2048"},
        "credits_per_image": 4,
        "is_recommended": True,
        "sort_order": 2,
    },
    {
        "code": "midjourney-v7",
        "name": "Midjourney V7",
        "vendor": "midjourney",
        "icon": "🎨",
        "model_type": "image",
        "description": "国际顶级生图，画质与艺术感兼备",
        "features": ["艺术级", "电影质感"],
        "specs": {"resolution": "2048"},
        "credits_per_image": 5,
        "is_premium": True,
        "sort_order": 3,
    },
    {
        "code": "image-2",
        "name": "Image 2 最强图片模型",
        "vendor": "image2",
        "icon": "🖼️",
        "model_type": "image",
        "description": "多语言文字渲染更清晰，排版表达更出色；高真实感与细节",
        "features": ["多语言文字", "排版", "高真实"],
        "specs": {"resolution": "4K"},
        "credits_per_image": 6,
        "is_premium": True,
        "sort_order": 4,
    },
    {
        "code": "seed-audio",
        "name": "Seed Audio",
        "vendor": "doubao",
        "icon": "🔊",
        "model_type": "audio",
        "description": "轻松翻译视频原声，配合音频分离使用",
        "features": ["音频翻译", "TTS", "60+ 音色"],
        "specs": {"languages": 12, "voices": 60},
        "credits_per_second": 1,
        "sort_order": 1,
    },
    {
        "code": "seko-talk",
        "name": "SekoTalk 多人口型",
        "vendor": "seko",
        "icon": "🗣️",
        "model_type": "audio",
        "description": "60 种音色，两人以上精准口型同步，单镜头最长 60 秒",
        "features": ["多人同步", "唇形对齐", "情绪控制"],
        "specs": {"max_duration": 60, "voices": 60},
        "credits_per_second": 2,
        "sort_order": 2,
    },
]


# 画风库（模仿 Seko：国风漫剧/真人古风/超现实奇幻/3D 现代/怪谈漫画）
DEFAULT_ART_STYLES = [
    {
        "code": "realistic",
        "name": "电影质感",
        "category": "realistic",
        "description": "电影级真实质感，适合现代/都市剧情",
        "visual_prompt": "cinematic realism, natural lighting, shallow depth of field, 8K detail",
        "tags": ["电影", "真实", "现代"],
        "sort_order": 1,
    },
    {
        "code": "guofeng",
        "name": "国风古韵",
        "category": "guofeng",
        "description": "中国传统文化美学，水墨/工笔",
        "visual_prompt": "Chinese traditional painting, ink wash, silk texture, oriental aesthetics",
        "tags": ["国风", "古风", "水墨"],
        "is_new": True,
        "sort_order": 2,
    },
    {
        "code": "guofeng-realistic",
        "name": "真人古风",
        "category": "guofeng",
        "description": "真实演员古风造型，影视级画面",
        "visual_prompt": "Chinese costume drama style, realistic, ancient costume, soft natural lighting",
        "tags": ["古风", "真人", "影视"],
        "is_new": True,
        "sort_order": 3,
    },
    {
        "code": "comic-manga",
        "name": "日漫风",
        "category": "comic",
        "description": "日式漫画分镜，适合漫剧",
        "visual_prompt": "Japanese manga style, cel shading, vibrant colors, expressive characters",
        "tags": ["日漫", "漫画", "漫剧"],
        "sort_order": 4,
    },
    {
        "code": "comic-guofeng",
        "name": "国风漫剧",
        "category": "comic",
        "description": "国风 + 漫画风，新中式漫剧",
        "visual_prompt": "Chinese style comic, ink outlines, soft colors, oriental aesthetics",
        "tags": ["国风", "漫剧", "中式"],
        "is_new": True,
        "sort_order": 5,
    },
    {
        "code": "3d-modern",
        "name": "3D 现代",
        "category": "3d",
        "description": "现代 3D 渲染，CG 动画风",
        "visual_prompt": "modern 3D render, Pixar style, soft lighting, stylized characters",
        "tags": ["3D", "现代", "动画"],
        "is_new": True,
        "sort_order": 6,
    },
    {
        "code": "horror-comic",
        "name": "怪谈漫画",
        "category": "horror",
        "description": "怪谈、悬疑、惊悚漫画风",
        "visual_prompt": "horror comic style, dark tones, dramatic shadows, atmospheric",
        "tags": ["怪谈", "悬疑", "惊悚"],
        "is_new": True,
        "sort_order": 7,
    },
    {
        "code": "fantasy",
        "name": "超现实奇幻",
        "category": "fantic",
        "description": "魔幻/奇幻/超现实风格",
        "visual_prompt": "fantasy surrealism, magical atmosphere, ethereal lighting, vivid colors",
        "tags": ["奇幻", "魔幻", "超现实"],
        "is_new": True,
        "sort_order": 8,
    },
    {
        "code": "anime-cyber",
        "name": "赛博朋克",
        "category": "anime",
        "description": "霓虹/未来感/赛博朋克",
        "visual_prompt": "cyberpunk style, neon lights, futuristic city, rain, high contrast",
        "tags": ["赛博", "未来", "霓虹"],
        "sort_order": 9,
    },
    {
        "code": "animation-flat",
        "name": "扁平插画",
        "category": "animation",
        "description": "扁平插画/科普动画风",
        "visual_prompt": "flat illustration, educational style, clean lines, bright colors",
        "tags": ["插画", "科普", "扁平"],
        "sort_order": 10,
    },
]


async def seed_default_memberships(db: AsyncSession):
    """填充默认会员计划"""
    from app.models.membership import Membership

    existing = set((await db.execute(select(Membership.tier))).scalars().all())
    for m in DEFAULT_MEMBERSHIPS:
        if m["tier"] not in existing:
            db.add(Membership(**m))
    await db.commit()


async def seed_default_models(db: AsyncSession):
    """填充默认模型"""
    from app.models.membership import ModelCatalog

    existing = set((await db.execute(select(ModelCatalog.code))).scalars().all())
    for m in DEFAULT_MODELS:
        if m["code"] not in existing:
            db.add(ModelCatalog(**m))
    await db.commit()


async def seed_default_art_styles(db: AsyncSession):
    """填充默认画风"""
    from app.models.membership import ArtStyleLibrary

    existing = set((await db.execute(select(ArtStyleLibrary.code))).scalars().all())
    for a in DEFAULT_ART_STYLES:
        if a["code"] not in existing:
            db.add(ArtStyleLibrary(**a))
    await db.commit()


async def seed_demo_inspirations(db: AsyncSession):
    """填充演示灵感作品（精选）"""
    from app.models.inspiration import Inspiration
    from app.models.project import Project

    existing = (await db.execute(select(Inspiration))).scalars().all()
    if existing:
        return

    # 创建几个 demo 项目和灵感
    demos = [
        {
            "project_name": "病弱王爷 × 富商嫡女",
            "title": "《王府秘事》—— 病弱王爷与富商嫡女的权谋之恋",
            "description": "她为皇商之位嫁入王府，他借她的商路暗查旧案；一纸各取所需的婚约，让两个各怀秘密的人在联手经营与相互试探中假戏真做，揭开牵动朝堂的军饷迷局。",
            "category": "drama",
            "tags": ["古风", "权谋", "甜虐交织", "短剧"],
            "art_style": "guofeng-realistic",
            "is_featured": True,
            "view_count": 28530,
            "like_count": 3421,
        },
        {
            "project_name": "李清照的诗与远方",
            "title": "李清照传——千古才女的诗词人生",
            "description": "从少女时代的「争渡，争渡，惊起一滩鸥鹭」到晚年「寻寻觅觅」的愁绪，重现一代词后的传奇人生。",
            "category": "knowledge",
            "tags": ["传记", "古风", "诗词", "知识科普"],
            "art_style": "guofeng",
            "is_featured": True,
            "view_count": 15821,
            "like_count": 2103,
        },
        {
            "project_name": "星际迷航：深渊边缘",
            "title": "星际迷航——深渊边缘的求救信号",
            "description": "公元 2387 年，深空探测器「晨曦号」在银河系边缘接收到了来自未知文明的求救信号。",
            "category": "drama",
            "tags": ["科幻", "太空", "悬疑"],
            "art_style": "fantasy",
            "is_featured": True,
            "view_count": 9843,
            "like_count": 1254,
        },
        {
            "project_name": "回村的诱惑",
            "title": "《回村》—— 大学生的乡村振兴故事",
            "description": "985 毕业的林晓回村创业，带领乡亲们把贫瘠的山村变成了网红打卡地。",
            "category": "drama",
            "tags": ["乡村", "现实", "温暖"],
            "art_style": "realistic",
            "is_featured": False,
            "view_count": 7201,
            "like_count": 893,
        },
        {
            "project_name": "九宫格宇宙",
            "title": "九宫格宇宙——多元宇宙的并行可能",
            "description": "如果当初你做了不同的选择，宇宙会变成什么样？",
            "category": "comic",
            "tags": ["科幻", "九宫格", "漫剧"],
            "art_style": "fantasy",
            "is_featured": False,
            "view_count": 5412,
            "like_count": 678,
        },
        {
            "project_name": "赛博都市",
            "title": "霓虹城下——赛博朋克短剧",
            "description": "2099 年的新东京，霓虹灯下的义体改造人侦探追查连环失踪案。",
            "category": "animation",
            "tags": ["赛博朋克", "悬疑", "霓虹"],
            "art_style": "anime-cyber",
            "is_featured": False,
            "view_count": 4356,
            "like_count": 521,
        },
    ]

    for d in demos:
        proj = Project(
            name=d["project_name"],
            description=d["description"],
            art_style=d["art_style"],
            status="completed",
        )
        db.add(proj)
        await db.flush()

        insp = Inspiration(
            project_id=proj.id,
            title=d["title"],
            description=d["description"],
            category=d["category"],
            tags=d["tags"],
            art_style=d["art_style"],
            is_featured=d["is_featured"],
            view_count=d["view_count"],
            like_count=d["like_count"],
            published=True,
            cover_url=f"https://picsum.photos/seed/{abs(hash(d['title'])) % 10000}/640/360",
        )
        db.add(insp)

    await db.commit()


async def run_all_seeds(db: AsyncSession):
    """运行所有种子数据"""
    await seed_default_memberships(db)
    await seed_default_models(db)
    await seed_default_art_styles(db)
    await seed_demo_inspirations(db)