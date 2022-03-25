from ast import Assert
import pytest
import yarl
from celer.connection import DirectConnection
from celer.handler import HTTPHandler
from celer.util import create_ssl_context
from celer.timeout import Timeout
from celer.request import make_request

async def test_handler_closed_connection():
    timeout = Timeout(5, 5, 5, 5)
    conn = DirectConnection("httpbin.org", 80, create_ssl_context(), timeout)
    with pytest.raises(AssertionError):
        handler = HTTPHandler(conn)

async def test_handler():
    timeout = Timeout(5, 5, 5, 5)
    conn = DirectConnection("httpbin.org", 80, create_ssl_context(), timeout)
    await conn.connect_tcp()
    handler = HTTPHandler(conn)
    url = yarl.URL("http://httpbin.org/")
    request = make_request("GET", url, {"Host": "httpbin.org"}, None)
    resp = await handler.write_request_read_response(request)