"""Configuration and constants for the phone finder tool."""

import os
import random
from dotenv import load_dotenv

load_dotenv()

# OpenAI settings
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Request settings
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "10"))
MAX_PAGES_PER_DOMAIN: int = int(os.getenv("MAX_PAGES_PER_DOMAIN", "22"))
_delay_raw: str = os.getenv("DELAY_BETWEEN_REQUESTS", "")
DELAY_BETWEEN_REQUESTS: float = float(_delay_raw) if _delay_raw else 0.0  # 0 = random 1-3s

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# User-Agent header
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Free/personal email providers to skip
BLOCKED_EMAIL_PROVIDERS: set[str] = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "protonmail.com",
    "mail.com",
    "yahoo.co.uk",
    "yahoo.fr",
    "yahoo.de",
    "msn.com",
    "ymail.com",
    "inbox.com",
    "gmx.com",
    "gmx.net",
}

# Common paths to check for contact information
CONTACT_PATHS: list[str] = [
    "/contact",
    "/contact-us",
    "/contacts",
    "/contact-info",
    "/reach-us",
    "/get-in-touch",
    "/about",
    "/about-us",
    "/about-us/contact",
    "/our-team",
    "/team",
    "/info",
    "/information",
    "/company",
    "/company-info",
    "/support",
    "/help",
    "/faq",
    "/imprint",
    "/impressum",
    "/legal",
]


def get_request_delay() -> float:
    """Return the delay in seconds between requests.

    Uses the configured fixed delay if set, otherwise returns a random
    value between 1 and 3 seconds.
    """
    if DELAY_BETWEEN_REQUESTS > 0:
        return DELAY_BETWEEN_REQUESTS
    return random.uniform(1.0, 3.0)
