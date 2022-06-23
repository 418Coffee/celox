import trio
import celox


async def main():
    try:
        async with celox.Client(timeout=celox.Timeout(total=1)) as client:
            async with client.get("https://httpbin.org/delay/2"):
                pass
    except celox.RequestTimeout:
        print("timed out!")


trio.run(main)
