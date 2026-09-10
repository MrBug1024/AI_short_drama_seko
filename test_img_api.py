import asyncio, aiohttp, json

BASE = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
KEY = 'sk-sp-H.DHMILL.qpSF.MEYCIQDxAQNLJQZfVrsJJgYXW_iBx-1B9kwHW9ijPOBrclDl3wIhAPEq_tZc5IY_1x91Ce-VkhegTlYFXmEx0_qwiXEyGguF'

async def try_payload(name, payload):
    headers = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
        async with s.post(f'{BASE}/images/generations', json=payload, headers=headers) as r:
            txt = await r.text()
            print(f'--- {name} -> {r.status}')
            print(txt[:600])

async def main():
    await try_payload('A: size=1024x1024 (current)', {'model':'wan2.7-image','prompt':'a red apple on a table','n':1,'size':'1024x1024'})
    await try_payload('B: size=1024*1024', {'model':'wan2.7-image','prompt':'a red apple on a table','n':1,'size':'1024*1024'})
    await try_payload('C: no size', {'model':'wan2.7-image','prompt':'a red apple on a table','n':1})

asyncio.run(main())
