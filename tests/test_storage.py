"""Tests for storage module."""

import tempfile
from datetime import datetime, timezone

import pytest

from kubera_reporting.storage import SnapshotStorage
from kubera_reporting.types import PortfolioSnapshot


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_snapshot() -> PortfolioSnapshot:
    """Create sample snapshot for testing."""
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
                "name": "Test Account",
                "institution": "Test Bank",
                "value": {"amount": 10000.0, "currency": "USD"},
                "category": "asset",
                "sheet_name": "Investments",
            }
        ],
    }


def test_save_and_load_snapshot(temp_dir, sample_snapshot):
    """Test saving and loading a snapshot."""
    storage = SnapshotStorage(temp_dir)

    # Save snapshot
    storage.save_snapshot(sample_snapshot)

    # Load snapshot
    timestamp = datetime.fromisoformat(sample_snapshot["timestamp"])
    loaded = storage.load_snapshot(timestamp)

    assert loaded is not None
    assert loaded["portfolio_id"] == sample_snapshot["portfolio_id"]
    assert loaded["net_worth"]["amount"] == sample_snapshot["net_worth"]["amount"]


def test_load_nonexistent_snapshot(temp_dir):
    """Test loading a snapshot that doesn't exist."""
    storage = SnapshotStorage(temp_dir)
    date = datetime(2020, 1, 1)

    loaded = storage.load_snapshot(date)
    assert loaded is None


def test_list_snapshots(temp_dir, sample_snapshot):
    """Test listing snapshots."""
    storage = SnapshotStorage(temp_dir)

    # Save multiple snapshots
    storage.save_snapshot(sample_snapshot)

    # List snapshots
    dates = storage.list_snapshots()

    assert len(dates) == 1
    assert dates[0].date() == datetime.fromisoformat(sample_snapshot["timestamp"]).date()


def test_load_latest_snapshot(temp_dir, sample_snapshot):
    """Test loading the latest snapshot."""
    storage = SnapshotStorage(temp_dir)

    storage.save_snapshot(sample_snapshot)

    latest = storage.load_latest_snapshot()
    assert latest is not None
    assert latest["portfolio_id"] == sample_snapshot["portfolio_id"]
