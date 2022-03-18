import collections
import ssl
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

class frozendict(collections.Mapping):
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
