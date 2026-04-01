"""Tests for scraper module."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch

import pytest

from scraper import _extract_text, _fetch_page, scrape_domain
from website_checker import DomainCheckResult


class TestExtractText:
    def test_removes_script_tags(self):
        html = "<html><body><script>var x=1;</script><p>Hello</p></body></html>"
        text = _extract_text(html)
        assert "var x=1" not in text
        assert "Hello" in text

    def test_removes_style_tags(self):
        html = "<html><body><style>.btn{color:red}</style><p>Content</p></body></html>"
        text = _extract_text(html)
        assert ".btn" not in text
        assert "Content" in text

    def test_collapses_blank_lines(self):
        html = "<html><body><p>A</p><p></p><p></p><p>B</p></body></html>"
        text = _extract_text(html)
        assert "\n\n\n" not in text

    def test_extracts_phone_like_text(self):
        html = "<html><body><p>Call us: +1 (800) 555-1234</p></body></html>"
        text = _extract_text(html)
        assert "+1 (800) 555-1234" in text


class TestFetchPage:
    def _mock_response(self, status: int, content: str = "<p>Hello</p>") -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.text = content
        return resp

    @patch("scraper.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_get.return_value = self._mock_response(200, "<p>Hello world</p>")
        page = _fetch_page("https://example.com/contact")
        assert page.success is True
        assert "Hello world" in page.text
        assert page.error is None

    @patch("scraper.requests.get")
    def test_non_200_returns_failure(self, mock_get):
        mock_get.return_value = self._mock_response(404)
        page = _fetch_page("https://example.com/missing")
        assert page.success is False
        assert "404" in page.error

    @patch("scraper.requests.get")
    def test_timeout_returns_failure(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout()
        page = _fetch_page("https://example.com/slow")
        assert page.success is False
        assert page.error == "Timeout"


class TestScrapeDomain:
    def _make_check(self, reachable: bool = True) -> DomainCheckResult:
        return DomainCheckResult(
            domain="example.com",
            reachable=reachable,
            base_url="https://example.com" if reachable else None,
            status_code=200 if reachable else None,
            error=None if reachable else "Unreachable",
            disallowed_paths=[],
        )

    def test_unreachable_domain_returns_empty(self):
        check = self._make_check(reachable=False)
        result = scrape_domain(check)
        assert result.pages == []

    @patch("scraper.time.sleep")
    @patch("scraper._fetch_page")
    def test_scrapes_multiple_pages(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = MagicMock(success=True, text="some text", url="https://example.com/")
        check = self._make_check()
        result = scrape_domain(check)
        # Should attempt homepage + CONTACT_PATHS
        assert mock_fetch.call_count >= 1
        assert len(result.pages) >= 1

    @patch("scraper.time.sleep")
    @patch("scraper._fetch_page")
    def test_combined_text_contains_source_markers(self, mock_fetch, mock_sleep):
        def make_page(url):
            p = MagicMock()
            p.success = True
            p.text = "Phone: 555-1234"
            p.url = url
            return p

        mock_fetch.side_effect = make_page
        check = self._make_check()
        result = scrape_domain(check)
        assert "[Source:" in result.combined_text
