from typing import Any, final
from trio import TooSlowError

class ClientError(Exception):
    """Base class for all client errors"""
    __slots__: "tuple[str]" = ()

class ConnectionError(Exception):
    """Base class for all connection errors"""
    __slots__: "tuple[str]" = ()

@final
class UnclosedClient(ClientError, RuntimeError):
    """A client was not closed"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "Unclosed client"

@final
class UnclosedConnection(ConnectionError, RuntimeError):
    """The underlying connection was not closed"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "Unclosed connection"

@final 
class UnclosedResponse(ClientError, RuntimeError):
    """The response was not closed"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "Unclosed response"

class ConnectionTimeout(ConnectionError, TooSlowError):
    """The connect attempt exceeded the given timeout"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "The server took too long to respond"

@final
class WriteTimeout(ConnectionError, TooSlowError):
    """The write attempt exceeded the given timeout"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "Writing took too long"

@final
class ReadTimeout(ConnectionError, TooSlowError):
    """The read attempt exceeded the given timeout"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "Reading took too long"

@final
class ProxyConnectionTimeout(ConnectionTimeout):
    """The proxy connect attempt exceeded the given timeout"""

    __slots__: "tuple[str]" = ()

    def __str__(self) -> str:
        return "The proxy took too long to respond"

class ProxyError(ConnectionError):
    """The proxy returned an unusual response"""

    __slots__: "tuple[str]" = (
        "status_code",
        "status",
    )

    def __init__(self, status_code: int, status: str, *args: object) -> None:
        self.status_code = status_code
        self.status = status
        super().__init__(*args)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} status_code={self.status_code} status={self.status}>"
    
    def __str__(self) -> str:
        return f"{self.status}: {self.status_code}"

class ProxyConnectionError(ConnectionError):
    """The proxy connect attempt failed"""

    __slots__: "tuple[str]" = ()



class ConnectionSSLError(ConnectionError):

    __slots__: "tuple[str]" = (
        "library",
        "reason",
        "message",
    )
    
    def __init__(self, library: str, reason: str, message: str) -> None:
        self.library = library
        self.reason = reason
        self.message = message

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} library={self.library} reason={self.reason}>"

    def __str__(self) -> str:
        return f"[{self.library}: {self.reason}]: {self.message}"


class InvalidURL(ClientError, ValueError):
    """Malformed url"""

    __slots__: "tuple[str]" = ("url",)

    def __init__(self, url: Any) -> None:
        self.url = url

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.url}>"

@final
class InvalidProxy(InvalidURL):
    """Malformed proxy"""

    __slots__: "tuple[str]" = ()

class MalformedResponse(ClientError):
    """Malformed HTTP response"""
    
    __slots__: "tuple[str]" = ("error",)

    def __init__(self, error: str) -> None:
        self.error = error

    def __str__(self) -> str:
        return self.error

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} error={self.error}>"

class MaxRedirect(ClientError):
    """Maximum amount of redirects reached"""

    __slots__: "tuple[str]" = ("last_url", "amount")

    def __init__(self, last_url: str, amount: int, *args: object) -> None:
        self.last_url = last_url
        self.amount = amount
        super().__init__(*args)

    def __str__(self, ) -> str:
        return f"Maximum amount of redirects reached: {self.amount}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} last_url={self.last_url} amount={self.amount}>"