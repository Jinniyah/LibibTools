from unittest.mock import patch
from chirp_to_libib.core import main


@patch("chirp_to_libib.core.write_unresolved")
@patch("chirp_to_libib.core.write_csv")
@patch("chirp_to_libib.core.sleep_between_requests")
@patch("chirp_to_libib.core.get_isbn", return_value="1234567890")
@patch("chirp_to_libib.core.scrape_chirp")
@patch("chirp_to_libib.core._prompt_credentials", return_value=("email", "password"))
def test_pipeline_dry_run(
    mock_creds,
    mock_scrape,
    mock_get_isbn,
    mock_sleep,
    mock_write_csv,
    mock_write_unresolved,
):
    mock_scrape.return_value = [
        ("Title A", "Author A", "coverA"),
        ("Title B", "Author B", "coverB"),
    ]

    with patch("sys.argv", ["prog", "--dry-run"]):
        main()

    mock_creds.assert_called_once()
    mock_scrape.assert_called_once()
    assert mock_get_isbn.call_count == 2
    mock_write_csv.assert_not_called()
    mock_write_unresolved.assert_not_called()
