"""Tests for multi-currency formatting."""

import json
from pathlib import Path

from kubera_reporting import currency_format
from kubera_reporting.reporter import PortfolioReporter


def test_currency_symbols():
    """Test that currency symbols are correctly retrieved."""
    assert currency_format.get_currency_symbol("USD") == "$"
    assert currency_format.get_currency_symbol("EUR") == "€"
    assert currency_format.get_currency_symbol("GBP") == "£"
    assert currency_format.get_currency_symbol("JPY") == "¥"


def test_format_money_usd():
    """Test USD formatting."""
    assert currency_format.format_money(1234.56, "USD") == "$1,235"
    assert currency_format.format_money(1234.56, "USD", hide_amounts=True) == "$XX"


def test_format_money_eur():
    """Test EUR formatting."""
    assert currency_format.format_money(1234.56, "EUR") == "€1,235"
    assert currency_format.format_money(1234.56, "EUR", hide_amounts=True) == "€XX"


def test_format_money_gbp():
    """Test GBP formatting."""
    assert currency_format.format_money(1234.56, "GBP") == "£1,235"
    assert currency_format.format_money(1234.56, "GBP", hide_amounts=True) == "£XX"


def test_format_change_usd():
    """Test USD change formatting."""
    result, color = currency_format.format_change(1234.56, "USD", 5.2)
    assert result == "↑ $1,235 (+5.20%)"
    assert color == "#00b383"

    result, color = currency_format.format_change(-1234.56, "USD", -3.1)
    assert result == "↓ $1,235 (-3.10%)"
    assert color == "#e53935"


def test_format_change_eur():
    """Test EUR change formatting."""
    result, color = currency_format.format_change(1234.56, "EUR", 5.2)
    assert result == "↑ €1,235 (+5.20%)"
    assert color == "#00b383"


def test_format_change_gbp():
    """Test GBP change formatting."""
    result, color = currency_format.format_change(-1234.56, "GBP", -3.1)
    assert result == "↓ £1,235 (-3.10%)"
    assert color == "#e53935"


def test_eur_report_generation(tmp_path):
    """Test generating a report with EUR currency."""
    fixtures_dir = Path("tests/fixtures")

    # Load EUR snapshots
    with open(fixtures_dir / "snapshot_eur_2025-01-15.json") as f:
        previous_snapshot = json.load(f)
    with open(fixtures_dir / "snapshot_eur_2025-01-16.json") as f:
        current_snapshot = json.load(f)

    # Generate report
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Check currency is EUR
    assert report_data["current"]["currency"] == "EUR"
    assert report_data["current"]["net_worth"]["currency"] == "EUR"

    # Generate HTML report
    html = reporter.generate_html_report(report_data, ai_summary=None)

    # Check that EUR symbol appears in HTML
    assert "€" in html
    # Should not have any USD symbols
    assert "$1," not in html  # Should not have USD formatting


def test_gbp_report_generation(tmp_path):
    """Test generating a report with GBP currency."""
    fixtures_dir = Path("tests/fixtures")

    # Load GBP snapshots
    with open(fixtures_dir / "snapshot_gbp_2025-01-15.json") as f:
        previous_snapshot = json.load(f)
    with open(fixtures_dir / "snapshot_gbp_2025-01-16.json") as f:
        current_snapshot = json.load(f)

    # Generate report
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Check currency is GBP
    assert report_data["current"]["currency"] == "GBP"
    assert report_data["current"]["net_worth"]["currency"] == "GBP"

    # Generate HTML report
    html = reporter.generate_html_report(report_data, ai_summary=None)

    # Check that GBP symbol appears in HTML
    assert "£" in html
    # Should not have any USD symbols
    assert "$1," not in html  # Should not have USD formatting


def test_usd_still_works(tmp_path):
    """Test that USD formatting still works correctly (regression test)."""
    fixtures_dir = Path("tests/fixtures")

    # Load USD snapshots
    with open(fixtures_dir / "snapshot_2025-01-15.json") as f:
        previous_snapshot = json.load(f)
    with open(fixtures_dir / "snapshot_2025-01-16.json") as f:
        current_snapshot = json.load(f)

    # Generate report
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Check currency is USD
    assert report_data["current"]["currency"] == "USD"

    # Generate HTML report
    html = reporter.generate_html_report(report_data, ai_summary=None)

    # Check that USD symbol appears in HTML
    assert "$" in html
    # Should not have EUR or GBP symbols
    assert "€" not in html
    assert "£" not in html
