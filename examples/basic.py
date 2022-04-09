import trio
import celox


async def main():
    async with celox.Client() as client:
        async with client.get("https://httpbin.org/") as resp:
            body = await resp.read()
            print(body)


trio.run(main)
