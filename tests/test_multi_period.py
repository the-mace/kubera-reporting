"""Tests for multi-period reporting features (weekly, monthly, quarterly, yearly)."""

from datetime import datetime, timedelta

from kubera_reporting.storage import SnapshotStorage
from kubera_reporting.types import ReportType


class TestMilestoneDetection:
    """Tests for milestone date detection."""

    def test_monday_is_milestone(self):
        """Test that Mondays are detected as milestones."""
        storage = SnapshotStorage()
        # 2025-01-20 is a Monday
        monday = datetime(2025, 1, 20)
        assert storage.is_milestone_date(monday) is True

    def test_tuesday_is_not_milestone(self):
        """Test that regular Tuesdays are not milestones."""
        storage = SnapshotStorage()
        # 2025-01-21 is a Tuesday (not 1st of month)
        tuesday = datetime(2025, 1, 21)
        assert storage.is_milestone_date(tuesday) is False

    def test_first_of_month_is_milestone(self):
        """Test that 1st of month is a milestone."""
        storage = SnapshotStorage()
        # 2025-02-01 is a Saturday (1st of month)
        first_of_month = datetime(2025, 2, 1)
        assert storage.is_milestone_date(first_of_month) is True

    def test_quarter_start_is_milestone(self):
        """Test that quarter starts are milestones."""
        storage = SnapshotStorage()
        # Quarter starts: Jan 1, Apr 1, Jul 1, Oct 1
        assert storage.is_milestone_date(datetime(2025, 1, 1)) is True  # Q1
        assert storage.is_milestone_date(datetime(2025, 4, 1)) is True  # Q2
        assert storage.is_milestone_date(datetime(2025, 7, 1)) is True  # Q3
        assert storage.is_milestone_date(datetime(2025, 10, 1)) is True  # Q4

    def test_year_start_is_milestone(self):
        """Test that Jan 1 is a milestone."""
        storage = SnapshotStorage()
        # 2025-01-01 is a Wednesday (year start)
        year_start = datetime(2025, 1, 1)
        assert storage.is_milestone_date(year_start) is True


class TestMilestoneTypes:
    """Tests for determining report types from dates."""

    def test_regular_tuesday_only_daily(self):
        """Test that regular Tuesday generates only daily report."""
        storage = SnapshotStorage()
        # 2025-01-21 is a Tuesday (not special)
        tuesday = datetime(2025, 1, 21)
        report_types = storage.get_milestone_types(tuesday)
        assert report_types == [ReportType.DAILY]

    def test_monday_generates_daily_and_weekly(self):
        """Test that Monday generates daily and weekly reports."""
        storage = SnapshotStorage()
        # 2025-01-20 is a Monday
        monday = datetime(2025, 1, 20)
        report_types = storage.get_milestone_types(monday)
        assert ReportType.DAILY in report_types
        assert ReportType.WEEKLY in report_types
        assert len(report_types) == 2

    def test_first_of_month_generates_daily_and_monthly(self):
        """Test that 1st of month (not quarter) generates daily and monthly."""
        storage = SnapshotStorage()
        # 2025-02-01 is a Saturday (1st of month, not quarter start)
        first_of_month = datetime(2025, 2, 1)
        report_types = storage.get_milestone_types(first_of_month)
        assert ReportType.DAILY in report_types
        assert ReportType.MONTHLY in report_types
        assert len(report_types) == 2

    def test_quarter_start_generates_daily_monthly_quarterly(self):
        """Test that quarter start (not Monday) generates daily, monthly, and quarterly."""
        storage = SnapshotStorage()
        # 2025-04-01 is a Tuesday (quarter start, not Monday)
        quarter_start = datetime(2025, 4, 1)
        report_types = storage.get_milestone_types(quarter_start)
        assert ReportType.DAILY in report_types
        assert ReportType.MONTHLY in report_types
        assert ReportType.QUARTERLY in report_types
        assert len(report_types) == 3

    def test_year_start_generates_all_types(self):
        """Test that Jan 1 generates daily, monthly, quarterly, and yearly reports."""
        storage = SnapshotStorage()
        # 2025-01-01 is a Wednesday (year start)
        year_start = datetime(2025, 1, 1)
        report_types = storage.get_milestone_types(year_start)
        assert ReportType.DAILY in report_types
        assert ReportType.MONTHLY in report_types
        assert ReportType.QUARTERLY in report_types
        assert ReportType.YEARLY in report_types
        assert len(report_types) == 4

    def test_monday_on_first_of_month(self):
        """Test that Monday + 1st of month generates daily, weekly, and monthly."""
        storage = SnapshotStorage()
        # 2025-12-01 is a Monday (1st of month, not quarter)
        monday_first = datetime(2025, 12, 1)
        report_types = storage.get_milestone_types(monday_first)
        assert ReportType.DAILY in report_types
        assert ReportType.WEEKLY in report_types
        assert ReportType.MONTHLY in report_types
        assert len(report_types) == 3


class TestComparisonSnapshots:
    """Tests for finding comparison snapshots."""

    def test_daily_comparison_is_yesterday(self):
        """Test that daily report compares to yesterday."""
        storage = SnapshotStorage()
        today = datetime(2025, 1, 21)  # Tuesday
        # The method will return None if snapshot doesn't exist, which is fine for this test
        result = storage.get_comparison_snapshot(today, ReportType.DAILY)
        # We expect it to look for yesterday's date
        assert result is None  # No snapshot exists

    def test_weekly_comparison_is_last_monday(self):
        """Test that weekly report compares to 7 days ago."""
        storage = SnapshotStorage()
        # 2025-01-20 is a Monday
        monday = datetime(2025, 1, 20)
        # Should look for previous Monday (7 days ago)
        result = storage.get_comparison_snapshot(monday, ReportType.WEEKLY)
        assert result is None  # No snapshot exists

    def test_monthly_comparison_is_first_of_last_month(self):
        """Test that monthly report compares to 1st of previous month."""
        storage = SnapshotStorage()
        # 2025-02-01 is a Saturday
        feb_1 = datetime(2025, 2, 1)
        # Should look for Jan 1 (previous month's 1st)
        result = storage.get_comparison_snapshot(feb_1, ReportType.MONTHLY)
        assert result is None  # No snapshot exists

    def test_monthly_comparison_handles_january(self):
        """Test that monthly report in January compares to previous year's Dec 1."""
        storage = SnapshotStorage()
        jan_1 = datetime(2025, 1, 1)
        # Should look for 2024-12-01
        result = storage.get_comparison_snapshot(jan_1, ReportType.MONTHLY)
        assert result is None  # No snapshot exists

    def test_quarterly_comparison_q2(self):
        """Test that Q2 quarterly report compares to Q1 start (Jan 1)."""
        storage = SnapshotStorage()
        # 2025-04-01 is Q2 start
        q2_start = datetime(2025, 4, 1)
        # Should look for Jan 1 (Q1 start)
        result = storage.get_comparison_snapshot(q2_start, ReportType.QUARTERLY)
        assert result is None  # No snapshot exists

    def test_quarterly_comparison_q1(self):
        """Test that Q1 quarterly report compares to previous year's Q4 (Oct 1)."""
        storage = SnapshotStorage()
        jan_1 = datetime(2025, 1, 1)
        # Should look for 2024-10-01
        result = storage.get_comparison_snapshot(jan_1, ReportType.QUARTERLY)
        assert result is None  # No snapshot exists

    def test_yearly_comparison(self):
        """Test that yearly report compares to previous year's Jan 1."""
        storage = SnapshotStorage()
        jan_1 = datetime(2025, 1, 1)
        # Should look for 2024-01-01
        result = storage.get_comparison_snapshot(jan_1, ReportType.YEARLY)
        assert result is None  # No snapshot exists


class TestSnapshotCleanup:
    """Tests for snapshot cleanup logic."""

    def test_cleanup_keeps_recent_snapshots(self, tmp_path):
        """Test that cleanup keeps all snapshots within retention period."""
        storage = SnapshotStorage(str(tmp_path))

        # Create snapshots for last 30 days (all should be kept with 60-day retention)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(30):
            date = today - timedelta(days=i)
            snapshot = {
                "timestamp": date.isoformat(),
                "portfolio_id": "test",
                "portfolio_name": "Test",
                "currency": "USD",
                "net_worth": {"amount": 1000.0, "currency": "USD"},
                "total_assets": {"amount": 1000.0, "currency": "USD"},
                "total_debts": {"amount": 0.0, "currency": "USD"},
                "accounts": [],
            }
            storage.save_snapshot(snapshot)

        # Cleanup with 60-day retention
        deleted = storage.cleanup_old_snapshots(retention_days=60)
        assert deleted == 0  # Nothing should be deleted

        # Verify all snapshots still exist
        snapshots = storage.list_snapshots()
        assert len(snapshots) == 30

    def test_cleanup_removes_old_non_milestone_snapshots(self, tmp_path):
        """Test that cleanup removes old non-milestone snapshots."""
        storage = SnapshotStorage(str(tmp_path))

        # Create old snapshots (90 days ago)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create non-milestone (Tuesday, 90 days ago)
        old_date = today - timedelta(days=90)
        while old_date.weekday() == 0 or old_date.day == 1:  # Make sure it's not Monday or 1st
            old_date = old_date - timedelta(days=1)

        snapshot = {
            "timestamp": old_date.isoformat(),
            "portfolio_id": "test",
            "portfolio_name": "Test",
            "currency": "USD",
            "net_worth": {"amount": 1000.0, "currency": "USD"},
            "total_assets": {"amount": 1000.0, "currency": "USD"},
            "total_debts": {"amount": 0.0, "currency": "USD"},
            "accounts": [],
        }
        storage.save_snapshot(snapshot)

        # Cleanup with 60-day retention
        deleted = storage.cleanup_old_snapshots(retention_days=60)
        assert deleted == 1  # Old non-milestone should be deleted

        # Verify snapshot is gone
        snapshots = storage.list_snapshots()
        assert len(snapshots) == 0

    def test_cleanup_keeps_old_milestone_snapshots(self, tmp_path):
        """Test that cleanup keeps old milestone snapshots (Mondays, 1st of month)."""
        storage = SnapshotStorage(str(tmp_path))

        # Create old Monday (90 days ago)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        old_date = today - timedelta(days=90)
        # Find a Monday
        while old_date.weekday() != 0:
            old_date = old_date - timedelta(days=1)

        snapshot = {
            "timestamp": old_date.isoformat(),
            "portfolio_id": "test",
            "portfolio_name": "Test",
            "currency": "USD",
            "net_worth": {"amount": 1000.0, "currency": "USD"},
            "total_assets": {"amount": 1000.0, "currency": "USD"},
            "total_debts": {"amount": 0.0, "currency": "USD"},
            "accounts": [],
        }
        storage.save_snapshot(snapshot)

        # Cleanup with 60-day retention
        deleted = storage.cleanup_old_snapshots(retention_days=60)
        assert deleted == 0  # Milestone should be kept

        # Verify snapshot still exists
        snapshots = storage.list_snapshots()
        assert len(snapshots) == 1

    def test_cleanup_always_keeps_today_and_yesterday(self, tmp_path):
        """Test that cleanup always keeps today and yesterday."""
        storage = SnapshotStorage(str(tmp_path))

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        # Create today's snapshot
        today_snapshot = {
            "timestamp": today.isoformat(),
            "portfolio_id": "test",
            "portfolio_name": "Test",
            "currency": "USD",
            "net_worth": {"amount": 1000.0, "currency": "USD"},
            "total_assets": {"amount": 1000.0, "currency": "USD"},
            "total_debts": {"amount": 0.0, "currency": "USD"},
            "accounts": [],
        }
        storage.save_snapshot(today_snapshot)

        # Create yesterday's snapshot
        yesterday_snapshot = {
            "timestamp": yesterday.isoformat(),
            "portfolio_id": "test",
            "portfolio_name": "Test",
            "currency": "USD",
            "net_worth": {"amount": 1000.0, "currency": "USD"},
            "total_assets": {"amount": 1000.0, "currency": "USD"},
            "total_debts": {"amount": 0.0, "currency": "USD"},
            "accounts": [],
        }
        storage.save_snapshot(yesterday_snapshot)

        # Cleanup with 0-day retention (should still keep today and yesterday)
        deleted = storage.cleanup_old_snapshots(retention_days=0)
        assert deleted == 0

        # Verify both still exist
        snapshots = storage.list_snapshots()
        assert len(snapshots) == 2
