from chirp_to_libib.core import (
    dedupe_books_by_title as chirp_dedupe,
    filter_invalid_books as chirp_filter,
)

from kindle_to_libib.core import (
    dedupe_books_by_title as kindle_dedupe,
    filter_invalid_books as kindle_filter,
)

from lib import filter_invalid_books
from kindle_to_libib.core import _KINDLE_UI_GARBAGE


# ==========================
# DEDUPE TESTS
# ==========================

def test_chirp_dedupe():
    books = [
        ("Title", "Author A", "cover1"),
        ("Title", "Author B", "cover2"),
    ]
    result = chirp_dedupe(books)
    assert len(result) == 1
    assert result[0][0] == "Title"


def test_kindle_dedupe():
    books = [
        ("Title", "Author A", "cover1"),
        ("Title", "Author B", "cover2"),
    ]
    result = kindle_dedupe(books)
    assert len(result) == 1
    assert result[0][0] == "Title"


# ==========================
# FILTER TESTS
# ==========================

def test_chirp_filter():
    books = [
        ("Valid Title", "Author", "cover"),
        ("", "Author", "cover"),
        ("#", "Author", "cover"),
        ("audiobook", "Author", "cover"),
    ]
    result = chirp_filter(books)
    assert len(result) == 1
    assert result[0][0] == "Valid Title"


def test_kindle_filter():
    books = [
        ("Valid Title", "Author", "cover"),
        ("", "Author", "cover"),
        ("#", "Author", "cover"),
        ("ebook", "Author", "cover"),
        ("devices", "Author", "cover"),
    ]
    result = filter_invalid_books(books, extra_garbage=_KINDLE_UI_GARBAGE)
    assert len(result) == 1
