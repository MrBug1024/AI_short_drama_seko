"""7 步创作流程核心服务

对应 Seko 的 7 个 Agent 流程：
1. Art Director   - 美术总监（视觉风格、色调、光影）
2. Scriptwriter   - 编剧（剧本拆解）
3. Character Designer - 角色设计
4. Scene Creator  - 场景创建
5. Animator       - 动画生成（图/视频）
6. Editor         - 剪辑
7. Sound Engineer - 音效（配音/配乐/口型同步）
"""
import json
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import ai_gateway
from app.models.project import Project
from app.models.episode import Episode
from app.models.script import Script
from app.models.character import Character, CharacterRelation
from app.models.scene import Scene
from app.models.prop import Prop
from app.models.shot import Shot
from app.models.generation_task import GenerationTask
from app.models.canvas import CanvasNode, CanvasEdge


SYSTEM_PROMPT = """你是 Seko AI 短视频创作平台的专业编剧团队，擅长创作 1-3 分钟的短剧剧本。

# 你的任务
根据用户的创意 prompt，输出结构化 JSON，包含：
1. logline: 一句话故事梗概（不超过 50 字）
2. art_style: 美术风格描述（用于提示词）
3. characters: 角色列表，每项包含：
   - name/alias/age/gender/role（主角/配角/反派）
   - appearance: **可直接用于 AI 生图的具体视觉描述**（发型发色、脸型、五官、体型、标志性特征，如"黑色齐肩短发，圆脸，大眼睛，左眼角有泪痣，身材娇小"），禁止抽象形容词
   - outfit: 具体到款式和颜色的服装（如"米白色针织开衫，浅蓝色牛仔裤"）
   - personality: 性格
   - backstory: 背景故事（50 字内）
4. relations: 角色关系列表，每项包含 from/to（角色 name）、type（恋人/夫妻/亲子/兄弟姐妹/朋友/同事/师生/对手/仇人/暗恋/陌生人）、description（关系描述与戏剧张力）
5. scenes: 场景列表，每项包含 name/location/time_of_day/weather/mood/description/visual_prompt（可直接生图的视觉描述：空间布局+关键物件+光线+色调）
6. props: 道具列表，每项包含 name/category/description
7. shots: 分镜列表（5-15 个镜头），每项包含：
   - shot_code: 镜头编号 SC01/SC02...
   - description: 画面描述（明确"谁在做什么"）
   - composition: 构图（九宫格/中心/对称/三分法等）
   - camera_movement: 运镜（推/拉/摇/移/跟/固定）
   - camera_angle: 角度（平视/俯视/仰视）+ 景别（特写/近景/中景/全景/远景）
   - dialogue: 台词
   - duration_sec: 时长（秒）
   - visual_prompt: **可直接用于 AI 生图的画面描述**（包含角色外貌特征+动作+环境+镜头语言）
   - scene_name: 该镜头所在场景名（必须与 scenes 列表中的 name 一致）
   - character_names: 该镜头出场的角色名列表（必须与 characters 列表中的 name 一致）

# 严格要求
- 只输出合法 JSON
- 所有文本字段用中文
- 必须包含完整的字段
- 镜头数量 5-15 个，单个时长 3-8 秒，总时长 1-3 分钟
- 剧情节奏紧凑，冲突前置，台词口语化有情绪张力
"""


def _strip_code_fences(text: str) -> str:
    """去除 AI 返回内容中的 ```json ... ``` 代码围栏"""
    s = (text or "").strip()
    if s.startswith("```"):
        # 去掉首行 ``` 或 ```json
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1:]
        # 去掉结尾的 ```
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


STEP_PROMPTS = {
    "art_director": "你是一位资深的影视美术总监，擅长根据故事主题确定视觉风格。",
    "scriptwriter": "你是一位专业的短剧编剧，擅长创作 1-3 分钟的紧凑剧本。",
    "character_designer": "你是一位角色设计师，根据剧本为每个角色设计详细的外貌和服装。",
    "scene_creator": "你是一位场景概念设计师，为故事创造具体场景和氛围。",
    "animator": "你是一位动画导演，为每个镜头设计视觉提示词。",
    "editor": "你是一位剪辑师，规划镜头节奏、转场、时长。",
    "sound_engineer": "你是一位音效师，为每个镜头设计配音、配乐和环境声。",
}


class CreationService:
    """7 步创作流程编排"""

    async def run_full_flow(
        self,
        db: AsyncSession,
        project: Project,
        prompt: str,
        art_style: str = "",
        skill_code: str = "drama_story",
    ) -> Dict[str, Any]:
        """
        执行完整 7 步流程
        返回中间结果，不等待异步任务完成
        """
        project.status = "creating"
        project.prompt = prompt
        if art_style:
            project.art_style = art_style
        await db.commit()

        # 创建主任务记录
        task = GenerationTask(
            project_id=project.id,
            task_type="script",
            status="running",
            progress=0,
            phase="编剧创作",
            prompt=prompt,
            provider_name="default",
            model_name="router",
            estimated_credits=10.0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # 一次性生成结构化剧本
        result = await ai_gateway.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"创意：{prompt}\n美术风格：{art_style or '电影质感'}\n技能：{skill_code}"},
            ],
            json_mode=True,
            temperature=0.8,
        )

        try:
            data = json.loads(_strip_code_fences(result["content"]))
        except Exception as e:
            logger.error(f"解析 JSON 失败: {e}\n{result['content'][:500]}")
            task.status = "failed"
            task.error_msg = f"AI 返回格式错误: {e}"
            project.status = "failed"
            await db.commit()
            return {"ok": False, "error": str(e), "raw": result["content"][:500]}

        # 写入数据库
        await self._persist_creation(db, project, data, task)

        task.status = "success"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        project.status = "draft"
        await db.commit()

        return {"ok": True, "task_id": task.id, "data": data}

    async def _persist_creation(
        self,
        db: AsyncSession,
        project: Project,
        data: Dict[str, Any],
        task: GenerationTask,
    ):
        """把 AI 生成的结构化数据落库（幂等：先清空旧实体，避免重复创作产生重复数据）"""
        # 0. 清空旧实体与旧画布（连线 → 节点 → 分镜 → 场景 → 角色 → 道具 → 剧本）
        await db.execute(delete(CanvasEdge).where(CanvasEdge.project_id == project.id))
        await db.execute(delete(CanvasNode).where(CanvasNode.project_id == project.id))
        await db.execute(delete(Shot).where(Shot.project_id == project.id))
        await db.execute(delete(Scene).where(Scene.project_id == project.id))
        await db.execute(delete(CharacterRelation).where(CharacterRelation.project_id == project.id))
        await db.execute(delete(Character).where(Character.project_id == project.id))
        await db.execute(delete(Prop).where(Prop.project_id == project.id))
        await db.execute(delete(Script).where(Script.project_id == project.id))
        await db.flush()

        # 1. 剧本
        script = Script(
            project_id=project.id,
            version=1,
            title=project.name,
            logline=data.get("logline", ""),
            content=self._format_script_md(data),
            raw_text=project.prompt,
            meta=data,
            source_task_id=str(task.id),
        )
        db.add(script)

        # 2. 角色
        char_map = {}
        for c in data.get("characters", []):
            character = Character(
                project_id=project.id,
                name=c.get("name", ""),
                alias=c.get("alias", ""),
                age=c.get("age", 0),
                gender=c.get("gender", ""),
                role=c.get("role", ""),
                appearance=c.get("appearance", ""),
                outfit=c.get("outfit", ""),
                backstory=c.get("backstory", ""),
                consistency_key=f"char_{uuid.uuid4().hex[:8]}",
            )
            db.add(character)
            await db.flush()
            char_map[c.get("name", "")] = character.id

        # 2.5 角色关系
        for r in data.get("relations", []):
            fid = char_map.get(r.get("from", ""))
            tid = char_map.get(r.get("to", ""))
            if not fid or not tid or fid == tid:
                continue
            db.add(CharacterRelation(
                project_id=project.id,
                from_character_id=fid,
                to_character_id=tid,
                relation_type=r.get("type", ""),
                description=r.get("description", ""),
            ))
            char_map[c.get("name", "")] = character.id

        # 3. 场景
        scene_map = {}
        for s in data.get("scenes", []):
            scene = Scene(
                project_id=project.id,
                name=s.get("name", ""),
                location=s.get("location", ""),
                time_of_day=s.get("time_of_day", "day"),
                weather=s.get("weather", ""),
                mood=s.get("mood", ""),
                description=s.get("description", ""),
                visual_prompt=s.get("visual_prompt", ""),
            )
            db.add(scene)
            await db.flush()
            scene_map[s.get("name", "")] = scene.id

        # 4. 道具
        for p in data.get("props", []):
            prop = Prop(
                project_id=project.id,
                name=p.get("name", ""),
                category=p.get("category", ""),
                description=p.get("description", ""),
            )
            db.add(prop)

        await db.flush()

        # 5. 镜头（关联角色/场景引用，用于画布连线）
        # 反向映射：别名/姓名 → 角色 id
        char_by_name = {}
        for c in data.get("characters", []):
            cid = char_map.get(c.get("name", ""))
            if cid:
                char_by_name[c.get("name", "")] = cid
                if c.get("alias"):
                    char_by_name[c.get("alias", "")] = cid

        for i, sh in enumerate(data.get("shots", [])):
            # 场景引用：优先 scene_name 字段，其次按描述模糊匹配
            scene_id = scene_map.get(sh.get("scene_name", ""))
            if not scene_id:
                desc = sh.get("description", "")
                for name, sid in scene_map.items():
                    if name and name in desc:
                        scene_id = sid
                        break
            # 兜底：轮流分配场景，保证每个分镜都有场景连线
            if not scene_id and scene_map:
                scene_id = list(scene_map.values())[i % len(scene_map)]

            # 角色引用：优先 character_names 字段，其次按描述/台词匹配角色名或别名
            char_ids = [char_by_name[n] for n in sh.get("character_names", []) if n in char_by_name]
            if not char_ids:
                text = sh.get("description", "") + sh.get("dialogue", "")
                char_ids = [cid for name, cid in char_by_name.items() if name and name in text]
            # 兜底：至少关联一个角色，保证画布有连线
            if not char_ids and char_by_name:
                char_ids = [list(char_by_name.values())[i % len(char_by_name)]]

            shot = Shot(
                project_id=project.id,
                shot_no=sh.get("shot_no", i + 1),
                shot_code=sh.get("shot_code", f"SC{i + 1:02d}"),
                description=sh.get("description", ""),
                composition=sh.get("composition", ""),
                camera_movement=sh.get("camera_movement", ""),
                camera_angle=sh.get("camera_angle", ""),
                dialogue=sh.get("dialogue", ""),
                duration_sec=sh.get("duration_sec", 5),
                visual_prompt=sh.get("visual_prompt") or sh.get("description", ""),
                scene_id=scene_id,
                character_ids=char_ids,
            )
            db.add(shot)

        await db.commit()

    def _format_script_md(self, data: Dict[str, Any]) -> str:
        """格式化为 Markdown 剧本"""
        md = f"# {data.get('title', '剧本')}\n\n"
        md += f"## 故事梗概\n{data.get('logline', '')}\n\n"
        md += f"## 美术风格\n{data.get('art_style', '')}\n\n"

        if data.get("characters"):
            md += "## 角色列表\n"
            for c in data["characters"]:
                md += f"- **{c.get('name', '')}**（{c.get('alias', '')}）"
                md += f"：{c.get('appearance', '')}，{c.get('outfit', '')}\n"
            md += "\n"

        if data.get("relations"):
            md += "## 角色关系\n"
            for r in data["relations"]:
                md += f"- {r.get('from', '')} → {r.get('to', '')}：{r.get('type', '')}（{r.get('description', '')}）\n"
            md += "\n"

        if data.get("scenes"):
            md += "## 场景列表\n"
            for s in data["scenes"]:
                md += f"- **{s.get('name', '')}**（{s.get('location', '')}，{s.get('time_of_day', '')}）"
                md += f"：{s.get('description', '')}\n"
            md += "\n"

        if data.get("shots"):
            md += "## 分镜剧本\n"
            for sh in data["shots"]:
                md += f"### {sh.get('shot_code', '')}（{sh.get('duration_sec', 5)}s）\n"
                md += f"- 画面：{sh.get('description', '')}\n"
                md += f"- 构图：{sh.get('composition', '')}\n"
                md += f"- 运镜：{sh.get('camera_movement', '')}\n"
                if sh.get("dialogue"):
                    md += f"- 台词：「{sh.get('dialogue', '')}」\n"
                md += "\n"

        return md

    # ============== 单步执行 ==============

    async def refine_step(
        self,
        db: AsyncSession,
        project: Project,
        step: str,
        user_prompt: str,
        target_type: str = "",
        target_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """对单个步骤进行优化/修改"""
        sys_prompt = STEP_PROMPTS.get(step, "你是 Seko 平台的 AI 助理。")

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = await ai_gateway.chat(messages=messages, temperature=0.7)
        return {"ok": True, "content": result["content"], "step": step}


creation_service = CreationService()