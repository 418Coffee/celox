import attr
from typing import Optional, Union

_valid_types = (float, int, type(None))

@attr.s(repr=True, slots=True)
class Timeout:
    total: Optional[Union[float, int]] = attr.ib(default=None, validator=attr.validators.instance_of(_valid_types))
    connect: Optional[Union[float, int]] = attr.ib(default=None, validator=attr.validators.instance_of(_valid_types))
    read: Optional[Union[float, int]] = attr.ib(default=None, validator=attr.validators.instance_of(_valid_types))
    write: Optional[Union[float, int]] = attr.ib(default=None, validator=attr.validators.instance_of(_valid_types))
