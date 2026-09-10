"""专业短剧提示词工程模块

参考开源短剧/故事生成项目的提示词实践：
- MoneyPrinterTurbo / ShortGPT：结构化分镜 prompt
- StoryDiffusion / ConsiStory：角色一致性描述（固定外貌锚点 + 多视图设计稿）
- OiiOii / Lum 风格：7-Agent 流程各自的职责提示词

核心原则：
1. 生图 prompt 必须包含【主体+外貌锚点+动作+场景+镜头语言+画风+质量词】
2. 角色一致性靠"外貌锚点短语"（appearance anchor）在所有相关图中重复出现
3. 负面提示词统一排除：风景/空镜头/文字/水印/多余人物等跑题内容
"""
from typing import Optional, Dict, Any, List

# ============== 画风映射（与 seed.py 的 ArtStyleLibrary 对齐） ==============
STYLE_PROMPTS: Dict[str, str] = {
    "realistic": "cinematic film still, photorealistic, natural lighting, shallow depth of field, 8K detail, movie color grading",
    "guofeng": "Chinese traditional painting style, ink wash texture, oriental aesthetics, elegant composition",
    "guofeng-realistic": "Chinese costume drama film still, realistic ancient costume, soft natural lighting, cinematic",
    "comic-manga": "Japanese anime style, cel shading, vibrant colors, expressive characters, clean lineart",
    "comic-guofeng": "Chinese style comic, ink outlines, soft colors, oriental aesthetics, manhua style",
    "3d-modern": "modern 3D render, Pixar style, soft lighting, stylized characters, octane render",
    "horror-comic": "horror comic style, dark tones, dramatic shadows, atmospheric, suspenseful",
    "fantasy": "fantasy surrealism, magical atmosphere, ethereal lighting, vivid colors, concept art",
    "anime-cyber": "cyberpunk style, neon lights, futuristic city, rain, high contrast, anime aesthetic",
    "animation-flat": "flat illustration, clean lines, bright colors, minimal shading",
}

# 通用兜底画风
DEFAULT_STYLE_PROMPT = STYLE_PROMPTS["realistic"]

# ============== 统一负面提示词 ==============
# 关键：排除"风景照/空镜头/文字"等跑题内容（用户反馈的核心问题）
GLOBAL_NEGATIVE = (
    "landscape only, empty scenery, no people, scenery photo, text, watermark, logo, "
    "subtitle, signature, blurry, low quality, deformed, extra limbs, extra fingers, "
    "bad anatomy, bad hands, distorted face, ugly, duplicate characters, multiple views collage"
)

# 角色图专用负面（防止生成风景或多人）
CHARACTER_NEGATIVE = GLOBAL_NEGATIVE + ", scenery, landscape, crowd, multiple people, group photo"

# 场景图专用负面（场景图允许无人，但要防止出现文字水印）
SCENE_NEGATIVE = (
    "text, watermark, logo, subtitle, signature, blurry, low quality, "
    "people, person, human, crowd, character"
)


def style_prompt(art_style: str) -> str:
    """把项目画风 code/名称 转成英文画风提示词"""
    if not art_style:
        return DEFAULT_STYLE_PROMPT
    key = art_style.strip().lower()
    if key in STYLE_PROMPTS:
        return STYLE_PROMPTS[key]
    # 用户自定义画风描述：原样使用
    return art_style


# ============== 角色外貌锚点 ==============

def character_anchor(c: Dict[str, Any]) -> str:
    """从角色数据构造"外貌锚点短语"——所有含该角色的图都必须带上，保证一致性

    c: dict，含 name/alias/age/gender/appearance/outfit 等字段（Character 模型或 dict）
    """
    def g(k):
        v = c.get(k) if isinstance(c, dict) else getattr(c, k, "")
        return (v or "").strip() if isinstance(v, str) else v

    parts = []
    name = g("name") or g("alias") or "角色"
    parts.append(str(name))

    gender = str(g("gender") or "").lower()
    gender_cn = {"male": "男性", "m": "男性", "男": "男性",
                 "female": "女性", "f": "女性", "女": "女性"}.get(gender, "")
    age = g("age")
    if gender_cn or age:
        desc = f"{int(age) if age else ''}岁{gender_cn}".strip()
        parts.append(desc)

    if g("appearance"):
        parts.append(str(g("appearance")))
    if g("outfit"):
        parts.append(f"穿着{g('outfit')}")

    return "，".join(p for p in parts if p)


# ============== 角色多视图设计稿 prompt ==============
# 参考 ConsiStory / 角色设计三视图实践：正面/侧面/背面 + 表情表

CHARACTER_VIEW_PROMPTS: Dict[str, str] = {
    "front": "character design sheet, front view, standing straight, arms relaxed at sides, full body, facing camera directly, neutral expression",
    "side": "character design sheet, side profile view, standing straight, full body, facing right, neutral expression",
    "back": "character design sheet, back view, standing straight, full body, facing away from camera",
    "expression": "character expression sheet, face close-up, 4 different expressions in a 2x2 grid: happy smile, angry, sad crying, surprised, same character same hairstyle",
    "closeup": "character portrait, face and upper body close-up, looking at camera, detailed facial features, soft studio lighting",
}

CHARACTER_VIEW_LABELS: Dict[str, str] = {
    "front": "正面全身",
    "side": "侧面全身",
    "back": "背面全身",
    "expression": "表情四宫格",
    "closeup": "面部特写",
}


def build_character_prompt(
    character: Dict[str, Any],
    art_style: str = "",
    view: str = "closeup",
    extra: str = "",
) -> str:
    """构造角色设计图 prompt

    view: front/side/back/expression/closeup（默认特写头像）
    """
    anchor = character_anchor(character)
    view_desc = CHARACTER_VIEW_PROMPTS.get(view, CHARACTER_VIEW_PROMPTS["closeup"])
    style = style_prompt(art_style)

    prompt = (
        f"{view_desc}, {anchor}, "
        f"plain solid light gray background, character concept art, "
        f"{style}, masterpiece, best quality, highly detailed"
    )
    if extra:
        prompt += f", {extra}"
    return prompt


# ============== 场景图 prompt ==============

def build_scene_prompt(scene: Dict[str, Any], art_style: str = "", extra: str = "") -> str:
    """构造场景概念图 prompt（无人空镜）"""
    def g(k):
        v = scene.get(k) if isinstance(scene, dict) else getattr(scene, k, "")
        return (v or "").strip() if isinstance(v, str) else v

    parts = [g("name") or "场景"]
    if g("location"):
        parts.append(str(g("location")))
    time_map = {"day": "白天", "night": "夜晚", "dawn": "清晨", "dusk": "黄昏",
                "白天": "白天", "夜晚": "夜晚", "清晨": "清晨", "黄昏": "黄昏"}
    tod = time_map.get(str(g("time_of_day")), str(g("time_of_day") or ""))
    if tod:
        parts.append(tod)
    if g("weather"):
        parts.append(str(g("weather")))
    if g("mood"):
        parts.append(f"{g('mood')}氛围")
    desc = g("visual_prompt") or g("description")
    if desc:
        parts.append(str(desc))

    style = style_prompt(art_style)
    prompt = (
        f"scene concept art, establishing shot, no people, empty environment, "
        f"{'，'.join(parts)}, {style}, wide angle, masterpiece, best quality, highly detailed"
    )
    if extra:
        prompt += f", {extra}"
    return prompt


# ============== 分镜图 prompt ==============

SHOT_SIZE_MAP = {
    "特写": "extreme close-up shot", "近景": "close-up shot", "中景": "medium shot",
    "全景": "full shot", "远景": "long shot", "大远景": "extreme long shot",
    "close-up": "close-up shot", "medium": "medium shot", "full": "full shot",
}

CAMERA_MOVE_MAP = {
    "推": "dolly in", "拉": "dolly out", "摇": "pan shot", "移": "tracking shot",
    "跟": "following shot", "固定": "static camera", "升": "crane up", "降": "crane down",
    "环绕": "orbiting camera", "手持": "handheld camera",
}


def build_shot_prompt(
    shot: Dict[str, Any],
    characters: Optional[List[Dict[str, Any]]] = None,
    scene: Optional[Dict[str, Any]] = None,
    art_style: str = "",
    extra: str = "",
) -> str:
    """构造分镜图 prompt：主体（角色锚点）+ 动作 + 场景 + 镜头语言 + 画风

    这是保证"分镜图里出现正确角色"的关键：把角色外貌锚点直接拼进 prompt。
    """
    def g(obj, k):
        if obj is None:
            return ""
        v = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, "")
        return (v or "").strip() if isinstance(v, str) else v

    parts: List[str] = []

    # 1. 角色锚点（最重要，放在最前面）
    if characters:
        anchors = [character_anchor(c) for c in characters]
        parts.append("画面主体：" + "；".join(a for a in anchors if a))

    # 2. 动作/画面描述
    desc = g(shot, "description") or g(shot, "visual_prompt")
    if desc:
        parts.append(str(desc))

    # 3. 场景环境
    if scene is not None:
        env = [g(scene, "name") or "", g(scene, "location") or ""]
        tod = g(scene, "time_of_day")
        if tod:
            env.append(str(tod))
        weather = g(scene, "weather")
        if weather:
            env.append(str(weather))
        env_str = "，".join(e for e in env if e)
        if env_str:
            parts.append(f"环境：{env_str}")

    # 4. 镜头语言
    cam = []
    comp = g(shot, "composition")
    if comp:
        cam.append(str(comp))
    move = g(shot, "camera_movement")
    if move:
        cam.append(CAMERA_MOVE_MAP.get(str(move), str(move)))
    angle = g(shot, "camera_angle")
    if angle:
        cam.append(str(angle))
    if cam:
        parts.append("镜头：" + "，".join(cam))

    style = style_prompt(art_style)
    prompt = f"{'。'.join(parts)}。{style}, cinematic lighting, masterpiece, best quality, highly detailed"
    if extra:
        prompt += f", {extra}"
    return prompt


def build_shot_negative(shot: Dict[str, Any], character_count: int = 1) -> str:
    """分镜图负面提示词"""
    neg = GLOBAL_NEGATIVE
    if character_count <= 1:
        neg += ", multiple people, crowd, group"
    return neg


# ============== LLM 优化类提示词（剧本/角色/场景/分镜的 AI 优化） ==============

OPTIMIZE_SYSTEM_PROMPTS: Dict[str, str] = {
    "script": """你是资深短剧编剧总监。用户会给你现有剧本内容和修改要求。
你的任务：按修改要求优化剧本，输出优化后的完整结构化 JSON（格式与输入 meta 一致）。
要求：
1. 保持未被要求修改的部分稳定，只改用户指出的部分
2. 剧情节奏紧凑，冲突前置，每 15-20 秒一个小钩子
3. 台词口语化、有情绪张力
4. 字符串值内禁止使用英文双引号 " 和反斜杠，需要引用时用中文引号「」
5. 只输出合法 JSON，不要 markdown 围栏""",

    "character": """你是专业角色设计师。用户会给你一个角色的现有设定和修改要求。
你的任务：输出优化后的角色设定 JSON：
{"name":"","alias":"","age":0,"gender":"","role":"","appearance":"","outfit":"","personality":"","backstory":""}
要求：
1. appearance 必须是可直接用于 AI 生图的具体视觉描述（发型发色/脸型/五官/体型/标志性特征），不要抽象形容词
2. outfit 具体到款式和颜色
3. 保持角色核心身份不变，只按用户要求调整
4. 字符串值内禁止使用英文双引号 " 和反斜杠，需要引用时用中文引号「」
5. 只输出合法 JSON""",

    "scene": """你是场景概念设计师。用户会给你一个场景的现有设定和修改要求。
你的任务：输出优化后的场景设定 JSON：
{"name":"","location":"","time_of_day":"","weather":"","mood":"","description":"","visual_prompt":""}
要求：
1. description 包含空间布局/关键物件/光线来源/色彩基调
2. 字符串值内禁止使用英文双引号 " 和反斜杠，需要引用时用中文引号「」
4. visual_prompt 是可直接生图的英文或中文视觉描述
3. 只输出合法 JSON""",

    "shot": """你是分镜导演。用户会给你一个镜头的现有设定（含所属场景和出场角色）和修改要求。
你的任务：输出优化后的镜头 JSON：
{"description":"","composition":"","camera_movement":"","camera_angle":"","dialogue":"","duration_sec":5,"visual_prompt":""}
要求：
1. description 明确"谁在做什么"，角色名与给定角色一致
2. composition/camera_movement/camera_angle 用专业镜头语言
3. 字符串值内禁止使用英文双引号 " 和反斜杠，需要引用时用中文引号「」
5. visual_prompt 是可直接生图的画面描述，必须包含角色外貌特征
4. 只输出合法 JSON""",

    "relation": """你是短剧人物关系设计师。根据剧本和角色列表，设计角色之间的关系。
输出 JSON：{"relations":[{"from":"角色A名","to":"角色B名","type":"关系类型","description":"关系描述与戏剧张力"}]}
关系类型可选：恋人/夫妻/亲子/兄弟姐妹/朋友/同事/师生/对手/仇人/暗恋/陌生人/其他
要求：
1. 关系要服务于剧情冲突，描述具体（如：青梅竹马但因家族恩怨对立）
2. 字符串值内禁止使用英文双引号 " 和反斜杠，需要引用时用中文引号「」
3. 只输出合法 JSON，不要 markdown 围栏""",
}


def build_relation_prompt(characters: List[Dict[str, Any]], logline: str = "", script_md: str = "") -> str:
    """构造人物关系生成的 user prompt"""
    lines = ["角色列表："]
    for c in characters:
        name = c.get("name", "") if isinstance(c, dict) else getattr(c, "name", "")
        role = c.get("role", "") if isinstance(c, dict) else getattr(c, "role", "")
        persona = c.get("personality", "") if isinstance(c, dict) else getattr(c, "personality", "")
        lines.append(f"- {name}（{role}）：{persona}")
    if logline:
        lines.append(f"\n故事梗概：{logline}")
    if script_md:
        lines.append(f"\n剧本节选：\n{script_md[:1500]}")
    lines.append("\n请设计所有有意义的角色关系（每对角色最多一条，双向关系合并为一条）。")
    return "\n".join(lines)
