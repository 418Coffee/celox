from .util import FrozenOrderedDict
from .timeout import Timeout
from . import __version__

USER_AGENT: str = f"celer/{__version__}"

DEFAULT_HEADERS: FrozenOrderedDict = FrozenOrderedDict({
    "Host": "",
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
})

DEFAULT_TIMEOUT: Timeout = Timeout(total=5)