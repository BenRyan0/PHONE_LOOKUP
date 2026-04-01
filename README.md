# Phone Finder

Extract phone numbers from business websites using email domains + OpenAI.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env      # add your OPENAI_API_KEY
python main.py --email john@acmecorp.com
```

## Usage

```bash
# Single email
python main.py --email john@acmecorp.com

# Multiple emails (comma-separated)
python main.py --emails john@acmecorp.com,jane@techstartup.io

# From file (one email per line, # lines are comments)
python main.py --file emails.txt

# Export to CSV
python main.py --file emails.txt --output results.csv

# Verbose output (shows source URL per phone number + debug logs)
python main.py --file emails.txt --verbose

# Dry run (shows what would be processed, no scraping)
python main.py --file emails.txt --dry-run
```

## How It Works

1. Validates email addresses and filters out free providers (Gmail, Outlook, etc.)
2. Checks if the business domain has an accessible website (HTTPS first, then HTTP)
3. Scrapes the homepage + common contact pages (`/contact`, `/about`, etc.)
4. Sends the collected text to GPT-4o-mini to extract phone numbers as structured JSON
5. Displays results as a table; optionally exports to CSV

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `REQUEST_TIMEOUT` | `10` | HTTP request timeout in seconds |
| `MAX_PAGES_PER_DOMAIN` | `6` | Max pages to scrape per domain |
| `DELAY_BETWEEN_REQUESTS` | random 1–3s | Fixed delay (seconds) between page fetches |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |

## CSV Output Columns

`email`, `domain`, `website_accessible`, `website_url`, `phone_numbers`, `confidence`, `source_page`, `notes`

## Running Tests

```bash
python -m pytest tests/ -v
```
