"""媒体本地化存储服务

将 AI 生成的视频/图片（外部临时 URL，如阿里云 OSS 24h 有效期）
下载到项目本地目录持久保存，并返回可供前端访问的本地相对地址。

目录结构：
    data/media/videos/project_{pid}/shot_{sid}_{ts}.mp4
    data/media/images/project_{pid}/...

访问地址：
    /media/videos/project_1/shot_5_xxx.mp4  （由 main.py 挂载 StaticFiles 提供）
"""
import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from loguru import logger

from app.core.config import settings


# 本地媒体根目录（绝对路径）
def _media_root() -> Path:
    root = Path(settings.MEDIA_ROOT)
    if not root.is_absolute():
        # 相对路径基于 backend 目录
        root = Path(os.getcwd()) / root
    root.mkdir(parents=True, exist_ok=True)
    return root


# 对外访问前缀（与 main.py 的 StaticFiles mount 一致）
PUBLIC_PREFIX = "/media"


def _safe_name(name: str) -> str:
    """清洗文件名中的非法字符"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:80]


def _ext_from_url(url: str, default: str = ".mp4") -> str:
    """从 URL 路径推断扩展名"""
    try:
        path = urlparse(url).path
        ext = Path(path).suffix
        if ext and len(ext) <= 6:
            return ext
    except Exception:
        pass
    return default


async def download_media(
    url: str,
    *,
    subdir: str = "videos",
    project_id: Optional[int] = None,
    shot_id: Optional[int] = None,
    default_ext: str = ".mp4",
    timeout: int = 300,
) -> str:
    """下载外部媒体到本地，返回可供前端访问的相对 URL（/media/...）。

    失败时返回空字符串（调用方可回退到原始外部 URL）。
    幂等：同一 shot 已有本地文件时直接复用，避免重复下载。
    """
    if not url:
        return ""

    # 已经是本地地址 → 直接返回
    if url.startswith(PUBLIC_PREFIX + "/"):
        return url

    root = _media_root()
    proj_dir = f"project_{project_id}" if project_id else "misc"
    target_dir = root / subdir / proj_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    # 幂等复用：同 shot 已下载过则直接用现有文件
    if shot_id:
        existing = sorted(target_dir.glob(f"shot_{shot_id}_*.mp4"))
        if existing:
            rel = existing[-1].relative_to(root).as_posix()
            logger.debug(f"复用已下载视频: {rel}")
            return f"{PUBLIC_PREFIX}/{rel}"

    ext = _ext_from_url(url, default_ext)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    base = f"shot_{shot_id}_{ts}" if shot_id else f"media_{ts}"
    filename = _safe_name(base + ext)
    dest = target_dir / filename

    try:
        client_timeout = aiohttp.ClientTimeout(total=timeout, connect=30, sock_read=timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"下载媒体失败 HTTP {resp.status}: {url[:80]}")
                    return ""
                # 流式写入，避免大视频占满内存
                with open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 256):
                        f.write(chunk)
        size_kb = dest.stat().st_size / 1024
        rel = dest.relative_to(root).as_posix()
        logger.info(f"媒体已本地化: {rel} ({size_kb:.0f} KB)")
        return f"{PUBLIC_PREFIX}/{rel}"
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(f"下载媒体异常 {url[:80]}: {e}")
        # 清理半成品文件
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        return ""


async def download_video_for_shot(
    url: str, project_id: Optional[int], shot_id: Optional[int]
) -> str:
    """便捷封装：下载分镜视频"""
    return await download_media(
        url, subdir="videos", project_id=project_id, shot_id=shot_id, default_ext=".mp4"
    )


async def backfill_local_videos() -> None:
    """启动补下载：扫描所有 video_url 仍指向外部临时地址的分镜，本地化并回写。

    用于修复历史数据——之前生成的视频只存了 24h 有效期的 OSS 外链，
    重启后统一下载到本地，保证前端始终可预览。
    """
    # 延迟导入避免循环依赖
    from app.core.database import AsyncSessionLocal
    from app.models.shot import Shot
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as db:
            shots = (await db.execute(
                select(Shot).where(Shot.video_url != "")
            )).scalars().all()

            pending = [
                s for s in shots
                if s.video_url and not s.video_url.startswith(PUBLIC_PREFIX + "/")
                and s.video_url.startswith("http")
            ]
            if not pending:
                return

            logger.info(f"发现 {len(pending)} 个未本地化的视频，开始补下载…")
            for s in pending:
                local = await download_video_for_shot(s.video_url, s.project_id, s.id)
                if local:
                    s.video_url = local
                    if s.status != "videod":
                        s.status = "videod"
            await db.commit()
            logger.info("✅ 视频补下载完成")
    except Exception as e:
        logger.warning(f"视频补下载异常: {e}")
