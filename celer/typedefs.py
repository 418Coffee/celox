from ssl import SSLContext, SSLObject
from typing import Dict, OrderedDict, Union
from yarl import URL
from trio import SSLStream, SocketStream
from .timeout import Timeout

StrOrURL = Union[str, URL]
CookieJar = ...
ClientTimeout = ...

TimeoutLike = Union[Timeout, float, int]
DictLike = Union[OrderedDict, dict, Dict]
ProxyLike = StrOrURL
SSLLike = Union[SSLContext, bool]
StreamLike = Union[SSLStream, SocketStream]