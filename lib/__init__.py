# lib package for shared modules (Open Library, utilities, constants, etc.)

from .openlibrary import get_isbn, sleep_between_requests

__all__ = ["get_isbn", "sleep_between_requests"]
