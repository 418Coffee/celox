import dataclasses
from typing import Optional


@dataclasses.dataclass(frozen=True, repr=True)
class Timeout:
    total: Optional[float] = None
    connect: Optional[float] = None
    read: Optional[float] = None
    write: Optional[float] = None

