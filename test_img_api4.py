import asyncio, aiohttp, json

KEY = 'sk-sp-H.DHMILL.qpSF.MEYCIQDxAQNLJQZfVrsJJgYXW_iBx-1B9kwHW9ijPOBrclDl3wIhAPEq_tZc5IY_1x91Ce-VkhegTlYFXmEx0_qwiXEyGguF'
BASE = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'

async def post(s, name, url, payload, headers):
    async with s.post(url, json=payload, headers=headers) as r:
        txt = await r.text()
        print(f'--- {name} -> {r.status}')
        print(txt[:800])
        print()

async def main():
    headers = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as s:
        # 1. size + negative_prompt 作为顶层参数
        await post(s, 'size+negative top-level', f'{BASE}/chat/completions', {
            'model': 'wan2.7-image',
            'messages': [{'role':'user','content':[{'type':'text','text':'a red apple'}]}],
            'size': '1024*1024',
            'negative_prompt': 'blurry, low quality',
        }, headers)
        # 2. parameters 包裹（dashscope 风格）
        await post(s, 'parameters wrapped', f'{BASE}/chat/completions', {
            'model': 'wan2.7-image',
            'messages': [{'role':'user','content':[{'type':'text','text':'a red apple'}]}],
            'parameters': {'size': '1024*1024', 'negative_prompt': 'blurry'},
        }, headers)
        # 3. 视频模型是否存在
        await post(s, 'video happyhorse', f'{BASE}/chat/completions', {
            'model': 'happyhorse-1.1-i2v',
            'messages': [{'role':'user','content':[{'type':'text','text':'a cat running'}]}],
        }, headers)

asyncio.run(main())
