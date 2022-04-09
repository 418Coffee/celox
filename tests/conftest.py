from functools import partial

import pytest
import trio
from celox.connection import DirectConnection
from celox.timeout import Timeout
from celox.util import create_ssl_context
from trio import socket as tsocket

import numpy as np
import math
import random

# http_handler, http_handler_no_body, http_handler_chunked are fixtures with module scopes.
# They write a HTTP message to the stream while ignoring any data that is read.
# They should be just in conjuction with the direct_connection fixture to create a local server whose only purpose is to write with single HTTP message.
# The main purpose of them is to test HTTP message parsing.


def _http_message():
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Date: Thu, 17 Mar 2022 12:47:32 GMT\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 602\r\n"
        b"Connection: keep-alive\r\n"
        b"Server: gunicorn/19.9.0\r\n"
        b"Access-Control-Allow-Origin: *\r\n"
        b"Access-Control-Allow-Credentials: true\r\n\r\n" + b"A" * 602
    )


def _http_message_no_body():
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Date: Thu, 17 Mar 2022 12:47:32 GMT\r\n"
        b"Content-Type: application/json\r\n"
        b"Connection: keep-alive\r\n"
        b"Server: gunicorn/19.9.0\r\n"
        b"Access-Control-Allow-Origin: *\r\n"
        b"Access-Control-Allow-Credentials: true\r\n\r\n"
    )


def _http_message_chunked() -> "tuple[bytes, list[str]]":
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Date: Thu, 17 Mar 2022 12:47:32 GMT\r\n"
        b"Content-Type: application/json\r\n"
        b"Connection: keep-alive\r\n"
        b"Server: gunicorn/19.9.0\r\n"
        b"Access-Control-Allow-Origin: *\r\n"
        b"Access-Control-Allow-Credentials: true\r\n"
        b"Transfer-Encoding: chunked\r\n"
    )
    yield response
    # 10k bytes body at max.
    chunk_sizes = [
        math.floor(i)
        for i in np.random.uniform(size=random.randint(2, 5), low=1, high=2000)
    ]
    for size in chunk_sizes:
        yield f"\r\n{format(size, 'x')}\r\n{chr(65+((size - 65) % 26))*size}".encode()
    yield b"\r\n0\r\n\r\n"


def _http_message_chunked_trailers() -> "tuple[bytes, list[str]]":
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Date: Thu, 17 Mar 2022 12:47:32 GMT\r\n"
        b"Content-Type: application/json\r\n"
        b"Connection: keep-alive\r\n"
        b"Server: gunicorn/19.9.0\r\n"
        b"Access-Control-Allow-Origin: *\r\n"
        b"Access-Control-Allow-Credentials: true\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"Trailer: Expires,Set-Cookie\r\n"
    )
    yield response
    # 10k bytes body at max.
    chunk_sizes = [
        math.floor(i)
        for i in np.random.uniform(size=random.randint(2, 5), low=1, high=2000)
    ]
    for size in chunk_sizes:
        yield f"\r\n{format(size, 'x')}\r\n{chr(65+((size - 65) % 26))*size}".encode()
    yield b"\r\n0\r\n"
    yield b"Expires: Thu, 17 Mar 2022 12:47:32 GMT\r\n" b"Set-Cookie: test=passed\r\n\r\n"


_http_message_bytes = _http_message()
_http_message_no_body_bytes = _http_message_no_body()
_http_message_chunked_bytes = [chunk for chunk in _http_message_chunked()]
_http_message_chunked_trailers_bytes = [
    chunk for chunk in _http_message_chunked_trailers()
]


async def http_handler(stream: trio.SocketStream):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(stream.receive_some)
        nursery.start_soon(stream.send_all, _http_message_bytes)


async def http_handler_no_body(stream: trio.SocketStream):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(stream.receive_some)
        nursery.start_soon(stream.send_all, _http_message_no_body_bytes)


async def http_handler_chunked(stream: trio.SocketStream):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(stream.receive_some)
        for chunk in _http_message_chunked_bytes:
            await stream.send_all(chunk)


async def http_handler_chunked_trailers(stream: trio.SocketStream):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(stream.receive_some)
        for chunk in _http_message_chunked_trailers_bytes:
            await stream.send_all(chunk)


@pytest.fixture(scope="function")
async def direct_connection(nursery, request):
    listeners = await nursery.start(partial(trio.serve_tcp, request.param, port=0))
    ln: trio.SocketListener = listeners[0]
    family = ln.socket.family
    sockaddr = ln.socket.getsockname()
    assert family in (tsocket.AF_INET, tsocket.AF_INET6)
    host = None
    port = None
    sockaddr = list(sockaddr)
    if sockaddr[0] == "0.0.0.0":
        host = "127.0.0.1"
    if sockaddr[0] == "::":
        host = "::1"
    port = sockaddr[1]
    async with DirectConnection(
        host, port, create_ssl_context(), Timeout(5, 5, 5, 5)
    ) as conn:
        yield conn
