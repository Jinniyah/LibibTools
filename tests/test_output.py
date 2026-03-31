import csv
import os
import tempfile

from chirp_to_libib.core import (
    write_csv as chirp_write_csv,
    write_unresolved as chirp_write_unresolved,
)
from kindle_to_libib.core import (
    write_csv as kindle_write_csv,
    write_unresolved as kindle_write_unresolved,
)

# ==========================
# CSV OUTPUT TESTS
# ==========================


def test_chirp_write_csv():
    records = [
        ("Title A", "Author A", "1234567890", "coverA"),
        ("Title B", "Author B", None, "coverB"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        path = chirp_write_csv(records, tmp)
        assert os.path.exists(path)

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))

        # Header + 2 rows
        assert len(reader) == 3
        assert reader[0] == ["Title", "Creator", "Identifier", "Type", "Image"]
        assert reader[1][0] == "Title A"
        assert reader[2][2] == ""  # unresolved ISBN becomes empty string


def test_kindle_write_csv():
    records = [
        ("Title A", "Author A", "9781402894626", "coverA"),
        ("Title B", "Author B", None, "coverB"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        path = kindle_write_csv(records, tmp)
        assert os.path.exists(path)

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))

        assert len(reader) == 3
        assert reader[0] == ["Title", "Creator", "Identifier", "Type", "Image"]
        assert reader[1][2] == "9781402894626"
        assert reader[2][2] == ""


# ==========================
# UNRESOLVED OUTPUT TESTS
# ==========================


def test_chirp_write_unresolved():
    records = [
        ("Title A", "Author A", "1234567890", "coverA"),
        ("Title B", "Author B", None, "coverB"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        path = chirp_write_unresolved(records, tmp)
        assert os.path.exists(path)

        with open(path, encoding="utf-8") as f:
            text = f.read()

        assert "Title B" in text
        assert "Title A" not in text


def test_kindle_write_unresolved():
    records = [
        ("Title A", "Author A", "9781402894626", "coverA"),
        ("Title B", "Author B", None, "coverB"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        path = kindle_write_unresolved(records, tmp)
        assert os.path.exists(path)

        with open(path, encoding="utf-8") as f:
            text = f.read()

        assert "Title B" in text
        assert "Title A" not in text
