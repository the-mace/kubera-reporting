#!/usr/bin/env python3
"""Basic usage example for Kubera Reporting."""

from datetime import datetime, timedelta

from kubera_reporting.fetcher import KuberaFetcher
from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.storage import SnapshotStorage


def main():
    """Demonstrate basic usage."""
    # Fetch current portfolio data
    print("Fetching current portfolio data...")
    with KuberaFetcher() as fetcher:
        current_snapshot = fetcher.fetch_snapshot()

    print(f"Portfolio: {current_snapshot['portfolio_name']}")
    print(f"Net Worth: ${current_snapshot['net_worth']['amount']:,.2f}")
    print(f"Accounts: {len(current_snapshot['accounts'])}")

    # Save snapshot
    print("\nSaving snapshot...")
    storage = SnapshotStorage()
    storage.save_snapshot(current_snapshot)
    print("Snapshot saved!")

    # Load previous snapshot
    print("\nLoading previous snapshot...")
    yesterday = datetime.now() - timedelta(days=1)
    previous_snapshot = storage.load_snapshot(yesterday)

    if previous_snapshot:
        print(f"Found snapshot from {previous_snapshot['timestamp'][:10]}")

        # Calculate deltas
        print("\nCalculating changes...")
        reporter = PortfolioReporter()
        report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

        if report_data["net_worth_change"]:
            change = report_data["net_worth_change"]["amount"]
            print(f"Net Worth Change: ${change:+,.2f}")

        # Show top movers
        print("\nTop Asset Movers:")
        for i, delta in enumerate(report_data["asset_changes"][:5], 1):
            change = delta["change"]["amount"]
            print(f"  {i}. {delta['name']}: ${change:+,.2f}")

    else:
        print("No previous snapshot found. Run this script daily to track changes!")


if __name__ == "__main__":
    main()
