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

from lib import (
    get_isbn,
    sleep_between_requests,
    dedupe_books_by_title,
    filter_invalid_books,
)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

# ==========================
# CONFIGURATION
# ==========================

ISBN_LOG_INTERVAL: int = 25
PAGE_WAIT_TIMEOUT: int = 20
LIBIB_TYPE = "kindle,ebook"

KINDLE_LIBRARY_URL: str = (
    "https://www.amazon.com/hz/mycd/digital-console/contentlist/booksAll/dateDsc/"
)

_KINDLE_UI_GARBAGE = frozenset(
    {"content", "devices", "preferences", "privacy settings"}
)

# ==========================
# LOGGING
# ==========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ==========================
# CLI
# ==========================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export your Kindle ebook library to a Libib-compatible CSV."
    )
    parser.add_argument("--pages", type=int, default=None, metavar="N")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default=".", metavar="PATH")
    return parser.parse_args()


# ==========================
# CREDENTIALS
# ==========================


def _prompt_credentials() -> tuple[str, str]:
    email = os.environ.get("KINDLE_EMAIL") or input("Enter your Amazon email: ").strip()
    password = os.environ.get("KINDLE_PASSWORD") or getpass.getpass(
        "Enter your Amazon password: "
    )
    if not email or not password:
        raise ValueError("Both email and password are required.")
    return email, password


# ==========================
# KINDLE SCRAPING
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
    log.info("Navigating to Kindle content library…")
    driver.get(KINDLE_LIBRARY_URL)

    try:
        WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
            EC.any_of(
                EC.presence_of_element_located((By.ID, "ap_email")),
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "tr[role='listitem'], div[role='listitem']")
                ),
            )
        )
    except Exception:
        log.warning("Initial page did not show sign-in or content list promptly.")

    content_items = driver.find_elements(
        By.CSS_SELECTOR, "tr[role='listitem'], div[role='listitem']"
    )
    if content_items:
        log.info("Already signed in; content list detected.")
        return

    try:
        email_el = driver.find_element(By.ID, "ap_email")
        email_el.clear()
        email_el.send_keys(email)
        driver.find_element(By.ID, "continue").click()
    except Exception:
        pass

    try:
        WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "ap_password"))
        )
        pwd_el = driver.find_element(By.ID, "ap_password")
        pwd_el.clear()
        pwd_el.send_keys(password)
        driver.find_element(By.ID, "signInSubmit").click()
    except Exception as exc:
        log.warning("Could not complete automated login: %s", exc)

    log.info("Waiting for Kindle content list after login…")
    WebDriverWait(driver, PAGE_WAIT_TIMEOUT * 2).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "tr[role='listitem'], div[role='listitem']")
        )
    )
    log.info("Login successful or already authenticated; content list visible.")


def _extract_cover_url(img_element: WebElement) -> str:
    srcset = img_element.get_attribute("srcset")
    if srcset:
        last_entry = srcset.split(",")[-1].strip()
        return last_entry.split()[0]
    return img_element.get_attribute("src") or ""


def _output_path(directory: str, filename: str) -> str:
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)


def _save_debug_snapshot(driver: WebDriver, tag: str) -> None:
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"kindle_debug_{ts}_{tag}"
        html_path = _output_path(".", base + ".html")
        img_path = _output_path(".", base + ".png")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        driver.save_screenshot(img_path)
        log.info("Saved debug snapshot: %s and %s", html_path, img_path)
    except Exception:
        log.debug("Debug snapshot failed (ignored).")


def _parse_items(items: Iterable[WebElement]) -> list[tuple[str, str, str]]:
    books = []
    for item in items:
        try:
            # ---- Title ----
            title = ""
            try:
                title_el = item.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='title'], [data-testid='entity-title']",
                )
                title = title_el.text.strip()
            except Exception:
                try:
                    title_el = item.find_element(
                        By.CSS_SELECTOR, "span[class*='title'], div[class*='title']"
                    )
                    title = title_el.text.strip()
                except Exception:
                    try:
                        title_el = item.find_element(
                            By.XPATH,
                            ".//a[normalize-space(text())!=''][1] | "
                            ".//span[normalize-space(text())!=''][1]",
                        )
                        title = title_el.text.strip()
                    except Exception:
                        title = ""

            # ---- Author ----
            author = ""
            try:
                author_el = item.find_element(
                    By.CSS_SELECTOR, "div.information_row[id^='content-author']"
                )
                author = author_el.text.strip()
            except Exception:
                try:
                    author_el = item.find_element(
                        By.CSS_SELECTOR, "div.information_row"
                    )
                    author = author_el.text.strip()
                except Exception:
                    author = ""

            # ---- Cover ----
            cover = ""
            try:
                img_el = item.find_element(
                    By.CSS_SELECTOR,
                    "div[class*='DigitalEntitySummary-module_image_container'] img, "
                    "img[class*='DigitalEntitySummary-module_image']",
                )
                cover = _extract_cover_url(img_el)
            except Exception:
                try:
                    img_el = item.find_element(By.CSS_SELECTOR, "img")
                    cover = _extract_cover_url(img_el)
                except Exception:
                    cover = ""

            if title or author or cover:
                books.append((title, author, cover))

        except Exception as exc:
            log.debug("Skipping item due to parse error: %s", exc)

    return books


def scrape_kindle(email: str, password: str, max_pages: Optional[int]):
    driver = _build_driver()
    try:
        _login(driver, email, password)
        log.info("Navigating to Kindle library…")
        driver.get(KINDLE_LIBRARY_URL)
        time.sleep(2)

        books = []
        page_number = 1

        while True:
            log.info("Scraping page %d…", page_number)

            WebDriverWait(driver, PAGE_WAIT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "tr[role='listitem'], div[role='listitem']")
                )
            )

            items = driver.find_elements(
                By.CSS_SELECTOR, "tr[role='listitem'], div[role='listitem']"
            )
            page_books = _parse_items(items)
            books.extend(page_books)

            log.info(
                " → %d book(s) on this page; %d total.", len(page_books), len(books)
            )

            if max_pages is not None and page_number >= max_pages:
                log.info("Reached --pages limit (%d) — stopping.", max_pages)
                break

            next_candidates = driver.find_elements(
                By.CSS_SELECTOR,
                "button[aria-label='Next page']:not([disabled]), "
                "button[aria-label='Next']:not([disabled]), "
                "li.a-last:not(.a-disabled) a",
            )
            if not next_candidates:
                log.info("No further pages found.")
                break

            next_candidates[0].click()
            page_number += 1
            time.sleep(2)

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
        isbn = get_isbn(title, author)  # <-- SHARED LOOKUP
        sleep_between_requests()  # <-- SHARED DELAY

        records.append((title, author, isbn, cover))

        if idx % ISBN_LOG_INTERVAL == 0 or idx == total:
            resolved = sum(1 for _, _, i, _ in records if i)
            log.info(
                "ISBN progress: %d/%d looked up, %d resolved.", idx, total, resolved
            )

    return records


# ==========================
# OUTPUT
# ==========================


def write_csv(records, output_dir):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = _output_path(output_dir, f"kindle_to_libib_{timestamp}.csv")

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
    path = _output_path(output_dir, f"kindle_to_libib_unresolved_{timestamp}.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write("Titles with no ISBN found in Open Library\n")
        f.write("=" * 44 + "\n\n")
        for title, author in unresolved:
            f.write(f"{title} — {author}\n")

    return path


# ==========================
# MAIN PIPELINE
# ==========================


def _filter_kindle_books(books):
    return filter_invalid_books(books, extra_garbage=_KINDLE_UI_GARBAGE)


def main():
    args = parse_args()
    if args.pages is not None and args.pages < 1:
        raise SystemExit("--pages must be 1 or greater.")

    email, password = _prompt_credentials()

    log.info("Starting Kindle library scrape…")
    books = scrape_kindle(email, password, max_pages=args.pages)
    del email, password

    log.info("Found %d book(s). Deduplicating…", len(books))
    books = dedupe_books_by_title(books)
    books = _filter_kindle_books(books)

    if not books:
        log.error("No books were scraped. Exiting.")
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
        return

    csv_path = write_csv(records, args.output_dir)
    log.info("CSV written: %s", csv_path)

    unresolved_path = write_unresolved(records, args.output_dir)
    if unresolved_path:
        log.info("Unresolved titles written to: %s", unresolved_path)

    print(f"\nUpload '{csv_path}' to Libib to update your collection.")
