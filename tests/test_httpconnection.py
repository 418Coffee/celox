import pytest
import yarl
from celer.connection import Cache, Connector, DirectConnection
from celer.connection import HTTPConnection
from celer.util import create_ssl_context
from celer.timeout import Timeout
from celer.request import make_request
from .conftest import http_handler, http_handler_chunked, http_handler_chunked_trailers

@pytest.fixture
async def connector():
    return Connector(limit=0)


async def test_handler_closed_connection(connector: Connector):
    timeout = Timeout(5, 5, 5, 5)
    conn = DirectConnection("httpbin.org", 80, create_ssl_context(), timeout)
    conn._closed = True
    with pytest.raises(AssertionError):
        handler = HTTPConnection(connector, conn)

@pytest.mark.parametrize("direct_connection", [http_handler], indirect=True)
async def test_handler(direct_connection: DirectConnection, connector: Connector):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(connector, direct_connection)
    url = yarl.URL(f"http://localhost{direct_connection.port}/")
    request = make_request("GET", url, {"Host": f"http://localhost{direct_connection.port}/"}, None)
    resp = await handler.write_request_read_response(request)
    c = Cache()
    c.connections.append(handler)
    c.aqcuired.add(handler)
    connector._cache[direct_connection.key] = c
    connector._acquired.add(handler)
    await resp.read()
    assert resp.ok
    assert resp.content_length == 602
    assert len(resp.body) == resp.content_length


@pytest.mark.parametrize("direct_connection", [http_handler_chunked], indirect=True)
async def test_handler_chunked(direct_connection: DirectConnection, connector: Connector):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(connector, direct_connection)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request("GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None)
    resp = await handler.write_request_read_response(request)
    c = Cache()
    c.connections.append(handler)
    c.aqcuired.add(handler)
    connector._cache[direct_connection.key] = c
    connector._acquired.add(handler)
    await resp.read()
    assert resp.ok
    assert resp.chunked
    assert resp.content_length > 0
    assert len(resp.body) == resp.content_length

@pytest.mark.parametrize("direct_connection", [http_handler_chunked_trailers], indirect=True)
async def test_handler_chunked_trailers(direct_connection: DirectConnection, connector: Connector):
    await direct_connection.connect_tcp()
    handler = HTTPConnection(connector, direct_connection)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request("GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None)
    resp = await handler.write_request_read_response(request)
    c = Cache()
    c.connections.append(handler)
    c.aqcuired.add(handler)
    connector._cache[direct_connection.key] = c
    connector._acquired.add(handler)
    await resp.read()
    assert resp.ok
    assert resp.chunked
    assert resp.content_length > 0
    assert len(resp.body) == resp.content_length
    assert resp.trailers == "Expires,Set-Cookie"
    assert resp.cookies.get("test").value == "passed"

