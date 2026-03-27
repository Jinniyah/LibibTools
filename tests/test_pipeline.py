import chirp_to_libib as c
from unittest.mock import patch

def test_pipeline_dry_run(tmp_path, mock_build_driver, no_sleep):
    # Mock credentials
    with patch("chirp_to_libib.core._prompt_credentials", return_value=("e", "p")):
        # Mock scrape_chirp
        with patch("chirp_to_libib.core.scrape_chirp") as mock_scrape:
            mock_scrape.return_value = [
                ("Book1", "Author1", "c1"),
                ("Book2", "Author2", "c2"),
            ]

            # Mock ISBN lookup
            with patch("chirp_to_libib.core.get_isbn", return_value="9781234567897"):
                args = ["prog", "--dry-run"]
                with patch("sys.argv", args):
                    c.main()

            # No files should be written
            assert not list(tmp_path.iterdir())
