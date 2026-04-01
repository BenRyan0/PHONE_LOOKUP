"""CLI entry point for the phone finder tool."""

import argparse
import logging
import sys

from config import LOG_LEVEL
from email_parser import EmailParseResult, load_emails_from_file, parse_emails
from website_checker import check_domain
from scraper import scrape_domain
from analyzer import analyze_scrape
from output import ProcessedEmail, export_csv, print_results


def _setup_logging(verbose: bool) -> None:
    """Configure root logger level and format.

    Args:
        verbose: If True, use DEBUG level regardless of LOG_LEVEL env var.
    """
    level = logging.DEBUG if verbose else getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phone-finder",
        description="Extract phone numbers from business websites via email domains.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--email",
        metavar="ADDRESS",
        help="Single email address to process.",
    )
    group.add_argument(
        "--emails",
        metavar="LIST",
        help="Comma-separated list of email addresses.",
    )
    group.add_argument(
        "--file",
        metavar="PATH",
        help="Path to a file with one email per line.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Export results to this CSV file.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging and verbose console output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which emails would be processed without scraping.",
    )
    return parser


def _load_email_results(args: argparse.Namespace) -> list[EmailParseResult]:
    """Load and parse email addresses from the appropriate CLI source."""
    if args.email:
        return parse_emails(args.email)
    if args.emails:
        return parse_emails(args.emails)
    # args.file is set
    try:
        return load_emails_from_file(args.file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)


def _process_email(result: EmailParseResult, dry_run: bool) -> ProcessedEmail:
    """Run the full pipeline for a single parsed email.

    Args:
        result: The parsed email record.
        dry_run: If True, skip actual scraping/analysis.

    Returns:
        A ProcessedEmail with all pipeline stages filled in.
    """
    record = ProcessedEmail(email_result=result)

    if not result.is_valid or result.is_blocked:
        record.skipped = True
        record.skip_reason = result.skip_reason
        return record

    if dry_run:
        record.skipped = True
        record.skip_reason = f"Dry run — would scrape {result.domain}"
        return record

    check = check_domain(result.domain)  # type: ignore[arg-type]
    record.domain_check = check

    if not check.reachable:
        return record

    scrape = scrape_domain(check)
    analysis = analyze_scrape(scrape)
    record.analysis = analysis

    return record


def main() -> None:
    """Parse arguments and run the phone finder pipeline."""
    parser = _build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    email_results = _load_email_results(args)
    if not email_results:
        print("No email addresses provided.", file=sys.stderr)
        sys.exit(1)

    logger.info("Processing %d email address(es)...", len(email_results))

    records: list[ProcessedEmail] = []
    for er in email_results:
        logger.debug("Processing: %s", er.email)
        try:
            record = _process_email(er, dry_run=args.dry_run)
        except Exception as exc:
            logger.error("Unexpected error processing %s: %s", er.email, exc)
            record = ProcessedEmail(
                email_result=er,
                skipped=True,
                skip_reason=f"Unexpected error: {exc}",
            )
        records.append(record)

    print_results(records, verbose=args.verbose)

    if args.output:
        export_csv(records, args.output)


if __name__ == "__main__":
    main()
