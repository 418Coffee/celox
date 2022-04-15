import pytest
import yarl
from celox.connection import Cache, Connector, DirectConnection
from celox.connection import HTTPConnection
from celox.util import create_ssl_context
from celox.timeout import Timeout
from celox.request import make_request
from .conftest import http_handler, http_handler_chunked, http_handler_chunked_trailers


@pytest.fixture
async def limitless_connector():
    c = Connector(limit=0)
    try:
        yield c
    finally:
        await c.close()


def add_handler_to_connector(handler: HTTPConnection, connector: Connector):
    c = Cache()
    c.connections.append(handler)
    c.aqcuired.add(handler)
    connector._cache[handler.key] = c
    connector._acquired.add(handler)


async def test_handler_closed_connection(limitless_connector: Connector):
    timeout = Timeout(5, 5, 5, 5)
    conn = DirectConnection("httpbin.org", 80, create_ssl_context(), timeout)
    conn._closed = True
    with pytest.raises(AssertionError):
        handler = HTTPConnection(limitless_connector, conn)
    await conn.close()


@pytest.mark.parametrize("direct_connection", [http_handler], indirect=True)
async def test_handler(
    direct_connection: DirectConnection, limitless_connector: Connector
):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(limitless_connector, direct_connection)
    add_handler_to_connector(handler, limitless_connector)
    url = yarl.URL(f"http://localhost{direct_connection.port}/")
    request = make_request(
        "GET", url, {"Host": f"http://localhost{direct_connection.port}/"}, None
    )
    resp = await handler.write_request_read_response(request)
    await resp.read()
    assert resp.ok
    assert resp.content_length == 602
    assert len(resp.body) == resp.content_length


@pytest.mark.parametrize("direct_connection", [http_handler_chunked], indirect=True)
async def test_handler_chunked(
    direct_connection: DirectConnection, limitless_connector: Connector
):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(limitless_connector, direct_connection)
    add_handler_to_connector(handler, limitless_connector)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request(
        "GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None
    )
    resp = await handler.write_request_read_response(request)
    await resp.read()
    assert resp.ok
    assert resp.chunked
    assert resp.content_length > 0
    assert len(resp.body) == resp.content_length


@pytest.mark.parametrize(
    "direct_connection", [http_handler_chunked_trailers], indirect=True
)
async def test_handler_chunked_trailers(
    direct_connection: DirectConnection, limitless_connector: Connector
):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(limitless_connector, direct_connection)
    add_handler_to_connector(handler, limitless_connector)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request(
        "GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None
    )
    resp = await handler.write_request_read_response(request)
    await resp.read()
    assert resp.ok
    assert resp.chunked
    assert resp.content_length > 0
    assert len(resp.body) == resp.content_length
    assert resp.trailers == "Expires,Set-Cookie"
    assert resp.cookies.get("test").value == "passed"


@pytest.mark.parametrize("direct_connection", [http_handler], indirect=True)
async def test_http_connection_close(
    direct_connection: DirectConnection, limitless_connector: Connector
):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(limitless_connector, direct_connection)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request(
        "GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None
    )
    resp = await handler.write_request_read_response(request)
    add_handler_to_connector(handler, limitless_connector)
    resp._closed = True
    await handler.close()
    await limitless_connector.close()
    with pytest.raises(RuntimeError):
        await limitless_connector.release_not_reusable(handler.key, handler)
