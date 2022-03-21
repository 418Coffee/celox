from abc import ABC, abstractmethod
from http.cookies import BaseCookie, Morsel
from typing import TYPE_CHECKING, Iterable, Optional, Sized

from yarl import URL

from .typedefs import ClearCookiePredicate, CookieLike

if TYPE_CHECKING:
    IterableBase = Iterable[Morsel[str]]
else:
    IterableBase = Iterable


class AbstractCookieJar(Sized, IterableBase):
    """Abstract Cookie Jar"""

    @abstractmethod
    def clear(self, predicate: Optional[ClearCookiePredicate] = None) -> None:
        """Clear all cookies if no predicate is passed."""

    @abstractmethod
    def clear_domain(self, domain: str) -> None:
        """Clear all cookies for domain and all subdomains."""

    @abstractmethod
    def update_cookies(self, cookies: CookieLike, response_url: URL = URL()) -> None:
        """Update cookies."""

    @abstractmethod
    def filter_cookies(self, request_url: URL) -> "BaseCookie[str]":
        """Return the jar's cookies filtered by their attributes."""

class JsonEncoder(ABC):
    """Abstract JSON Encoder"""

    @abstractmethod
    def dumps(self) -> str:
        """Serialize obj to a JSON formatted str"""
        pass
