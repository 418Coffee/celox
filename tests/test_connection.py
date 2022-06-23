from itertools import count

import pytest
import trio
from celox.connection import DirectConnection, ProxyConnection
from celox import (
    ProxyConnectionSSLError,
    Timeout,
    Connector,
    ConnectionTimeout,
    ReadTimeout,
    WriteTimeout,
    ConnectionOSError,
    ConnectionSSLError,
)
from celox.exceptions import InvalidProxy
from celox.util import create_ssl_context
from tests.conftest import http_handler


async def try_connect(tid: int, connector: Connector):
    if tid == 1:
        await connector.acquire(
            "localhost", 80, create_ssl_context(), Timeout(5, 5, 5, 5), None
        )
    else:
        # Sleep a little if 2 goes first
        await trio.sleep(0.2)
        with trio.fail_after(0.3):
            await connector.acquire(
                "localhost", 80, create_ssl_context(), Timeout(5, 5, 5, 5), None
            )


async def test_connector_limited():
    id = count(1)
    async with Connector(limit=1) as c:
        with pytest.raises(trio.TooSlowError):
            async with trio.open_nursery() as nursery:
                nursery.start_soon(try_connect, next(id), c)
                nursery.start_soon(try_connect, next(id), c)


async def test_connector_limit_similair_connection():
    id = count(1)
    async with Connector(limit_per_similair_connection=1) as c:
        with pytest.raises(trio.TooSlowError):
            async with trio.open_nursery() as nursery:
                nursery.start_soon(try_connect, next(id), c)
                nursery.start_soon(try_connect, next(id), c)


async def test_closed_connector():
    with pytest.raises(RuntimeError):
        async with Connector() as c:
            await c.close()
            await c.acquire(
                "localhost", 80, create_ssl_context(), Timeout(5, 5, 5, 5), None
            )


async def test_full_connector():
    with pytest.raises(trio.MultiError):
        async with Connector(limit=1) as c:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(
                    c.acquire,
                    "localhost",
                    80,
                    create_ssl_context(),
                    Timeout(5, 5, 5, 5),
                    None,
                )
                nursery.start_soon(
                    c.acquire,
                    "localhost",
                    80,
                    create_ssl_context(),
                    Timeout(5, 5, 5, 5),
                    None,
                )
                await c.close()


@pytest.mark.parametrize("direct_connection", [http_handler], indirect=True)
async def test_direct_connection_runtime_errors(
    direct_connection: DirectConnection,
):
    await direct_connection.connect_tcp()
    await direct_connection.connect_tcp()
    direct_connection._ssl = True
    with pytest.raises(RuntimeError):
        await direct_connection.connect_tcp()
    direct_connection._ssl = False
    with pytest.raises(RuntimeError):
        await direct_connection.connect_ssl()


@pytest.mark.parametrize("direct_connection", [http_handler], indirect=True)
async def test_direct_connection_timeouts(direct_connection: DirectConnection):
    direct_connection._timeout = Timeout(0, 0, 0, 0, 0)
    with pytest.raises(ConnectionTimeout):
        await direct_connection.connect_tcp()
    direct_connection._timeout = Timeout(0, 0, 0, 0, 5)
    await direct_connection.connect_tcp()
    direct_connection._timeout = Timeout(0, 0, 0, 0, 0)
    with pytest.raises(ReadTimeout):
        await direct_connection.recv(1)
    with pytest.raises(ReadTimeout):
        await direct_connection.recv_exactly(1)
    with pytest.raises(WriteTimeout):
        await direct_connection.send_all(b"")


async def test_direct_connection_os_error():
    async with DirectConnection(
        "localhost",
        443,  # let's hope nothings on here
        create_ssl_context(),
        Timeout(),
    ) as conn:
        with pytest.raises(ConnectionOSError):
            await conn.connect_tcp()


async def test_direct_connection_ssl_error():
    async with DirectConnection(
        "expired.badssl.com",
        443,
        create_ssl_context(),
        Timeout(),
    ) as conn:
        with pytest.raises(ConnectionSSLError):
            await conn.connect_ssl()


async def test_proxy_connection_invalid_proxy():
    with pytest.raises(InvalidProxy):
        async with ProxyConnection(
            "httpbin.org",
            443,
            "badprotocol://test.com",
            create_ssl_context(),
            Timeout(),
        ) as conn:
            await conn.connect_tcp()


# The proxies below are outdated...


@pytest.mark.skip
async def test_proxy_connection_http():
    async with ProxyConnection(
        "httpbin.org",
        80,
        "http://54.38.78.155:8080",
        create_ssl_context(),
        Timeout(),
    ) as conn:
        await conn.connect_tcp()


@pytest.mark.skip
async def test_proxy_connection_https():
    async with ProxyConnection(
        "httpbin.org",
        443,
        "http://93.158.214.155:3128",
        create_ssl_context(),
        Timeout(),
    ) as conn:
        await conn.connect_ssl()


@pytest.mark.skip
async def test_proxy_connection_ssl_error():
    async with ProxyConnection(
        "expired.badssl.com",
        443,
        "http://93.158.214.155:3128",
        create_ssl_context(),
        Timeout(),
    ) as conn:
        with pytest.raises(ProxyConnectionSSLError):
            await conn.connect_ssl()
