from abc import ABCMeta, abstractmethod
from http.cookies import BaseCookie, Morsel
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sized

import yarl

from .typedefs import ClearCookiePredicate, CookieLike

if TYPE_CHECKING:
    IterableBase = Iterable[Morsel[str]]
else:
    IterableBase = Iterable

__all__ = ("AbstractCookieJar", "JsonEncoder")


class AbstractCookieJar(Sized, IterableBase, metaclass=ABCMeta):
    """Abstract Cookie Jar"""

    __slots__ = ()

    @abstractmethod
    def clear(self, predicate: Optional[ClearCookiePredicate] = None) -> None:
        """Clear all cookies if no predicate is passed."""

    @abstractmethod
    def clear_domain(self, domain: str) -> None:
        """Clear all cookies for domain and all subdomains."""

    @abstractmethod
    def update_cookies(
        self, cookies: CookieLike, response_url: yarl.URL = yarl.URL()
    ) -> None:
        """Update cookies."""

    @abstractmethod
    def filter_cookies(self, request_url: yarl.URL) -> "BaseCookie[str]":
        """Return the jar's cookies filtered by their attributes."""


class JsonEncoder(metaclass=ABCMeta):
    """Abstract JSON Encoder"""

    __slots__ = ()

    @abstractmethod
    def dumps(self, obj: Any, *args, **kwargs) -> str:
        """Serialize obj to a JSON formatted str."""
        pass
