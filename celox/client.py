import json
import ssl as stdlib_ssl
import warnings
from types import TracebackType

# For 3.7 support we could import get_args from typing_extensions
from typing import Any, Coroutine, Generator, List, Mapping, Optional, Set, Tuple, Type
from urllib.parse import urlencode

import trio
import yarl
from multidict import CIMultiDict, MultiDict
from typing_extensions import final

from .abc import AbstractCookieJar, JsonEncoder
from .connection import Connector, HTTPConnection
from .cookiejar import CookieJar
from .defaults import DEFAULT_HEADERS, DEFAULT_TIMEOUT
from .exceptions import (
    InvalidURL,
    MalformedResponse,
    MaxRedirect,
    RequestTimeout,
    UnclosedClient,
)
from .proxy import _prepare_proxy
from .request import METHODS, make_request
from .response import Response
from .timeout import Timeout
from .typedefs import (
    CookieLike,
    DictInstances,
    DictLike,
    ProxyLike,
    SSLLike,
    StrOrURL,
    TimeoutLike,
)
from .util import SCHEMES, create_ssl_context, set_value_non_existing

__all__ = ("Client",)


@final
class Client:

    __slots__: Tuple[str, str, str, str, str, str, str, str] = (
        "_base_url",
        "_timeout",
        "_cookie_jar",
        "_ssl_context",
        "_connector",
        "_proxy",
        "_json_encoder",
        "_closed",
    )

    def __init__(
        self,
        base_url: Optional[StrOrURL] = None,
        *,
        timeout: Optional[TimeoutLike] = None,
        cookie_jar: Optional[AbstractCookieJar] = None,
        proxy: Optional[ProxyLike] = None,
        ssl: Optional[SSLLike] = None,
        json_encoder: Optional[JsonEncoder] = None,
        connector: Optional[Connector] = None,
    ):
        if base_url is None or isinstance(base_url, yarl.URL):
            self._base_url: Optional[yarl.URL] = base_url
        else:
            self._base_url = yarl.URL(base_url)
            assert (
                self._base_url.origin() == self._base_url
            ), "Only absolute URLs without path part are supported"
            if self._base_url.scheme not in SCHEMES:
                raise InvalidURL(f"Unsupported protocol {self._base_url.scheme}")

        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        elif isinstance(timeout, (int, float)):
            timeout = Timeout(total=timeout)
        self._timeout = timeout

        if cookie_jar is None:
            cookie_jar = CookieJar()
        self._cookie_jar = cookie_jar

        if proxy is not None:
            proxy = _prepare_proxy(proxy)
        self._proxy = proxy

        if ssl is None or ssl is True:
            self._ssl_context = create_ssl_context(ssl_skip_verify=False)
        elif ssl is False:
            self._ssl_context = create_ssl_context(ssl_skip_verify=True)
        else:
            assert isinstance(ssl, stdlib_ssl.SSLContext)
            self._ssl_context = ssl

        if json_encoder is None:
            json_encoder = json  # type: ignore
        assert json_encoder is not None
        self._json_encoder = json_encoder

        if connector is None:
            connector = Connector()
        self._connector = connector

        self._closed = False

    @property
    def proxy(self):
        return self._proxy

    @proxy.setter
    def proxy(self, value: ProxyLike):
        self._proxy = _prepare_proxy(value) if value is not None else None

    @property
    def closed(self):
        return self._closed

    @property
    def cookie_jar(self):
        return self._cookie_jar

    async def _request(
        self,
        method: str,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> Response:
        if self.closed:
            raise RuntimeError("Session is closed")

        if method not in METHODS:
            raise ValueError(f"{method!s} is an invalid HTTP method")

        if data is not None and json is not None:
            raise ValueError(
                "data and json parameters can not be used at the same time"
            )

        try:
            url = self._prepare_url(url)
        except (ValueError, TypeError) as e:
            raise InvalidURL(url) from e

        if params is not None:
            url = url.update_query(params)

        hdrs = self._prepare_headers(headers, url)

        if proxy is not None:
            proxy = _prepare_proxy(proxy)
        elif self._proxy is not None:
            proxy = self._proxy

        if timeout is None:
            timeout = self._timeout

        if json is not None:
            data = self._json_encoder.dumps(json)
            set_value_non_existing(hdrs, "Content-Type", "application/json")

        if isinstance(data, DictInstances):
            data = self._prepare_form(data)
            set_value_non_existing(
                hdrs, "Content-Type", "application/x-www-form-urlencoded"
            )
        elif isinstance(data, str):
            set_value_non_existing(hdrs, "Content-Type", "text/plain")
        elif isinstance(data, bytes):
            set_value_non_existing(hdrs, "Content-Type", "application/octet-stream")

        if data is not None:
            set_value_non_existing(hdrs, "Content-Length", str(len(data)))

        # Load the cookies we already have for this domain.
        all_cookies = self._cookie_jar.filter_cookies(url)
        # Did the user supply any extra cookies?
        if cookies is not None:
            # Yes, let's add them.
            tmp_cookie_jar = CookieJar()
            tmp_cookie_jar.update_cookies(cookies)
            req_cookies = tmp_cookie_jar.filter_cookies(url)
            if req_cookies:
                all_cookies.load(req_cookies)

        if all_cookies:
            hdrs.add("Cookie", all_cookies.output(header="", sep=";").strip())

        is_ssl = url.scheme == "https"

        ssl_context = self._ssl_context
        if ssl_skip_verify:
            ssl_context = create_ssl_context(ssl_skip_verify=True)

        redirects = 1
        history: List[Response] = list()
        must_acquire_new_connection = True
        conn: HTTPConnection
        resp: Response
        try:
            with trio.fail_after(self._timeout.total or self._timeout.any):
                while True:
                    # We have to put _connector.acquire in a while True loop because we must acquire a new connection if we get redirect to a different domain.
                    # Block until we're a connection is ready or we're under the conncurrent connection limit.
                    if must_acquire_new_connection:
                        conn = await self._connector.acquire(
                            url.raw_host, url.port, ssl_context, timeout, proxy
                        )
                        # Connect to the peer, this is a noop if we're already connected.
                        if is_ssl:
                            await conn._conn.connect_ssl()
                        else:
                            await conn._conn.connect_tcp()
                    assert conn is not None
                    # Create the request.
                    req = make_request(method, url, hdrs, data)
                    # Send the request and read the response.
                    resp = await conn.write_request_read_response(req, self._cookie_jar)
                    # Set the request url to the resp object, for debugging purposes we are redirected.
                    resp._url = url
                    # Are we redirected?
                    location = resp.headers.get("Location")
                    if location is not None:
                        # Yes we're redirected, but should we actually follow the redirect?
                        if not allow_redirects:
                            # No, just return the response.
                            break
                        # Yes, are we over the limit of redirects?
                        if redirects > max_redirects:
                            # We are, close the response because we won't use it again and raise an exception.
                            await resp.close()
                            raise MaxRedirect(url.human_repr(), max_redirects)
                        # We aren't, prepare url for sending again.
                        old_host = url.raw_host
                        try:
                            url = self._prepare_url(location)
                        except (ValueError, TypeError) as e:
                            raise MalformedResponse(
                                f"Invalid url for redirect: {url}"
                            ) from e
                        # Are we redirect to a different domain?
                        if old_host != url.raw_host:
                            # Yes, we can close the old response now.
                            await resp.close()
                            # The next time we iterate we will acquire a connection to the new host.
                            must_acquire_new_connection = True
                        else:
                            # No, this is perhaps the trickiest situation.
                            # We cannot call resp.close, because that would release the connection back to _connector,
                            # but we still want to be sure that the connection is reusable.
                            # But, we cheated a little bit in write_request_read_response,
                            # if we already read all the response body then resp.body will be non-nil, meaning that this connection can be reused.
                            if resp.body is not None:
                                # We set resp._closed to True otherwise __del__ will scream at use for not closing the response.
                                resp._closed = True
                                must_acquire_new_connection = False
                            else:
                                # Well, we're out of luck, there are still bytes left to be read.
                                # Best we can do now is close the response and block to acquire a new connection to perform the redirect.
                                await resp.close()
                                must_acquire_new_connection = True
                        # Check via status code what to do with our method/body.
                        if resp.status in (301, 302, 303):
                            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Redirections says we can choose if we change our method to GET.
                            # Let's do that.
                            method = "GET"
                            data = None
                            hdrs.pop("Content-Type", None)
                            hdrs.pop("Content-Length", None)
                        else:
                            # Now we're getting 307 or 308 most likely.
                            # We keep everything the same.
                            # This code block is unnecessary really.
                            pass
                        hdrs["Host"] = (
                            url.raw_host  # type: ignore
                            if url.is_default_port()
                            else f"{url.raw_host}:{url.port}"
                        )
                        # Keep track of the amount redirects and the responses.
                        redirects += 1
                        history.append(resp)
                        continue
                    break
                resp._history += history
                return resp
        except trio.TooSlowError as e:
            raise RequestTimeout() from e

    def request(
        self,
        method: str,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    def get(
        self,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method="GET",
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    def head(
        self,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method="HEAD",
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    def post(
        self,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method="POST",
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    def put(
        self,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method="PUT",
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    def patch(
        self,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method="PATCH",
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    def delete(
        self,
        url: StrOrURL,
        *,
        params: Optional[Mapping[str, str]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[DictLike] = None,
        proxy: Optional[ProxyLike] = None,
        cookies: Optional[CookieLike] = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: Optional[Timeout] = None,
        ssl_skip_verify: bool = False,
    ) -> "_RequestContextManager":
        return _RequestContextManager(
            self._request(
                method="DELETE",
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                proxy=proxy,
                cookies=cookies,
                allow_redirects=allow_redirects,
                max_redirects=max_redirects,
                timeout=timeout,
                ssl_skip_verify=ssl_skip_verify,
            )
        )

    async def close(self):
        if self._closed:
            return
        await self._connector.close()
        self._closed = True

    def _prepare_url(self, url: StrOrURL) -> yarl.URL:
        url = yarl.URL(url)
        if url.is_absolute() and url.scheme not in SCHEMES:
            raise ValueError(f"Unsupported protocol {self._base_url.scheme}")  # type: ignore
        if self._base_url is None:
            return url
        else:
            assert not url.is_absolute() and url.path.startswith("/")
            return self._base_url.join(url)

    def _prepare_headers(
        self, headers: Optional[DictLike], url: yarl.URL
    ) -> CIMultiDict[str]:
        hdrs: CIMultiDict[str] = CIMultiDict()
        if headers is not None:
            if not isinstance(headers, MultiDict):  # type: ignore
                headers = CIMultiDict(headers)
            added_names: Set[str] = set()
            for key, value in headers.items():
                if key in added_names:
                    hdrs.add(key, value)
                else:
                    hdrs[key] = value
                    added_names.add(key)
        for k, v in DEFAULT_HEADERS.items():
            if k == "Host":
                v = (
                    url.raw_host
                    if url.is_default_port()
                    else f"{url.raw_host}:{url.port}"
                )
            set_value_non_existing(hdrs, k, v)
        return hdrs

    def _prepare_form(self, form: DictLike) -> str:
        return urlencode(form, doseq=True, encoding="utf-8")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} closed={self.closed} connector={self._connector} ssl_context={self._ssl_context}>"

    def __del__(self, _warnings: Any = warnings) -> None:
        # We might error in __init__, since we set _closed last it might not be defined yet.
        # If it's not defined we know we're not open.
        if not getattr(self, "_closed", True):
            _warnings.warn(
                f"Unclosed client session {self!r}",
                ResourceWarning,
                source=self,
            )
            raise UnclosedClient

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()


class _RequestContextManager(Coroutine[Any, Any, Response]):

    __slots__ = ("_coro", "_resp")

    def __init__(self, coro: Coroutine[Any, None, Response]) -> None:
        self._coro = coro

    def send(self, arg: None) -> Any:
        return self._coro.send(arg)

    def throw(self, arg: BaseException) -> None:  # type: ignore[override]
        self._coro.throw(arg)

    def close(self) -> None:
        return self._coro.close()

    def __await__(self) -> Generator[Any, None, Response]:
        ret = self._coro.__await__()
        return ret

    def __iter__(self) -> Generator[Any, None, Response]:
        return self.__await__()

    async def __aenter__(self) -> Response:
        self._resp = await self._coro
        return self._resp

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self._resp.close()
