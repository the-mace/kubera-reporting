"""Test the send command (uses --dry-run to avoid sending real emails)."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from kubera_reporting.cli import cli


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory with test snapshots."""
    temp_dir = tempfile.mkdtemp()
    data_dir = Path(temp_dir) / "data"
    data_dir.mkdir(parents=True)

    # Copy fixtures to temp directory
    fixture_dir = Path(__file__).parent / "fixtures"
    for fixture in ["snapshot_2025-01-15.json", "snapshot_2025-01-16.json"]:
        src = fixture_dir / fixture
        dst = data_dir / fixture
        shutil.copy(src, dst)

    yield data_dir

    # Cleanup
    shutil.rmtree(temp_dir)


def test_send_command_dry_run(temp_data_dir):
    """Test send command with --dry-run flag (no emails sent)."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "send",
            "--date",
            "2025-01-16",
            "--data-dir",
            str(temp_data_dir),
            "--no-ai",  # Skip AI to avoid API calls
            "--dry-run",  # Don't send email
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "Loaded snapshot for 2025-01-16" in result.output
    assert "Daily report generated" in result.output
    assert "Dry-run mode" in result.output
    assert "NOT sent (dry-run mode)" in result.output
    assert "no emails sent" in result.output


def test_send_command_monday_dry_run(temp_data_dir):
    """Test send command on a Monday (should generate daily + weekly reports)."""
    # Create Monday snapshot (2025-01-20 is a Monday)
    fixture_dir = Path(__file__).parent / "fixtures"
    with open(fixture_dir / "snapshot_2025-01-16.json") as f:
        snapshot = json.load(f)

    # Save as Monday
    snapshot["timestamp"] = "2025-01-20T12:00:00Z"
    with open(temp_data_dir / "snapshot_2025-01-20.json", "w") as f:
        json.dump(snapshot, f)

    # Save previous Monday (7 days ago) for weekly comparison
    snapshot["timestamp"] = "2025-01-13T12:00:00Z"
    with open(temp_data_dir / "snapshot_2025-01-13.json", "w") as f:
        json.dump(snapshot, f)

    # Save yesterday for daily comparison
    snapshot["timestamp"] = "2025-01-19T12:00:00Z"
    with open(temp_data_dir / "snapshot_2025-01-19.json", "w") as f:
        json.dump(snapshot, f)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "send",
            "--date",
            "2025-01-20",
            "--data-dir",
            str(temp_data_dir),
            "--no-ai",
            "--dry-run",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "Generating 2 report(s): daily, weekly" in result.output
    assert "DAILY REPORT" in result.output
    assert "WEEKLY REPORT" in result.output
    assert "Generated 2 report(s) (dry-run, no emails sent)" in result.output


def test_send_command_no_snapshot_error(temp_data_dir):
    """Test send command with non-existent snapshot."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "send",
            "--date",
            "2025-01-01",
            "--data-dir",
            str(temp_data_dir),
            "--dry-run",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "No snapshot found for 2025-01-01" in result.output


def test_send_command_invalid_date():
    """Test send command with invalid date format."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "send",
            "--date",
            "invalid-date",
            "--dry-run",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "Invalid date format" in result.output
