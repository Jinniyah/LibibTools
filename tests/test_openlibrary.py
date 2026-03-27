import chirp_to_libib as c
from unittest.mock import MagicMock

def test_get_isbn_pass1_hit(mock_requests_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "docs": [{"title": "Test Book", "isbn": ["9781234567897"]}]
    }
    mock_resp.raise_for_status.return_value = None
    mock_requests_get.return_value = mock_resp

    isbn = c.get_isbn("Test Book", "Author")
    assert isbn == "9781234567897"

def test_get_isbn_pass2_hit(mock_requests_get):
    # Pass 1 returns empty
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {"docs": []}
    mock_resp1.raise_for_status.return_value = None

    # Pass 2 returns valid
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "docs": [{"title": "Test Book", "isbn": ["123456789X"]}]
    }
    mock_resp2.raise_for_status.return_value = None

    mock_requests_get.side_effect = [mock_resp1, mock_resp2]

    isbn = c.get_isbn("Test Book", "Author")
    assert isbn == "123456789X"

def test_get_isbn_network_error(mock_requests_get):
    mock_requests_get.side_effect = Exception("Network down")
    assert c.get_isbn("Test Book", "Author") is None
