from collections import OrderedDict
from http.cookies import BaseCookie, Morsel
from ssl import SSLContext
from typing import Any, Callable, Iterable, Mapping, Union

from multidict import CIMultiDict, CIMultiDictProxy
from trio import SocketStream, SSLStream
from yarl import URL

from .timeout import Timeout
from .util import FrozenOrderedDict, frozendict

# URL
StrOrURL = Union[str, URL]

# Cookies
CookieItem = Union[str, "Morsel[str]"]
ClearCookiePredicate = Callable[["Morsel[str]"], bool]
LooseCookiesMappings = Mapping[str, Union[str, "BaseCookie[str]", "Morsel[Any]"]]
LooseCookiesIterables = Iterable['tuple[str, Union[str, "BaseCookie[str]", "Morsel[Any]"]]']

# Likes
TimeoutLike = Union[Timeout, float, int]
DictLike = Union[OrderedDict, dict, frozendict, FrozenOrderedDict, CIMultiDict, CIMultiDictProxy]
ProxyLike = StrOrURL
SSLLike = Union[SSLContext, bool]
StreamLike = Union[SSLStream, SocketStream]
CookieLike = Union[LooseCookiesMappings, LooseCookiesIterables, "BaseCookie[str]"]

