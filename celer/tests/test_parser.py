
import pytest
from celer.parser import ReceiveBuffer

@pytest.fixture(scope="module")
def http_message():
    return \
    b"HTTP/1.1 200 OK\r\n" \
    b"Date: Thu, 17 Mar 2022 12:47:32 GMT\r\n" \
    b"Content-Type: application/json\r\n" \
    b"Content-Length: 602\r\n" \
    b"Connection: keep-alive\r\n" \
    b"Server: gunicorn/19.9.0\r\n" \
    b"Access-Control-Allow-Origin: *\r\n" \
    b"Access-Control-Allow-Credentials: true\r\n\r\n" + b"A"*602

def test_parse_complete_http_message(http_message: bytes):
    buf = ReceiveBuffer(http_message)
    status_and_headers = buf.read()
    # \r\n\r\n is stripped
    assert len(status_and_headers) == (len(http_message) - 4 - len(buf))

def test_parse_split_http_message(http_message: bytes):
    part1, part2 = http_message.split(b"Server")
    part1 += b"Server"
    buf = ReceiveBuffer(part1)
    assert buf.read() == None
    buf += part2
    status_and_headers = buf.read()
    # \r\n\r\n is stripped
    assert len(status_and_headers) == (len(http_message) - 4 - len(buf))

def test_parse_complete_http_message_with_body(http_message: bytes):
    buf = ReceiveBuffer(http_message)
    status_and_headers = buf.read()
    # \r\n\r\n is stripped
    assert len(status_and_headers) == (len(http_message) - 4 - len(buf))

def test_parse_split_http_message_with_body(http_message: bytes):
    part1, part2 = http_message.split(b"Server")
    part1 += b"Server"
    buf = ReceiveBuffer(part1)
    assert buf.read() == None
    buf += part2
    status_and_headers = buf.read()
    # \r\n\r\n is stripped
    assert len(status_and_headers) == (len(http_message) - 4 - len(buf))


    
        
