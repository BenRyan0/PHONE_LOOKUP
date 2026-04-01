"""Tests for email_parser module."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from email_parser import parse_email, parse_emails


class TestParseEmail:
    def test_valid_business_email(self):
        result = parse_email("john@acmecorp.com")
        assert result.is_valid is True
        assert result.is_blocked is False
        assert result.domain == "acmecorp.com"
        assert result.skip_reason is None

    def test_invalid_email_format(self):
        result = parse_email("not-an-email")
        assert result.is_valid is False
        assert result.domain is None
        assert result.skip_reason == "Invalid email format"

    def test_blocked_gmail(self):
        result = parse_email("user@gmail.com")
        assert result.is_valid is True
        assert result.is_blocked is True
        assert "gmail.com" in result.skip_reason

    def test_blocked_outlook(self):
        result = parse_email("user@outlook.com")
        assert result.is_blocked is True

    def test_blocked_yahoo(self):
        result = parse_email("user@yahoo.com")
        assert result.is_blocked is True

    def test_case_insensitive(self):
        result = parse_email("John@AcmeCorp.COM")
        assert result.email == "john@acmecorp.com"
        assert result.domain == "acmecorp.com"
        assert result.is_blocked is False

    def test_strips_whitespace(self):
        result = parse_email("  john@acmecorp.com  ")
        assert result.is_valid is True
        assert result.domain == "acmecorp.com"

    def test_email_with_plus(self):
        result = parse_email("john+tag@acmecorp.com")
        assert result.is_valid is True
        assert result.domain == "acmecorp.com"

    def test_subdomain_email(self):
        result = parse_email("john@mail.acmecorp.com")
        assert result.is_valid is True
        assert result.domain == "mail.acmecorp.com"


class TestParseEmails:
    def test_comma_separated(self):
        results = parse_emails("john@acmecorp.com,jane@techstartup.io")
        assert len(results) == 2
        assert results[0].domain == "acmecorp.com"
        assert results[1].domain == "techstartup.io"

    def test_single_email(self):
        results = parse_emails("john@acmecorp.com")
        assert len(results) == 1

    def test_ignores_empty_entries(self):
        results = parse_emails("john@acmecorp.com,,jane@techstartup.io")
        assert len(results) == 2

    def test_mixed_valid_and_blocked(self):
        results = parse_emails("john@acmecorp.com,user@gmail.com")
        assert results[0].is_blocked is False
        assert results[1].is_blocked is True
