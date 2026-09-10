import asyncio, aiohttp, json

KEY = 'sk-0b6bb5a193337faa7be334650d6fba98f724b5f02a4dbf33b25eb3fc3e7f1fc0'
BASE = 'https://model.rhzy.ai/v1'

async def req(s, name, method, url, payload=None):
    headers = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}
    try:
        if method == 'GET':
            async with s.get(url, headers=headers) as r:
                print(f'--- {name} -> {r.status}'); print((await r.text())[:500])
        else:
            async with s.post(url, json=payload, headers=headers) as r:
                print(f'--- {name} -> {r.status}'); print((await r.text())[:500])
    except Exception as e:
        print(f'--- {name} EXC: {e}')
    print()

async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
        await req(s, 'models list', 'GET', f'{BASE}/models')
        await req(s, 'mj-v7 images/generations', 'POST', f'{BASE}/images/generations',
            {'model':'mj-v7','prompt':'a red apple on a table','n':1,'size':'1024x1024'})

asyncio.run(main())
