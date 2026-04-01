"""Web scraping logic for collecting page text content."""

import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import CONTACT_PATHS, MAX_PAGES_PER_DOMAIN, REQUEST_TIMEOUT, USER_AGENT, get_request_delay
from website_checker import DomainCheckResult, is_path_allowed

logger = logging.getLogger(__name__)

HEADERS: dict[str, str] = {"User-Agent": USER_AGENT}

# Keywords that suggest a link leads to a page with contact/phone info
_RELEVANT_KEYWORDS: re.Pattern = re.compile(
    r"contact|about|info|imprint|impressum|team|support|help|"
    r"reach|touch|company|legal|faq|phone|address|location|office|headquarters",
    re.IGNORECASE,
)


@dataclass
class PageContent:
    """Text content scraped from a single page."""

    url: str
    text: str
    success: bool
    error: str | None = None


@dataclass
class ScrapeResult:
    """Aggregated scraping result for a single domain."""

    domain: str
    pages: list[PageContent] = field(default_factory=list)

    @property
    def combined_text(self) -> str:
        """Concatenate all successfully scraped page texts."""
        return "\n\n---\n\n".join(
            f"[Source: {p.url}]\n{p.text}" for p in self.pages if p.success
        )

    @property
    def successful_urls(self) -> list[str]:
        """List of URLs that were scraped successfully."""
        return [p.url for p in self.pages if p.success]


def scrape_domain(check: DomainCheckResult) -> ScrapeResult:
    """Scrape the homepage then follow relevant links discovered on it.

    Strategy:
    1. Fetch the homepage and collect its text.
    2. Parse all internal links from the homepage HTML.
    3. Score each link by how well its href/anchor text matches contact-
       related keywords and pick the top candidates.
    4. Fall back to the hardcoded CONTACT_PATHS for any slots still
       available if the homepage yielded few useful links.

    Respects robots.txt rules stored in *check* and inserts random delays
    between requests.

    Args:
        check: A successful DomainCheckResult with ``base_url`` set.

    Returns:
        A ScrapeResult containing text content from all scraped pages.
    """
    result = ScrapeResult(domain=check.domain)

    if not check.reachable or not check.base_url:
        logger.error("Cannot scrape unreachable domain: %s", check.domain)
        return result

    # --- Step 1: fetch homepage ---
    homepage_url = check.base_url + "/"
    homepage_resp = _fetch_raw(homepage_url)
    if homepage_resp is None:
        logger.warning("Could not fetch homepage for %s", check.domain)
        return result

    homepage_text = _extract_text(homepage_resp)
    result.pages.append(PageContent(url=homepage_url, text=homepage_text, success=True))
    logger.debug("Fetched homepage for %s (%d chars)", check.domain, len(homepage_text))

    # --- Step 2: discover relevant links from the homepage ---
    discovered = _discover_relevant_links(homepage_resp, check.base_url)
    logger.info(
        "Discovered %d relevant link(s) on homepage of %s", len(discovered), check.domain
    )

    # --- Step 3: fill remaining slots with fallback paths ---
    visited: set[str] = {homepage_url}
    urls_to_scrape = _merge_urls(discovered, check.base_url, visited)

    scraped_count = 1  # homepage already done
    for url in urls_to_scrape:
        if scraped_count >= MAX_PAGES_PER_DOMAIN:
            logger.debug("Reached max pages (%d) for %s", MAX_PAGES_PER_DOMAIN, check.domain)
            break

        path = urlparse(url).path or "/"
        if not is_path_allowed(check.base_url, path, check.disallowed_paths):
            logger.info("Skipping disallowed path: %s", url)
            continue

        if url in visited:
            continue
        visited.add(url)

        time.sleep(get_request_delay())
        page = _fetch_page(url)
        result.pages.append(page)
        if page.success:
            scraped_count += 1

    logger.info("Scraped %d page(s) from %s", scraped_count, check.domain)
    return result


def _discover_relevant_links(html: str, base_url: str) -> list[str]:
    """Parse a page's HTML and return internal links that look contact-related.

    Links are ranked by the number of keyword matches in their href and
    anchor text, then deduplicated.

    Args:
        html: Raw HTML of the page to parse.
        base_url: Scheme + domain used to resolve relative URLs and filter
                  out external links.

    Returns:
        Ordered list of absolute URLs, best matches first.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href: str = tag["href"].strip()

        # Skip anchors, mailto, tel, javascript
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        abs_url = urljoin(base_url, href).split("#")[0].rstrip("/")

        # Only follow internal links
        if urlparse(abs_url).netloc != base_host:
            continue

        if abs_url in seen:
            continue
        seen.add(abs_url)

        anchor_text = tag.get_text(" ", strip=True)
        combined = f"{href} {anchor_text}"
        matches = len(_RELEVANT_KEYWORDS.findall(combined))
        if matches > 0:
            scored.append((matches, abs_url))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in scored]


def _merge_urls(discovered: list[str], base_url: str, visited: set[str]) -> list[str]:
    """Combine discovered links with hardcoded fallback paths.

    Discovered links come first (they are real links from the site).
    Fallback paths fill remaining capacity without duplicating anything
    already in the discovered list.

    Args:
        discovered: Absolute URLs found on the homepage.
        base_url: Used to construct fallback absolute URLs.
        visited: URLs already fetched (excluded from output).

    Returns:
        Deduplicated list of absolute URLs to scrape, discovered first.
    """
    result: list[str] = []
    seen: set[str] = set(visited)

    for url in discovered:
        if url not in seen:
            seen.add(url)
            result.append(url)

    for path in CONTACT_PATHS:
        url = base_url + path
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


def _fetch_raw(url: str) -> str | None:
    """Fetch a URL and return the raw HTML, or None on failure.

    Args:
        url: The URL to fetch.

    Returns:
        Raw HTML string, or None if the request failed.
    """
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
        if response.status_code == 200:
            return response.text
        logger.debug("Non-200 from %s: %d", url, response.status_code)
    except requests.exceptions.RequestException as exc:
        logger.warning("Error fetching %s: %s", url, exc)
    return None


def _fetch_page(url: str) -> PageContent:
    """Fetch a single page and return its extracted text content.

    Args:
        url: The full URL to fetch.

    Returns:
        A PageContent with the extracted text or an error message.
    """
    raw = _fetch_raw(url)
    if raw is None:
        return PageContent(url=url, text="", success=False, error="Fetch failed")
    text = _extract_text(raw)
    logger.debug("Fetched %s (%d chars)", url, len(text))
    return PageContent(url=url, text=text, success=True)


def _extract_text(html: str) -> str:
    """Parse HTML and return clean visible text.

    Removes script, style, nav, footer, and header tags before extracting
    text to reduce noise in the content sent to OpenAI.

    Args:
        html: Raw HTML source.

    Returns:
        Cleaned plain-text string.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "meta"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    return "\n".join(cleaned).strip()
