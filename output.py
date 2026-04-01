"""Console formatting and CSV export for phone extraction results."""

import csv
import io
import logging
from dataclasses import dataclass, field

from analyzer import AnalysisResult, PhoneNumber
from email_parser import EmailParseResult
from website_checker import DomainCheckResult

logger = logging.getLogger(__name__)

# ANSI colour codes (disabled when not a TTY)
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_RESET = "\033[0m"


@dataclass
class ProcessedEmail:
    """Full processing record for a single input email."""

    email_result: EmailParseResult
    domain_check: DomainCheckResult | None = None
    analysis: AnalysisResult | None = None
    skipped: bool = False
    skip_reason: str | None = None


def print_results(records: list[ProcessedEmail], verbose: bool = False) -> None:
    """Print a formatted summary table to stdout.

    Args:
        records: All processed email records.
        verbose: If True, print additional detail per phone number.
    """
    print()
    print(f"{_BOLD}{'=' * 72}{_RESET}")
    print(f"{_BOLD}  PHONE FINDER RESULTS{_RESET}")
    print(f"{_BOLD}{'=' * 72}{_RESET}")

    for rec in records:
        email = rec.email_result.email
        print(f"\n{_BOLD}Email:{_RESET} {email}")

        if rec.skipped:
            print(f"  {_YELLOW}Skipped:{_RESET} {rec.skip_reason}")
            continue

        check = rec.domain_check
        if check is None or not check.reachable:
            reason = check.error if check else "No domain check performed"
            print(f"  {_RED}Domain unreachable:{_RESET} {reason}")
            continue

        print(f"  {_GREEN}Domain:{_RESET} {check.base_url}")

        analysis = rec.analysis
        if analysis is None:
            print(f"  {_YELLOW}Analysis not performed{_RESET}")
            continue

        if analysis.error:
            print(f"  {_RED}Analysis error:{_RESET} {analysis.error}")
            continue

        if not analysis.phone_numbers:
            print(f"  {_YELLOW}No phone numbers found{_RESET}")
            continue

        print(f"  {_CYAN}Phone numbers found:{_RESET}")
        _print_phone_table(analysis.phone_numbers, verbose=verbose)

    print()
    print(f"{_BOLD}{'=' * 72}{_RESET}")
    _print_summary(records)
    print()


def _print_phone_table(phones: list[PhoneNumber], verbose: bool) -> None:
    """Print a compact table of phone numbers."""
    col_w = [28, 14, 10]
    header = (
        f"  {'Number':<{col_w[0]}} {'Format':<{col_w[1]}} {'Confidence':<{col_w[2]}}"
    )
    sep = "  " + "-" * (sum(col_w) + len(col_w) * 1)
    print(header)
    print(sep)
    for phone in phones:
        conf_colour = {
            "high": _GREEN,
            "medium": _YELLOW,
            "low": _RED,
        }.get(phone.confidence, "")
        print(
            f"  {phone.number:<{col_w[0]}} "
            f"{phone.format:<{col_w[1]}} "
            f"{conf_colour}{phone.confidence:<{col_w[2]}}{_RESET}"
        )
        if verbose:
            print(f"    Source: {phone.source_page}")


def _print_summary(records: list[ProcessedEmail]) -> None:
    """Print a one-line summary of processing statistics."""
    total = len(records)
    skipped = sum(1 for r in records if r.skipped)
    unreachable = sum(
        1 for r in records
        if not r.skipped and r.domain_check and not r.domain_check.reachable
    )
    with_phones = sum(
        1 for r in records
        if r.analysis and r.analysis.has_results
    )
    print(
        f"Summary: {total} input(s) | "
        f"{skipped} skipped | "
        f"{unreachable} unreachable | "
        f"{with_phones} with phone numbers"
    )


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "email",
    "domain",
    "website_accessible",
    "website_url",
    "phone_numbers",
    "confidence",
    "source_page",
    "notes",
]


def export_csv(records: list[ProcessedEmail], path: str) -> None:
    """Export results to a CSV file.

    One row is written per phone number found. Emails with no phone numbers
    still get a single row with empty phone columns so the full input is
    represented.

    Args:
        records: All processed email records.
        path: Destination file path.
    """
    rows = _build_csv_rows(records)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Exported %d row(s) to %s", len(rows), path)
    print(f"\nResults exported to: {path}")


def _build_csv_rows(records: list[ProcessedEmail]) -> list[dict]:
    """Convert ProcessedEmail records to flat CSV row dicts."""
    rows: list[dict] = []

    for rec in records:
        email = rec.email_result.email
        domain = rec.email_result.domain or ""
        base: dict = {
            "email": email,
            "domain": domain,
            "website_accessible": "",
            "website_url": "",
            "phone_numbers": "",
            "confidence": "",
            "source_page": "",
            "notes": "",
        }

        if rec.skipped:
            base["notes"] = rec.skip_reason or "Skipped"
            rows.append(base)
            continue

        check = rec.domain_check
        if check:
            base["website_accessible"] = "yes" if check.reachable else "no"
            base["website_url"] = check.base_url or ""
            if not check.reachable:
                base["notes"] = check.error or "Unreachable"

        analysis = rec.analysis
        if analysis and analysis.error:
            base["notes"] = analysis.error

        if analysis and analysis.phone_numbers:
            for phone in analysis.phone_numbers:
                row = base.copy()
                row["phone_numbers"] = phone.number
                row["confidence"] = phone.confidence
                row["source_page"] = phone.source_page
                rows.append(row)
        else:
            rows.append(base)

    return rows
