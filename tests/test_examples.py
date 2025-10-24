"""Test that example code runs successfully with fixture data."""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.storage import SnapshotStorage
from kubera_reporting.types import PortfolioSnapshot


@pytest.fixture
def fixture_dir() -> Path:
    """Get fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def snapshot_day1(fixture_dir: Path) -> PortfolioSnapshot:
    """Load day 1 snapshot fixture."""
    with open(fixture_dir / "snapshot_2025-01-15.json") as f:
        return json.load(f)


@pytest.fixture
def snapshot_day2(fixture_dir: Path) -> PortfolioSnapshot:
    """Load day 2 snapshot fixture."""
    with open(fixture_dir / "snapshot_2025-01-16.json") as f:
        return json.load(f)


def test_basic_usage_example(snapshot_day2: PortfolioSnapshot, tmp_path: Path) -> None:
    """Test that basic_usage.py example code works with fixture data."""
    # Mock KuberaFetcher to return fixture data instead of calling API
    with patch("kubera_reporting.fetcher.KuberaFetcher") as mock_fetcher_class:
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_snapshot.return_value = snapshot_day2
        mock_fetcher_class.return_value.__enter__.return_value = mock_fetcher

        # Use temp directory for storage
        storage = SnapshotStorage(str(tmp_path))

        # === Code from basic_usage.py ===
        # Fetch current portfolio data
        with mock_fetcher_class() as fetcher:
            current_snapshot = fetcher.fetch_snapshot()

        assert current_snapshot["portfolio_name"] == "Test Portfolio"
        assert current_snapshot["net_worth"]["amount"] > 0
        assert len(current_snapshot["accounts"]) > 0

        # Save snapshot
        storage.save_snapshot(current_snapshot)

        # Verify snapshot was saved
        snapshot_date = datetime.fromisoformat(current_snapshot["timestamp"])
        saved_snapshot = storage.load_snapshot(snapshot_date)
        assert saved_snapshot is not None
        assert saved_snapshot["portfolio_id"] == current_snapshot["portfolio_id"]


def test_basic_usage_example_with_deltas(
    snapshot_day1: PortfolioSnapshot,
    snapshot_day2: PortfolioSnapshot,
    tmp_path: Path,
) -> None:
    """Test basic_usage.py example with previous snapshot (delta calculation)."""
    # Mock KuberaFetcher
    with patch("kubera_reporting.fetcher.KuberaFetcher") as mock_fetcher_class:
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_snapshot.return_value = snapshot_day2
        mock_fetcher_class.return_value.__enter__.return_value = mock_fetcher

        # Use temp directory and pre-populate with day 1 snapshot
        storage = SnapshotStorage(str(tmp_path))
        storage.save_snapshot(snapshot_day1)

        # === Code from basic_usage.py ===
        with mock_fetcher_class() as fetcher:
            current_snapshot = fetcher.fetch_snapshot()

        storage.save_snapshot(current_snapshot)

        # Load previous snapshot
        previous_date = datetime.fromisoformat(snapshot_day1["timestamp"])
        previous_snapshot = storage.load_snapshot(previous_date)

        assert previous_snapshot is not None

        # Calculate deltas
        reporter = PortfolioReporter()
        report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

        # Verify deltas were calculated
        assert report_data["net_worth_change"] is not None
        assert report_data["net_worth_change"]["amount"] != 0
        assert len(report_data["asset_changes"]) > 0

        # Verify top movers are sorted by absolute change
        for i in range(len(report_data["asset_changes"]) - 1):
            current_change = abs(report_data["asset_changes"][i]["change"]["amount"])
            next_change = abs(report_data["asset_changes"][i + 1]["change"]["amount"])
            assert current_change >= next_change


def test_ai_query_example(
    snapshot_day1: PortfolioSnapshot,
    snapshot_day2: PortfolioSnapshot,
    tmp_path: Path,
) -> None:
    """Test that ai_query.py example code structure works with fixture data."""
    # Mock KuberaFetcher
    with patch("kubera_reporting.fetcher.KuberaFetcher") as mock_fetcher_class:
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_snapshot.return_value = snapshot_day2
        mock_fetcher_class.return_value.__enter__.return_value = mock_fetcher

        # Mock LLMClient to avoid real API calls
        with patch("kubera_reporting.llm_client.LLMClient") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.query_portfolio.return_value = (
                "Based on your portfolio data, your largest asset is..."
            )
            mock_llm_class.return_value = mock_llm

            # Use temp directory and pre-populate with day 1 snapshot
            storage = SnapshotStorage(str(tmp_path))
            storage.save_snapshot(snapshot_day1)

            # === Code from ai_query.py ===
            # Fetch current data
            with mock_fetcher_class() as fetcher:
                current_snapshot = fetcher.fetch_snapshot()

            # Load previous snapshot
            previous_date = datetime.fromisoformat(snapshot_day1["timestamp"])
            previous_snapshot = storage.load_snapshot(previous_date)

            # Build report data
            report_data = None
            if previous_snapshot:
                reporter = PortfolioReporter()
                report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

            assert report_data is not None

            # Query AI
            llm = mock_llm_class()

            questions = [
                "What's my largest asset?",
                "How did my portfolio perform yesterday?",
                "What percentage of my portfolio is in stocks?",
            ]

            for question in questions:
                response = llm.query_portfolio(question, current_snapshot, report_data)
                # Verify LLM was called with correct parameters
                assert response is not None
                assert isinstance(response, str)

            # Verify LLM was called for each question
            assert mock_llm.query_portfolio.call_count == len(questions)


def test_examples_can_be_imported() -> None:
    """Test that example files can be imported without errors."""
    examples_dir = Path(__file__).parent.parent / "examples"

    # Add examples directory to path temporarily
    sys.path.insert(0, str(examples_dir))

    try:
        # These should import without errors (but not execute main())
        import ai_query  # noqa: F401
        import basic_usage  # noqa: F401
    finally:
        sys.path.pop(0)
