from multidict import MultiDict, MultiDictProxy

from .timeout import Timeout
from . import __version__

USER_AGENT: str = f"celer/{__version__}"

DEFAULT_HEADERS: MultiDictProxy = MultiDictProxy(MultiDict({
    "User-Agent": USER_AGENT,
}))

DEFAULT_TIMEOUT: Timeout = Timeout(total=5)