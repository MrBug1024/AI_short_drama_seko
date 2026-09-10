import asyncio, aiohttp, json

KEY = 'sk-sp-H.DHMILL.qpSF.MEYCIQDxAQNLJQZfVrsJJgYXW_iBx-1B9kwHW9ijPOBrclDl3wIhAPEq_tZc5IY_1x91Ce-VkhegTlYFXmEx0_qwiXEyGguF'

async def probe(name, url, payload=None, method='POST'):
    headers = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
            if method == 'GET':
                async with s.get(url, headers=headers) as r:
                    print(f'--- {name} -> {r.status}'); print((await r.text())[:400])
            else:
                async with s.post(url, json=payload, headers=headers) as r:
                    print(f'--- {name} -> {r.status}'); print((await r.text())[:400])
    except Exception as e:
        print(f'--- {name} EXC: {e}')

async def main():
    # 1. dashscope native text2image (async task)
    await probe('dashscope native t2i', 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
        {'model':'wan2.7-image','input':{'prompt':'a red apple'},'parameters':{'size':'1024*1024','n':1}})
    # 2. token-plan native path
    await probe('token-plan native t2i', 'https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
        {'model':'wan2.7-image','input':{'prompt':'a red apple'},'parameters':{'size':'1024*1024','n':1}})
    # 3. token-plan compatible chat (does chat work there?)
    await probe('token-plan chat', 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions',
        {'model':'wan2.7-image','messages':[{'role':'user','content':'a red apple, photo'}]})
    # 4. token-plan models list
    await probe('token-plan models', 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/models', method='GET')

asyncio.run(main())
