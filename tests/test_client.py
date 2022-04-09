import ssl

import yarl
from celox import Client, InvalidURL, RequestTimeout
import pytest

from celox.exceptions import InvalidProxy, MaxRedirect


# Sadly we must a "function" scope because of pytest-trio.
@pytest.fixture(scope="function")
async def client():
    async with Client() as c:
        yield c


async def test_get(client: Client):
    # cheeky https
    async with client.get("https://httpbin.org/get") as resp:
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


async def test_client_baseurl():
    async with Client(base_url="http://httpbin.org/") as client:
        async with client.get("/get") as resp:
            assert resp.status == 200


async def test_client_invalid_baseurl():
    with pytest.raises(InvalidURL):
        async with Client(base_url="ftp://httpbin.org/") as client:
            async with client.get("/get") as resp:
                assert resp.status == 200


async def test_client_timeout():
    async with Client(base_url="http://httpbin.org/", timeout=0.1) as client:
        with pytest.raises(RequestTimeout):
            await client.get("/get")


async def test_client_proxy():
    proxy = yarl.URL("http://localhost:8888")
    async with Client(base_url="http://httpbin.org/", proxy=proxy) as client:
        assert client.proxy == proxy
        client.proxy = None
        assert client.proxy is None


async def test_client_invalid_proxy():
    with pytest.raises(InvalidProxy):
        async with Client(
            base_url="http://httpbin.org/", proxy="ftp://localhost:8888"
        ) as client:
            await client.get("/get")


@pytest.mark.parametrize(
    "ssl,expected_verify_mode",
    [
        (None, ssl.CERT_REQUIRED),
        (True, ssl.CERT_REQUIRED),
        (False, ssl.CERT_NONE),
        (ssl.create_default_context(ssl.Purpose.SERVER_AUTH), ssl.CERT_REQUIRED),
    ],
)
async def test_client_ssl_context(ssl: ssl.SSLContext, expected_verify_mode):
    async with Client(base_url="http://httpbin.org/", ssl=ssl) as client:
        assert client._ssl_context.verify_mode == expected_verify_mode


async def test_client_redirect(client: Client):
    async with client.get("http://httpbin.org/absolute-redirect/1") as resp:
        assert resp.status == 200
        assert len(resp.history) == 1


async def test_client_disallow_redirects(client: Client):
    async with client.get(
        "http://httpbin.org/absolute-redirect/1", allow_redirects=False
    ) as resp:
        assert resp.status == 302
        assert len(resp.history) == 0


async def test_client_max_redirect(client: Client):
    with pytest.raises(MaxRedirect):
        async with client.get(
            "http://httpbin.org/absolute-redirect/1", max_redirects=0
        ) as resp:
            assert resp.status == 200


async def test_client_different_domain(client: Client):
    async with client.get(
        "http://httpbin.org/redirect-to?url=http://httpbin.org/get"
    ) as resp:
        assert resp.status == 200
        assert resp.url.human_repr() == "http://httpbin.org/get"
