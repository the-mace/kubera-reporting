"""Tests for reporter module."""

from datetime import datetime, timezone

import pytest

from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.types import PortfolioSnapshot


@pytest.fixture
def current_snapshot() -> PortfolioSnapshot:
    """Create current snapshot for testing."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "portfolio_id": "test-123",
        "portfolio_name": "Test Portfolio",
        "currency": "USD",
        "net_worth": {"amount": 105000.0, "currency": "USD"},
        "total_assets": {"amount": 155000.0, "currency": "USD"},
        "total_debts": {"amount": 50000.0, "currency": "USD"},
        "accounts": [
            {
                "id": "account-1",
                "name": "Stocks",
                "institution": "Broker",
                "value": {"amount": 15000.0, "currency": "USD"},
                "category": "asset",
                "sheet_name": "Investments",
            },
            {
                "id": "account-2",
                "name": "Savings",
                "institution": "Bank",
                "value": {"amount": 5000.0, "currency": "USD"},
                "category": "asset",
                "sheet_name": "Cash",
            },
        ],
    }


@pytest.fixture
def previous_snapshot() -> PortfolioSnapshot:
    """Create previous snapshot for testing."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "portfolio_id": "test-123",
        "portfolio_name": "Test Portfolio",
        "currency": "USD",
        "net_worth": {"amount": 100000.0, "currency": "USD"},
        "total_assets": {"amount": 150000.0, "currency": "USD"},
        "total_debts": {"amount": 50000.0, "currency": "USD"},
        "accounts": [
            {
                "id": "account-1",
                "name": "Stocks",
                "institution": "Broker",
                "value": {"amount": 10000.0, "currency": "USD"},
                "category": "asset",
                "sheet_name": "Investments",
            },
            {
                "id": "account-2",
                "name": "Savings",
                "institution": "Bank",
                "value": {"amount": 5000.0, "currency": "USD"},
                "category": "asset",
                "sheet_name": "Cash",
            },
        ],
    }


def test_calculate_deltas(current_snapshot, previous_snapshot):
    """Test calculating deltas between snapshots."""
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Check net worth change
    assert report_data["net_worth_change"] is not None
    assert report_data["net_worth_change"]["amount"] == 5000.0

    # Check asset changes
    assert len(report_data["asset_changes"]) == 2

    # Find the stocks account change
    stocks_change = next((c for c in report_data["asset_changes"] if c["name"] == "Stocks"), None)
    assert stocks_change is not None
    assert stocks_change["change"]["amount"] == 5000.0
    assert stocks_change["change_percent"] == 50.0

    # Find the savings account (no change)
    savings_change = next((c for c in report_data["asset_changes"] if c["name"] == "Savings"), None)
    assert savings_change is not None
    assert savings_change["change"]["amount"] == 0.0


def test_calculate_deltas_no_previous(current_snapshot):
    """Test calculating deltas with no previous snapshot."""
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, None)

    assert report_data["net_worth_change"] is None
    assert len(report_data["asset_changes"]) == 2


def test_generate_html_report(current_snapshot, previous_snapshot):
    """Test HTML report generation."""
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    html = reporter.generate_html_report(report_data)

    assert "<!DOCTYPE html>" in html
    assert "Net worth" in html
    assert "$105,000" in html  # Net worth (no decimals)
    assert "Stocks" in html
    assert "Assets" in html
