# LibibTools

![Tests](https://github.com/Jinniyah/LibibTools/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-generated-blue)

Tools for automating and enriching personal library management workflows.  
This repository currently includes two Python packages that scrape your digital book libraries and export Libib‑compatible CSVs:

- **chirp‑to‑libib** — scrapes your [Chirp Books](https://www.chirpbooks.com) audiobook library
- **kindle‑to‑libib** — scrapes your [Amazon Kindle](https://www.amazon.com/hz/mycd/digital-console/contentlist/booksAll/dateDsc/) ebook library

Both tools share a common `lib/` layer for ISBN resolution, deduplication, and filtering.

---

# Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Shared Modules](#shared-modules)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Credentials](#credentials)
- [Usage](#usage)
- [Options](#options)
- [Output Files](#output-files)
- [Importing into Libib](#importing-into-libib)
- [Configuration](#configuration)
- [Development Workflow](#development-workflow)
- [Makefile Tasks](#makefile-tasks)
- [Troubleshooting](#troubleshooting)
- [Privacy](#privacy)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Versioning](#versioning)
- [License](#license)

---

# Overview

LibibTools automates the process of exporting your digital book libraries into a format compatible with **Libib**, including:

- Automated login via Selenium
- Full multi-page library scraping
- ISBN lookup via Open Library with retry and fallback logic
- High‑resolution cover URL extraction
- CSV generation (UTF‑8 with BOM)
- Unresolved ISBN reporting

Both scrapers share a common library (`lib/`) for all ISBN resolution, deduplication, and filtering logic, keeping provider-specific code minimal and focused.

---

# Features

- Secure credential handling (env vars or interactive prompt)
- Multi‑page scraping with configurable page limits
- ISBN resolution with author+title and title-only fallback
- Standards‑compliant CSV output
- Full‑resolution cover URLs
- Deduplication and invalid entry filtering
- Automated tests with CI
- Coverage reporting
- Configurable runtime behavior

---

## Shared Modules

The `lib/` directory contains shared logic used by all providers:

- **`lib/openlibrary.py`** — Open Library ISBN lookup with exponential backoff, title plausibility matching, and ISBN-10/ISBN-13 validation
- **`lib/__init__.py`** — Re-exports `get_isbn`, `sleep_between_requests`, `dedupe_books_by_title`, and `filter_invalid_books` for clean provider imports

---

# Architecture

```
+---------------------------+     +---------------------------+
|  chirp_to_libib CLI       |     |  kindle_to_libib CLI      |
|  __main__.py / core.py    |     |  __main__.py / core.py    |
|  - Selenium login         |     |  - Selenium login         |
|  - Chirp page scraping    |     |  - Kindle page scraping   |
+------------+--------------+     +-------------+-------------+
             |                                  |
             +----------------+-----------------+
                              |
                              v
             +----------------+-----------------+
             |            lib/                  |
             |  - ISBN lookup (Open Library)    |
             |  - Retry / exponential backoff   |
             |  - Title plausibility matching   |
             |  - Deduplication                 |
             |  - Invalid entry filtering       |
             +----------------------------------+
                              |
                              v
             +----------------------------------+
             |         Output Artifacts         |
             |  CSV + unresolved ISBN log       |
             +----------------------------------+
```

Key design principles:

- **DRY**: All shared logic lives in `lib/` — no duplication between providers
- **Idempotent**: Running multiple times produces predictable results
- **Observable**: Structured logging at key checkpoints throughout the pipeline
- **Extensible**: Adding a new provider (e.g., Audible) requires only a new `core.py` consuming the shared `lib/`

---

# Requirements

- Python **3.10+**
- Google Chrome installed
- `webdriver-manager` (installed via `requirements.txt`)

---

# Installation

```bash
git clone https://github.com/Jinniyah/LibibTools.git
cd LibibTools

python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

---

# Credentials

Set credentials as environment variables before running. If not set, the script will prompt interactively.

### Chirp

#### macOS / Linux
```bash
export CHIRP_EMAIL="you@example.com"
export CHIRP_PASSWORD="yourpassword"
```

#### Windows
```cmd
set CHIRP_EMAIL=you@example.com
set CHIRP_PASSWORD=yourpassword
```

### Kindle

#### macOS / Linux
```bash
export KINDLE_EMAIL="you@example.com"
export KINDLE_PASSWORD="yourpassword"
```

#### Windows
```cmd
set KINDLE_EMAIL=you@example.com
set KINDLE_PASSWORD=yourpassword
```

---

# Usage

### Chirp — Full scrape
```bash
python -m chirp_to_libib
```

### Kindle — Full scrape
```bash
python -m kindle_to_libib
```

### Limit to N pages
```bash
python -m chirp_to_libib --pages 3
python -m kindle_to_libib --pages 3
```

### Dry run (resolve ISBNs but do not write files)
```bash
python -m chirp_to_libib --dry-run
python -m kindle_to_libib --dry-run
```

### Custom output directory
```bash
python -m chirp_to_libib --output-dir ~/Documents/Libib
python -m kindle_to_libib --output-dir ~/Documents/Libib
```

---

# Options

Both providers support the same CLI flags:

| Option | Description |
|--------|-------------|
| `--pages N` | Scrape only the first N pages |
| `--dry-run` | Resolve ISBNs but do not write output files |
| `--output-dir PATH` | Directory for output files (default: current directory) |

---

# Output Files

### Chirp

| File | Description |
|------|-------------|
| `chirp_to_libib_YYYY-MM-DD_HH-MM.csv` | Libib‑compatible CSV |
| `chirp_to_libib_unresolved_YYYY-MM-DD_HH-MM.txt` | Titles with missing ISBNs |

### Kindle

| File | Description |
|------|-------------|
| `kindle_to_libib_YYYY-MM-DD_HH-MM.csv` | Libib‑compatible CSV |
| `kindle_to_libib_unresolved_YYYY-MM-DD_HH-MM.txt` | Titles with missing ISBNs |

### CSV Columns

| Column | Description |
|--------|-------------|
| Title | Book title |
| Creator | Author(s) |
| Identifier | ISBN‑13 (preferred) or ISBN‑10 |
| Type | `chirp,audiobook` for Chirp; `kindle,ebook` for Kindle |
| Image | Full‑resolution cover URL |

---

# Importing into Libib

1. Log in at <https://www.libib.com>
2. Open your library
3. **Add Items → Import CSV**
4. Upload the generated CSV
5. Map columns if prompted

---

# Configuration

### `lib/openlibrary.py`

| Constant | Default | Description |
|----------|---------|-------------|
| `ISBN_DELAY_RANGE` | `(0.8, 1.6)` | Randomized delay range between API requests (seconds) |

### `chirp_to_libib/core.py` and `kindle_to_libib/core.py`

| Constant | Default | Description |
|----------|---------|-------------|
| `ISBN_LOG_INTERVAL` | `25` | Log ISBN progress every N books |
| `PAGE_WAIT_TIMEOUT` | `20` | Selenium wait timeout (seconds) |

---

# Development Workflow

### Install dev dependencies

```bash
pip install -r requirements-dev.txt
```

### Run tests

```bash
pytest
```

### Run coverage

```bash
# Chirp
pytest --cov=chirp_to_libib --cov-report=term-missing

# Kindle
pytest --cov=kindle_to_libib --cov-report=term-missing
```

### Linting

```bash
ruff check .
```

### Formatting

```bash
black .
```

### Type checking

```bash
mypy chirp_to_libib kindle_to_libib lib
```

---

# Makefile Tasks

```bash
make test        # run tests
make lint        # run ruff
make format      # run black
make typecheck   # run mypy
make coverage    # run full coverage suite
```

---

# Troubleshooting

**Login fails**
Provider may have updated their login page. Update the relevant selectors in `core.py`.

**No books scraped**
HTML structure may have changed. Update parsing logic in `_parse_items`.

**ChromeDriver mismatch**
```bash
pip install --upgrade webdriver-manager
```

**Missing ISBNs**
Open Library coverage varies by title. Use the unresolved report for manual lookup.

---

# Privacy

- Only Chirp, Amazon, and Open Library are contacted during a run
- Output files contain personal library data and are excluded via `.gitignore`
- Credentials are never written to disk
- Credentials are deleted from memory immediately after the scrape completes

---

# Project Structure

```text
LibibTools/
├── chirp_to_libib/
│   ├── __init__.py
│   ├── __main__.py
│   └── core.py
├── kindle_to_libib/
│   ├── __init__.py
│   ├── __main__.py
│   └── core.py
├── lib/
│   ├── __init__.py
│   └── openlibrary.py
├── tests/
│   ├── test_chirp.py
│   ├── test_cli.py
│   ├── test_dedupe_filter.py
│   ├── test_isbn_utils.py
│   ├── test_kindle.py
│   ├── test_openlibrary.py
│   ├── test_output.py
│   ├── test_pipeline.py
│   └── test_scrape.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Makefile
└── README.md
```

---

# Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch
3. Write tests for any new behavior
4. Ensure linting, formatting, and type checks pass
5. Submit a pull request

---

# Versioning

This project follows **Semantic Versioning (SemVer)**:

```
MAJOR.MINOR.PATCH
```

- **MAJOR**: Breaking changes
- **MINOR**: New features
- **PATCH**: Bug fixes

---

# License

MIT — see `LICENSE`.
