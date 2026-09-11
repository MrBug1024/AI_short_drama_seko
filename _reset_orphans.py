"""先把项目1的shot 47-63 改回孤儿状态（模拟刚 create-with-script 出来时）"""
import asyncio
from sqlalchemy import update
from app.core.database import AsyncSessionLocal
from app.models.shot import Shot

async def main():
    async with AsyncSessionLocal() as db:
        stmt = update(Shot).where(
            Shot.project_id == 1,
            Shot.id >= 47,
        ).values(scene_id=None, character_ids=[])
        result = await db.execute(stmt)
        await db.commit()
        print(f"已重置 {result.rowcount} 个 shot 为孤儿状态")

asyncio.run(main())