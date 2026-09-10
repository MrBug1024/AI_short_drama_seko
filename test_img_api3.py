import asyncio, aiohttp, json

KEY = 'sk-sp-H.DHMILL.qpSF.MEYCIQDxAQNLJQZfVrsJJgYXW_iBx-1B9kwHW9ijPOBrclDl3wIhAPEq_tZc5IY_1x91Ce-VkhegTlYFXmEx0_qwiXEyGguF'
BASE = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'

async def main():
    headers = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
        async with s.get(f'{BASE}/models', headers=headers) as r:
            data = await r.json()
            ids = [m['id'] for m in data.get('data', [])]
            print('MODELS:', json.dumps(ids, ensure_ascii=False))

        # 试 multimodal chat 格式调用图片模型
        payload = {
            'model': 'wan2.7-image',
            'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'a red apple on a wooden table, photo'}]}],
        }
        async with s.post(f'{BASE}/chat/completions', json=payload, headers=headers) as r:
            print('--- wan2.7-image via chat ->', r.status)
            print((await r.text())[:1500])

asyncio.run(main())
