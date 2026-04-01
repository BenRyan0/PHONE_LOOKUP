"""Domain accessibility checking with robots.txt awareness."""

import logging
import urllib.robotparser
from dataclasses import dataclass, field

import requests

from config import REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

HEADERS: dict[str, str] = {"User-Agent": USER_AGENT}


@dataclass
class DomainCheckResult:
    """Result of checking whether a domain hosts an accessible website."""

    domain: str
    reachable: bool
    base_url: str | None  # The URL that responded (https or http)
    status_code: int | None
    error: str | None
    disallowed_paths: list[str] = field(default_factory=list)


def check_domain(domain: str) -> DomainCheckResult:
    """Try HTTPS then HTTP for a domain and return the first successful response.

    Args:
        domain: The bare domain name, e.g. ``acmecorp.com``.

    Returns:
        A DomainCheckResult describing reachability and the resolved URL.
    """
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if response.status_code == 200:
                logger.info("Domain reachable: %s → %s", domain, response.url)
                disallowed = _get_disallowed_paths(domain, scheme)
                return DomainCheckResult(
                    domain=domain,
                    reachable=True,
                    base_url=f"{scheme}://{domain}",
                    status_code=response.status_code,
                    error=None,
                    disallowed_paths=disallowed,
                )
            logger.debug(
                "Non-200 response from %s: %d", url, response.status_code
            )
        except requests.exceptions.Timeout:
            logger.warning("Timeout reaching %s", url)
        except requests.exceptions.ConnectionError as exc:
            logger.debug("Connection error for %s: %s", url, exc)
        except requests.exceptions.RequestException as exc:
            logger.debug("Request error for %s: %s", url, exc)

    logger.warning("Domain unreachable: %s", domain)
    return DomainCheckResult(
        domain=domain,
        reachable=False,
        base_url=None,
        status_code=None,
        error="Domain unreachable via HTTPS and HTTP",
    )


def _get_disallowed_paths(domain: str, scheme: str) -> list[str]:
    """Fetch and parse robots.txt for the domain.

    Args:
        domain: The bare domain name.
        scheme: Either ``"https"`` or ``"http"``.

    Returns:
        List of path prefixes disallowed for the configured User-Agent.
    """
    robots_url = f"{scheme}://{domain}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        logger.debug("Could not read robots.txt for %s: %s", domain, exc)
        return []

    # urllib.robotparser doesn't expose a simple list of rules, so we
    # re-fetch to extract disallowed paths ourselves for reporting.
    disallowed: list[str] = []
    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        for line in resp.text.splitlines():
            line = line.strip()
            if line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    disallowed.append(path)
    except Exception:
        pass
    return disallowed


def is_path_allowed(base_url: str, path: str, disallowed_paths: list[str]) -> bool:
    """Check whether a path is allowed by the site's robots.txt rules.

    Args:
        base_url: The scheme + domain, e.g. ``https://acmecorp.com``.
        path: The path to check, e.g. ``/contact``.
        disallowed_paths: List of disallowed path prefixes from robots.txt.

    Returns:
        ``True`` if the path may be crawled, ``False`` otherwise.
    """
    for disallowed in disallowed_paths:
        if path.startswith(disallowed):
            logger.debug("Path %s disallowed by robots.txt (%s)", path, disallowed)
            return False
    return True
