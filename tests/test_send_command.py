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


def test_send_command_monday_without_previous_monday(temp_data_dir):
    """Test that weekly report is skipped when there's no previous Monday snapshot."""
    # Create Monday snapshot (2025-01-20 is a Monday)
    fixture_dir = Path(__file__).parent / "fixtures"
    with open(fixture_dir / "snapshot_2025-01-16.json") as f:
        snapshot = json.load(f)

    # Save as Monday
    snapshot["timestamp"] = "2025-01-20T12:00:00Z"
    with open(temp_data_dir / "snapshot_2025-01-20.json", "w") as f:
        json.dump(snapshot, f)

    # Save yesterday for daily comparison (but no previous Monday)
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
    # Verify weekly report was skipped
    assert "Skipping weekly report" in result.output
    assert "No comparison snapshot found" in result.output
    # Should only generate 1 report (daily)
    assert "Generated 1 report(s) (dry-run, no emails sent)" in result.output


def test_send_command_first_of_month_without_previous_month(temp_data_dir):
    """Test that monthly report is skipped when there's no previous month snapshot."""
    # Create 1st of month snapshot (2025-02-01)
    fixture_dir = Path(__file__).parent / "fixtures"
    with open(fixture_dir / "snapshot_2025-01-16.json") as f:
        snapshot = json.load(f)

    # Save as 1st of February
    snapshot["timestamp"] = "2025-02-01T12:00:00Z"
    with open(temp_data_dir / "snapshot_2025-02-01.json", "w") as f:
        json.dump(snapshot, f)

    # Save yesterday for daily comparison (but no previous 1st of month)
    snapshot["timestamp"] = "2025-01-31T12:00:00Z"
    with open(temp_data_dir / "snapshot_2025-01-31.json", "w") as f:
        json.dump(snapshot, f)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "send",
            "--date",
            "2025-02-01",
            "--data-dir",
            str(temp_data_dir),
            "--no-ai",
            "--dry-run",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    # Feb 1 2025 is a Saturday, so should get daily, weekly, and monthly
    assert "daily" in result.output.lower()
    assert "DAILY REPORT" in result.output
    # Should skip weekly and monthly due to no comparison data
    assert "Skipping" in result.output
