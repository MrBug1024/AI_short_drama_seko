"""AI 统一网关 - 对接多个 Provider

支持的接口（OpenAI 兼容）：
- chat(text) 文本生成
- image(prompt) 图片生成
- video(prompt) 视频生成（异步）
- audio(text) TTS 配音
"""
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from loguru import logger
import aiohttp

from app.core.config import settings


class AIGateway:
    """AI 网关：根据 .env 自动适配用户配置的 Provider"""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=120)
        # 图片生成模型（wan2.x-image 等）出图慢，单独放宽超时
        self.image_timeout = aiohttp.ClientTimeout(total=300)
        # 视频生成不限制总超时（用户要求取消超时）：只限制连接建立时间
        self.video_timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=600)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

    @property
    def base_url(self) -> str:
        return settings.LLM_BASE_URL.rstrip("/")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """调用文本对话接口"""
        if not settings.has_llm:
            return self._mock_chat_response(messages, json_mode)

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model or settings.LLM_MODEL_TEXT or settings.LLM_MODEL_ROUTER,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=self.headers) as resp:
                    if resp.status != 200:
                        txt = await resp.text()
                        logger.error(f"LLM 调用失败 {resp.status}: {txt[:300]}")
                        return self._mock_chat_response(messages, json_mode)
                    data = await resp.json()
                    return {
                        "content": data["choices"][0]["message"]["content"],
                        "model": data.get("model", ""),
                        "usage": data.get("usage", {}),
                    }
        except Exception as e:
            logger.exception(f"LLM 调用异常: {e}")
            return self._mock_chat_response(messages, json_mode)

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        model: Optional[str] = None,
        reference_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """生成图片

        实测：阿里云百炼 token-plan（wan2.x-image 系列）不支持 OpenAI 的
        /images/generations 路径（返回 400 url error），正确方式是走
        /chat/completions + 多模态 messages 格式，图片 URL 在
        output.choices[0].message.content[].image 中返回。

        为兼容其它服务商，先尝试 chat/completions 多模态格式，
        失败再回退 /images/generations 标准格式。
        """
        if not settings.has_image:
            return self._mock_image_response(prompt)

        base = settings.IMAGE_API_BASE.rstrip("/")
        img_model = model or settings.IMAGE_MODEL
        headers = {
            "Authorization": f"Bearer {settings.IMAGE_API_KEY}",
            "Content-Type": "application/json",
        }

        # 组合提示词：正向 + 负向
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\n负面要求（画面中不要出现）：{negative_prompt}"

        # 参考图（图生图/角色一致性）：多模态 content 列表
        text_part = {"type": "text", "text": full_prompt}
        img_parts = [
            {"type": "image_url", "image_url": {"url": ref}}
            for ref in (reference_images or [])[:4] if ref
        ]
        content_with_ref: List[Dict[str, Any]] = img_parts + [text_part]
        content_text_only: List[Dict[str, Any]] = [text_part]

        size = f"{width}*{height}"

        async def _post_chat(session, content_list) -> Optional[str]:
            """发送 chat/completions 生图请求，成功返回图片 URL，失败返回 None"""
            payload = {
                "model": img_model,
                "messages": [{"role": "user", "content": content_list}],
                "parameters": {"size": size, "n": 1},
            }
            if negative_prompt:
                payload["parameters"]["negative_prompt"] = negative_prompt
            async with session.post(
                f"{base}/chat/completions", json=payload, headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = self._extract_image_url(data)
                    if url:
                        return url
                    logger.error(f"图片响应中未找到 URL: {json.dumps(data, ensure_ascii=False)[:300]}")
                else:
                    txt = await resp.text()
                    logger.warning(f"chat/completions 生图失败 {resp.status}: {txt[:200]}")
            return None

        try:
            async with aiohttp.ClientSession(timeout=self.image_timeout) as session:
                # ---- 方式 1：chat/completions 多模态（阿里云百炼 wan-image）----
                # 先带参考图（图生图强化一致性）；若模型不支持图文混合
                # （wan2.x-image 纯文生图会报 "Either text or image, not both"），
                # 自动降级为纯文本请求。
                if img_parts:
                    url = await _post_chat(session, content_with_ref)
                    if url:
                        return {"url": url, "model": img_model}
                    logger.info("带参考图生图失败，降级为纯文本生图")

                url = await _post_chat(session, content_text_only)
                if url:
                    return {"url": url, "model": img_model}

                # ---- 方式 2：标准 OpenAI /images/generations ----
                payload2 = {
                    "model": img_model,
                    "prompt": full_prompt,
                    "n": 1,
                    "size": f"{width}x{height}",
                }
                async with session.post(
                    f"{base}/images/generations", json=payload2, headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("data", [])
                        url = ""
                        if items:
                            url = items[0].get("url") or items[0].get("b64_json", "")
                        if url:
                            return {"url": url, "model": img_model}
                    txt = await resp.text()
                    logger.error(f"images/generations 生图失败 {resp.status}: {txt[:300]}")

            # 两种方式都失败：返回空 URL，让任务标记为 failed（不再用假图糊弄）
            return {"url": "", "model": img_model, "error": "图片生成失败，请检查 IMAGE_API 配置"}
        except asyncio.TimeoutError:
            logger.error("图片生成超时（300s）")
            return {"url": "", "model": img_model, "error": "图片生成超时，请稍后重试"}
        except Exception as e:
            logger.exception(f"图片生成异常: {e}")
            return {"url": "", "model": img_model, "error": str(e) or e.__class__.__name__}

    @staticmethod
    def _extract_image_url(data: Dict[str, Any]) -> str:
        """从多模态 chat 响应中提取图片 URL（兼容 OpenAI / DashScope 两种结构）"""
        # OpenAI 标准: choices[0].message.content
        choices = data.get("choices") or (data.get("output") or {}).get("choices") or []
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    # DashScope: {"type":"image","image":"https://..."}
                    if part.get("type") == "image" and part.get("image"):
                        return part["image"]
                    # OpenAI: {"type":"image_url","image_url":{"url":...}}
                    if part.get("type") == "image_url":
                        iu = part.get("image_url")
                        if isinstance(iu, dict) and iu.get("url"):
                            return iu["url"]
                        if isinstance(iu, str):
                            return iu
            elif isinstance(content, str) and content.startswith("http"):
                return content
        # DashScope 原生: output.results[0].url
        results = (data.get("output") or {}).get("results") or []
        if results and results[0].get("url"):
            return results[0]["url"]
        return ""

    def _dashscope_native_base(self) -> str:
        """把 VIDEO_API_BASE 归一化为 DashScope 原生异步接口基址（/api/v1）

        阿里云百炼视频生成（happyhorse / wan 系列）只支持 DashScope 原生异步协议，
        端点是 /api/v1/services/aigc/video-generation/video-synthesis，
        而不是 OpenAI 兼容的 /compatible-mode/v1。
        用户 .env 里常写成 compatible-mode，这里自动纠正。
        """
        base = settings.VIDEO_API_BASE.rstrip("/")
        if "/compatible-mode" in base:
            base = base.split("/compatible-mode")[0] + "/api/v1"
        elif base.endswith("/api/v1"):
            pass
        elif base.endswith("/v1"):
            base = base[: -len("/v1")] + "/api/v1"
        else:
            base = base + "/api/v1"
        return base

    @staticmethod
    def _resolve_video_model(v_model: str, has_image: bool) -> str:
        """根据 .env 配的视频模型和是否有参考图，自动派生可用的子模型。

        设计原则：用户只关心 .env 里配置的 VIDEO_MODEL，后端负责兼容性。
        - happyhorse-1.1-r2v（参考生视频）：有 image → 用 r2v；无 image → 自动降级为 t2v
        - happyhorse-1.1-i2v（图生视频）：有 image → 用 i2v；无 image → 自动降级为 t2v
        - happyhorse-1.1-t2v：始终用 t2v
        - 其他模型：原样使用（依赖服务端是否支持）
        """
        m = (v_model or "").lower().strip()
        if not m:
            return m
        # 已经是显式的 t2v：跳过
        if m.endswith("-t2v") or "-t2v-" in m:
            return v_model
        # r2v / i2v：没图时降级为 t2v
        if not has_image:
            if "r2v" in m or "i2v" in m or "kf2v" in m:
                # happyhorse-1.1-r2v → happyhorse-1.1-t2v
                t2v_name = v_model.replace("-r2v", "-t2v").replace("-i2v", "-t2v").replace("-kf2v", "-t2v")
                logger.info(f"视频生成无参考图，自动降级 {v_model} → {t2v_name}")
                return t2v_name
        return v_model

    @staticmethod
    def _build_video_input(v_model: str, prompt: str, image_url: str) -> Dict[str, Any]:
        """按模型类型构造 DashScope 原生 input 字段

        - r2v（参考生视频）：input.media = [{"type":"reference_image","url":...}]
        - i2v / kf2v（图生视频-首帧）：input.img_url = ...
        - t2v（文生视频）：仅 prompt
        """
        inp: Dict[str, Any] = {"prompt": prompt}
        m = (v_model or "").lower()
        if image_url:
            if "r2v" in m:
                inp["media"] = [{"type": "reference_image", "url": image_url}]
            else:
                # i2v / kf2v / 其它图生视频：首帧图
                inp["img_url"] = image_url
        return inp

    async def generate_video(
        self,
        prompt: str,
        image_url: str = "",
        duration: int = 5,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成视频（DashScope 原生异步协议，返回任务 ID）

        阿里云百炼视频模型（happyhorse-1.1-r2v / i2v / t2v、wan 系列）必须走：
          POST {base}/api/v1/services/aigc/video-generation/video-synthesis
          Header: X-DashScope-Async: enable（缺失会报 does not support synchronous calls）
          Body:   {"model", "input": {...}, "parameters": {...}}
        之前用 OpenAI 兼容 /video/generations、/chat/completions 会返回 "url error"。
        """
        if not settings.has_video:
            return self._mock_video_response(prompt)

        v_model = model or settings.VIDEO_MODEL
        # 自动根据是否有参考图，派生正确的子模型（避免 r2v 无图调用失败）
        v_model = self._resolve_video_model(v_model, has_image=bool(image_url))
        native_base = self._dashscope_native_base()
        url = f"{native_base}/services/aigc/video-generation/video-synthesis"
        headers = {
            "Authorization": f"Bearer {settings.VIDEO_API_KEY}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": v_model,
            "input": self._build_video_input(v_model, prompt, image_url),
            "parameters": {
                "resolution": "720P",
                "duration": int(duration or 5),
            },
        }

        # 视频生成：取消总超时（total=None），只限制连接建立与单次读取，避免慢响应被掐断
        try:
            async with aiohttp.ClientSession(timeout=self.video_timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    txt = await resp.text()
                    try:
                        data = json.loads(txt) if txt else {}
                    except Exception:
                        data = {}
                    if resp.status == 200:
                        out = data.get("output") or {}
                        tid = out.get("task_id") or data.get("task_id") or ""
                        if tid:
                            return {"task_id": tid, "status": "running", "model": v_model}
                        logger.error(f"视频任务提交成功但无 task_id: {txt[:200]}")
                        return {"task_id": "", "status": "failed", "model": v_model,
                                "error": f"视频模型 {v_model} 未返回任务 ID"}
                    err = (data.get("message") or data.get("code")
                           or txt[:160] or f"HTTP {resp.status}")
                    logger.error(f"视频任务提交失败 {resp.status}: {err}")
                    return {"task_id": "", "status": "failed", "model": v_model,
                            "error": f"视频模型 {v_model} 提交失败：{str(err)[:160]}"}
        except asyncio.TimeoutError:
            logger.error("视频生成连接/读取超时")
            return {"task_id": "", "status": "failed", "model": v_model, "error": "视频服务连接超时"}
        except Exception as e:
            logger.exception(f"视频生成异常: {e}")
            return {"task_id": "", "status": "failed", "model": v_model, "error": str(e) or e.__class__.__name__}

    async def query_video_task(self, external_task_id: str, model: Optional[str] = None) -> Dict[str, Any]:
        """查询外部视频生成任务状态（DashScope 原生异步轮询）

        GET {base}/api/v1/tasks/{task_id}
        返回 {"status": "running|success|failed", "video_url": "", "error": ""}
        """
        if not external_task_id:
            return {"status": "failed", "error": "无外部任务 ID"}
        native_base = self._dashscope_native_base()
        url = f"{native_base}/tasks/{external_task_id}"
        headers = {"Authorization": f"Bearer {settings.VIDEO_API_KEY}"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers=headers) as resp:
                    txt = await resp.text()
                    try:
                        data = json.loads(txt) if txt else {}
                    except Exception:
                        data = {}
                    if resp.status != 200:
                        logger.warning(f"查询视频任务失败 {resp.status}: {txt[:200]}")
                        # 4xx/5xx 不立即判失败（可能限流），保持 running 让下轮重试
                        return {"status": "running"}
                    out = data.get("output") or {}
                    ts = (out.get("task_status") or "").upper()
                    if ts == "SUCCEEDED":
                        vurl = out.get("video_url") or ""
                        if not vurl:
                            results = out.get("results") or []
                            if results and isinstance(results, list):
                                vurl = results[0].get("url", "") if isinstance(results[0], dict) else ""
                        return {"status": "success", "video_url": vurl}
                    if ts in ("FAILED", "CANCELED", "UNKNOWN"):
                        err = out.get("message") or out.get("code") or data.get("message") or "外部任务失败"
                        return {"status": "failed", "error": str(err)[:200]}
                    # PENDING / RUNNING
                    return {"status": "running"}
        except Exception as e:
            logger.warning(f"查询视频任务异常: {e}")
            return {"status": "running"}  # 网络抖动时不误判失败

    async def tts(
        self,
        text: str,
        voice: str = "default",
        language: str = "zh",
    ) -> Dict[str, Any]:
        """TTS 配音（占位）"""
        if not settings.has_audio:
            return {"url": "", "duration": len(text) * 0.15}
        # 实际实现略，返回 mock
        return {"url": "", "duration": len(text) * 0.15}

    async def audio_separator(self, video_url: str) -> Dict[str, Any]:
        """音频分离（Seko 特性：人声/配乐/环境声）"""
        # 占位实现：返回三个通道的 mock URL
        return {
            "vocals_url": "",
            "music_url": "",
            "ambient_url": "",
            "original_url": video_url,
        }

    async def lipsync(self, video_url: str, audio_url: str, characters: List[str]) -> Dict[str, Any]:
        """SekoTalk 多角色口型同步（占位）"""
        return {"url": video_url, "duration": 5, "characters": characters}

    # ============== Mock 实现 ==============

    def _mock_chat_response(self, messages: List[Dict], json_mode: bool = False) -> Dict[str, Any]:
        """未配置 API Key 时的占位回复"""
        await_sleep = 0.5
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if json_mode:
            content = json.dumps(self._mock_json_for_prompt(last_user), ensure_ascii=False)
        else:
            content = self._mock_text_for_prompt(last_user)
        return {
            "content": content,
            "model": "mock",
            "usage": {"total_tokens": len(content)},
        }

    def _mock_json_for_prompt(self, prompt: str) -> Dict:
        """根据 prompt 返回合理的 mock JSON"""
        return {
            "logline": f"关于「{prompt[:30]}」的 AI 短剧创作示例",
            "art_style": "电影质感，温暖色调，电影感构图",
            "characters": [
                {"name": "主角", "alias": "陈明", "age": 25, "gender": "male", "role": "主角",
                 "appearance": "青年男子，短发，深邃眼神", "outfit": "简约休闲服"},
                {"name": "配角", "alias": "林雪", "age": 23, "gender": "female", "role": "女主",
                 "appearance": "年轻女性，长发，温柔", "outfit": "白色连衣裙"},
            ],
            "scenes": [
                {"name": "城市街道", "location": "现代都市", "time_of_day": "傍晚",
                 "weather": "晴", "mood": "温馨", "description": "夕阳下的城市街道"},
                {"name": "咖啡馆", "location": "室内", "time_of_day": "午后",
                 "weather": "晴", "mood": "浪漫", "description": "温馨的咖啡馆"},
            ],
            "props": [
                {"name": "手机", "category": "电子", "description": "现代智能手机"},
            ],
            "shots": [
                {"shot_code": "SC01", "description": "陈明走在夕阳下的街道",
                 "composition": "九宫格构图，人物在左侧三分之一", "camera_movement": "跟拍",
                 "dialogue": "今天天气真好啊", "duration_sec": 5},
                {"shot_code": "SC02", "description": "林雪在咖啡馆窗边微笑",
                 "composition": "中心构图", "camera_movement": "缓推",
                 "dialogue": "你好，请坐", "duration_sec": 4},
            ],
        }

    def _mock_text_for_prompt(self, prompt: str) -> str:
        return (
            f"# 创意方案\n\n"
            f"## 故事梗概\n根据您的创意「{prompt[:80]}」，这是一个浪漫温馨的 AI 短剧故事...\n\n"
            f"## 美术风格\n电影质感，温暖色调，电影感构图，专业镜头语言\n\n"
            f"## 主体列表\n- 主角（陈明）：青年男子\n- 配角（林雪）：年轻女性\n\n"
            f"## 场景\n- 城市街道：夕阳西下\n- 咖啡馆：温馨室内\n\n"
            f"## 分镜剧本\n### 镜头1\n- 画面：陈明走在夕阳下的街道\n- 构图：九宫格\n- 运镜：跟拍\n- 台词：「今天天气真好啊」\n"
        )

    def _mock_image_response(self, prompt: str) -> Dict[str, Any]:
        # 返回占位图
        return {
            "url": f"https://picsum.photos/seed/{abs(hash(prompt)) % 10000}/1024/1024",
            "model": "mock",
        }

    def _mock_video_response(self, prompt: str) -> Dict[str, Any]:
        return {
            "task_id": f"mock-{int(time.time() * 1000)}",
            "status": "running",
        }


# 全局单例
ai_gateway = AIGateway()