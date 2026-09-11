"""执行分镜关系修复（项目 1）"""
import asyncio
import sys
sys.path.insert(0, '.')
from app.services.shot_repair import repair_project_shots
from app.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        result = await repair_project_shots(db, project_id=1)
        print("=" * 60)
        print(f"扫描: {result['scanned']} 个 shot")
        print(f"孤儿: {result.get('orphans', 0)} 个")
        print(f"修复场景关联: {result['fixed_scene']} 个")
        print(f"修复角色关联: {result['fixed_characters']} 个")
        print("=" * 60)
        print("修复后详情:")
        for d in result['details']:
            print(f"  #{d['shot_id']} {d['shot_code']} scene={d['scene_id']} chars={d['character_ids']} | {d['desc_preview']}")


asyncio.run(main())
