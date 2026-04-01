"""Email validation and domain extraction."""

import logging
from dataclasses import dataclass

import validators

from config import BLOCKED_EMAIL_PROVIDERS

logger = logging.getLogger(__name__)


@dataclass
class EmailParseResult:
    """Result of parsing a single email address."""

    email: str
    domain: str | None
    is_valid: bool
    is_blocked: bool
    skip_reason: str | None


def parse_email(email: str) -> EmailParseResult:
    """Validate an email address and extract its domain.

    Args:
        email: The raw email address string to parse.

    Returns:
        An EmailParseResult with validation status and extracted domain.
    """
    email = email.strip().lower()

    if not validators.email(email):
        logger.warning("Invalid email format: %s", email)
        return EmailParseResult(
            email=email,
            domain=None,
            is_valid=False,
            is_blocked=False,
            skip_reason="Invalid email format",
        )

    domain = email.split("@", 1)[1]

    if domain in BLOCKED_EMAIL_PROVIDERS:
        logger.info("Skipping free/personal email provider: %s (%s)", email, domain)
        return EmailParseResult(
            email=email,
            domain=domain,
            is_valid=True,
            is_blocked=True,
            skip_reason=f"Free/personal email provider: {domain}",
        )

    return EmailParseResult(
        email=email,
        domain=domain,
        is_valid=True,
        is_blocked=False,
        skip_reason=None,
    )


def parse_emails(raw: str) -> list[EmailParseResult]:
    """Parse a comma-separated string of email addresses.

    Args:
        raw: Comma-separated email addresses.

    Returns:
        List of EmailParseResult, one per input address.
    """
    return [parse_email(e) for e in raw.split(",") if e.strip()]


def load_emails_from_file(path: str) -> list[EmailParseResult]:
    """Read email addresses from a file (one per line) and parse them.

    Args:
        path: Path to the file containing email addresses.

    Returns:
        List of EmailParseResult for each non-empty line.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    with open(path, encoding="utf-8") as fh:
        lines = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    logger.debug("Loaded %d email(s) from %s", len(lines), path)
    return [parse_email(line) for line in lines]
