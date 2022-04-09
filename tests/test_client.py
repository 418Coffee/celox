from celox import Client
import pytest

# Sadly we must a "function" scope because of pytest-trio.
@pytest.fixture(scope="function")
async def client():
    async with Client() as c:
        yield c


async def test_get(client: Client):
    async with client.get("http://httpbin.org") as resp:
        assert resp.status == 200


async def test_post(client: Client):
    async with client.post("http://httpbin.org/post", data="test") as resp:
        assert resp.status == 200


async def test_put(client: Client):
    async with client.put("http://httpbin.org/put", data="test") as resp:
        assert resp.status == 200


async def test_patch(client: Client):
    async with client.patch("http://httpbin.org/patch", data="test") as resp:
        assert resp.status == 200


async def test_delete(client: Client):
    async with client.delete("http://httpbin.org/delete", data="test") as resp:
        assert resp.status == 200
