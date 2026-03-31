from unittest.mock import MagicMock, patch

from chirp_to_libib.core import _parse_items, scrape_chirp


# ==========================
# PARSE ITEMS TESTS
# ==========================

def test_parse_items_basic():
    # Mock WebElement structure
    item = MagicMock()
    item.find_element.side_effect = [
        MagicMock(text="Test Title"),  # title
        MagicMock(text="By Author Name"),  # byline
        MagicMock(get_attribute=lambda attr: "http://example.com/cover.jpg"),  # img
    ]

    result = _parse_items([item])
    assert len(result) == 1
    assert result[0][0] == "Test Title"
    assert result[0][1] == "Author Name"
    assert result[0][2] == "http://example.com/cover.jpg"


def test_parse_items_missing_author():
    item = MagicMock()
    item.find_element.side_effect = [
        MagicMock(text="Test Title"),  # title
        Exception("no author"),        # byline missing
        MagicMock(get_attribute=lambda attr: "http://example.com/cover.jpg"),
    ]

    result = _parse_items([item])
    assert result[0][1] == ""


def test_parse_items_missing_cover():
    item = MagicMock()
    item.find_element.side_effect = [
        MagicMock(text="Test Title"),  # title
        MagicMock(text="By Author"),   # byline
        Exception("no cover"),         # cover missing
    ]

    result = _parse_items([item])
    assert result[0][2] == ""


# ==========================
# SCRAPE TESTS (MOCKED SELENIUM)
# ==========================

@patch("chirp_to_libib.core._build_driver")
@patch("chirp_to_libib.core._prompt_credentials", return_value=("email", "password"))
def test_scrape_chirp_basic(mock_creds, mock_driver):
    # Mock driver and elements
    driver = MagicMock()
    mock_driver.return_value = driver

    # Mock login
    driver.find_element.return_value = MagicMock()

    # Mock library page load
    driver.find_elements.return_value = [
        MagicMock(),  # one fake item
    ]

    # Mock parse_items to avoid DOM complexity
    with patch("chirp_to_libib.core._parse_items", return_value=[
        ("Title A", "Author A", "coverA")
    ]):
        result = scrape_chirp("email", "password", max_pages=1)

    assert len(result) == 1
    assert result[0][0] == "Title A"
    assert result[0][1] == "Author A"


@patch("chirp_to_libib.core._build_driver")
@patch("chirp_to_libib.core._prompt_credentials", return_value=("email", "password"))
def test_scrape_chirp_no_items(mock_creds, mock_driver):
    driver = MagicMock()
    mock_driver.return_value = driver

    # Simulate no items found
    driver.find_elements.return_value = []

    with patch("chirp_to_libib.core._parse_items", return_value=[]):
        result = scrape_chirp("email", "password", max_pages=1)

    assert result == []
