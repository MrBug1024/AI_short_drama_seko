"""查看数据库状态"""
import asyncio
from sqlalchemy import select, func
from app.core.database import init_db, AsyncSessionLocal
from app.models.project import Project
from app.models.character import Character
from app.models.scene import Scene
from app.models.shot import Shot

async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        projs = (await db.execute(select(Project))).scalars().all()
        for p in projs:
            cc = (await db.execute(select(func.count(Character.id)).where(Character.project_id == p.id))).scalar()
            sc = (await db.execute(select(func.count(Scene.id)).where(Scene.project_id == p.id))).scalar()
            sh = (await db.execute(select(func.count(Shot.id)).where(Shot.project_id == p.id))).scalar()
            print(f"项目 {p.id}: {p.name}  状态:{p.status}  角色:{cc} 场景:{sc} 镜头:{sh}")
            if sh and sh > 0:
                shots = (await db.execute(select(Shot).where(Shot.project_id == p.id))).scalars().all()
                for s in shots[:3]:
                    desc = s.description or ''
                    print(f"  - {s.shot_code}: {desc[:50]}  prompt_len={len(s.visual_prompt or '')}")
asyncio.run(main())
