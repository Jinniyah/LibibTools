import pytest
from unittest.mock import patch

from chirp_to_libib.core import (
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


def test_filter_invalid_books():
    books = [
        ("Valid Title", "Author", "cover"),
        ("", "Author", "cover"),
        ("#", "Author", "cover"),
        ("audiobook", "Author", "cover"),
    ]
    result = filter_invalid_books(books)
    assert len(result) == 1
    assert result[0][0] == "Valid Title"


@patch("chirp_to_libib.core.get_isbn", return_value="1234567890")
@patch("chirp_to_libib.core.sleep_between_requests")
def test_resolve_isbns(mock_sleep, mock_isbn):
    books = [("Title", "Author", "cover")]
    result = resolve_isbns(books)
    assert result[0][2] == "1234567890"
    mock_isbn.assert_called_once()
