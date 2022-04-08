from http.cookies import BaseCookie, Morsel
from ssl import SSLContext
from typing import Any, Callable, Dict, Iterable, Mapping, OrderedDict, Tuple, Union

import yarl
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from trio import SocketStream, SSLStream

from .timeout import Timeout

# URL
StrOrURL = Union[str, yarl.URL]

# Cookies
CookieItem = Union[str, "Morsel[str]"]
ClearCookiePredicate = Callable[["Morsel[str]"], bool]
LooseCookiesMappings = Mapping[str, Union[str, "BaseCookie[str]", "Morsel[Any]"]]
LooseCookiesIterables = Iterable[
    'Tuple[str, Union[str, "BaseCookie[str]", "Morsel[Any]"]]'
]

# Likes
TimeoutLike = Union[Timeout, float, int]
DictLike = Union[
    OrderedDict,
    Dict,
    CIMultiDict[str],
    CIMultiDictProxy[str],
    MultiDict[str],
    MultiDictProxy[str],
]
ProxyLike = StrOrURL
SSLLike = Union[SSLContext, bool]
StreamLike = Union[SSLStream, SocketStream]
CookieLike = Union[LooseCookiesMappings, LooseCookiesIterables, "BaseCookie[str]"]
