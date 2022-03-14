from ssl import SSLContext, SSLObject
from typing import Dict, OrderedDict, Union
from yarl import URL
from trio import SSLStream, SocketStream

StrOrURL = Union[str, URL]
ClientTimeout = ...
Timeout = ...
CookieJar = ...

DictLike = Union[OrderedDict, dict, Dict]
ProxyLike = StrOrURL
SSLLike = Union[SSLContext, bool]
StreamLike = Union[SSLStream, SocketStream]