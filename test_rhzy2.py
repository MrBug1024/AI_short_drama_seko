import asyncio, aiohttp, json
KEY = 'sk-0b6bb5a193337faa7be334650d6fba98f724b5f02a4dbf33b25eb3fc3e7f1fc0'
async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
        async with s.get('https://model.rhzy.ai/v1/models', headers={'Authorization': f'Bearer {KEY}'}) as r:
            d = await r.json()
            print(json.dumps([m['id'] for m in d.get('data', [])], ensure_ascii=False, indent=0))
asyncio.run(main())
