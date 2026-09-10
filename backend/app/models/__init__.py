"""模型包入口 - 统一注册所有 ORM 模型，便于 create_all 发现"""
from app.models.user import User
from app.models.project import Project
from app.models.episode import Episode
from app.models.script import Script
from app.models.character import Character
from app.models.scene import Scene
from app.models.prop import Prop
from app.models.shot import Shot
from app.models.canvas import CanvasNode, CanvasEdge
from app.models.generation_task import GenerationTask
from app.models.ai_provider import AIProvider
from app.models.skill import Skill
from app.models.inspiration import Inspiration
from app.models.membership import Membership, CreditTransaction

__all__ = [
    "User",
    "Project",
    "Episode",
    "Script",
    "Character",
    "Scene",
    "Prop",
    "Shot",
    "CanvasNode",
    "CanvasEdge",
    "GenerationTask",
    "AIProvider",
    "Skill",
    "Inspiration",
    "Membership",
    "CreditTransaction",
]