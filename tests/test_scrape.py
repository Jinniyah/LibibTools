"""
Tests for Chirp scraping logic.

These tests are designed to run without a live browser or Selenium installation.
All Selenium names used inside core.py are patched at the module level before
any calls into _parse_items or scrape_chirp are made.
"""

from unittest.mock import MagicMock, patch

from chirp_to_libib.core import _parse_items, scrape_chirp

# A lightweight stand-in for selenium.webdriver.common.by.By
_MockBy = type("By", (), {"CSS_SELECTOR": "css selector", "XPATH": "xpath"})

# Patch targets: all Selenium names used inside chirp_to_libib.core at call time
_SELENIUM_PATCHES = {
    "chirp_to_libib.core.By": _MockBy,
    "chirp_to_libib.core.WebDriverWait": MagicMock(),
    "chirp_to_libib.core.EC": MagicMock(),
}


# ==========================
# PARSE ITEMS TESTS
# ==========================


@patch.dict("chirp_to_libib.core.__dict__", _SELENIUM_PATCHES)
def test_parse_items_basic():
    item = MagicMock()
    img_mock = MagicMock()
    # srcset=None → _extract_cover_url falls through to src
    img_mock.get_attribute.side_effect = lambda attr: (
        None if attr == "srcset" else "http://example.com/cover.jpg"
    )
    item.find_element.side_effect = [
        MagicMock(text="Test Title"),  # title element
        MagicMock(text="By Author Name"),  # byline element
        img_mock,  # cover image element
    ]
    result = _parse_items([item])
    assert len(result) == 1
    assert result[0][0] == "Test Title"
    assert result[0][1] == "Author Name"
    assert result[0][2] == "http://example.com/cover.jpg"


@patch.dict("chirp_to_libib.core.__dict__", _SELENIUM_PATCHES)
def test_parse_items_missing_author():
    item = MagicMock()
    img_mock = MagicMock()
    img_mock.get_attribute.side_effect = lambda attr: (
        None if attr == "srcset" else "http://example.com/cover.jpg"
    )
    item.find_element.side_effect = [
        MagicMock(text="Test Title"),
        Exception("no byline element"),
        img_mock,
    ]
    result = _parse_items([item])
    assert result[0][1] == ""


@patch.dict("chirp_to_libib.core.__dict__", _SELENIUM_PATCHES)
def test_parse_items_missing_cover():
    item = MagicMock()
    item.find_element.side_effect = [
        MagicMock(text="Test Title"),
        MagicMock(text="By Author"),
        Exception("no primary cover img"),
        Exception("no fallback cover img"),
    ]
    result = _parse_items([item])
    assert result[0][2] == ""


# ==========================
# SCRAPE TESTS (MOCKED SELENIUM)
# ==========================


@patch("chirp_to_libib.core._login")
@patch("chirp_to_libib.core._build_driver")
@patch.dict("chirp_to_libib.core.__dict__", _SELENIUM_PATCHES)
def test_scrape_chirp_basic(mock_build_driver, mock_login):
    driver = MagicMock()
    mock_build_driver.return_value = driver

    with patch(
        "chirp_to_libib.core._parse_items",
        return_value=[("Title A", "Author A", "coverA")],
    ):
        result = scrape_chirp("email", "password", max_pages=1)

    assert len(result) == 1
    assert result[0][0] == "Title A"
    assert result[0][1] == "Author A"


@patch("chirp_to_libib.core._login")
@patch("chirp_to_libib.core._build_driver")
@patch.dict("chirp_to_libib.core.__dict__", _SELENIUM_PATCHES)
def test_scrape_chirp_no_items(mock_build_driver, mock_login):
    driver = MagicMock()
    mock_build_driver.return_value = driver
    driver.find_elements.return_value = []

    with patch("chirp_to_libib.core._parse_items", return_value=[]):
        result = scrape_chirp("email", "password", max_pages=1)

    assert result == []
