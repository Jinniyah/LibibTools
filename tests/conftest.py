import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure project root is on path for pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_driver():
    """Mock Selenium Chrome driver."""
    driver = MagicMock()
    driver.find_element.return_value = MagicMock()
    driver.find_elements.return_value = []
    return driver


@pytest.fixture
def mock_build_driver(mock_driver):
    """Patch _build_driver to return our mock driver."""
    with patch("chirp_to_libib.core._build_driver", return_value=mock_driver):
        yield mock_driver


@pytest.fixture
def mock_requests_get():
    """Patch requests.get inside the shared Open Library module."""
    with patch("lib.openlibrary.requests.get") as mock:
        yield mock


@pytest.fixture
def no_sleep():
    """Disable sleep_between_requests for fast tests."""
    with patch("lib.openlibrary.sleep_between_requests"):
        yield
