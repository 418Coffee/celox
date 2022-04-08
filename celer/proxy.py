import base64
from typing import Any, Optional

import yarl

from .exceptions import InvalidProxy
from .typedefs import ProxyLike
from .util import SCHEMES


def _connect_request(
    host: Any, port: Any, *, user: Optional[Any] = None, password: Optional[Any] = None
) -> bytes:
    request = f"CONNECT {host}:{port} HTTP/1.1\r\n" f"Host: {host}:{port}\r\n"
    if not user and not password:
        request += "\r\n"
        return request.encode()
    auth = base64.b64encode(f"{user}:{password}".encode("ascii"))
    request += f"Proxy-Authorization: basic {auth.decode('ascii')}\r\n"
    return request.encode("ascii")


def _prepare_proxy(proxy: ProxyLike) -> yarl.URL:
    if isinstance(proxy, yarl.URL):
        if proxy.scheme not in SCHEMES:
            raise InvalidProxy(proxy)
        return proxy
    try:
        proxy = yarl.URL(proxy)
        if proxy.scheme not in SCHEMES:
            raise InvalidProxy(proxy)
        return proxy
    except (ValueError, TypeError) as e:
        raise InvalidProxy(proxy) from e
