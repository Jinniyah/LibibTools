# LibibTools

![Tests](https://github.com/Jinniyah/LibibTools/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-generated-blue)

Tools for automating and enriching personal library management workflows.  
This repository currently includes **chirp‑to‑libib**, a Python package that scrapes your **Chirp Books** audiobook library and exports a Libib‑compatible CSV.

---

# Table of Contents

- [Overview](#overview)
- [Features](#features)
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

`chirp‑to‑libib` automates the process of exporting your Chirp Books audiobook library into a format compatible with **Libib**, including:

- Automated login via Selenium  
- Scraping your full Chirp library  
- ISBN lookup via Open Library  
- High‑resolution cover extraction  
- CSV generation (UTF‑8 with BOM)  
- Unresolved ISBN reporting  

This tool is designed for reliability, repeatability, and long‑term maintainability.

---

# Features

- 🔐 Secure credential handling  
- 🧭 Multi‑page scraping  
- 🔎 ISBN resolution with fallback logic  
- 📦 Standards‑compliant CSV output  
- 🖼 Full‑resolution cover URLs  
- 🧪 Automated tests with CI  
- 📊 Coverage reporting  
- 🛠 Configurable runtime behavior  

---

# Architecture

```
+-----------------------+
|  User CLI Invocation  |
+-----------+-----------+
            |
            v
+-----------------------+
|   __main__.py         |
|   Argument parsing     |
+-----------+-----------+
            |
            v
+-----------------------+
|       core.py         |
|  - Selenium login      |
|  - Page scraping       |
|  - ISBN lookup         |
|  - CSV generation      |
+-----------+-----------+
            |
            v
+-----------------------+
|   Output Artifacts    |
|  CSV + unresolved log |
+-----------------------+
```

Key design principles:

- **Idempotent**: Running multiple times produces predictable results  
- **Observable**: Logging at key checkpoints  
- **Extensible**: Architecture supports future scrapers (e.g., Audible → Libib)  

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

Set your Chirp credentials as environment variables.

### macOS / Linux

```bash
export CHIRP_EMAIL="you@example.com"
export CHIRP_PASSWORD="yourpassword"
```

### Windows

```cmd
set CHIRP_EMAIL=you@example.com
set CHIRP_PASSWORD=yourpassword
```

If missing, the script will prompt interactively.

---

# Usage

### Full scrape

```bash
python -m chirp_to_libib
```

### Limit to N pages

```bash
python -m chirp_to_libib --pages 3
```

### Dry run

```bash
python -m chirp_to_libib --dry-run
```

### Custom output directory

```bash
python -m chirp_to_libib --output-dir ~/Documents/Libib
```

---

# Options

| Option | Description |
|--------|-------------|
| `--pages N` | Scrape only the first N pages |
| `--dry-run` | Resolve ISBNs but do not write files |
| `--output-dir PATH` | Directory for output files |

---

# Output Files

| File | Description |
|------|-------------|
| `chirp_to_libib_YYYY-MM-DD_HH-MM.csv` | Libib‑compatible CSV |
| `chirp_to_libib_unresolved_YYYY-MM-DD_HH-MM.txt` | Titles with missing ISBNs |

### CSV Columns

| Column | Description |
|--------|-------------|
| Title | Book title |
| Creator | Author(s) |
| Identifier | ISBN‑13 or ISBN‑10 |
| Type | Always `audiobook` |
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

Located in `chirp_to_libib/core.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `ISBN_REQUEST_DELAY` | `1.0` | Delay between API requests |
| `ISBN_LOG_INTERVAL` | `25` | Log progress every N books |
| `PAGE_WAIT_TIMEOUT` | `20` | Selenium wait timeout |

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
pytest --cov=chirp_to_libib --cov-report=term-missing
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
mypy chirp_to_libib
```

---

# Makefile Tasks

If you use the included Makefile:

```bash
make test        # run tests
make lint        # run ruff
make format      # run black
make typecheck   # run mypy
make coverage    # run coverage suite
```

---

# Troubleshooting

**Login fails**  
Chirp may have updated their login page. Update selectors.

**No books scraped**  
HTML structure may have changed. Update parsing logic.

**ChromeDriver mismatch**  
```bash
pip install --upgrade webdriver-manager
```

**Missing ISBNs**  
Open Library coverage varies. Use unresolved report for manual lookup.

---

# Privacy

- Only Chirp and Open Library are contacted  
- Output files contain personal library data and are ignored via `.gitignore`  
- Credentials are never written to disk  

---

# Project Structure

```text
LibibTools/
├── chirp_to_libib/
│   ├── __main__.py
│   ├── core.py
│   └── __init__.py
├── tests/
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
3. Write tests  
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