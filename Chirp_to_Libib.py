"""
chirp_to_libib.py
=================
Scrapes your Chirp audiobook library and exports a Libib-compatible CSV.

Dependencies:
    pip install selenium requests webdriver-manager
    Chrome must be installed on your system.

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
    chirp_to_libib_YYYY-MM-DD_HH-MM.csv              (UTF-8 with BOM, ready for Libib import)
    chirp_to_libib_unresolved_YYYY-MM-DD_HH-MM.txt   (titles with no ISBN found, if any)
"""

from __future__ import annotations

import argparse
import csv
import getpass
import logging
import os
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# ==========================
# CONFIGURATION
# ==========================

# Overridden at runtime by --first-page-only flag.
SCRAPE_ALL_PAGES: bool = True

# Seconds to pause between Open Library ISBN requests.
ISBN_REQUEST_DELAY: float = 1.0

# Log a progress line every N ISBN lookups.
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
    """Return (email, password) from environment variables or interactive prompts."""
    email = os.environ.get("CHIRP_EMAIL") or input("Enter your Chirp email: ").strip()
    password = (
        os.environ.get("CHIRP_PASSWORD")
        or getpass.getpass("Enter your Chirp password: ")
    )
    if not email or not password:
        raise ValueError("Both email and password are required.")
    return email, password


# ==========================
# ISBN LOOKUP  (Open Library)
# ==========================

_OL_URL = "https://openlibrary.org/search.json"
_OL_BASE_PARAMS: dict = {
    "mode": "everything",
    "limit": 5,
    "fields": "title,isbn",
}


def _normalize_isbn(raw: str) -> str:
    return re.sub(r"[^0-9Xx]", "", raw or "").upper()


def _valid_isbn13(s: str) -> bool:
    return len(s) == 13 and s.isdigit()


def _valid_isbn10(s: str) -> bool:
    return len(s) == 10 and s[:-1].isdigit() and (s[-1].isdigit() or s[-1] == "X")


def _best_isbn(isbns: list[str]) -> Optional[str]:
    """Return the first ISBN-13 found, then first ISBN-10, or None."""
    normed = [_normalize_isbn(i) for i in isbns if i]
    for i in normed:
        if _valid_isbn13(i):
            return i
    for i in normed:
        if _valid_isbn10(i):
            return i
    return None


def _title_is_plausible(query_title: str, returned_title: str, threshold: float = 0.55) -> bool:
    """
    Return True if the returned title is plausibly the same book.

    Passes if ANY of:
      - SequenceMatcher ratio >= threshold
      - query title is a substring of returned title (case/punct-insensitive)
      - >= 60% of significant query words (len > 3) appear in returned title

    The low threshold is intentional — audiobook and print titles often differ
    slightly (subtitles, "A Novel", series tags, etc.).
    """
    q = re.sub(r"[^\w\s]", "", query_title.lower()).strip()
    r = re.sub(r"[^\w\s]", "", returned_title.lower()).strip()

    if SequenceMatcher(None, q, r).ratio() >= threshold:
        return True
    if q and q in r:
        return True
    q_words = {w for w in q.split() if len(w) > 3}
    r_words = set(r.split())
    if q_words and len(q_words & r_words) / len(q_words) >= 0.60:
        return True
    return False


def _ol_query(params: dict, title_for_log: str) -> list[dict]:
    """Execute one Open Library search and return the docs list."""
    try:
        resp = requests.get(_OL_URL, params={**_OL_BASE_PARAMS, **params}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("docs", [])
    except requests.RequestException as exc:
        log.warning("Open Library network error for '%s': %s", title_for_log, exc)
        return []
    except Exception as exc:
        log.warning("Open Library parse error for '%s': %s", title_for_log, exc)
        return []


def _pick_isbn_from_docs(docs: list[dict], title: str) -> Optional[str]:
    """
    Two-pass ISBN picker:
      Pass 1 — only consider docs whose title passes the plausibility check.
      Pass 2 — drop the title check and accept the first valid ISBN in any doc.
    """
    for doc in docs:
        if _title_is_plausible(title, doc.get("title", "")):
            isbn = _best_isbn(doc.get("isbn") or [])
            if isbn:
                return isbn
    for doc in docs:
        isbn = _best_isbn(doc.get("isbn") or [])
        if isbn:
            return isbn
    return None


def get_isbn(title: str, author: str) -> Optional[str]:
    """
    Look up an ISBN via Open Library.

      Pass 1 — title= + author= as separate API fields (most accurate).
      Pass 2 — title= only, in case the author name is spelled differently.

    Returns an ISBN-13 if found, ISBN-10 if that is all that is available,
    or None if neither pass finds anything.
    """
    # Pass 1: dedicated title + author fields
    if author:
        docs = _ol_query({"title": title, "author": author}, title)
        isbn = _pick_isbn_from_docs(docs, title)
        if isbn:
            log.debug("OL title+author hit for '%s': %s", title, isbn)
            return isbn

    # Pass 2: title only (catches author-name mismatches / missing authors)
    docs = _ol_query({"title": title}, title)
    isbn = _pick_isbn_from_docs(docs, title)
    if isbn:
        log.debug("OL title-only hit for '%s': %s", title, isbn)
        return isbn

    log.debug("No ISBN found for '%s' by '%s'", title, author)
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


def _output_path(directory: str, filename: str) -> str:
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)


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
        log.debug("Debug snapshot failed (ignored).")


def _parse_items(items) -> list[tuple[str, str, str]]:
    books = []
    for item in items:
        try:
            title_el = item.find_element(By.CSS_SELECTOR, "a[href^='/audiobooks/']")
            title = title_el.text.strip()

            try:
                byline = item.find_element(By.CSS_SELECTOR, "div[class*='byline']").text.strip()
            except Exception:
                try:
                    byline = item.find_element(
                        By.XPATH, ".//div[starts-with(normalize-space(.),'by ')]"
                    ).text.strip()
                except Exception:
                    byline = ""

            author = re.sub(r"(?i)^\s*by\s+", "", byline).strip()

            try:
                img_el = item.find_element(
                    By.CSS_SELECTOR,
                    "img[data-testid='cover-image-image'], img[class*='cover-image-image']",
                )
                cover = _extract_cover_url(img_el)
            except Exception:
                cover = ""

            books.append((title, author, cover))

        except Exception as exc:
            log.debug("Skipping item due to parse error: %s", exc)

    return books


def scrape_chirp(email: str, password: str, scrape_all: bool) -> list[tuple[str, str, str]]:
    """Log in to Chirp and scrape the library. Returns [(title, author, cover_url)]."""
    driver = _build_driver()
    try:
        _login(driver, email, password)

        log.info("Navigating to library…")
        driver.get("https://www.chirpbooks.com/library?sort=recently_added")
        time.sleep(2)

        books: list[tuple[str, str, str]] = []
        page_number = 1

        while True:
            log.info("Scraping page %d…", page_number)

            try:
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
                time.sleep(1)
            except Exception:
                try:
                    _save_debug_snapshot(driver, f"page_{page_number}_no_items")
                except Exception:
                    pass
                log.warning("No library items found on page %d — stopping.", page_number)
                break

            items = driver.find_elements(
                By.XPATH, "//div[.//a[starts-with(@href,'/audiobooks/')]]"
            )
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
# DEDUPLICATION & FILTERING
# ==========================

def dedupe_books_by_title(books: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """
    Remove duplicates by title (case-insensitive), preserving order.
    If a duplicate is found and the existing record lacks an author but the new
    one has one, the new record replaces the old.
    """
    seen: set[str] = set()
    index_by_title: dict[str, int] = {}
    unique: list[tuple[str, str, str]] = []
    removed = replaced = 0

    for title, author, cover in books:
        key = (title or "").strip().lower()
        if not key:
            unique.append((title, author, cover))
            continue
        if key not in seen:
            seen.add(key)
            index_by_title[key] = len(unique)
            unique.append((title, author, cover))
        else:
            idx = index_by_title[key]
            _, existing_author, _ = unique[idx]
            if not existing_author.strip() and author.strip():
                unique[idx] = (title, author, cover)
                replaced += 1
            else:
                removed += 1

    if removed or replaced:
        log.info("Deduplication: %d removed, %d replaced.", removed, replaced)
    return unique


def filter_invalid_books(books: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Remove rows with empty, too-short, or placeholder titles."""
    valid: list[tuple[str, str, str]] = []
    removed = 0
    for title, author, cover in books:
        t = (title or "").strip()
        if not t:
            removed += 1
            continue
        if len(re.findall(r"[A-Za-z0-9]", t)) < 2:
            removed += 1
            continue
        if t.lower() == "audiobook":
            removed += 1
            continue
        if re.match(r"^[\W_]+$", t):
            removed += 1
            continue
        valid.append((title, author, cover))

    if removed:
        log.info("Filtered %d invalid book(s) before ISBN lookup.", removed)
    return valid


# ==========================
# ISBN RESOLUTION
# ==========================

def resolve_isbns(
    books: list[tuple[str, str, str]],
) -> list[tuple[str, str, Optional[str], str]]:
    """Look up ISBNs for every book via Open Library."""
    total = len(books)
    records: list[tuple[str, str, Optional[str], str]] = []

    for idx, (title, author, cover) in enumerate(books, start=1):
        isbn = get_isbn(title, author)
        records.append((title, author, isbn, cover))

        if idx % ISBN_LOG_INTERVAL == 0 or idx == total:
            resolved = sum(1 for _, _, i, _ in records if i)
            log.info("ISBN progress: %d/%d looked up, %d resolved.", idx, total, resolved)

        time.sleep(ISBN_REQUEST_DELAY)

    return records


# ==========================
# OUTPUT
# ==========================

def write_csv(
    records: list[tuple[str, str, Optional[str], str]],
    output_dir: str,
) -> str:
    """
    Write a Libib-compatible CSV file.

    Columns : Title | Creator | Identifier | Type | Image
    Encoding: UTF-8 with BOM (required by some Libib import flows).
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
    """Write a plain-text list of titles for which no ISBN was found."""
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

    del email, password  # no longer needed

    books = dedupe_books_by_title(books)
    books = filter_invalid_books(books)

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
