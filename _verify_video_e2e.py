"""端到端验证：项目1的分镜生成视频（无图场景），验证 gateway 自动降级 r2v -> t2v"""
import asyncio, aiohttp, json

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4Iiwicm9sZSI6InVzZXIiLCJpYXQiOjE3ODkxMDMxNTgsImV4cCI6MTc4OTcwNzk1OH0.t8eVHMOi3UIFS6rZkGjadOzBgr6UJBDSlrVrABL5EXU'


async def main():
    hdr = {'Authorization': f'Bearer {TOKEN}'}
    async with aiohttp.ClientSession() as s:
        async with s.get('http://127.0.0.1:8000/api/v1/projects/1/canvas', headers=hdr) as r:
            j = await r.json()
            shots = [n for n in j['nodes'] if n['node_type'] == 'shot']
            print(f'canvas: nodes={len(j["nodes"])} shots={len(shots)}')
            if not shots:
                print('no shots')
                return
            s0 = shots[0]
            print(f'first shot: ref_id={s0["ref_id"]} thumb={s0.get("thumbnail_url")!r} title={s0.get("title")!r}')
            # 提交视频任务
            params = {
                'prompt': s0.get('title') or 'a cinematic scene from short drama',
                'image_url': s0.get('thumbnail_url') or '',
                'duration': 5,
                'shot_id': s0['ref_id'],
            }
            print('submit video task with params:', params)
            async with s.post('http://127.0.0.1:8000/api/v1/projects/1/generation/video', params=params, headers=hdr) as r2:
                res = await r2.json()
                print('=== result ===')
                print(json.dumps(res, ensure_ascii=False, indent=2))


asyncio.run(main())
