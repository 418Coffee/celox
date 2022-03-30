import collections.abc
import functools
import re
import ssl
from typing import Any, Callable, Generic, Optional, Pattern, Protocol, Type, TypeVar, Union
import warnings

from multidict import CIMultiDict
from yarl import URL

def is_ssl(url: URL) -> bool:
    if url.port == 443 or url.scheme == "https":
        return True
    return False

def add_default_headers_non_existing(headers: CIMultiDict, key: str, value: str) -> None:
    # Is key already in dict?
    if key in headers:
        # Yes, don't set it.
        return
    # No, set it.
    headers[key] = value

def create_ssl_context(ssl_skip_verify: bool = False) -> ssl.SSLContext:
    ssl_context =  ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # SSLv2 is easily broken and is considered harmful and dangerous.
    ssl_context.options |= ssl.OP_NO_SSLv2
    # SSLv3 has several problems and is now dangerous.
    ssl_context.options |= ssl.OP_NO_SSLv3
    try:
        # Disable compression to prevent CRIME attacks for OpenSSL 1.0+.
        ssl_context.options |= ssl.OP_NO_COMPRESSION
    except AttributeError as attr_err:
        warnings.warn(
            f"{attr_err!s}: The Python interpreter is compiled "
            "against OpenSSL < 1.0.0. Ref: "
            "https://docs.python.org/3/library/ssl.html"
            "#ssl.OP_NO_COMPRESSION"
        )
    if ssl_skip_verify:
        # Don't check hostname.
        ssl_context.check_hostname = False
        # Don't verify certificates.
        ssl_context.verify_mode = ssl.CERT_NONE
        # Set CA and ROOT certificates.
    ssl_context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    return ssl_context

class frozendict(collections.abc.Mapping):
    """
    An immutable wrapper around dictionaries that implements the complete :py:class:`collections.Mapping`
    interface. It can be used as a drop-in replacement for dictionaries where immutability is desired.
    """

    dict_cls = dict

    def __init__(self, *args, **kwargs):
        self._dict = self.dict_cls(*args, **kwargs)
        self._hash = None

    def __getitem__(self, key):
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def copy(self, **add_or_replace):
        return self.__class__(self, **add_or_replace)

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self._dict)

    def __hash__(self):
        if self._hash is None:
            h = 0
            for key, value in self._dict.items():
                h ^= hash((key, value))
            self._hash = h
        return self._hash

class FrozenOrderedDict(frozendict):
    """
    A frozendict subclass that maintains key order
    """

    dict_cls = collections.OrderedDict

_T = TypeVar("_T")


class _TSelf(Protocol, Generic[_T]):
    _cache: "dict[str, _T]"

class reify(Generic[_T]):
    """Use as a class method decorator.

    It operates almost exactly like
    the Python `@property` decorator, but it puts the result of the
    method it decorates into the instance dict after the first call,
    effectively replacing the function it decorates with an instance
    variable.  It is, in Python parlance, a data descriptor.
    """

    def __init__(self, wrapped: Callable[..., _T]) -> None:
        self.wrapped = wrapped
        self.__doc__ = wrapped.__doc__
        self.name = wrapped.__name__

    def __get__(self, inst: _TSelf[_T], owner: Optional[Type[Any]] = None) -> _T:
        try:
            try:
                return inst._cache[self.name]
            except KeyError:
                val = self.wrapped(inst)
                inst._cache[self.name] = val
                return val
        except AttributeError:
            if inst is None:
                return self
            raise

    def __set__(self, inst: _TSelf[_T], value: _T) -> None:
        raise AttributeError("reified property is read-only")

_ipv4_pattern = (
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)
_ipv6_pattern = (
    r"^(?:(?:(?:[A-F0-9]{1,4}:){6}|(?=(?:[A-F0-9]{0,4}:){0,6}"
    r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}$)(([0-9A-F]{1,4}:){0,5}|:)"
    r"((:[0-9A-F]{1,4}){1,5}:|:)|::(?:[A-F0-9]{1,4}:){5})"
    r"(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])|(?:[A-F0-9]{1,4}:){7}"
    r"[A-F0-9]{1,4}|(?=(?:[A-F0-9]{0,4}:){0,7}[A-F0-9]{0,4}$)"
    r"(([0-9A-F]{1,4}:){1,7}|:)((:[0-9A-F]{1,4}){1,7}|:)|(?:[A-F0-9]{1,4}:){7}"
    r":|:(:[A-F0-9]{1,4}){7})$"
)
_ipv4_regex = re.compile(_ipv4_pattern)
_ipv6_regex = re.compile(_ipv6_pattern, flags=re.IGNORECASE)
_ipv4_regexb = re.compile(_ipv4_pattern.encode("ascii"))
_ipv6_regexb = re.compile(_ipv6_pattern.encode("ascii"), flags=re.IGNORECASE)


def _is_ip_address(
    regex: Pattern[str], regexb: Pattern[bytes], host: Optional[Union[str, bytes]]
) -> bool:
    if host is None:
        return False
    if isinstance(host, str):
        return bool(regex.match(host))
    elif isinstance(host, (bytes, bytearray, memoryview)):
        return bool(regexb.match(host))
    else:
        raise TypeError(f"{host} [{type(host)}] is not a str or bytes")


is_ipv4_address = functools.partial(_is_ip_address, _ipv4_regex, _ipv4_regexb)
is_ipv6_address = functools.partial(_is_ip_address, _ipv6_regex, _ipv6_regexb)


def is_ip_address(host: Optional[Union[str, bytes, bytearray, memoryview]]) -> bool:
    return is_ipv4_address(host) or is_ipv6_address(host)