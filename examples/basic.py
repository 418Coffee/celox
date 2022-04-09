import trio
import celer


async def main():
    async with celer.Client() as client:
        async with client.get("https://httpbin.org/") as resp:
            body = await resp.read()
            print(body)


trio.run(main)
