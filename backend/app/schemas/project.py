"""项目相关 Pydantic schemas"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============== Project ==============

class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str = ""
    art_style: str = "realistic"
    target_episodes: int = 1
    target_duration_sec: int = 60
    prompt: str = ""
    skill_code: str = "drama_story"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    status: Optional[str] = None
    art_style: Optional[str] = None
    target_episodes: Optional[int] = None
    target_duration_sec: Optional[int] = None
    prompt: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    cover_url: str
    status: str
    art_style: str
    target_episodes: int
    target_duration_sec: int
    prompt: str
    created_at: datetime
    updated_at: datetime
    owner_id: Optional[int] = None  # 归属用户（None = 公开/历史项目）

    # 统计
    episode_count: int = 0
    character_count: int = 0
    scene_count: int = 0
    shot_count: int = 0
    task_count: int = 0
    task_pending: int = 0

    class Config:
        from_attributes = True


class ProjectListOut(BaseModel):
    items: List[ProjectOut]
    total: int


# ============== Episode ==============

class EpisodeCreate(BaseModel):
    title: str = ""
    synopsis: str = ""


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    status: Optional[str] = None


class EpisodeOut(BaseModel):
    id: int
    project_id: int
    episode_no: int
    title: str
    synopsis: str
    status: str
    shot_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True