"""角色/场景/道具/分镜 schemas"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============== Character ==============

class CharacterCreate(BaseModel):
    name: str
    alias: str = ""
    age: int = 0
    gender: str = ""
    role: str = ""
    appearance: str = ""
    outfit: str = ""
    personality: str = ""
    backstory: str = ""
    reference_images: List[str] = []
    portrait_url: str = ""
    view_images: Dict[str, str] = {}


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    appearance: Optional[str] = None
    outfit: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None
    reference_images: Optional[List[str]] = None
    portrait_url: Optional[str] = None
    view_images: Optional[Dict[str, str]] = None


class CharacterOut(BaseModel):
    id: int
    project_id: int
    name: str
    alias: str
    age: int
    gender: str
    role: str
    appearance: str
    outfit: str
    personality: str
    backstory: str
    reference_images: List[str]
    portrait_url: str
    view_images: Dict[str, str]
    consistency_key: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== CharacterRelation ==============

class RelationCreate(BaseModel):
    from_character_id: int
    to_character_id: int
    relation_type: str = ""
    description: str = ""


class RelationUpdate(BaseModel):
    relation_type: Optional[str] = None
    description: Optional[str] = None


class RelationOut(BaseModel):
    id: int
    project_id: int
    from_character_id: int
    to_character_id: int
    relation_type: str
    description: str
    # 冗余展示字段
    from_name: str = ""
    to_name: str = ""

    class Config:
        from_attributes = True


# ============== Scene ==============

class SceneCreate(BaseModel):
    name: str
    location: str = ""
    time_of_day: str = "day"
    weather: str = ""
    mood: str = ""
    description: str = ""
    visual_prompt: str = ""
    reference_images: List[str] = []


class SceneUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    mood: Optional[str] = None
    description: Optional[str] = None
    visual_prompt: Optional[str] = None
    reference_images: Optional[List[str]] = None


class SceneOut(BaseModel):
    id: int
    project_id: int
    name: str
    location: str
    time_of_day: str
    weather: str
    mood: str
    description: str
    visual_prompt: str
    reference_images: List[str]
    panorama_url: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Prop ==============

class PropCreate(BaseModel):
    name: str
    category: str = ""
    description: str = ""
    visual_prompt: str = ""
    reference_images: List[str] = []


class PropUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    visual_prompt: Optional[str] = None
    reference_images: Optional[List[str]] = None


class PropOut(BaseModel):
    id: int
    project_id: int
    name: str
    category: str
    description: str
    visual_prompt: str
    reference_images: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Shot ==============

class ShotCreate(BaseModel):
    shot_no: int = 1
    shot_code: str = ""
    description: str = ""
    composition: str = ""
    camera_movement: str = ""
    camera_angle: str = ""
    character_ids: List[int] = []
    scene_id: Optional[int] = None
    prop_ids: List[int] = []
    dialogue: str = ""
    narration: str = ""
    subtitle: str = ""
    duration_sec: float = 5
    visual_prompt: str = ""
    negative_prompt: str = ""


class ShotUpdate(BaseModel):
    description: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    camera_angle: Optional[str] = None
    character_ids: Optional[List[int]] = None
    scene_id: Optional[int] = None
    prop_ids: Optional[List[int]] = None
    dialogue: Optional[str] = None
    narration: Optional[str] = None
    subtitle: Optional[str] = None
    duration_sec: Optional[float] = None
    visual_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    status: Optional[str] = None


class ShotOut(BaseModel):
    id: int
    project_id: int
    episode_id: Optional[int]
    shot_no: int
    shot_code: str
    description: str
    composition: str
    camera_movement: str
    camera_angle: str
    character_ids: List[int]
    scene_id: Optional[int]
    prop_ids: List[int]
    dialogue: str
    narration: str
    subtitle: str
    duration_sec: float
    visual_prompt: str
    negative_prompt: str
    image_url: str
    video_url: str
    audio_url: str
    character_refs: List[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Script ==============

class ScriptCreate(BaseModel):
    title: str = ""
    logline: str = ""
    content: str = ""
    raw_text: str = ""
    meta: Dict[str, Any] = {}
    version: int = 1


class ScriptOut(BaseModel):
    id: int
    project_id: int
    episode_id: Optional[int]
    version: int
    title: str
    logline: str
    content: str
    raw_text: str
    meta: Dict[str, Any]
    source_task_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True