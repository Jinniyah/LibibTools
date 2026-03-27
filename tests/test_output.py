import chirp_to_libib.core as c
import csv
import os

def test_write_csv(tmp_path):
    records = [
        ("Title", "Author", "9781234567897", "cover.jpg"),
    ]
    path = c.write_csv(records, tmp_path)

    assert os.path.exists(path)

    with open(path, "rb") as f:
        assert f.read(3) == b"\xef\xbb\xbf"  # UTF‑8 BOM

    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
        assert rows[0] == ["Title", "Creator", "Identifier", "Type", "Image"]
        assert rows[1][0] == "Title"

def test_write_unresolved(tmp_path):
    records = [
        ("Book1", "A", None, "c"),
        ("Book2", "B", "9781234567897", "c"),
    ]
    path = c.write_unresolved(records, tmp_path)
    assert os.path.exists(path)

    with open(path, encoding="utf-8") as f:
        text = f.read()
        assert "Book1" in text
        assert "Book2" not in text

def test_write_unresolved_none(tmp_path):
    records = [
        ("Book1", "A", "9781234567897", "c"),
    ]
    assert c.write_unresolved(records, tmp_path) is None
