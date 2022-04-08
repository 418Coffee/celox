from math import inf
from typing import Optional, Union

import attr

_valid_types = (float, int, type(None))


@attr.s(repr=True, slots=True)
class Timeout:
    """
    ``Timeout`` is a dataclass that holds values that can apply a timeout on certain network operations and HTTP roundtrips in general.
    ``total`` is the timeout for one whole HTTP roundtrip: connecting, writing and reading.
    ``connect`` is the timeout for connecting to a peer and, if applicable, performing a SSL/TLS handshake.
    ``read`` is the timeout for one read operation on a socket.
    ``write`` is the timeout for one write operation on a socket.
    ``any`` is the default timeout used if any of the above attributes are None. (defaults to math.inf, so no timeout)
    """

    total: Optional[Union[float, int]] = attr.ib(
        default=None, validator=attr.validators.instance_of(_valid_types)
    )
    connect: Optional[Union[float, int]] = attr.ib(
        default=None, validator=attr.validators.instance_of(_valid_types)
    )
    read: Optional[Union[float, int]] = attr.ib(
        default=None, validator=attr.validators.instance_of(_valid_types)
    )
    write: Optional[Union[float, int]] = attr.ib(
        default=None, validator=attr.validators.instance_of(_valid_types)
    )
    any: Optional[Union[float, int]] = attr.ib(
        default=inf, validator=attr.validators.instance_of((float, int))
    )
