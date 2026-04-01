# Phone Finder — Developer Notes

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # then add your OPENAI_API_KEY
```

## Running
```bash
python main.py --email john@acmecorp.com
python main.py --emails john@acmecorp.com,jane@techstartup.io
python main.py --file emails.txt --output results.csv
python main.py --file emails.txt --verbose
python main.py --file emails.txt --dry-run
```

## Tests
```bash
python -m pytest tests/ -v
```

## Module Responsibilities
| File | Responsibility |
|------|---------------|
| `config.py` | All env vars, constants, blocked providers list |
| `email_parser.py` | Validate email format, filter blocked domains, extract domain |
| `website_checker.py` | HTTPS/HTTP probe, robots.txt parsing |
| `scraper.py` | Fetch homepage + contact pages, extract visible text |
| `analyzer.py` | Send text to OpenAI, parse structured JSON response |
| `output.py` | Console table + CSV export |
| `main.py` | CLI arg parsing, orchestration |

## Key Design Decisions
- OpenAI response format is `json_object` — the model always returns valid JSON.
- Scraped text is truncated to 15,000 chars before sending to GPT to stay within token budget.
- robots.txt disallowed paths are checked per-request before scraping.
- Random 1–3 s delays between page fetches (overridable via `DELAY_BETWEEN_REQUESTS`).
