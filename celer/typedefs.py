from abc import ABC, abstractmethod
from collections import OrderedDict
from ssl import SSLContext
from typing import Any, Union

from multidict import CIMultiDict, CIMultiDictProxy
from trio import SocketStream, SSLStream
from yarl import URL

from .timeout import Timeout
from .util import FrozenOrderedDict, frozendict

StrOrURL = Union[str, URL]
# TODO:
# This should get it's own class
CookieJar = Any

TimeoutLike = Union[Timeout, float, int]
DictLike = Union[OrderedDict, dict, frozendict, FrozenOrderedDict, CIMultiDict, CIMultiDictProxy]
ProxyLike = StrOrURL
SSLLike = Union[SSLContext, bool]
StreamLike = Union[SSLStream, SocketStream]

class JsonEncoder(ABC):
    
    @abstractmethod
    def dumps(self) -> str:
        pass
