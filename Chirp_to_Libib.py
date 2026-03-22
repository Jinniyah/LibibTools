"""
chirp_to_libib.py
=================
Scrapes your Chirp audiobook library and exports a Libib-compatible CSV.

Dependencies:
    pip install selenium requests
    ChromeDriver must be installed and on your PATH (matching your Chrome version).
    https://googlechromelabs.github.io/chrome-for-testing/

Usage:
    python chirp_to_libib.py [options]

    Options:
        --first-page-only     Only scrape the first page of your library.
        --dry-run             Scrape and look up ISBNs, but do not write a CSV.
        --output-dir PATH     Directory to write the CSV to (default: current directory).

    Credentials can be supplied via environment variables to avoid interactive prompts:
        For Bash: 
            export CHIRP_EMAIL="you@example.com"
            export CHIRP_PASSWORD="yourpassword"

        For Windows:
            set CHIRP_EMAIL=you@example.com
            set CHIRP_PASSWORD=yourpassword

Output:
    chirp_to_libib_YYYY-MM-DD_HH-MM.csv  (UTF-8 with BOM, ready for Libib import)
    chirp_to_libib_unresolved_YYYY-MM-DD_HH-MM.txt  (titles with no ISBN found, if any)
"""

from __future__ import annotations

import argparse
import csv
import getpass
import logging
import os
import time
from datetime import datetime
from typing import Optional

import requests
from selenium import webdriver

# Sanity check Selenium.
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait



# ==========================
# CONFIGURATION
# ==========================

# --- Scraping behavior ---
# Overridden at runtime by --first-page-only flag.
SCRAPE_ALL_PAGES: bool = True

# --- Timeouts & rate limiting ---
# Seconds to pause between Open Library ISBN requests.
ISBN_REQUEST_DELAY: float = 0.5
# Log a progress line every N ISBN lookups instead of every single one.
ISBN_LOG_INTERVAL: int = 25
# Selenium wait timeout in seconds for page elements to appear.
PAGE_WAIT_TIMEOUT: int = 20

# ==========================
# LOGGING
# ==========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ==========================
# CLI
# ==========================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export your Chirp audiobook library to a Libib-compatible CSV."
    )
    parser.add_argument(
        "--first-page-only",
        action="store_true",
        help="Stop after scraping the first page of the library.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and resolve ISBNs, but do not write any output files.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        metavar="PATH",
        help="Directory to write output files to (default: current directory).",
    )
    return parser.parse_args()


# ==========================
# CREDENTIALS
# ==========================
def _prompt_credentials() -> tuple[str, str]:
    """
    Return (email, password) from environment variables or interactive prompts.
    Credentials are never stored beyond the immediate call site.
    """
    email = os.environ.get("CHIRP_EMAIL") or input("Enter your Chirp email: ").strip()
    password = (
        os.environ.get("CHIRP_PASSWORD")
        or getpass.getpass("Enter your Chirp password: ")
    )
    if not email or not password:
        raise ValueError("Both email and password are required.")
    return email, password


# ==========================
# ISBN LOOKUP
# ==========================
def get_isbn(title: str, author: str) -> Optional[str]:
    """
    Query Open Library for an ISBN matching title + author.

    Checks up to 3 results. Applies a loose title-word confidence check
    to reduce false positives before accepting an ISBN.

    Preference order: ISBN-13 → ISBN-10 → None.
    """
    url = "https://openlibrary.org/search.json"
    params = {"title": title, "author": author, "limit": 3}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        docs = data.get("docs", [])
        if not docs:
            return None

        query_words = {w for w in title.lower().split() if len(w) > 3}

        for doc in docs:
            returned_title = doc.get("title", "").lower()
            if query_words and not query_words.intersection(returned_title.split()):
                continue

            isbns = doc.get("isbn", [])
            for isbn in isbns:
                if len(isbn) == 13:
                    return isbn
            for isbn in isbns:
                if len(isbn) == 10:
                    return isbn

        return None

    except requests.RequestException as exc:
        log.warning("ISBN lookup network error for '%s': %s", title, exc)
        return None
    except (KeyError, ValueError) as exc:
        log.warning("ISBN lookup parse error for '%s': %s", title, exc)
        return None


# ==========================
# CHIRP SCRAPING
# ==========================
def _build_driver() -> webdriver.Chrome:
    options = Options()
    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)



def _login(driver: webdriver.Chrome, email: str, password: str) -> None:
    """Navigate to the Chirp login page and authenticate."""
    log.info("Navigating to Chirp login page…")
    # driver.get("https://www.chirpbooks.com/login") # Original
    driver.get("https://www.chirpbooks.com/users/sign_in")

    WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "user_email"))
    )

    driver.find_element(By.ID, "user_email").send_keys(email)
    driver.find_element(By.ID, "user_password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/library']"))
    )
    log.info("Login successful.")


def _extract_cover_url(img_element) -> str:
    """Return the highest-resolution URL from srcset, or fall back to src."""
    srcset = img_element.get_attribute("srcset")
    if srcset:
        last_entry = srcset.split(",")[-1].strip()
        return last_entry.split()[0]
    return img_element.get_attribute("src") or ""


def _save_debug_snapshot(driver, tag: str) -> None:
    """Save page_source and a screenshot for debugging DOM / selector issues."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"chirp_debug_{ts}_{tag}"
        html_path = _output_path(".", base + ".html")
        img_path = _output_path(".", base + ".png")
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception as exc:
            log.debug("Failed saving debug HTML: %s", exc)
        try:
            driver.save_screenshot(img_path)
        except Exception as exc:
            log.debug("Failed saving debug PNG: %s", exc)
        log.info("Saved debug snapshot: %s and %s", html_path, img_path)
    except Exception:
        # Never let debug snapshot break scraping
        log.debug("Debug snapshot failed (ignored).")


def _parse_items(items):
    import re

    books = []
    for item in items:
        try:
            # Title: the audiobook link anchor (href starts with /audiobooks/)
            title_el = item.find_element(By.CSS_SELECTOR, "a[href^='/audiobooks/']")
            title = title_el.text.strip()

            # Author: prefer a class-containing 'byline', strip a leading "by "
            try:
                byline = item.find_element(By.CSS_SELECTOR, "div[class*='byline']").text.strip()
            except Exception:
                # Fallback: any div whose text starts with 'by '
                try:
                    byline = item.find_element(By.XPATH, ".//div[starts-with(normalize-space(.),'by ')]").text.strip()
                except Exception:
                    byline = ""

            author = re.sub(r'(?i)^\s*by\s+', '', byline).strip()

            # Cover: prefer data-testid image or any cover-image-like img; use _extract_cover_url
            try:
                img_el = item.find_element(By.CSS_SELECTOR, "img[data-testid='cover-image-image'], img[class*='cover-image-image']")
                cover = _extract_cover_url(img_el)
            except Exception:
                cover = ""

            books.append((title, author, cover))

        except Exception as exc:
            log.debug("Skipping item due to parse error: %s", exc)

    return books




def scrape_chirp(email: str, password: str, scrape_all: bool) -> list[tuple[str, str, str]]:
    """
    Log in to Chirp and scrape the library.

    Returns a list of (title, author, cover_url) tuples.
    """
    driver = _build_driver()

    try:
        _login(driver, email, password)

        log.info("Navigating to library…")
        driver.get("https://www.chirpbooks.com/library?sort=recently_added")

        # Give React time to reload the list
        time.sleep(2)

        books: list[tuple[str, str, str]] = []
        page_number = 1

        while True:
            log.info("Scraping page %d…", page_number)

            try:
                # Wait for at least one audiobook card (container that contains an /audiobooks/ link)
                WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[.//a[starts-with(@href,'/audiobooks/')]]")
                    )
                )

                WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//div[.//a[starts-with(@href,'/audiobooks/')]]")
                    )
                )

                # Give React time to populate the list
                time.sleep(1)

            except Exception:
                # Save debug snapshot to inspect the page DOM that caused the failure
                try:
                    _save_debug_snapshot(driver, f"page_{page_number}_no_items")
                except Exception:
                    pass
                log.warning(
                    "No library items found on page %d — stopping.", page_number
                )
                break

            # Find all card containers that include an audiobook link
            items = driver.find_elements(By.XPATH, "//div[.//a[starts-with(@href,'/audiobooks/')]]")
            page_books = _parse_items(items)
            if items and not page_books:
                try:
                    _save_debug_snapshot(driver, f"page_{page_number}_parse_zero")
                except Exception:
                    pass

            books.extend(page_books)
            log.info("  → %d book(s) on this page; %d total.", len(page_books), len(books))

            if not scrape_all:
                log.info("--first-page-only set — stopping after page 1.")
                break

            next_buttons = driver.find_elements(By.CSS_SELECTOR, "a[rel='next']")
            if not next_buttons:
                log.info("No further pages found.")
                break

            next_buttons[0].click()
            page_number += 1

        return books

    finally:
        driver.quit()


# ==========================
# ISBN RESOLUTION
# ==========================
def resolve_isbns(
    books: list[tuple[str, str, str]],
) -> list[tuple[str, str, Optional[str], str]]:
    """
    Look up ISBNs for every book via Open Library.

    Logs progress every ISBN_LOG_INTERVAL items rather than every single one,
    keeping output clean for large libraries.
    """
    total = len(books)
    records: list[tuple[str, str, Optional[str], str]] = []

    for idx, (title, author, cover) in enumerate(books, start=1):
        isbn = get_isbn(title, author)
        records.append((title, author, isbn, cover))

        log.debug("[%d/%d] '%s' → %s", idx, total, title, isbn or "not found")

        if idx % ISBN_LOG_INTERVAL == 0 or idx == total:
            resolved = sum(1 for _, _, i, _ in records if i)
            log.info(
                "ISBN progress: %d/%d looked up, %d resolved.", idx, total, resolved
            )

        time.sleep(ISBN_REQUEST_DELAY)

    return records


# ==========================
# OUTPUT
# ==========================
def _output_path(directory: str, filename: str) -> str:
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)


def write_csv(
    records: list[tuple[str, str, Optional[str], str]],
    output_dir: str,
) -> str:
    """
    Write a Libib-compatible CSV file.

    Columns : Title | Creator | Identifier | Type | Image
    Encoding: UTF-8 with BOM (required by some Libib import flows).

    Note: 'Identifier' (ISBN) may be empty for titles not found in Open Library.
    Libib will still import these rows but cannot auto-fill metadata for them.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = _output_path(output_dir, f"chirp_to_libib_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Creator", "Identifier", "Type", "Image"])
        for title, author, isbn, cover in records:
            writer.writerow([title, author, isbn or "", "audiobook", cover])

    return path


def write_unresolved(
    records: list[tuple[str, str, Optional[str], str]],
    output_dir: str,
) -> Optional[str]:
    """
    Write a plain-text list of titles for which no ISBN was found.
    Returns the file path, or None if all ISBNs were resolved.
    """
    unresolved = [(t, a) for t, a, isbn, _ in records if not isbn]
    if not unresolved:
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = _output_path(output_dir, f"chirp_to_libib_unresolved_{timestamp}.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write("Titles with no ISBN found in Open Library\n")
        f.write("=" * 44 + "\n\n")
        for title, author in unresolved:
            f.write(f"{title}  —  {author}\n")

    return path


# ==========================
# MAIN PIPELINE
# ==========================
def main() -> None:
    args = parse_args()
    scrape_all = SCRAPE_ALL_PAGES and not args.first_page_only

    email, password = _prompt_credentials()

    log.info("Starting Chirp library scrape…")
    books = scrape_chirp(email, password, scrape_all=scrape_all)

    # Credentials no longer needed — allow GC.
    del email, password

    if not books:
        log.error(
            "No books were scraped. Check your credentials and CSS selectors. "
            "Exiting without writing any output files."
        )
        return

    log.info("Found %d book(s). Resolving ISBNs via Open Library…", len(books))
    records = resolve_isbns(books)

    resolved = sum(1 for _, _, isbn, _ in records if isbn)
    unresolved_count = len(records) - resolved
    log.info(
        "ISBN resolution complete: %d/%d resolved, %d unresolved.",
        resolved,
        len(records),
        unresolved_count,
    )

    if args.dry_run:
        log.info("--dry-run set — no output files written.")
        if unresolved_count:
            log.info("Unresolved titles:")
            for title, author, isbn, _ in records:
                if not isbn:
                    log.info("  • %s  —  %s", title, author)
        return

    csv_path = write_csv(records, args.output_dir)
    log.info("CSV written: %s", csv_path)

    unresolved_path = write_unresolved(records, args.output_dir)
    if unresolved_path:
        log.info(
            "Unresolved titles (%d) written to: %s", unresolved_count, unresolved_path
        )
    else:
        log.info("All ISBNs resolved — no unresolved file written.")

    print(f"\nUpload '{csv_path}' to Libib to update your collection.")


if __name__ == "__main__":
    main()