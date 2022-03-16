from ssl import SSLContext, SSLObject
from typing import Dict, OrderedDict, Union
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL
from trio import SSLStream, SocketStream

from .util import FrozenOrderedDict, frozendict
from .timeout import Timeout

StrOrURL = Union[str, URL]
CookieJar = ...
ClientTimeout = ...

TimeoutLike = Union[Timeout, float, int]
DictLike = Union[OrderedDict, dict, frozendict, FrozenOrderedDict, CIMultiDict, CIMultiDictProxy]
ProxyLike = StrOrURL
SSLLike = Union[SSLContext, bool]
StreamLike = Union[SSLStream, SocketStream]