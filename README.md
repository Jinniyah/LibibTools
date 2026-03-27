# LibibTools

![CI](https://github.com/Jinniyah/LibibTools/actions/workflows/tests.yml/badge.svg)

Web-scraping tool to get ebooks and audiobooks into Libib.

# chirp-to-libib

A Python script that scrapes your [Chirp](https://www.chirpbooks.com) audiobook library and exports a CSV you can import directly into [Libib](https://www.libib.com) to maintain your personal collection.

---

## What it does

1. Logs in to your Chirp account using a Chrome browser (automated via Selenium)
2. Scrapes your library for title, author, and cover image URL across one or more pages
3. Looks up each book's ISBN via the [Open Library API](https://openlibrary.org/developers/api)
4. Writes a Libib-compatible CSV ready for import
5. Writes a separate report of any titles whose ISBNs could not be found

---

## Requirements

- Python 3.10 or higher
- Google Chrome installed
- `webdriver-manager` (installed automatically via `requirements.txt`) — handles ChromeDriver installation for you, no manual setup needed

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-username/chirp-to-libib.git
cd chirp-to-libib
```

**2. Create and activate a virtual environment (recommended)**

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Setting up your credentials

Your Chirp email and password should **never** be typed into the script or committed to Git. Instead, set them as environment variables before running.

**macOS / Linux — current session only:**

```bash
export CHIRP_EMAIL="you@example.com"
export CHIRP_PASSWORD="yourpassword"
```

**macOS / Linux — permanent (add to `~/.zshrc` or `~/.bashrc`):**

```bash
export CHIRP_EMAIL="you@example.com"
export CHIRP_PASSWORD="yourpassword"
```

Then run `source ~/.zshrc` (or `~/.bashrc`) to apply.

**Windows — current session only (Command Prompt):**

```cmd
set CHIRP_EMAIL=you@example.com
set CHIRP_PASSWORD=yourpassword
```

**Windows — permanent:**

Search for **"Edit environment variables for your account"** in the Start menu,
then add `CHIRP_EMAIL` and `CHIRP_PASSWORD` under User Variables.

> If environment variables are not set, the script will prompt you to enter your
> credentials interactively each time it runs.

---

## Usage

**Basic — scrape full library and export CSV:**

```bash
python -m chirp_to_libib
```

**Scrape only the first N pages (useful for testing or incremental imports):**

```bash
python -m chirp_to_libib --pages 3
```

**Dry run — scrape and resolve ISBNs without writing any files:**

```bash
python -m chirp_to_libib --dry-run
```

**Write output files to a specific folder:**

```bash
python -m chirp_to_libib --output-dir ~/Documents/Libib
```

**Combine options:**

```bash
python -m chirp_to_libib --pages 3 --dry-run --output-dir ~/Documents/Libib
```

---

## Options

| Option | Description |
|--------|-------------|
| `--pages N` | Stop after scraping the first N pages. Omit to scrape all pages. |
| `--dry-run` | Scrape and resolve ISBNs, but do not write any output files. |
| `--output-dir PATH` | Directory to write output files to (default: current directory). |

---

## Output files

| File | Description |
|------|-------------|
| `chirp_to_libib_YYYY-MM-DD_HH-MM.csv` | Libib-compatible CSV — import this file |
| `chirp_to_libib_unresolved_YYYY-MM-DD_HH-MM.txt` | Titles with no ISBN found (only created if needed) |

The CSV is encoded as **UTF-8 with BOM**, which is the format Libib expects.

### CSV columns

| Column | Description |
|--------|-------------|
| Title | Book title |
| Creator | Author(s) as listed on Chirp |
| Identifier | ISBN-13 (preferred) or ISBN-10, if found |
| Type | Always `audiobook` |
| Image | Full-resolution cover URL |

> Rows with an empty Identifier will still import into Libib, but Libib won't be
> able to auto-fill metadata for those titles. Use the unresolved report to look
> them up manually.

---

## Importing into Libib

1. Log in to [libib.com](https://www.libib.com)
2. Open the library you want to update (or create a new one)
3. Click **Add Items → Import CSV**
4. Upload the generated `chirp_to_libib_*.csv` file
5. Map the columns if prompted and confirm the import

---

## Configuration

A few options can be changed directly in the script under the `CONFIGURATION` section at the top:

| Constant | Default | Description |
|----------|---------|-------------|
| `ISBN_REQUEST_DELAY` | `1.0` | Seconds to wait between Open Library requests |
| `ISBN_LOG_INTERVAL` | `25` | How often to log ISBN progress (every N books) |
| `PAGE_WAIT_TIMEOUT` | `20` | Selenium timeout in seconds for page elements |

---

## Troubleshooting

**Login fails silently or the script hangs at login**
Chirp may have updated their page structure. Check that the `email` and `password`
field IDs and the submit button selector still match the current login page.

**No books are scraped from the library**
Chirp may have updated their library page HTML. The selectors in `_parse_items()`
may need updating to match the current DOM structure.

**ChromeDriver version mismatch error**
The script uses `webdriver-manager` to handle ChromeDriver automatically. If you
see a version mismatch, try upgrading it:
```bash
pip install --upgrade webdriver-manager
```

**ISBNs are frequently wrong or missing**
Open Library's coverage of audiobooks is incomplete. ISBNs for audiobook editions
in particular are often absent. The unresolved report will list all affected titles
for manual follow-up. The script searches using separate `title` and `author`
fields for best accuracy, with a title-only fallback pass if the first search
returns nothing.

---

## Privacy

- No data is sent anywhere other than Chirp (to log in and scrape) and Open Library (for ISBN lookups).
- Output files may contain your personal library data. They are excluded from Git via `.gitignore` — do not remove those rules.
- Credentials are never written to disk by this script.

---

## License

MIT — see [LICENSE](LICENSE) for details.
