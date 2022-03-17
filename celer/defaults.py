from typing import Final
from .util import FrozenOrderedDict
from .timeout import Timeout
from . import __version__

USER_AGENT: Final[str] = f"celer/{__version__}"

DEFAULT_HEADERS: FrozenOrderedDict = FrozenOrderedDict({
    "Host": "",
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
})

DEFAULT_TIMEOUT: Final[Timeout] = Timeout(total=5)