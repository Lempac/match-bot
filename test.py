import asyncio
from aiohttp import ClientSession


async def main():
    url = "https://stackoverflow.com/"

    async with ClientSession() as session:
        async with session.get(url) as resp:
            print(resp.status)

asyncio.run(main())