from typing import Final

from . import __version__
from .timeout import Timeout
from .util import FrozenOrderedDict

USER_AGENT: Final[str] = f"celox/{__version__}"

DEFAULT_HEADERS: FrozenOrderedDict = FrozenOrderedDict(
    {
        "Host": "",
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }
)

DEFAULT_TIMEOUT: Final[Timeout] = Timeout(total=5)
