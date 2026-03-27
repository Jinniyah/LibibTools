import chirp_to_libib as c

def test_normalize_isbn():
    assert c._normalize_isbn("978-1-2345-6789-7") == "9781234567897"
    assert c._normalize_isbn(" 123X ") == "123X"

def test_valid_isbn13():
    assert c._valid_isbn13("9781234567897")
    assert not c._valid_isbn13("123")

def test_valid_isbn10():
    assert c._valid_isbn10("123456789X")
    assert not c._valid_isbn10("12345")

def test_best_isbn_prefers_13():
    isbns = ["123456789X", "9781234567897"]
    assert c._best_isbn(isbns) == "9781234567897"

def test_title_is_plausible():
    assert c._title_is_plausible("The Great Book", "Great Book, The")
    assert not c._title_is_plausible("Cats", "The History of Airplanes")
