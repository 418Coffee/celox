from itertools import count

import pytest
import trio
from celox.connection import Connector
from celox.defaults import DEFAULT_HEADERS
from celox.request import make_request
from celox.timeout import Timeout
from celox.util import create_ssl_context


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
