# lib/openlibrary.py

from __future__ import annotations
import logging
import random
import re
import time
from difflib import SequenceMatcher
from typing import Optional

import requests

log = logging.getLogger(__name__)

# Base Open Library endpoint
_OL_URL = "https://openlibrary.org/search.json"

# Default parameters for all queries
_OL_BASE_PARAMS = {
    "mode": "everything",
    "limit": 5,
    "fields": "title,isbn",
}

# Randomized delay range (seconds)
ISBN_DELAY_RANGE = (0.8, 1.6)


# -----------------------------
# ISBN Normalization & Validation
# -----------------------------

def _normalize_isbn(raw: str) -> str:
    return re.sub(r"[^0-9Xx]", "", raw or "").upper()


def _valid_isbn13(s: str) -> bool:
    if len(s) != 13 or not s.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(s))
    return total % 10 == 0


def _valid_isbn10(s: str) -> bool:
    if len(s) != 10 or not s[:-1].isdigit() or not (s[-1].isdigit() or s[-1] == "X"):
        return False
    total = sum((10 - i) * (10 if s[i] == "X" else int(s[i])) for i in range(10))
    return total % 11 == 0


def _best_isbn(isbns: list[str]) -> Optional[str]:
    """Return the first ISBN-13, then ISBN-10, or None."""
    normed = [_normalize_isbn(i) for i in isbns if i]
    for i in normed:
        if _valid_isbn13(i):
            return i
    for i in normed:
        if _valid_isbn10(i):
            return i
    return None


# -----------------------------
# Title Matching
# -----------------------------

def _title_is_plausible(query_title: str, returned_title: str, threshold: float = 0.55) -> bool:
    """
    Determine whether a returned title plausibly matches the query.
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


# -----------------------------
# Open Library Query with Retry
# -----------------------------

def _ol_query(params: dict, title_for_log: str) -> list[dict]:
    """Execute one Open Library search with retries and exponential backoff."""
    max_retries = 4
    backoff = 2

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                _OL_URL,
                params={**_OL_BASE_PARAMS, **params},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json().get("docs", [])
        except Exception as exc:
            log.warning(
                "Open Library error for '%s' (attempt %d/%d): %s",
                title_for_log,
                attempt,
                max_retries,
                exc,
            )
            time.sleep(backoff)
            backoff *= 2

    return []


# -----------------------------
# ISBN Selection Logic
# -----------------------------

def _pick_isbn_from_docs(docs: list[dict], title: str) -> Optional[str]:
    """Two-pass ISBN selection."""
    # Pass 1: title plausibility check
    for doc in docs:
        if _title_is_plausible(title, doc.get("title", "")):
            isbn = _best_isbn(doc.get("isbn") or [])
            if isbn:
                return isbn

    # Pass 2: accept any valid ISBN
    for doc in docs:
        isbn = _best_isbn(doc.get("isbn") or [])
        if isbn:
            return isbn

    return None


# -----------------------------
# Public API
# -----------------------------

def get_isbn(title: str, author: str) -> Optional[str]:
    """
    Look up an ISBN via Open Library using:
    1. title + author
    2. title only
    """
    # Pass 1: title + author
    if author:
        docs = _ol_query({"title": title, "author": author}, title)
        isbn = _pick_isbn_from_docs(docs, title)
        if isbn:
            return isbn

    # Pass 2: title only
    docs = _ol_query({"title": title}, title)
    isbn = _pick_isbn_from_docs(docs, title)
    if isbn:
        return isbn

    return None


def sleep_between_requests() -> None:
    """Randomized delay to avoid rate-limiting."""
    time.sleep(random.uniform(*ISBN_DELAY_RANGE))



def dedupe_books_by_title(books: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Remove duplicate titles, preferring entries that have an author."""
    seen: dict[str, int] = {}
    unique: list[tuple[str, str, str]] = []
    removed = replaced = 0

    for title, author, cover in books:
        key = (title or "").strip().lower()
        if key not in seen:
            seen[key] = len(unique)
            unique.append((title, author, cover))
        else:
            idx = seen[key]
            _, existing_author, _ = unique[idx]
            if not existing_author and author:
                unique[idx] = (title, author, cover)
                replaced += 1
            else:
                removed += 1

    if removed or replaced:
        log.info("Deduplication: %d removed, %d replaced.", removed, replaced)
    return unique


def filter_invalid_books(
    books: list[tuple[str, str, str]],
    extra_garbage: frozenset[str] = frozenset(),
) -> list[tuple[str, str, str]]:
    """
    Drop entries with missing, trivial, or garbage titles.

    Pass ``extra_garbage`` to add platform-specific junk titles
    (e.g. Kindle UI strings) without touching shared logic.
    """
    _BASE_GARBAGE = frozenset({"audiobook", "book", "ebook"})
    garbage = _BASE_GARBAGE | extra_garbage

    valid: list[tuple[str, str, str]] = []
    removed = 0

    for title, author, cover in books:
        t = (title or "").strip()
        if not t or len(re.findall(r"[A-Za-z0-9]", t)) < 2:
            removed += 1
            continue
        if t.lower() in garbage:
            removed += 1
            continue
        if re.match(r"^[\W_]+$", t):
            removed += 1
            continue
        valid.append((title, author, cover))

    if removed:
        log.info("Filtered %d invalid book(s) before ISBN lookup.", removed)
    return valid