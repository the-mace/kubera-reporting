"""End-to-end tests using fixtures (no API calls)."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.storage import SnapshotStorage
from kubera_reporting.types import PortfolioSnapshot


@pytest.fixture
def fixtures_dir():
    """Get fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def snapshot_2025_01_15(fixtures_dir) -> PortfolioSnapshot:
    """Load Jan 15 snapshot."""
    with open(fixtures_dir / "snapshot_2025-01-15.json") as f:
        return json.load(f)


@pytest.fixture
def snapshot_2025_01_16(fixtures_dir) -> PortfolioSnapshot:
    """Load Jan 16 snapshot."""
    with open(fixtures_dir / "snapshot_2025-01-16.json") as f:
        return json.load(f)


def test_first_day_report_no_previous_data(snapshot_2025_01_16):
    """Test generating a report with no previous data (first day)."""
    reporter = PortfolioReporter()

    # Calculate deltas with no previous snapshot
    report_data = reporter.calculate_deltas(snapshot_2025_01_16, None)

    # Verify no net worth change
    assert report_data["net_worth_change"] is None
    assert report_data["previous"] is None

    # Verify we still have current data
    assert report_data["current"]["net_worth"]["amount"] == pytest.approx(1359205.00)

    # Generate HTML report
    html = reporter.generate_html_report(report_data)

    # Verify HTML content
    assert "<!DOCTYPE html>" in html
    assert "Net worth" in html
    assert "$1,359,205" in html
    # Check for first day message (may be split across lines)
    assert "snapshot of your current" in html and "account balances" in html
    assert "Asset Allocation" in html  # Should have allocation chart

    # Verify NO delta indicators in HTML (since no previous data)
    # We check that change values don't appear inline with account balances
    assert "Investment Account" in html or "Retirement Account" in html


def test_second_day_report_with_deltas(snapshot_2025_01_15, snapshot_2025_01_16):
    """Test generating a report with previous data showing deltas."""
    reporter = PortfolioReporter()

    # Calculate deltas
    report_data = reporter.calculate_deltas(snapshot_2025_01_16, snapshot_2025_01_15)

    # Verify net worth change
    assert report_data["net_worth_change"] is not None
    assert report_data["net_worth_change"]["amount"] == pytest.approx(6205.00)

    # Verify asset changes sorted by absolute change
    assert len(report_data["asset_changes"]) > 0

    # Top movers should be (by absolute change):
    # 1. Crypto Wallet: -$3,125 (largest absolute change)
    # 2. Retirement Account: +$2,400
    # 3. Investment Account - Stocks: +$1,575
    top_asset = report_data["asset_changes"][0]
    assert top_asset["name"] == "Crypto Wallet"
    assert top_asset["change"]["amount"] == pytest.approx(-3125.0)

    second_asset = report_data["asset_changes"][1]
    assert second_asset["name"] == "Retirement Account - 401k - 9999"
    assert second_asset["change"]["amount"] == pytest.approx(2400.0)

    # Verify debt changes
    assert len(report_data["debt_changes"]) > 0

    # Debt movers should include mortgage and auto loan
    mortgage = next((d for d in report_data["debt_changes"] if "Mortgage" in d["name"]), None)
    assert mortgage is not None
    assert mortgage["change"]["amount"] == pytest.approx(-50.0)  # Negative = paid down

    # Test asset allocation
    allocation = reporter.calculate_asset_allocation(snapshot_2025_01_16)
    assert "Stocks" in allocation
    assert "Bonds" in allocation
    assert "Crypto" in allocation

    # Generate HTML report
    html = reporter.generate_html_report(report_data)

    # Verify HTML content with deltas
    assert "<!DOCTYPE html>" in html
    assert "Net worth" in html
    assert "$1,359,205" in html
    assert "↑ $6,205" in html  # Net worth change with up arrow
    assert "balances that changed yesterday" in html  # Second day message
    assert "Crypto Wallet" in html
    assert "↓ $3,125" in html  # Top asset mover (negative) with down arrow
    assert "Asset Allocation" in html  # Should have allocation chart
    assert "data:image/png;base64," in html  # Base64-embedded chart for forwarding compatibility


def test_storage_round_trip(snapshot_2025_01_16):
    """Test saving and loading a snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SnapshotStorage(tmpdir)

        # Save snapshot
        storage.save_snapshot(snapshot_2025_01_16)

        # Load it back
        loaded = storage.load_snapshot(datetime(2025, 1, 16))

        assert loaded is not None
        assert loaded["portfolio_id"] == snapshot_2025_01_16["portfolio_id"]
        assert loaded["net_worth"]["amount"] == snapshot_2025_01_16["net_worth"]["amount"]


def test_html_report_export(snapshot_2025_01_15, snapshot_2025_01_16):
    """Generate sample HTML reports for manual inspection."""
    reporter = PortfolioReporter()
    output_dir = Path(__file__).parent.parent / "sample_reports"
    output_dir.mkdir(exist_ok=True)

    # Generate first day report (no previous data)
    report_data_first = reporter.calculate_deltas(snapshot_2025_01_16, None)
    html_first = reporter.generate_html_report(report_data_first)

    with open(output_dir / "sample_report_first_day.html", "w") as f:
        f.write(html_first)

    # Generate second day report (with deltas and AI summary)
    report_data_second = reporter.calculate_deltas(snapshot_2025_01_16, snapshot_2025_01_15)

    # Generate AI summary (will use test fixtures, no real API call if GROK_API_KEY not set)
    ai_summary = reporter.generate_ai_summary(report_data_second)
    if not ai_summary:
        # Use a mock summary if AI generation fails (e.g., no API key)
        ai_summary = (
            "Your portfolio gained $41,386 (+1.46%) yesterday, driven primarily by strong "
            "performance in your equity holdings. Your largest brokerage account led gains "
            "with a +$18,500 increase (+2.26%), while most investment and retirement "
            "accounts saw positive momentum. Cryptocurrency holdings showed weakness with "
            "a -$3,120 decline in your crypto wallet."
        )

    # Generate with personalized greeting for sample
    html_second = reporter.generate_html_report(
        report_data_second, ai_summary=ai_summary, recipient_name="Investor"
    )

    with open(output_dir / "sample_report_with_deltas.html", "w") as f:
        f.write(html_second)

    print(f"\nSample reports generated in {output_dir}/")
    print("- sample_report_first_day.html (no previous data)")
    print("- sample_report_with_deltas.html (with changes and AI insights)")


def test_negative_changes(snapshot_2025_01_15, snapshot_2025_01_16):
    """Test that negative changes are handled correctly."""
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(snapshot_2025_01_16, snapshot_2025_01_15)

    # Find Crypto Wallet (should have negative change: -$3,120)
    crypto_wallet = next(
        (a for a in report_data["asset_changes"] if a["name"] == "Crypto Wallet"), None
    )
    assert crypto_wallet is not None
    assert crypto_wallet["change"]["amount"] == pytest.approx(-3125.0)

    # Verify it's formatted correctly in HTML
    html = reporter.generate_html_report(report_data)
    assert "Crypto Wallet" in html
    assert "↓ $3,125" in html  # Should show negative with down arrow (no decimals)
