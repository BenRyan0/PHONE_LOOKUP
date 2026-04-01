"""OpenAI-powered phone number extraction from scraped text."""

import json
import logging
import time
from dataclasses import dataclass, field

from openai import OpenAI, RateLimitError, APIError, APIConnectionError

from config import OPENAI_API_KEY, OPENAI_MODEL
from scraper import ScrapeResult

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI client, creating it on first call."""
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


@dataclass
class PhoneNumber:
    """A single extracted phone number with metadata."""

    number: str
    format: str          # "local" | "international" | "unknown"
    source_page: str
    confidence: str      # "high" | "medium" | "low"


@dataclass
class AnalysisResult:
    """Phone extraction result for a single domain."""

    domain: str
    phone_numbers: list[PhoneNumber] = field(default_factory=list)
    error: str | None = None

    @property
    def has_results(self) -> bool:
        return bool(self.phone_numbers)


_SYSTEM_PROMPT = """\
You are a precise data extraction assistant. Your task is to find all phone numbers
present in the provided website text content.

For each phone number found, return a JSON array where every element has:
  - "number": the phone number as written on the page (preserve original formatting)
  - "format": one of "local", "international", or "unknown"
  - "source_page": the URL of the page where the number was found (use the [Source: URL] markers)
  - "confidence": one of "high", "medium", or "low" based on context clarity

Rules:
- Only include numbers that are clearly presented as contact phone numbers.
- Do not include order numbers, ZIP codes, or other numerical strings.
- If no phone numbers are found, return an empty array [].
- Respond with ONLY the JSON array. No explanation, no markdown fences.
"""


def analyze_scrape(scrape: ScrapeResult, max_retries: int = 3) -> AnalysisResult:
    """Send scraped text to OpenAI and extract structured phone number data.

    Args:
        scrape: The scraping result containing page text and source URLs.
        max_retries: Number of retry attempts on rate-limit errors.

    Returns:
        An AnalysisResult with extracted phone numbers or an error message.
    """
    if not scrape.combined_text.strip():
        logger.warning("No text content to analyze for %s", scrape.domain)
        return AnalysisResult(domain=scrape.domain, error="No text content scraped")

    # Truncate to ~15k chars to stay within token limits
    text_for_analysis = scrape.combined_text[:15_000]

    client = _get_client()

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(
                "Sending %d chars to OpenAI for %s (attempt %d)",
                len(text_for_analysis),
                scrape.domain,
                attempt,
            )
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text_for_analysis},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content or "[]"
            return _parse_response(scrape.domain, raw)

        except RateLimitError:
            wait = 2 ** attempt
            logger.warning(
                "OpenAI rate limit hit for %s, retrying in %ds (attempt %d/%d)",
                scrape.domain, wait, attempt, max_retries,
            )
            time.sleep(wait)

        except APIConnectionError as exc:
            logger.error("OpenAI connection error for %s: %s", scrape.domain, exc)
            return AnalysisResult(domain=scrape.domain, error=f"Connection error: {exc}")

        except APIError as exc:
            logger.error("OpenAI API error for %s: %s", scrape.domain, exc)
            return AnalysisResult(domain=scrape.domain, error=f"API error: {exc}")

    return AnalysisResult(
        domain=scrape.domain,
        error="OpenAI rate limit exceeded after all retries",
    )


def _parse_response(domain: str, raw: str) -> AnalysisResult:
    """Parse the JSON response from OpenAI into PhoneNumber objects.

    Args:
        domain: The domain being analyzed (for error reporting).
        raw: The raw JSON string returned by the model.

    Returns:
        An AnalysisResult with parsed PhoneNumber entries.
    """
    try:
        data = json.loads(raw)
        # The model may return {"numbers": [...]} or just [...]
        if isinstance(data, dict):
            entries = next(
                (v for v in data.values() if isinstance(v, list)), []
            )
        elif isinstance(data, list):
            entries = data
        else:
            entries = []

        phones: list[PhoneNumber] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            phones.append(
                PhoneNumber(
                    number=str(item.get("number", "")).strip(),
                    format=str(item.get("format", "unknown")).strip(),
                    source_page=str(item.get("source_page", "")).strip(),
                    confidence=str(item.get("confidence", "low")).strip(),
                )
            )

        logger.info("Extracted %d phone number(s) for %s", len(phones), domain)
        return AnalysisResult(domain=domain, phone_numbers=phones)

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse OpenAI response for %s: %s", domain, exc)
        return AnalysisResult(domain=domain, error=f"JSON parse error: {exc}")
