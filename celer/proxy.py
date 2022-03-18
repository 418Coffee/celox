from yarl import URL

from .client_exceptions import InvalidProxy
from .typedefs import ProxyLike


def _connect_request(host, port) -> bytes:
    return  f"CONNECT {host}:{port} HTTP/1.1\r\n"   \
            f"Host: {host}:{port}\r\n\r\n".encode("ascii")

def _prepare_proxy(proxy: ProxyLike) -> URL:
    if isinstance(proxy, URL):
        return proxy
    try:
        return URL(proxy)
    except ValueError as e:
        raise InvalidProxy(proxy) from e
