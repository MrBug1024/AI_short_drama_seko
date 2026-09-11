import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.scene import Scene

async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Scene).where(Scene.project_id == 1).order_by(Scene.id))).scalars().all()
        for s in rows:
            print(f"#{s.id} name='{s.name}' location='{s.location}' desc='{(s.description or '')[:60]}'")

asyncio.run(main())