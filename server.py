"""FastAPI server exposing the phone finder pipeline via HTTP POST."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import LOG_LEVEL
from email_parser import parse_email
from website_checker import check_domain
from scraper import scrape_domain
from analyzer import analyze_scrape

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Thread pool for running blocking scrape/analysis work concurrently.
# I/O-bound work (HTTP + OpenAI) scales well beyond core count.
# 16 cores × 2 threads/core = 32 logical CPUs → 20 threads per worker
# gives up to 16 workers × 20 threads = 320 concurrent pipelines.
_executor = ThreadPoolExecutor(max_workers=20)

app = FastAPI(
    title="Phone Finder API",
    description="Extract phone numbers from business websites via email domains.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LookupRequest(BaseModel):
    """Accepts a single email address."""
    email: str


class PhoneResult(BaseModel):
    number: str
    format: str
    source_page: str
    confidence: str


class EmailResult(BaseModel):
    email: str
    domain: Optional[str]
    website_accessible: bool
    website_url: Optional[str]
    phone_numbers: list[PhoneResult]
    skipped: bool
    skip_reason: Optional[str]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.post("/lookup", response_model=EmailResult)
async def lookup(request: LookupRequest) -> EmailResult:
    """Process a single email address and return extracted phone numbers.

    Runs the blocking scrape + OpenAI pipeline in a thread pool so the
    server can handle multiple simultaneous requests without stalling.
    """
    if not request.email.strip():
        raise HTTPException(status_code=422, detail="Email address is required.")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _process_single, request.email)


def _process_single(raw_email: str) -> EmailResult:
    """Run the full pipeline for one email and return a structured result."""
    parsed = parse_email(raw_email)

    base = EmailResult(
        email=parsed.email,
        domain=parsed.domain,
        website_accessible=False,
        website_url=None,
        phone_numbers=[],
        skipped=False,
        skip_reason=None,
        error=None,
    )

    if not parsed.is_valid or parsed.is_blocked:
        base.skipped = True
        base.skip_reason = parsed.skip_reason
        return base

    try:
        check = check_domain(parsed.domain)  # type: ignore[arg-type]
        base.website_accessible = check.reachable
        base.website_url = check.base_url

        if not check.reachable:
            base.error = check.error
            return base

        scrape = scrape_domain(check)
        analysis = analyze_scrape(scrape)

        if analysis.error:
            base.error = analysis.error
            return base

        base.phone_numbers = [
            PhoneResult(
                number=p.number,
                format=p.format,
                source_page=p.source_page,
                confidence=p.confidence,
            )
            for p in analysis.phone_numbers
        ]

    except Exception as exc:
        logger.exception("Unexpected error processing %s", parsed.email)
        base.error = str(exc)

    return base


# ---------------------------------------------------------------------------
# Run directly: python server.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=57439, reload=False, workers=16)
