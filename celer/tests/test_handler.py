import pytest
import yarl
from celer.connection import DirectConnection
from celer.handler import HTTPHandler
from celer.util import create_ssl_context
from celer.timeout import Timeout
from celer.request import make_request
from .conftest import http_handler, http_handler_chunked, http_handler_chunked_trailers


async def test_handler_closed_connection():
    timeout = Timeout(5, 5, 5, 5)
    conn = DirectConnection("httpbin.org", 80, create_ssl_context(), timeout)
    with pytest.raises(AssertionError):
        handler = HTTPHandler(conn)

@pytest.mark.parametrize("direct_connection", [http_handler], indirect=True)
async def test_handler(direct_connection: DirectConnection):
    await direct_connection.connect_tcp()
    handler = HTTPHandler(direct_connection)
    url = yarl.URL(f"http://localhost{direct_connection.port}/")
    request = make_request("GET", url, {"Host": f"http://localhost{direct_connection.port}/"}, None)
    resp = await handler.write_request_read_response(request)
    assert resp.ok
    assert resp.content_length == 602
    assert len(resp.body) == resp.content_length


@pytest.mark.parametrize("direct_connection", [http_handler_chunked], indirect=True)
async def test_handler_chunked(direct_connection: DirectConnection):
    await direct_connection.connect_tcp()
    handler = HTTPHandler(direct_connection)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request("GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None)
    resp = await handler.write_request_read_response(request)
    assert resp.ok
    assert resp.chunked
    assert resp.content_length > 0
    assert len(resp.body) == resp.content_length

@pytest.mark.parametrize("direct_connection", [http_handler_chunked_trailers], indirect=True)
async def test_handler_chunked_trailers(direct_connection: DirectConnection):
    await direct_connection.connect_tcp()
    handler = HTTPHandler(direct_connection)
    url = yarl.URL(f"http://localhost:{direct_connection.port}/")
    request = make_request("GET", url, {"Host": f"http://localhost:{direct_connection.port}/"}, None)
    resp = await handler.write_request_read_response(request)
    assert resp.ok
    assert resp.chunked
    assert resp.content_length > 0
    assert len(resp.body) == resp.content_length
    assert resp.trailers == "Expires,Set-Cookie"
    assert resp.cookies.get("test").value == "passed"


