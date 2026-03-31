from unittest.mock import patch

from kindle_to_libib.core import (
    dedupe_books_by_title,
    filter_invalid_books,
    resolve_isbns,
)


def test_dedupe_books_by_title():
    books = [
        ("Title", "Author A", "cover1"),
        ("Title", "Author B", "cover2"),
    ]
    result = dedupe_books_by_title(books)
    assert len(result) == 1


# test_kindle.py and test_dedupe_filter.py
from lib import filter_invalid_books

_KINDLE_UI_GARBAGE = frozenset({"content", "devices", "preferences", "privacy settings"})

def test_filter_invalid_books():
    books = [
        ("Valid Title", "Author", "cover"),
        ("", "Author", "cover"),
        ("#", "Author", "cover"),
        ("ebook", "Author", "cover"),
        ("devices", "Author", "cover"),
    ]
    result = filter_invalid_books(books, extra_garbage=_KINDLE_UI_GARBAGE)
    assert len(result) == 1


@patch("kindle_to_libib.core.get_isbn", return_value="9781402894626")
@patch("kindle_to_libib.core.sleep_between_requests")
def test_resolve_isbns(mock_sleep, mock_isbn):
    books = [("Title", "Author", "cover")]
    result = resolve_isbns(books)
    assert result[0][2] == "9781402894626"
    mock_isbn.assert_called_once()
