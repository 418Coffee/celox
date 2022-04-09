import warnings
from http.cookies import CookieError, SimpleCookie
from types import TracebackType
from typing import Any, Coroutine, Dict, List, Optional, Tuple, Type, Union

import yarl
from multidict import CIMultiDict, CIMultiDictProxy

from .abc import AbstractCookieJar
from .exceptions import MalformedResponse, UnclosedResponse
from .util import reify

__all__ = ("Response",)


class Response:
    """
    ``Response`` represents a HTTP response message.
    """

    __slots__: Tuple[
        str, str, str, str, str, str, str, str, str, str, str, str, str, str
    ] = (
        "_url",
        "_headers",
        "_history",
        "_closed",
        "_read_cb",
        "_close_cb",
        "_cookie_jar",
        "_cache",  # used for reify
        "status",
        "reason",
        "content_length",
        "cookies",
        "trailers",
        "body",
    )

    def __init__(
        self,
        status_line: Union[bytes, bytearray],
        headers: Union[bytes, bytearray],
        read_cb: Coroutine[Any, Any, Union[str, None]],
        _close_cb: Coroutine[Any, Any, None],
        cookie_jar: Optional[AbstractCookieJar] = None,
    ):
        self._url = yarl.URL()
        self._headers: CIMultiDict[str] = CIMultiDict()
        self._history: List[Response] = []
        self._closed = False
        self._read_cb = read_cb
        self._close_cb = _close_cb
        self._cookie_jar = cookie_jar
        self._cache: Dict[str, Any] = dict()
        self.content_length = -1
        self.cookies: SimpleCookie[str] = SimpleCookie()
        self.status, self.reason = self._parse_status_line(status_line)
        self._headers = self._parse_headers(headers)
        self.content_length = int(self._headers.get("Content-Length", 0))
        self.trailers = self._headers.get("Trailer")
        self._parse_cookies(self._headers)
        self.body: Union[str, None] = None

    @property
    def url(self) -> yarl.URL:
        """The last requested url, basically the url that was requested or the redirect location."""
        return self._url

    @property
    def ok(self) -> bool:
        """Check if the status code is <= 200 and < 400."""
        return 200 <= self.status < 400

    @property  # @reify?
    def chunked(self) -> bool:
        """Check if the response body is chunked."""
        return self._headers.get("Transfer-Encoding", "") == "chunked"  # type: ignore

    @property
    def closed(self) -> bool:
        """Has the response been closed. Particularly, has ``close`` or ``read`` been called."""
        return self._closed

    @property
    def history(self) -> List["Response"]:
        """A list of all redirects that let to this response."""
        return self._history

    @reify
    def headers(self) -> CIMultiDictProxy[str]:
        """The HTTP response headers."""
        return CIMultiDictProxy(self._headers)

    def _parse_status_line(
        self, status_line: Union[bytes, bytearray]
    ) -> Tuple[int, str]:
        if self._is_line_obviously_invalid_request_line(status_line):
            raise MalformedResponse("HTTP status line is malformed")
        status_code_and_reason_phrase = status_line.split(b" ", maxsplit=1)[1]
        status_code, reason_phrase = status_code_and_reason_phrase.split(
            b" ", maxsplit=1
        )
        return int(status_code.decode()), reason_phrase.decode()

    def _parse_headers(self, headers: Union[bytes, bytearray]) -> CIMultiDict[str]:
        hdrs: CIMultiDict[str] = CIMultiDict()
        lines = headers.split(b"\r\n")
        for header_line in lines:
            if self._is_line_obviously_invalid_request_line(header_line):
                raise MalformedResponse("HTTP header line is malformed")
            k, v = header_line.split(b": ", maxsplit=1)
            hdrs.add(k.decode(), v.decode())
        return hdrs

    def _parse_cookies(
        self, headers: Union[CIMultiDictProxy[str], CIMultiDict[str]]
    ) -> None:
        for set_cookie in headers.getall("Set-Cookie", ()):
            try:
                self.cookies.load(set_cookie)
                if self._cookie_jar is not None:
                    self._cookie_jar.update_cookies(self.cookies)
            except CookieError as e:
                raise MalformedResponse("Unable to load response cookie") from e

    def _is_line_obviously_invalid_request_line(
        self, data: Union[bytes, bytearray]
    ) -> bool:
        try:
            # HTTP header line must not contain non-printable characters
            # and should not start with a space
            return data[0] < 0x21
        except IndexError:
            return False

    async def read(self) -> str:
        """
        Read the response body and free up underlying resources if possible.
        Users should always call ``close`` OR ``read`` to release a connection back to the connector.

        The context manager takes care of closing the response if it's used.
        """
        if not self._closed:
            # We can "close" the response here because _read_cb already released the connection back to the Connector.
            self._closed = True
        return await self._read_cb()  # type: ignore

    async def close(self) -> None:
        """
        Close the response and free up underlying resources if possible.
        Users should always call ``close`` OR ``read`` to release a connection back to the connector.

        The context manager takes care of closing the response if it's used.
        """
        if self._closed:
            return
        self._closed = True
        return await self._close_cb()  # type: ignore

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} [{self.status} {self.reason}]>"

    def __del__(self, _warnings: Any = warnings) -> None:
        if not self._closed:
            _warnings.warn(
                f"Unclosed response {self!r}",
                ResourceWarning,
                source=self,
            )
            raise UnclosedResponse

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        return await self.close()
