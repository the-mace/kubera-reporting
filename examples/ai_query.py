#!/usr/bin/env python3
"""AI query example for Kubera Reporting."""

from datetime import datetime, timedelta

from kubera_reporting.fetcher import KuberaFetcher
from kubera_reporting.llm_client import LLMClient
from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.storage import SnapshotStorage


def main():
    """Demonstrate AI queries."""
    # Fetch current data
    print("Fetching portfolio data...")
    with KuberaFetcher() as fetcher:
        current_snapshot = fetcher.fetch_snapshot()

    # Load previous snapshot
    storage = SnapshotStorage()
    yesterday = datetime.now() - timedelta(days=1)
    previous_snapshot = storage.load_snapshot(yesterday)

    # Build report data
    report_data = None
    if previous_snapshot:
        reporter = PortfolioReporter()
        report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Query AI
    llm = LLMClient()

    questions = [
        "What's my largest asset?",
        "How did my portfolio perform yesterday?",
        "What percentage of my portfolio is in stocks?",
    ]

    for question in questions:
        print(f"\n[Question] {question}")
        print("-" * 60)

        response = llm.query_portfolio(question, current_snapshot, report_data)
        print(response)


if __name__ == "__main__":
    main()
