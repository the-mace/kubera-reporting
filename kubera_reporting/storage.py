"""Storage for portfolio snapshots."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from kubera_reporting.exceptions import StorageError
from kubera_reporting.types import PortfolioSnapshot, ReportType


class SnapshotStorage:
    """Manages storage of portfolio snapshots."""

    def __init__(self, data_dir: str | None = None) -> None:
        """Initialize storage.

        Args:
            data_dir: Directory for storing snapshots (default: ~/.kubera-reporting/data)
        """
        if data_dir:
            self.data_dir = Path(data_dir)
            is_default_location = False
        else:
            self.data_dir = Path.home() / ".kubera-reporting" / "data"
            is_default_location = True

        # Create directory if it doesn't exist (secure permissions: user-only)
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Secure parent directory only for default location (~/.kubera-reporting)
            if is_default_location:
                parent = self.data_dir.parent
                if parent.exists():
                    try:
                        os.chmod(parent, 0o700)
                    except PermissionError:
                        # Parent directory may not be owned by us, skip
                        pass
        except Exception as e:
            raise StorageError(f"Failed to create data directory: {e}") from e

    def _get_snapshot_path(self, date: datetime) -> Path:
        """Get path for snapshot file.

        Args:
            date: Date for the snapshot

        Returns:
            Path to snapshot file
        """
        filename = f"snapshot_{date.strftime('%Y-%m-%d')}.json"
        return self.data_dir / filename

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Save a snapshot to disk.

        Args:
            snapshot: Snapshot to save

        Raises:
            StorageError: If saving fails
        """
        try:
            # Parse timestamp to get date
            timestamp = datetime.fromisoformat(snapshot["timestamp"])
            path = self._get_snapshot_path(timestamp)

            # Write snapshot with secure permissions (user-only: rw-------)
            # Create file descriptor with secure mode first
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise StorageError(f"Failed to save snapshot: {e}") from e

    def load_snapshot(self, date: datetime) -> PortfolioSnapshot | None:
        """Load a snapshot from disk.

        Args:
            date: Date of the snapshot to load

        Returns:
            Snapshot if found, None otherwise

        Raises:
            StorageError: If loading fails
        """
        try:
            path = self._get_snapshot_path(date)

            if not path.exists():
                return None

            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                return cast(PortfolioSnapshot, data)

        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in snapshot file: {e}") from e
        except Exception as e:
            raise StorageError(f"Failed to load snapshot: {e}") from e

    def load_latest_snapshot(self) -> PortfolioSnapshot | None:
        """Load the most recent snapshot.

        Returns:
            Most recent snapshot if any exist, None otherwise

        Raises:
            StorageError: If loading fails
        """
        try:
            # Find all snapshot files
            snapshot_files = sorted(self.data_dir.glob("snapshot_*.json"), reverse=True)

            if not snapshot_files:
                return None

            # Load the most recent one
            with open(snapshot_files[0], encoding="utf-8") as f:
                data = json.load(f)
                return cast(PortfolioSnapshot, data)

        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in snapshot file: {e}") from e
        except Exception as e:
            raise StorageError(f"Failed to load latest snapshot: {e}") from e

    def list_snapshots(self) -> list[datetime]:
        """List all available snapshot dates.

        Returns:
            List of dates for which snapshots exist

        Raises:
            StorageError: If listing fails
        """
        try:
            snapshot_files = self.data_dir.glob("snapshot_*.json")
            dates = []

            for path in snapshot_files:
                # Extract date from filename
                date_str = path.stem.replace("snapshot_", "")
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    dates.append(date)
                except ValueError:
                    # Skip files with invalid date format
                    continue

            return sorted(dates, reverse=True)

        except Exception as e:
            raise StorageError(f"Failed to list snapshots: {e}") from e

    def is_milestone_date(self, date: datetime) -> bool:
        """Check if a date is a milestone (Monday, 1st of month, quarter start, or year start).

        Args:
            date: Date to check

        Returns:
            True if date is a milestone
        """
        # Monday (weekday 0)
        if date.weekday() == 0:
            return True

        # First of month
        if date.day == 1:
            return True

        # Already covered by day == 1, but explicit for clarity:
        # Quarter starts (Jan 1, Apr 1, Jul 1, Oct 1)
        if date.month in [1, 4, 7, 10] and date.day == 1:
            return True

        # Year start (Jan 1) - already covered but explicit
        if date.month == 1 and date.day == 1:
            return True

        return False

    def get_milestone_types(self, date: datetime) -> list[ReportType]:
        """Get list of report types that should be generated for this date.

        Args:
            date: Date to check

        Returns:
            List of report types (always includes DAILY, plus WEEKLY/MONTHLY/QUARTERLY/YEARLY
            as applicable)
        """
        report_types = [ReportType.DAILY]

        # Monday = weekly report
        if date.weekday() == 0:
            report_types.append(ReportType.WEEKLY)

        # First of month = monthly report
        if date.day == 1:
            report_types.append(ReportType.MONTHLY)

            # Quarter starts (Jan 1, Apr 1, Jul 1, Oct 1)
            if date.month in [1, 4, 7, 10]:
                report_types.append(ReportType.QUARTERLY)

            # Year start (Jan 1)
            if date.month == 1:
                report_types.append(ReportType.YEARLY)

        return report_types

    def get_comparison_snapshot(
        self, current_date: datetime, report_type: ReportType
    ) -> PortfolioSnapshot | None:
        """Get the appropriate comparison snapshot for a given report type.

        Args:
            current_date: Date of current snapshot
            report_type: Type of report being generated

        Returns:
            Comparison snapshot, or None if not available

        Raises:
            StorageError: If loading fails
        """
        try:
            if report_type == ReportType.DAILY:
                # Compare to yesterday
                comparison_date = current_date - timedelta(days=1)
                return self.load_snapshot(comparison_date)

            elif report_type == ReportType.WEEKLY:
                # Compare to last Monday (7 days ago)
                comparison_date = current_date - timedelta(days=7)
                return self.load_snapshot(comparison_date)

            elif report_type == ReportType.MONTHLY:
                # Compare to first day of last month
                # If we're on Feb 1, compare to Jan 1
                if current_date.month == 1:
                    # January - compare to previous year's December 1st
                    comparison_date = current_date.replace(
                        year=current_date.year - 1, month=12, day=1
                    )
                else:
                    # Other months - compare to previous month's 1st
                    comparison_date = current_date.replace(month=current_date.month - 1, day=1)
                return self.load_snapshot(comparison_date)

            elif report_type == ReportType.QUARTERLY:
                # Compare to first day of last quarter
                # Quarters: Q1=Jan, Q2=Apr, Q3=Jul, Q4=Oct
                quarter_starts = {1: 1, 4: 4, 7: 7, 10: 10}
                current_quarter_month = max(
                    m for m in quarter_starts.values() if m <= current_date.month
                )

                if current_quarter_month == 1:
                    # Q1 - compare to previous year's Q4 (Oct 1)
                    comparison_date = current_date.replace(
                        year=current_date.year - 1, month=10, day=1
                    )
                else:
                    # Other quarters - compare to previous quarter
                    prev_quarter_month = max(
                        m for m in quarter_starts.values() if m < current_quarter_month
                    )
                    comparison_date = current_date.replace(month=prev_quarter_month, day=1)

                return self.load_snapshot(comparison_date)

            elif report_type == ReportType.YEARLY:
                # Compare to Jan 1 of last year
                comparison_date = current_date.replace(year=current_date.year - 1, month=1, day=1)
                return self.load_snapshot(comparison_date)

            return None

        except Exception as e:
            raise StorageError(f"Failed to get comparison snapshot: {e}") from e

    def cleanup_old_snapshots(self, retention_days: int = 60) -> int:
        """Clean up old non-milestone snapshots.

        Keeps:
        - All snapshots from last `retention_days` days
        - All milestone dates (Mondays, 1st of month, quarter starts, year starts)
        - Yesterday and today

        Args:
            retention_days: Number of days to keep all snapshots (default: 60)

        Returns:
            Number of snapshots deleted

        Raises:
            StorageError: If cleanup fails
        """
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            retention_cutoff = today - timedelta(days=retention_days)

            snapshots = self.list_snapshots()
            deleted_count = 0

            for snapshot_date in snapshots:
                # Always keep today and yesterday
                if snapshot_date.date() in [today.date(), yesterday.date()]:
                    continue

                # Keep all snapshots within retention period
                if snapshot_date >= retention_cutoff:
                    continue

                # Keep milestone dates
                if self.is_milestone_date(snapshot_date):
                    continue

                # Delete this snapshot
                path = self._get_snapshot_path(snapshot_date)
                if path.exists():
                    path.unlink()
                    deleted_count += 1

            return deleted_count

        except Exception as e:
            raise StorageError(f"Failed to cleanup old snapshots: {e}") from e
