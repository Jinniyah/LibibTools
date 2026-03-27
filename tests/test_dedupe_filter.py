import chirp_to_libib.core as c

def test_dedupe_replaces_missing_author():
    books = [
        ("Book", "", "c1"),
        ("Book", "Author", "c2"),
    ]
    out = c.dedupe_books_by_title(books)
    assert out == [("Book", "Author", "c2")]

def test_dedupe_case_insensitive():
    books = [
        ("Book", "A", "c1"),
        ("book", "B", "c2"),
    ]
    out = c.dedupe_books_by_title(books)
    assert out == [("Book", "A", "c1")]

def test_filter_invalid_titles():
    books = [
        ("", "A", "c"),
        ("!", "A", "c"),
        ("Audiobook", "A", "c"),
        ("A", "A", "c"),
        ("Valid Title", "A", "c"),
    ]
    out = c.filter_invalid_books(books)
    assert out == [("Valid Title", "A", "c")]
