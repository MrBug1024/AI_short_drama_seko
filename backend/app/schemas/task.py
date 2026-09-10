"""画布/任务队列/AI Provider/Skill schemas"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============== Canvas ==============

class CanvasNodeCreate(BaseModel):
    node_type: str
    ref_id: Optional[int] = None
    title: str = ""
    position_x: float = 0
    position_y: float = 0
    thumbnail_url: str = ""
    meta: Dict[str, Any] = {}


class CanvasNodeUpdate(BaseModel):
    title: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    thumbnail_url: Optional[str] = None
    status: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class CanvasNodeOut(BaseModel):
    id: int
    project_id: int
    node_type: str
    ref_id: Optional[int]
    title: str
    position_x: float
    position_y: float
    thumbnail_url: str
    status: str
    meta: Dict[str, Any]

    class Config:
        from_attributes = True


class CanvasEdgeCreate(BaseModel):
    source_id: int
    target_id: int
    edge_type: str = "reference"
    label: str = ""


class CanvasEdgeOut(BaseModel):
    id: int
    project_id: int
    source_id: int
    target_id: int
    edge_type: str
    label: str

    class Config:
        from_attributes = True


class CanvasSnapshot(BaseModel):
    """画布全量快照"""
    nodes: List[CanvasNodeOut]
    edges: List[CanvasEdgeOut]


# ============== Generation Task ==============

class TaskCreate(BaseModel):
    task_type: str
    shot_id: Optional[int] = None
    character_id: Optional[int] = None
    scene_id: Optional[int] = None
    prop_id: Optional[int] = None
    prompt: str = ""
    negative_prompt: str = ""
    params: Dict[str, Any] = {}


class TaskOut(BaseModel):
    id: int
    project_id: int
    task_type: str
    shot_id: Optional[int]
    character_id: Optional[int]
    scene_id: Optional[int]
    prop_id: Optional[int]
    status: str
    progress: int
    phase: str
    prompt: str
    output_url: str
    error_msg: str
    provider_name: str
    model_name: str
    estimated_credits: float
    actual_credits: float
    duration_ms: int
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskListItem(TaskOut):
    """任务列表项（含目标标题）"""
    shot_code: str = ""
    target_title: str = ""


# ============== AI Provider ==============

class AIProviderCreate(BaseModel):
    name: str
    provider_type: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""
    text_model: str = ""
    image_model: str = ""
    video_model: str = ""
    audio_model: str = ""
    enabled: bool = True
    priority: int = 50


class AIProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    text_model: Optional[str] = None
    image_model: Optional[str] = None
    video_model: Optional[str] = None
    audio_model: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class AIProviderOut(BaseModel):
    id: int
    name: str
    provider_type: str
    base_url: str
    api_key_masked: str
    text_model: str
    image_model: str
    video_model: str
    audio_model: str
    enabled: bool
    is_builtin: bool
    priority: int
    last_test_at: Optional[datetime]
    last_test_status: str

    class Config:
        from_attributes = True


# ============== Skill ==============

class SkillOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    icon: str
    category: str
    installed: bool
    is_builtin: bool
    sort_order: int
    usage_count: int

    class Config:
        from_attributes = True