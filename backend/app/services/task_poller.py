"""后台任务轮询 worker

定期扫描 status=running 且有 external_task_id 的生成任务，
查询外部视频任务状态并回填结果（分镜 video_url + 画布节点）。
"""
import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ai.gateway import ai_gateway
from app.models.generation_task import GenerationTask
from app.models.shot import Shot
from app.models.canvas import CanvasNode
from app.services.media_store import download_video_for_shot


async def poll_once():
    """扫描一轮 running 任务"""
    async with AsyncSessionLocal() as db:
        tasks = (await db.execute(
            select(GenerationTask).where(
                GenerationTask.status == "running",
                GenerationTask.external_task_id != "",
            )
        )).scalars().all()

        for task in tasks:
            r = await ai_gateway.query_video_task(task.external_task_id)
            status = r.get("status", "running")
            if status == "success":
                url = r.get("video_url", "")
                # 下载到本地持久化（外部 OSS 链接仅 24h 有效）
                local_url = ""
                if url:
                    local_url = await download_video_for_shot(url, task.project_id, task.shot_id)
                final_url = local_url or url  # 下载失败回退外部链接
                task.status = "success"
                task.output_url = final_url
                task.progress = 100
                task.finished_at = datetime.utcnow()
                if task.shot_id and final_url:
                    sh = (await db.execute(select(Shot).where(Shot.id == task.shot_id))).scalar_one_or_none()
                    if sh:
                        sh.video_url = final_url
                        sh.status = "videod"
                    node = (await db.execute(
                        select(CanvasNode).where(
                            CanvasNode.project_id == task.project_id,
                            CanvasNode.node_type == "shot",
                            CanvasNode.ref_id == task.shot_id,
                        )
                    )).scalars().first()
                    if node:
                        node.status = ""
                        # meta 记录本地视频地址，前端画布据此显示可预览状态
                        meta = dict(node.meta or {})
                        meta["video_url"] = final_url
                        node.meta = meta
                await db.commit()
                logger.info(f"视频任务 {task.id} 完成: {final_url[:80]}")
            elif status == "failed":
                task.status = "failed"
                task.error_msg = r.get("error", "外部视频任务失败")
                task.progress = 100
                task.finished_at = datetime.utcnow()
                if task.shot_id:
                    node = (await db.execute(
                        select(CanvasNode).where(
                            CanvasNode.project_id == task.project_id,
                            CanvasNode.node_type == "shot",
                            CanvasNode.ref_id == task.shot_id,
                        )
                    )).scalars().first()
                    if node:
                        node.status = ""
                await db.commit()
                logger.warning(f"视频任务 {task.id} 失败: {task.error_msg}")


async def poller_loop():
    """常驻轮询循环"""
    interval = max(5, settings.TASK_POLL_INTERVAL)
    while True:
        try:
            await poll_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"任务轮询异常: {e}")
        await asyncio.sleep(interval)
