"""核心配置 - 读取 .env 文件"""
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """应用配置（自动读取 .env）"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用基础
    APP_NAME: str = "Seko AI 短视频创作平台"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/seko.db"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 文件存储
    MEDIA_ROOT: str = "./data/media"
    PROJECT_ROOT: str = "./data/projects"

    # LLM 主路由
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL_ROUTER: str = ""
    LLM_MODEL_TEXT: str = ""

    # 图片
    IMAGE_API_BASE: str = ""
    IMAGE_API_KEY: str = ""
    IMAGE_MODEL: str = ""

    # 视频
    VIDEO_API_BASE: str = ""
    VIDEO_API_KEY: str = ""
    VIDEO_MODEL: str = ""

    # 音频
    AUDIO_API_BASE: str = ""
    AUDIO_API_KEY: str = ""
    AUDIO_MODEL: str = ""

    # 任务
    TASK_POLL_INTERVAL: int = 5
    TASK_MAX_RETRIES: int = 3

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def has_llm(self) -> bool:
        return bool(self.LLM_API_KEY and self.LLM_BASE_URL)

    @property
    def has_image(self) -> bool:
        return bool(self.IMAGE_API_KEY and self.IMAGE_API_BASE)

    @property
    def has_video(self) -> bool:
        return bool(self.VIDEO_API_KEY and self.VIDEO_API_BASE)

    @property
    def has_audio(self) -> bool:
        return bool(self.AUDIO_API_KEY and self.AUDIO_API_BASE)


settings = Settings()