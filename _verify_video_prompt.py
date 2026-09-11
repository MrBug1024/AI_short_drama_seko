"""验证 video prompt builder 在不同分镜下的输出"""
import asyncio
from app.services.video_prompt_builder import build_shot_video_prompt
from app.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 挑几个典型 shot：有角色 / 多个角色 / 无角色 / 有台词
        for shot_id in [30, 5, 25, 15]:
            prompt, meta = await build_shot_video_prompt(
                db, project_id=1, shot_id=shot_id, fallback_title=f"shot{shot_id}"
            )
            print("=" * 70)
            print(f"#{shot_id} {meta.get('shot_code','-')} chars={len(prompt)}")
            print(f"  scene: {meta['scene_name']} | characters: {meta['character_names']}")
            print(f"  meta:  comp={meta['composition']} move={meta['camera_movement']} dur={meta['duration_sec']}s")
            print("PROMPT:")
            print(prompt)
            print()


asyncio.run(main())
