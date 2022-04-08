from itertools import count

import pytest
import trio
from celer.connection import Connector
from celer.defaults import DEFAULT_HEADERS
from celer.request import make_request
from celer.timeout import Timeout
from celer.util import create_ssl_context


async def test_connector_limited():
    async def try_connect(id: int, connector: Connector):
        if id == 1:
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

    id = count(1)
    with Connector(limit=1) as c:
        with pytest.raises(trio.TooSlowError):
            async with trio.open_nursery() as nursery:
                nursery.start_soon(try_connect, next(id), c)
                nursery.start_soon(try_connect, next(id), c)


async def test_connector_limit_similair_connection():
    async def try_connect(id: int, connector: Connector):
        if id == 1:
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

    id = count(1)
    with Connector(limit_per_similair_connection=1) as c:
        with pytest.raises(trio.TooSlowError):
            async with trio.open_nursery() as nursery:
                nursery.start_soon(try_connect, next(id), c)
                nursery.start_soon(try_connect, next(id), c)
