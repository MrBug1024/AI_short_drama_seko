"""LBP_M 短剧创作平台 - FastAPI 主入口
LBP = Lumière Brothers（卢米埃尔兄弟）
M = 用户名的「梦」字首拼
"""
import asyncio
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.logging import setup_logger

from app.api import auth, projects, assets, canvas, tasks, providers, skills, inspiration, membership, media, script, design
from app.skills.registry import ensure_default_skills
from app.core.seed import run_all_seeds
from app.services.task_poller import poller_loop


setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"📡 数据库: {settings.DATABASE_URL}")
    logger.info(f"🤖 LLM Provider: {'已配置' if settings.has_llm else '未配置（使用 mock）'}")
    logger.info(f"🖼  Image Provider: {'已配置' if settings.has_image else '未配置（使用 mock）'}")
    logger.info(f"🎬 Video Provider: {'已配置' if settings.has_video else '未配置（使用 mock）'}")

    # 初始化数据库
    await init_db()
    logger.info("✅ 数据库表结构初始化完成")

    # 同步内置技能
    async with AsyncSessionLocal() as db:
        await ensure_default_skills(db)
    logger.info("✅ 内置技能同步完成")

    # 初始化默认数据（会员/模型/画风/灵感广场）
    async with AsyncSessionLocal() as db:
        await run_all_seeds(db)
    logger.info("✅ 默认数据同步完成（会员/模型/画风/灵感）")

    # 启动后台任务轮询 worker（查询外部视频任务状态）
    poller = asyncio.create_task(poller_loop())
    logger.info("✅ 后台任务轮询 worker 已启动")

    # 启动补下载：把历史已生成但仍指向外部临时 URL 的视频本地化
    from app.services.media_store import backfill_local_videos
    asyncio.create_task(backfill_local_videos())
    logger.info("✅ 视频本地化补下载任务已启动")

    logger.info(f"🎉 {settings.APP_NAME} 启动完成!")
    yield
    poller.cancel()
    logger.info("👋 应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
# LBP_M 短剧创作平台

LBP = Lumière Brothers（卢米埃尔兄弟，致敬电影之父）
M = 用户名的「梦」字首拼
灵感：仿商汤 Seko 视觉的 AI 短剧创作 Agent 平台。

## 核心特性
- 🎬 **7 步创作流程**：从创意到成片，全流程自动化
- 🎨 **无限画布**：节点式工作流，支持拖拽/连线/缩放
- 🧑 **角色一致性**：跨集形象一致
- 🗣 **多角色口型同步**：多人口型自然对齐
- 🎵 **音频分离**：人声/配乐/环境声一键分离
- 🌍 **出海剧转绘**：外语视频转本地化分镜+翻译配音

## 模块
- `/api/v1/projects` - 项目 CRUD + 启动创作
- `/api/v1/characters` - 角色管理
- `/api/v1/scenes` - 场景管理
- `/api/v1/props` - 道具管理
- `/api/v1/shots` - 分镜管理
- `/api/v1/canvas` - 无限画布
- `/api/v1/generation` - 生成任务队列
- `/api/v1/ai-providers` - AI 服务商配置
- `/api/v1/skills` - 技能市场
    """,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 挂载本地媒体静态目录（供前端访问已下载的视频/图片）
def _mount_media_static():
    media_root = Path(settings.MEDIA_ROOT)
    if not media_root.is_absolute():
        media_root = Path(os.getcwd()) / media_root
    media_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_root)), name="media")
    logger.info(f"📁 本地媒体目录已挂载 /media -> {media_root}")


_mount_media_static()


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"未处理异常 {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# 根路由
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "api_v1": "/api/v1",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "llm": settings.has_llm, "image": settings.has_image}


# 注册路由
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX, tags=["用户认证"])
app.include_router(projects.router, prefix=API_PREFIX, tags=["项目"])
app.include_router(assets.router, prefix=API_PREFIX, tags=["资产（角色/场景/道具/分镜）"])
app.include_router(canvas.router, prefix=API_PREFIX, tags=["无限画布"])
app.include_router(tasks.router, prefix=API_PREFIX, tags=["生成任务"])
app.include_router(providers.router, prefix=API_PREFIX, tags=["AI Provider"])
app.include_router(skills.router, prefix=API_PREFIX, tags=["技能市场"])
app.include_router(inspiration.router, prefix=API_PREFIX, tags=["灵感广场"])
app.include_router(membership.router, prefix=API_PREFIX, tags=["会员/积分/模型/画风"])
app.include_router(media.router, prefix=API_PREFIX, tags=["媒体编辑（消除笔/口型/音频分离）"])
app.include_router(script.router, prefix=API_PREFIX, tags=["剧本解析/批量生成"])
app.include_router(design.router, prefix=API_PREFIX, tags=["设计工作台（角色设计稿/AI优化/关系）"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )