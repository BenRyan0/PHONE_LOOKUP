"""Tests for website_checker module."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch

import pytest
import requests

from website_checker import check_domain, is_path_allowed


class TestCheckDomain:
    def _mock_response(self, status_code: int, url: str = "") -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.url = url
        resp.text = ""
        return resp

    @patch("website_checker.requests.get")
    def test_https_success(self, mock_get):
        mock_get.return_value = self._mock_response(200, "https://acmecorp.com")
        result = check_domain("acmecorp.com")
        assert result.reachable is True
        assert result.base_url == "https://acmecorp.com"
        assert result.status_code == 200

    @patch("website_checker.requests.get")
    def test_https_fails_falls_back_to_http(self, mock_get):
        def side_effect(url, **kwargs):
            if url.startswith("https"):
                raise requests.exceptions.ConnectionError("refused")
            return self._mock_response(200, url)

        mock_get.side_effect = side_effect
        result = check_domain("acmecorp.com")
        assert result.reachable is True
        assert result.base_url == "http://acmecorp.com"

    @patch("website_checker.requests.get")
    def test_both_schemes_fail(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")
        result = check_domain("nonexistent-domain-xyz.com")
        assert result.reachable is False
        assert result.base_url is None
        assert result.error is not None

    @patch("website_checker.requests.get")
    def test_timeout_falls_back(self, mock_get):
        def side_effect(url, **kwargs):
            if url.startswith("https"):
                raise requests.exceptions.Timeout()
            return self._mock_response(200, url)

        mock_get.side_effect = side_effect
        result = check_domain("slowdomain.com")
        assert result.reachable is True

    @patch("website_checker.requests.get")
    def test_non_200_response(self, mock_get):
        mock_get.return_value = self._mock_response(404)
        result = check_domain("acmecorp.com")
        assert result.reachable is False


class TestIsPathAllowed:
    def test_allowed_path(self):
        assert is_path_allowed("https://example.com", "/contact", []) is True

    def test_disallowed_path(self):
        assert is_path_allowed("https://example.com", "/admin", ["/admin"]) is False

    def test_disallowed_prefix(self):
        assert is_path_allowed("https://example.com", "/admin/settings", ["/admin"]) is False

    def test_root_disallowed(self):
        assert is_path_allowed("https://example.com", "/contact", ["/"]) is False

    def test_unrelated_disallowed_path(self):
        assert is_path_allowed("https://example.com", "/contact", ["/private"]) is True
