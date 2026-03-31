from __future__ import annotations

import argparse
import csv
import getpass
import logging
import os
import time
from datetime import datetime
from typing import Optional
from collections.abc import Iterable

from lib import get_isbn, sleep_between_requests, dedupe_books_by_title, filter_invalid_books

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from webdriver_manager.chrome import ChromeDriverManager

# ==========================
# CONFIGURATION
# ==========================

ISBN_LOG_INTERVAL: int = 25
PAGE_WAIT_TIMEOUT: int = 20
LIBIB_TYPE = "chirp,audiobook"

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
    parser.add_argument("--pages", type=int, default=None, metavar="N")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default=".", metavar="PATH")
    return parser.parse_args()

# ==========================
# CREDENTIALS
# ==========================

def _prompt_credentials() -> tuple[str, str]:
    email = os.environ.get("CHIRP_EMAIL") or input("Enter your Chirp email: ").strip()
    password = os.environ.get("CHIRP_PASSWORD") or getpass.getpass(
        "Enter your Chirp password: "
    )
    if not email or not password:
        raise ValueError("Both email and password are required.")
    return email, password

# ==========================
# CHIRP SCRAPING
# ==========================

def _build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def _login(driver: webdriver.Chrome, email: str, password: str) -> None:
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

def _extract_cover_url(img_element: WebElement) -> str:
    srcset = img_element.get_attribute("srcset")
    if srcset:
        last_entry = srcset.split(",")[-1].strip()
        return last_entry.split()[0]
    return img_element.get_attribute("src") or ""

def _output_path(directory: str, filename: str) -> str:
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)

def _parse_items(items: Iterable[WebElement]) -> list[tuple[str, str, str]]:
    books = []
    for item in items:
        try:
            title_el = item.find_element(By.CSS_SELECTOR, "a[href^='/audiobooks/']")
            title = title_el.text.strip()

            try:
                byline = item.find_element(
                    By.CSS_SELECTOR, "div[class*='byline']"
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

def scrape_chirp(email: str, password: str, max_pages: Optional[int]):
    driver = _build_driver()
    try:
        _login(driver, email, password)
        log.info("Navigating to library…")
        driver.get("https://www.chirpbooks.com/library?sort=recently_added")
        time.sleep(2)

        books = []
        page_number = 1

        while True:
            log.info("Scraping page %d…", page_number)

            WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[.//a[starts-with(@href,'/audiobooks/')]]")
                )
            )

            items = driver.find_elements(
                By.XPATH, "//div[.//a[starts-with(@href,'/audiobooks/')]]"
            )
            page_books = _parse_items(items)
            books.extend(page_books)

            log.info("  → %d book(s) on this page; %d total.", len(page_books), len(books))

            if max_pages is not None and page_number >= max_pages:
                log.info("Reached --pages limit (%d) — stopping.", max_pages)
                break

            next_el = driver.find_elements(
                By.CSS_SELECTOR, "li.rc-pagination-next[aria-disabled='false']"
            )
            if not next_el:
                log.info("No further pages found.")
                break

            next_el[0].click()
            page_number += 1

        return books
    finally:
        driver.quit()


# ==========================
# ISBN RESOLUTION (UPDATED)
# ==========================

def resolve_isbns(books):
    total = len(books)
    records = []

    for idx, (title, author, cover) in enumerate(books, start=1):
        isbn = get_isbn(title, author)
        sleep_between_requests()

        records.append((title, author, isbn, cover))

        if idx % ISBN_LOG_INTERVAL == 0 or idx == total:
            resolved = sum(1 for _, _, i, _ in records if i)
            log.info(
                "ISBN progress: %d/%d looked up, %d resolved.",
                idx, total, resolved
            )

    return records

# ==========================
# OUTPUT
# ==========================

def write_csv(records, output_dir):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = _output_path(output_dir, f"chirp_to_libib_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Creator", "Identifier", "Type", "Image"])
        for title, author, isbn, cover in records:
            writer.writerow([title, author, isbn or "", LIBIB_TYPE, cover])

    return path

def write_unresolved(records, output_dir):
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

def main():
    args = parse_args()

    if args.pages is not None and args.pages < 1:
        raise SystemExit("--pages must be 1 or greater.")

    email, password = _prompt_credentials()

    log.info("Starting Chirp library scrape…")
    books = scrape_chirp(email, password, max_pages=args.pages)

    del email, password
        
    books = filter_invalid_books(books)

    if not books:
        log.error("No books were scraped. Exiting.")
        return

    log.info("Found %d book(s). Deduplicating…", len(books))
    records = dedupe_books_by_title(books)

    log.info("Found %d book(s). Resolving ISBNs via Open Library…", len(records))   
    records = resolve_isbns(records)
    
    resolved = sum(1 for _, _, isbn, _ in records if isbn)
    unresolved_count = len(records) - resolved

    log.info(
        "ISBN resolution complete: %d/%d resolved, %d unresolved.",
        resolved, len(records), unresolved_count
    )

    if args.dry_run:
        log.info("--dry-run set — no output files written.")
        return

    csv_path = write_csv(records, args.output_dir)
    log.info("CSV written: %s", csv_path)

    unresolved_path = write_unresolved(records, args.output_dir)
    if unresolved_path:
        log.info("Unresolved titles written to: %s", unresolved_path)

    print(f"\nUpload '{csv_path}' to Libib to update your collection.")
