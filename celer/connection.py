import ssl
import warnings
from collections import deque
from types import TracebackType
from typing import Any, Deque, Dict, Optional, Set, Tuple, Type, Union, final

import attr
import trio
import yarl

# Some common trio imports.
from trio import (
    BrokenResourceError,
    SocketStream,
    SSLStream,
    TooSlowError,
    open_tcp_stream,
)

from .abc import AbstractCookieJar
from .exceptions import (
    ConnectionOSError,
    ConnectionSSLError,
    ConnectionTimeout,
    MalformedResponse,
    ProxyConnectionError,
    ProxyConnectionSSLError,
    ProxyConnectionTimeout,
    ProxyError,
    ReadTimeout,
    UnclosedConnection,
    UnclosedConnector,
    WriteTimeout,
)
from .parser import ReceiveBuffer
from .proxy import _connect_request, _prepare_proxy
from .response import Response
from .timeout import Timeout
from .typedefs import ProxyLike, TimeoutLike
from .util import is_ssl, winsock2strerror

__all__ = (
    "ConnectionKey",
    "BaseConnection",
    "DirectConnection",
    "ProxyConnection",
    "HTTPConnection",
    "Connector",
)


@attr.s(frozen=True, repr=True, slots=True)
class ConnectionKey:
    """
    A ``ConnectionKey`` is used to commonly identify connections.
    Meaning that every underlying connections whose ``ConnectionKey`` is the same may in theory be swapped.
    The use of ``ConnectionsKeys`` is abstracted away by ``BaseConnection`` (and it's children) and ``Connector``,
    thus the end-user should generally not use them.
    """

    host: str = attr.ib()
    port: int = attr.ib()
    ssl_skip_verify: bool = attr.ib()


class BaseConnection:
    """
    ``BaseConnection`` is the lowest level construction of a TCP connection.
    It wraps ``trio.SocketStream`` and ``trio.SSLStream`` for TCP and SSL/TLS over TCP respectively.
    It implements timeouts and wraps errors.
    Most end-users will not use ``BaseConnection`` directly.
    """

    __slots__: Tuple[str, str, str, str, str, str, str, str] = (
        "host",
        "port",
        "ssl_context",
        "key",
        "_stream",
        "_ssl",
        "_timeout",
        "_closed",
    )

    def __init__(
        self, host: Any, port: Any, ssl_context: ssl.SSLContext, timeout: TimeoutLike
    ) -> None:
        assert ssl_context is not None
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.key: ConnectionKey = ConnectionKey(
            host, port, ssl_context.verify_mode is ssl.CERT_NONE
        )
        self._stream: Union[SSLStream, SocketStream] = None
        self._ssl: Union[bool, None] = None
        if isinstance(timeout, (float, int)):
            timeout = Timeout(total=float(timeout))
        self._timeout = timeout
        self._closed: Union[bool, None] = None

    @property
    def closed(self) -> Union[bool, None]:
        return self._closed

    async def connect_tcp(self) -> None:
        # Was connect_* already called?
        if self._stream:
            # Yes, did they call connect_ssl first?
            if self._ssl:
                # Why would someone call connect_tcp after calling connect_tcp?
                raise RuntimeError("This is an ssl connection, use 'connect_ssl'")
            # noop
            return
        # No, create a new stream.
        try:
            with trio.fail_after(self._timeout.connect or self._timeout.any):
                self._stream = await open_tcp_stream(self.host, self.port)
        except TooSlowError as e:
            raise ConnectionTimeout() from e
        except OSError as e:
            # If all connect attempts fail, then open_tcp_stream returns a MultiError with all ConnectionRefusedErrors (basically an OSError).
            # Otherwise we probably just got an OSError (e.g. getaddrinfo failed).
            cause = e.__cause__
            if isinstance(cause, trio.MultiError):
                _cause: ConnectionRefusedError = cause.exceptions[0]
                # Try to map errno to a Winsock2.h error if possible.
                _cause.strerror = (
                    winsock2strerror(_cause.errno)
                    if "Unknown error" in _cause.strerror
                    else _cause.strerror
                )
                cause = _cause
            else:
                cause = cause if e.__cause__ else e
            raise ConnectionOSError(self.host, self.port, cause) from e
        self._ssl = False
        self._closed = False
        return

    async def connect_ssl(self) -> None:
        # Was connect_* already called?
        if self._stream:
            # Yes, did they call connect_tcp first?
            if self._ssl is False:
                # Why would someone call connect_ssl after calling connect_tcp?
                raise RuntimeError("This is a tcp connection, use 'connect_tcp'")
            return
        # No, create a new stream, wrap it into a trio.SSLStream and perform the handshake.
        try:
            # We basically imitate trio.open_ssl_over_tcp_stream here,
            # but because we call our own self.connect_tcp we no longer have to catch for OSErrors here.
            # Also almost all timeouts will happen in self.connect_tcp. We will only raise a ConnectionTimeout if do_handshake times out.
            with trio.fail_after(self._timeout.connect or self._timeout.any):
                await self.connect_tcp()
                self._stream = trio.SSLStream(
                    self._stream,
                    self.ssl_context,
                    server_hostname=self.host,
                    https_compatible=True,
                )
                await self._stream.do_handshake()
        except TooSlowError as e:
            raise ConnectionTimeout() from e
        except BrokenResourceError as e:
            cause = e.__cause__
            if isinstance(cause, ssl.SSLCertVerificationError):
                raise ConnectionSSLError(
                    cause.library,
                    cause.reason,
                    f"certificate verify failed: {cause.verify_message}",
                ) from e
        self._ssl = True
        self._closed = False
        return

    async def send_all(self, data: Any) -> None:
        if self._stream is None:
            exc = (
                RuntimeError("Connection closed")
                if self._closed
                else RuntimeError("Connect before receiving data")
            )
            raise exc
        try:
            with trio.fail_after(self._timeout.write or self._timeout.any):
                await self._stream.send_all(data)
        except TooSlowError as e:
            raise WriteTimeout() from e

    async def recv(self, max_bytes: Any = None) -> bytes:
        if self._stream is None:
            exc = (
                RuntimeError("Connection closed")
                if self._closed
                else RuntimeError("Connect before receiving data")
            )
            raise exc
        try:
            with trio.fail_after(self._timeout.read or self._timeout.any):
                return await self._stream.receive_some(max_bytes)  # type: ignore
        except TooSlowError as e:
            raise ReadTimeout() from e

    async def recv_exactly(self, n: int) -> bytes:
        data = bytes()
        while n > 0:
            received = await self.recv(n)
            if received == b"":
                # EOF
                return b""
            n -= len(received)
            data += received
        return data

    async def close(self) -> None:
        if self._closed or self._stream is None:
            return
        self._closed = True
        await self._stream.aclose()
        # The class may be reused by calling a connect_* method again.
        # Setting _stream to None will result in consecutive recv and send_all calls to fail.
        # If we did not set _stream to None recv and send_all would raise trio.ClosedResourceErrors.
        self._stream = None
        return

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} stream={self._stream} closed={self._closed} is_ssl={self._ssl}>"

    def __del__(self, _warnings: Any = warnings) -> None:
        if self._closed is False:
            warnings.warn(
                f"Unclosed connection {self!r}",
                ResourceWarning,
                source=self,
            )
            # TODO:
            raise UnclosedConnection

    async def __aenter__(self) -> "BaseConnection":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        exc_traceback: Optional[TracebackType] = None,
    ) -> None:
        await self.close()


@final
class DirectConnection(BaseConnection):
    """
    ``DirectConnection`` represents a direct connection to a TCP peer.
    It is identical to BaseConnection, there are only 2 subtle differences:
    1. The name change is to display that the connection does not use a proxy.
    2. The class is marked with the ``@final`` decorator.
    """

    __slots__ = ()


@final
class ProxyConnection(BaseConnection):
    """
    ``ProxyConnection`` represents a connection to a TCP peer via an HTTP(S) proxy.
    It overrides the ``connect_tcp``, ``connect_ssl`` and ``close`` to accomplish this.
    Some errors are wrapped when handling the proxy peer.
    """

    __slots__: Tuple[str, str] = ("proxy", "_proxy_connection")

    def __init__(
        self,
        host: Any,
        port: Any,
        proxy_url: ProxyLike,
        ssl_context: ssl.SSLContext,
        timeout: TimeoutLike,
    ) -> None:
        self.proxy: yarl.URL = _prepare_proxy(proxy_url)
        self._proxy_connection: DirectConnection = DirectConnection(
            self.proxy.host, self.proxy.port, ssl_context, timeout
        )
        super().__init__(host, port, ssl_context, timeout)

    async def connect_tcp(self):
        # Are we already connected?
        if self._proxy_connection._closed is False:
            # Yes, there's nothing to do.
            return
        # No, let's create a conenction to the proxy and hand the stream over to us.
        try:
            await self._proxy_connection.connect_tcp()
        except ConnectionOSError as e:
            # Wrap and reraise.
            raise ProxyConnectionError(e.host, e.port, e.os_error) from e
        except ConnectionTimeout as e:
            raise ProxyConnectionTimeout from e
        self._stream = self._proxy_connection._stream
        self._closed = False

    async def connect_ssl(self) -> None:
        # Are we already connected?
        if self._proxy_connection._closed is False:
            # Yes, there's nothing to do.
            return
        # No, let's create a conenction to the proxy and hand stream over to us.
        try:
            # Are we connecting to the proxy over HTTPS or HTTP?
            if is_ssl(self.proxy):
                # HTTPS, let's setup a tls-in-tls connection.
                await self._proxy_connection.connect_ssl()
            else:
                # HTTP, just connect to the proxy using tcp
                await self._proxy_connection.connect_tcp()
        except ConnectionSSLError as e:
            # Wrap and reraise.
            raise ProxyConnectionSSLError(e.library, e.reason, e.message) from e
        except ConnectionOSError as e:
            # Wrap and reraise.
            raise ProxyConnectionError(e.host, e.port, e.os_error) from e
        except ConnectionTimeout as e:
            raise ProxyConnectionTimeout from e
        # Since we basically wrap the DirectConnection to the proxy we are now "open".
        self._closed = False
        # Send the CONNECT request for the tunnel setup.
        req = _connect_request(
            self.host,
            self.port,
            user=self.proxy.raw_user,
            password=self.proxy.raw_password,
        )
        # We now have an HTTPConnection inside an HTTPConnection.
        http_connection = HTTPConnection(None, self._proxy_connection)  # type: ignore
        # Read and parse the CONNECT response.
        resp = await http_connection.write_request_read_response(req)
        # We are unable to call release or close and thus also read on http_connection (because we don't pass a Connector),
        # meaning that we are that we are unable read the body on the response message.
        # However, a CONNECT response should not have any Content-Length/Transfer-Encoding header and no body.
        # Thus we don't need to read the response body and the response is finished with just the headers.
        # So _proxy_connection is ready to perform a SSL/TLS handshake directly after receiving a 200 on the CONNECT request.
        # Reference: https://www.ietf.org/archive/id/draft-ietf-httpbis-semantics-19.txt
        # We must close resp however, or __del__ will scream at us.
        # We close resp by setting _closed to True and let the GC know we're done with resp.
        resp._closed = True
        # Did the proxy accept our request?
        if not resp.ok:
            # No, let's throw an error.
            raise ProxyError(resp.status, resp.reason)
        del resp
        # Setup TLS in the tunnel.
        # We might still get errors performing the handshake.
        try:
            self._stream = SSLStream(
                self._proxy_connection._stream,
                self.ssl_context,
                server_hostname=self.host,
                https_compatible=True,
            )
            await self._stream.do_handshake()
        except BrokenResourceError as e:
            cause = e.__cause__
            if isinstance(cause, ssl.SSLCertVerificationError):
                raise ConnectionSSLError(
                    cause.library,
                    cause.reason,
                    f"certificate verify failed: {cause.verify_message}",
                ) from e
            elif isinstance(cause, trio.MultiError):
                _cause: ConnectionRefusedError = cause.exceptions[0]
                # Try to map errno to a Winsock2.h error if possible.
                _cause.strerror = (
                    winsock2strerror(_cause.errno)
                    if "Unknown error" in _cause.strerror
                    else _cause.strerror
                )
                cause = _cause
            else:
                cause = cause if e.__cause__ else e
            raise ProxyConnectionError(self.host, self.port, cause) from e

    async def close(self):
        if self._closed:
            # Nothing is open, nothing to close.
            return
        elif self._stream is None:
            # Only the proxy connection is open, we have not wrapped the stream yet.
            # The proxy most likely denied our CONNECT request.
            await self._proxy_connection.close()
        else:
            # The proxy connection is open and we have wrapped the stream.
            # The user is probably done with using the proxy.
            # When we connect using tcp self._stream == self._proxy_connection._stream
            # So the second call to is a no-op, except for setting self._proxy_connection._closed to True.
            await self._stream.aclose()
            await self._proxy_connection.close()
        self._closed = True


@attr.s(slots=True, repr=True)
class Cache:
    """
    ``Cache`` represents a collection of similair connections who are identified by their ``ConnectionKeys``.
    It uses ``trio.lowlevel.ParkingLot`` to handling "waiting" for a connection to be useable.
    """

    lot: trio.lowlevel.ParkingLot = attr.field(factory=trio.lowlevel.ParkingLot)
    connections: Deque["HTTPConnection"] = attr.field(factory=deque)
    aqcuired: Set["HTTPConnection"] = attr.field(factory=set)


class HTTPConnection:
    """
    ``HTTPConnection`` is one level higher in the abstraction tree of connections.
    It uses a ``DirectConnection`` or ``ProxyConnection`` and actually implements writing and reading HTTP messages.
    It also uses ``Connector`` to cache and reuse connections.
    """

    __slots__: Tuple[str, str, str, str, str] = (
        "_connector",
        "_conn",
        "_max_bytes",
        "_closed",
        "_released",
    )

    def __init__(
        self,
        connector: "Connector",
        conn: Union[DirectConnection, ProxyConnection],
        max_bytes: int = 4096,
    ):
        self._connector = connector
        self._conn = conn
        self._max_bytes = max_bytes
        # Connection MUST NOT be closed.
        assert self._conn.closed in (None, False)
        self._closed = False
        self._released = False

    @property
    def key(self):
        return self._conn.key

    @property
    def max_bytes(self):
        return self._max_bytes

    @property
    def closed(self):
        return self._closed or self._conn.closed

    @property
    def released(self):
        return self._released

    def _decode_chunk_size(self, chunk_size: Union[bytes, bytearray]) -> int:
        try:
            return int(chunk_size, 16)
        except ValueError as e:
            raise MalformedResponse("Chunked response is malformed") from e

    async def write_request_read_response(
        self, request: bytes, cookie_jar: Optional[AbstractCookieJar] = None
    ) -> Response:
        # Connection MUST be open.
        assert self._conn.closed is False, "This connection is closed"
        # "Acquire" this connection by setting _released to False, marking it as being able to be released back.
        # We could also put this in _connector.acquire, because _connector governs us basically.
        # It's a little odd that we decide if we're acquired/released or not.
        self._released = False
        # Inspiration for this concurrent reading and writing:
        # https://trio.readthedocs.io/en/stable/tutorial.html?highlight=read#flow-control-in-our-echo-client-and-server
        buf = ReceiveBuffer()
        status_line_and_headers: bytearray = None  # type: ignore

        async def writer():
            await self._conn.send_all(request)

        async def reader():
            nonlocal buf, status_line_and_headers
            while status_line_and_headers is None:  # type: ignore
                data = await self._conn.recv(self._max_bytes)  # type: ignore
                if data == b"":
                    # TODO: raise proper error
                    raise EOFError("conn closed")
                buf += data
                status_line_and_headers = buf.read()

        # Block until we have atleast read until \r\n\r\n or we timeout.
        async with trio.open_nursery() as nursery:
            nursery.start_soon(writer)
            nursery.start_soon(reader)

        # already_received_body is only a naming convention,
        # if we close buf (i.e. delete the bytearray),
        # already_received_body shall also be deleted because the bytearray is immutable and thus a reference.
        # We don't copy the bytearray here because we can stil append data to it.
        # In a later stadium (i.e. setting the body on the Response object) we can still copy it.
        assert status_line_and_headers is not None
        already_received_body = buf._buf
        status_line, headers = status_line_and_headers.split(b"\r\n", maxsplit=1)

        async def read_callback():
            # Have we already read the body?
            # Either because resp.content_length == len(already_received_body) or because resp.read was already called.
            if resp.body is not None:
                # We have, release ourselves and return the body.
                # Because release is noop if _release is True we can just call it.
                self.release()  # type: ignore
                return resp.body
            # We haven't, let's read the body.
            nonlocal buf, already_received_body
            # Is the body chunked?
            if resp.chunked:
                # Yes, read each chunk and the trailer-part (if any).
                # We can still use buf, there might already be a part of a chunk in there.
                # But since each chunk is terminated by CRLF we set the terminator to CRLF instead of CRLFCRLF.
                # body is the actual data we're sent.
                # Reference: https://datatracker.ietf.org/doc/html/rfc7230#section-4.1
                buf.terminator = b"\r\n"
                body = bytearray()
                while True:
                    # Do we (already) have a "chunk-size\r\n..." segment in buf?
                    raw_chunk_size = buf.read()
                    if raw_chunk_size is None:
                        # No, let's read some data.
                        data = await self._conn.recv(self._max_bytes)
                        if data == b"":
                            # TODO: raise proper error
                            raise EOFError("conn closed")
                        buf += data
                        continue
                    # Yes, decode the bytes because they are in HEXDIG.
                    chunk_size = self._decode_chunk_size(raw_chunk_size)
                    # Have we reached the last-chunk?
                    if chunk_size == 0:
                        # Yes, do we have trailers?
                        if resp.trailers is None:
                            # No, since we set the terminator to CRLF there is still another CRLF left to be read.
                            # Do we have that CRLF in the buffer already?
                            while buf.read() is None:
                                data = await self._conn.recv(self._max_bytes)
                                if data == b"":
                                    # TODO: raise proper error
                                    raise EOFError("conn closed")
                                buf += data
                            break
                        # Yes, now we have something similair to parsing headers.
                        # We set the terminator back to CRLFCRLF and recv until we have read until it.
                        buf.terminator = b"\r\n\r\n"
                        while True:
                            raw_trailers = buf.read()
                            if raw_trailers is None:
                                data = await self._conn.recv(self._max_bytes)
                                if data == b"":
                                    # TODO: raise proper error
                                    raise EOFError("conn closed")
                                buf += data
                                continue
                            break
                        # Parse the trailers into a CIMultiDict.
                        trailers = resp._parse_headers(raw_trailers)
                        # Did we get any cookies in the trailers?
                        if trailers.get("Set-Cookie", None) is not None:
                            # Yes, add them to the cookie attribute.
                            resp._parse_cookies(trailers)
                        # Add the trailers to the headers as per RFC7230.
                        # RFC7230 also says to:
                        # - Remove "chunked" from Transfer-Encoding
                        # - Remove Trailer from existing header fields
                        # But we won't do that for debugging purposes.
                        resp._headers.extend(trailers)
                        break
                    # No, let's prepare how much we need to read.
                    # Since we might have "overread" chunk_size we need to subtract what we already len(buf).
                    # We also add CRLF because buf's terminator is CRLF.
                    # This might lead to some, for lack of a better word, unusual situations where we recv_exactly(2), because chunk_size == len(buf).
                    # Aka, the next chunk is already exactly in the buffer but we cannot read it because we read until CRLF.
                    # IDEA:
                    # If we would want to decrease the number of reads,
                    # perhaps we could add max_bytes to size_to_read to already read a next chunk from the socket?
                    # This could however, lead to timeouts if we would use recv_exactly, and too little reads if we would use recv.
                    size_to_read = (chunk_size - len(buf)) + 2
                    # Do we already have the next chunk in buf?
                    if size_to_read > 0:
                        # No, Receive the chunk plus the CRLF so that the next data read will start with "chunk-size\r\n".
                        buf += await self._conn.recv_exactly(size_to_read)
                    # Read buf until the CRLF (i.e. the chunk) and append it to the body
                    body += buf.read()  # type: ignore
                # TODO: Handle response body encodings.
                resp.body = body.decode()
            else:
                # No, read the remaining body.
                # We could also "stream" the remaining body to the user on-demand, by passing in the recv_exactly function in the Response object.
                # Then a "read" function would wrap recv_exactly making it possible for the user read the body on-demand.
                # The problem with this approach is that connections might not be reused as often as we want,
                # because we must to read one entire HTTP message from the socket before reading the next one.
                # It's impossible to read the headers and discard the body, the body will still be left in some buffer somewhere.
                to_receive_still = resp.content_length - len(already_received_body)
                already_received_body += await self._conn.recv_exactly(to_receive_still)
                # TODO: Handle response body encodings.
                resp.body = already_received_body.decode()
            resp.content_length = len(resp.body)
            # Release ourselves back to _connector.
            self.release()
            return resp.body

        async def close_callback():
            # User has already called resp.read, so the connection is already released back.
            if resp.body is not None and self._released:
                return
            # The following implementation loosely resembles Go's.
            # Can we do something cheap to save this connection to be reused?
            # Is the content-length small enough (less than 2KiB) to "quickly" read?
            to_receive_still = resp.content_length - len(already_received_body)
            if to_receive_still <= 2048:
                await self._conn.recv_exactly(to_receive_still)
                return self.release()
            # Nothing we can do to save this connection really, the body is too big to read without blocking for some time.
            # So we just close the underlying connection and tell connector that this connection is not reusable.
            return await self.close()

        resp = Response(status_line, headers, read_callback, close_callback, cookie_jar)  # type: ignore
        # We cheat a little bit, we handle the edge case where we already have read all of the response body.
        # This makes resp.read idempotent.
        # And it helps with deciding if we can reuse this connection if we are redirected.
        if not resp.chunked and resp.content_length == len(already_received_body):
            # TODO: Handle response body encodings.
            resp.body = already_received_body.decode()
        return resp

    def release(self):
        # We cannot release twice, this will cause an error in _connector.
        if self._released:
            return
        self._connector.release(self._conn.key, self)
        self._released = True

    async def close(self) -> None:
        # We cannot close the connection if we have already released it back to _connector.
        # We could in theory close the underlying _conn and still mark the connection as closed but the user than should have just called close to begin with.
        # So a user should call release or close but not both.
        if self._closed or self._released:
            return
        self._closed = True
        await self._conn.close()
        return self._connector.release_not_reusable(self._conn.key, self)

    # TODO:
    # Dunder methods, __repr__, __del__, __aenter__ and __aexit__.
    # Although the latter two will probably not really be used much.


class Connector:
    """
    ``Connector`` handles the distribution and caching of ``HTTPConnections``.
    It is similair to a queue where items are taken from an object and after use are put back.
    """

    __slots__: Tuple[str, str, str, str, str, str] = (
        "_limit",
        "_limit_per_connection",
        "_closed",
        "_wait_queue",
        "_cache",
        "_acquired",
    )

    def __init__(
        self, *, limit: int = 100, limit_per_similair_connection: int = 0
    ) -> None:
        self._limit = limit
        self._limit_per_connection = limit_per_similair_connection
        self._closed = False
        self._wait_queue = trio.lowlevel.ParkingLot()
        self._cache: Dict[ConnectionKey, Cache] = dict()
        self._acquired: Set[HTTPConnection] = set()

    @property
    def limit(self):
        return self._limit

    @property
    def limit_per_connection(self):
        return self._limit_per_connection

    @property
    def closed(self):
        return self._closed

    def _available_connections(self, cached: Union[Cache, None]) -> int:
        # Is our limit == 0, aka we don't have a limit.
        if not self._limit:
            # Yes, we can always create a connection.
            return 1
        # No, calculate how many connections we have left.
        available = self._limit - len(self._acquired)
        # Are we using a limit per configuration?
        if self._limit_per_connection:
            # Yes, calculate how many connections for the current configuration we have left.
            # Do we already have a connection with this configuration?
            if cached is None:
                # No, so we have self._limit_per_connection connection's left.
                return self._limit_per_connection
            available = self._limit_per_connection - len(cached.aqcuired)
        return available

    def _create_connection(
        self,
        host: Any,
        port: Any,
        ssl_context: ssl.SSLContext,
        timeout: TimeoutLike,
        proxy_url: Union[ProxyLike, None],
    ) -> Union[DirectConnection, ProxyConnection]:
        if proxy_url is not None:
            return ProxyConnection(host, port, proxy_url, ssl_context, timeout)
        return DirectConnection(host, port, ssl_context, timeout)

    async def acquire(
        self,
        host: Any,
        port: Any,
        ssl_context: ssl.SSLContext,
        timeout: TimeoutLike,
        proxy_url: Union[ProxyLike, None],
    ):
        key = ConnectionKey(host, port, ssl_context.verify_mode == ssl.CERT_NONE)
        # Do we already have a connection with an identical configuration in the cache?
        cached = self._cache.get(key, None)  # type: ignore
        # Are we above the limit of concurrent connections?
        if self._available_connections(cached) < 1:
            # Yes, we now need to wait for a connection to be released.
            # So, have we given out a connection already with a identical configuration?
            if cached is not None:
                # Yes we have.
                await cached.lot.park()
            else:
                # No we have not.
                await self._wait_queue.park()
        # We're not above the limit of concurrent connections, check if we can use a cached connection or not.
        if cached is not None:
            if self._closed:
                raise RuntimeError("Connector closed")
            conn = None
            # Is our cache actually filled with a usable connection?
            if len(cached.connections) < 1:
                # No, there are connections with identical configurations but they are all in use, create a new one.
                raw_conn = self._create_connection(
                    host, port, ssl_context, timeout, proxy_url
                )
                conn = HTTPConnection(self, raw_conn)
            else:
                # Yes, there is a ready-to-use connection avaible in our cache.
                conn = cached.connections.popleft()
            assert conn is not None
            # If we were to set _released on conn to False in Connector, we would do it here.
            #
            # Notify that we are using this connection.
            cached.aqcuired.add(conn)
            self._acquired.add(conn)
            return conn
        if self._closed:
            raise RuntimeError("Connector closed")
        # We do not have any connections with identical configurations cached, let's create an index in the cache.
        raw_conn = self._create_connection(host, port, ssl_context, timeout, proxy_url)
        conn = HTTPConnection(self, raw_conn)
        # Create an index with the ConnectionKey.
        cached = self._cache[key] = Cache()
        # Notify that we are using this connection.
        cached.aqcuired.add(conn)
        self._acquired.add(conn)
        return conn

    def release(self, key: ConnectionKey, connection: HTTPConnection):
        """Put a connection back, marking it as being able to be reused by another user."""
        if self._closed:
            raise RuntimeError("Connector closed")
        cached = self._cache.get(key)  # type: ignore
        assert cached is not None
        # Append the connection back to the cache, this means it's ready to be used again.
        cached.connections.append(connection)
        # Notify that we're done with using this connection.
        self._acquired.remove(connection)
        cached.aqcuired.remove(connection)
        # Do we have any waiters for our connection?
        if len(cached.lot) > 0:
            # Yes, let's notify one waiter that they may use this connection.
            cached.lot.unpark()
        else:
            # No, but we might have a waiter that's waiting to use a connection with different configuration.
            # Since we free up one connection, one new connection should still be able to be made or reused.
            self._wait_queue.unpark()

    def release_not_reusable(
        self, key: ConnectionKey, connection: HTTPConnection
    ) -> None:
        """Remove a connection without it being able to be reused by another user."""
        if self._closed:
            raise RuntimeError("Connector closed")
        cached = self._cache.get(key)  # type: ignore
        assert cached is not None
        cached.aqcuired.remove(connection)
        self._acquired.remove(connection)
        # Do we have any waiters for our connection?
        if len(cached.lot) > 0:
            # Yes, let's notify one waiter that they may use this connection.
            cached.lot.unpark()
        else:
            # No, but we might have a waiter that's waiting to use a connection with different configuration.
            # Since we free up one connection, one new connection should still be able to be made or reused.
            self._wait_queue.unpark()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # First close all connections.
        async with trio.open_nursery() as nursery:
            for _, cache in self._cache.items():
                for conn in cache.aqcuired.union(cache.connections):
                    # conn.close calls release_not_reusable which will fail because _closed is set to True.
                    # So we actually close the underlying DirectConnection | ProxyConnection
                    # And just set the connection to closed.
                    nursery.start_soon(conn._conn.close)
                    conn._closed = True
                # Now we will probably get RuntimeErrors from waiters.
                cache.lot.unpark_all()
        # If there are waiting in _wait_queue we will get RuntimeErrors.
        self._wait_queue.unpark_all()
        self._cache.clear()
        self._acquired.clear()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} limit={self._limit} limit_per_similair_connection={self._limit_per_connection} "
            f"len(acquired)={len(self._acquired)} len(cache)={len(self._cache)}>"
        )

    def __del__(self, _warnings: Any = warnings) -> None:
        if not self._closed:
            _warnings.warn(
                f"Unclosed connector {self!r}",
                ResourceWarning,
                source=self,
            )
            raise UnclosedConnector

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()
