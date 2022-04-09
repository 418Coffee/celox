from celox import Client
import pytest

# Sadly we must a "function" scope because of pytest-trio.
@pytest.fixture(scope="function")
async def client():
    async with Client() as c:
        yield c


async def test_response(client: Client):
    async with client.get("http://httpbin.org/") as resp:
        body = await resp.read()
        assert resp.url.human_repr() == "http://httpbin.org/"
        assert len(body) == resp.content_length
        assert resp.chunked is False
        assert resp.closed is True
        assert resp.headers.get("Date") is not None
