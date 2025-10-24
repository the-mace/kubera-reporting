"""Command-line interface for Kubera Reporting."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from kubera_reporting.emailer import EmailSender
from kubera_reporting.exceptions import KuberaReportingError
from kubera_reporting.fetcher import KuberaFetcher
from kubera_reporting.llm_client import LLMClient
from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.storage import SnapshotStorage
from kubera_reporting.types import PortfolioSnapshot, ReportType

console = Console()


@click.group()
@click.version_option(package_name="kubera-reporting")
def cli() -> None:
    """Kubera Reporting - Daily reports and AI analysis for your portfolio."""
    pass


def _generate_and_send_report(
    current_snapshot: PortfolioSnapshot,
    previous_snapshot: PortfolioSnapshot | None,
    report_type: ReportType,
    email: str,
    recipient_name: str | None = None,
    generate_ai: bool = True,
) -> None:
    """Helper function to generate and send a single report.

    Args:
        current_snapshot: Current portfolio snapshot
        previous_snapshot: Previous portfolio snapshot (may be None)
        report_type: Type of report to generate
        email: Email address to send to
        recipient_name: Optional recipient name for personalization
        generate_ai: Whether to generate AI insights (default: True)
    """
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Generate AI summary if we have previous data and AI is enabled
    ai_summary = None
    if previous_snapshot and generate_ai:
        console.print(f"[bold]Generating AI insights for {report_type.value} report...[/bold]")
        ai_summary = reporter.generate_ai_summary(report_data, report_type)
        if ai_summary:
            console.print(f"[green]✓[/green] AI insights generated for {report_type.value} report")

    html_report = reporter.generate_html_report(
        report_data, report_type=report_type, ai_summary=ai_summary, recipient_name=recipient_name
    )

    # Generate chart image
    allocation = reporter.calculate_asset_allocation(current_snapshot)
    chart_image = reporter.generate_allocation_chart(allocation) if allocation else None

    console.print(f"[green]✓[/green] {report_type.value.capitalize()} report generated")

    # Send email
    emailer = EmailSender(email)
    report_date = datetime.now().strftime("%b %d")

    # Format subject based on report type
    period_descriptions = {
        ReportType.DAILY: "balance activity",
        ReportType.WEEKLY: "weekly summary",
        ReportType.MONTHLY: "monthly summary",
        ReportType.QUARTERLY: "quarterly summary",
        ReportType.YEARLY: "yearly summary",
    }
    period_desc = period_descriptions.get(report_type, "balance activity")
    subject = f"Your portfolio {period_desc} for {report_date}"

    emailer.send_html_email(subject, html_report, chart_image=chart_image)
    console.print(f"[green]✓[/green] {report_type.value.capitalize()} report sent to {email}")


@cli.command()
@click.option(
    "--portfolio-id",
    help="Portfolio ID/index to report on (uses KUBERA_REPORT_PORTFOLIO_INDEX env if not set)",
)
@click.option(
    "--email", help="Email address to send report to (uses KUBERA_REPORT_EMAIL env if not set)"
)
@click.option(
    "--save-only", is_flag=True, help="Only save snapshot without generating/sending report"
)
@click.option("--data-dir", help="Data directory (default: ~/.kubera-reporting/data)")
@click.option(
    "--test", is_flag=True, help="Send test report using sample data (no API call required)"
)
def report(
    portfolio_id: str | None,
    email: str | None,
    save_only: bool,
    data_dir: str | None,
    test: bool,
) -> None:
    """Generate and send daily portfolio report."""
    try:
        import json
        import os

        # Handle test mode
        if test:
            console.print("[bold yellow]Test Mode:[/bold yellow] Using sample fixtures")

            # Load fixtures
            fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures"
            with open(fixture_dir / "snapshot_2025-01-16.json") as f:
                current_snapshot = json.load(f)
            with open(fixture_dir / "snapshot_2025-01-15.json") as f:
                previous_snapshot = json.load(f)

            console.print("[green]✓[/green] Loaded test snapshots")

            # Get email address
            if not email:
                email = os.getenv("KUBERA_REPORT_EMAIL")
                if not email:
                    console.print(
                        "[red]Error:[/red] No email address specified. "
                        "Use --email or set KUBERA_REPORT_EMAIL environment variable."
                    )
                    sys.exit(1)

            # Get recipient name for personalization
            recipient_name = os.getenv("KUBERA_REPORT_NAME")

            # Generate and send test report (always daily)
            console.print("[bold]Generating test report (daily)...[/bold]")
            _generate_and_send_report(
                current_snapshot,
                previous_snapshot,
                ReportType.DAILY,
                email,
                recipient_name,
                generate_ai=True,
            )

            console.print(f"[bold green]Done![/bold green] Test report sent to {email}")
            return

        # Get portfolio ID from env if not specified
        if not portfolio_id:
            portfolio_id = os.getenv("KUBERA_REPORT_PORTFOLIO_INDEX")
            if not portfolio_id:
                console.print(
                    "[red]Error:[/red] No portfolio specified. "
                    "Use --portfolio-id or set KUBERA_REPORT_PORTFOLIO_INDEX in ~/.env"
                )
                sys.exit(1)

        # Initialize storage
        storage = SnapshotStorage(data_dir)

        # Check if we already have today's snapshot (avoid redundant API calls)
        today = datetime.now()
        current_snapshot = storage.load_snapshot(today)

        if current_snapshot:
            console.print(
                "[yellow]Using cached snapshot from today[/yellow] "
                f"(Net Worth: ${current_snapshot['net_worth']['amount']:,.2f})"
            )
            if save_only:
                console.print(
                    "[bold green]Done![/bold green] Today's snapshot already exists, "
                    "no report generated."
                )
                return
        else:
            console.print("[bold]Fetching portfolio data...[/bold]")

            # Fetch current data from API
            with KuberaFetcher() as fetcher:
                current_snapshot = fetcher.fetch_snapshot(portfolio_id)

            console.print(
                f"[green]✓[/green] Fetched {current_snapshot['portfolio_name']} "
                f"(Net Worth: ${current_snapshot['net_worth']['amount']:,.2f})"
            )

            # Save snapshot
            storage.save_snapshot(current_snapshot)
            console.print("[green]✓[/green] Snapshot saved")

            if save_only:
                console.print("[bold green]Done![/bold green] Snapshot saved, no report generated.")
                return

        # Get email address (needed for report generation)
        if not email:
            email = os.getenv("KUBERA_REPORT_EMAIL")
            if not email:
                console.print(
                    "[red]Error:[/red] No email address specified. "
                    "Use --email or set KUBERA_REPORT_EMAIL environment variable."
                )
                sys.exit(1)

        # Get recipient name for personalization
        recipient_name = os.getenv("KUBERA_REPORT_NAME")

        # Determine which report types to generate for today
        report_types = storage.get_milestone_types(today)
        console.print(
            f"[bold]Generating {len(report_types)} report(s): "
            f"{', '.join(rt.value for rt in report_types)}[/bold]"
        )

        # Generate and send each report type
        for report_type in report_types:
            console.print(f"\n[bold cyan]--- {report_type.value.upper()} REPORT ---[/bold cyan]")

            # Get appropriate comparison snapshot for this report type
            previous_snapshot = storage.get_comparison_snapshot(today, report_type)

            if not previous_snapshot:
                console.print(
                    f"[yellow]Note:[/yellow] No comparison snapshot found for "
                    f"{report_type.value} report. Generating report with current balances only."
                )

            # Generate and send this report
            _generate_and_send_report(
                current_snapshot,
                previous_snapshot,
                report_type,
                email,
                recipient_name,
                generate_ai=True,
            )

        # Clean up old snapshots (keep milestones and recent data)
        console.print("\n[bold]Cleaning up old snapshots...[/bold]")
        deleted_count = storage.cleanup_old_snapshots(retention_days=60)
        if deleted_count > 0:
            console.print(f"[green]✓[/green] Removed {deleted_count} old snapshot(s)")
        else:
            console.print("[dim]No old snapshots to remove[/dim]")

        console.print(
            f"\n[bold green]Done![/bold green] Sent {len(report_types)} report(s) to {email}"
        )

    except KuberaReportingError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--portfolio-id",
    help="Portfolio ID/index to show (uses KUBERA_REPORT_PORTFOLIO_INDEX env if not set)",
)
@click.option("--data-dir", help="Data directory (default: ~/.kubera-reporting/data)")
@click.option("--date", help="Show snapshot for specific date (YYYY-MM-DD)")
def show(portfolio_id: str | None, data_dir: str | None, date: str | None) -> None:
    """Show current or historical portfolio snapshot."""
    try:
        import os

        storage = SnapshotStorage(data_dir)

        if date:
            # Load specific date
            snapshot_date = datetime.strptime(date, "%Y-%m-%d")
            snapshot = storage.load_snapshot(snapshot_date)
            if not snapshot:
                console.print(f"[red]Error:[/red] No snapshot found for {date}")
                sys.exit(1)
        else:
            # Check if we already have today's snapshot (avoid redundant API calls)
            today = datetime.now()
            snapshot = storage.load_snapshot(today)

            if snapshot:
                console.print(
                    "[yellow]Using cached snapshot from today[/yellow] "
                    f"(Net Worth: ${snapshot['net_worth']['amount']:,.2f})"
                )
            else:
                # Get portfolio ID from env if not specified
                if not portfolio_id:
                    portfolio_id = os.getenv("KUBERA_REPORT_PORTFOLIO_INDEX")
                    if not portfolio_id:
                        console.print(
                            "[red]Error:[/red] No portfolio specified. "
                            "Use --portfolio-id or set KUBERA_REPORT_PORTFOLIO_INDEX in ~/.env"
                        )
                        sys.exit(1)

                # Fetch current from API
                console.print("[bold]Fetching current data...[/bold]")
                with KuberaFetcher() as fetcher:
                    snapshot = fetcher.fetch_snapshot(portfolio_id)

        # Display snapshot
        console.print(f"\n[bold]{snapshot['portfolio_name']}[/bold]")
        console.print(f"Date: {snapshot['timestamp'][:10]}")
        console.print(f"\nNet Worth: [bold]${snapshot['net_worth']['amount']:,.2f}[/bold]")
        console.print(f"Total Assets: ${snapshot['total_assets']['amount']:,.2f}")
        console.print(f"Total Debts: ${snapshot['total_debts']['amount']:,.2f}")

        # Show top assets
        assets = [a for a in snapshot["accounts"] if a["category"] == "asset"]
        assets.sort(key=lambda x: x["value"]["amount"], reverse=True)

        if assets:
            console.print("\n[bold]Top Assets:[/bold]")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Name", style="cyan")
            table.add_column("Institution", style="dim")
            table.add_column("Value", style="green", justify="right")

            for asset in assets[:10]:
                table.add_row(
                    asset["name"],
                    asset["institution"] or "-",
                    f"${asset['value']['amount']:,.2f}",
                )

            console.print(table)

    except KuberaReportingError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("question")
@click.option(
    "--portfolio-id",
    help="Portfolio ID/index to query (uses KUBERA_REPORT_PORTFOLIO_INDEX env if not set)",
)
@click.option("--data-dir", help="Data directory (default: ~/.kubera-reporting/data)")
@click.option(
    "--model", help="LLM model to use (default: from KUBERA_REPORT_LLM_MODEL env or grok-4-fast)"
)
def query(question: str, portfolio_id: str | None, data_dir: str | None, model: str | None) -> None:
    """Ask AI questions about your portfolio."""
    try:
        import os

        # Initialize storage
        storage = SnapshotStorage(data_dir)

        # Check if we already have today's snapshot (avoid redundant API calls)
        today = datetime.now()
        current_snapshot = storage.load_snapshot(today)

        if current_snapshot:
            console.print(
                "[yellow]Using cached snapshot from today[/yellow] "
                f"(Net Worth: ${current_snapshot['net_worth']['amount']:,.2f})"
            )
        else:
            # Get portfolio ID from env if not specified
            if not portfolio_id:
                portfolio_id = os.getenv("KUBERA_REPORT_PORTFOLIO_INDEX")
                if not portfolio_id:
                    console.print(
                        "[red]Error:[/red] No portfolio specified. "
                        "Use --portfolio-id or set KUBERA_REPORT_PORTFOLIO_INDEX in ~/.env"
                    )
                    sys.exit(1)

            console.print("[bold]Fetching portfolio data...[/bold]")

            # Fetch current data from API
            with KuberaFetcher() as fetcher:
                current_snapshot = fetcher.fetch_snapshot(portfolio_id)

            # Save snapshot for future use
            storage.save_snapshot(current_snapshot)
            console.print("[green]✓[/green] Snapshot saved")

        # Load previous snapshot for context
        yesterday = today - timedelta(days=1)
        previous_snapshot = storage.load_snapshot(yesterday)

        # Build report data if previous exists
        report_data = None
        if previous_snapshot:
            reporter = PortfolioReporter()
            report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

        # Query LLM
        console.print("[bold]Analyzing...[/bold]\n")
        llm = LLMClient(model)
        response = llm.query_portfolio(question, current_snapshot, report_data)

        # Render markdown as formatted text for human readability
        console.print(Markdown(response))

    except KuberaReportingError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--data-dir", help="Data directory (default: ~/.kubera-reporting/data)")
def list_snapshots(data_dir: str | None) -> None:
    """List all saved snapshots."""
    try:
        storage = SnapshotStorage(data_dir)
        dates = storage.list_snapshots()

        if not dates:
            console.print("[yellow]No snapshots found.[/yellow]")
            return

        console.print(f"\n[bold]Found {len(dates)} snapshot(s):[/bold]\n")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Date", style="cyan")
        table.add_column("File", style="dim")

        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            file_path = Path(storage.data_dir) / f"snapshot_{date_str}.json"
            table.add_row(date_str, str(file_path))

        console.print(table)

    except KuberaReportingError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@cli.command()
def regenerate_samples() -> None:
    """Regenerate sample reports with synthetic data and embedded pie charts."""
    try:
        import json

        console.print("[bold]Regenerating sample reports...[/bold]\n")

        # Load fixtures
        fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"

        with open(fixtures_dir / "snapshot_2025-01-15.json") as f:
            snapshot_day1 = json.load(f)

        with open(fixtures_dir / "snapshot_2025-01-16.json") as f:
            snapshot_day2 = json.load(f)

        console.print("[green]✓[/green] Loaded test fixtures")

        reporter = PortfolioReporter()

        # Generate first day report (no previous data)
        console.print("[bold]Generating first day sample report...[/bold]")
        report_data_day1 = reporter.calculate_deltas(snapshot_day2, None)
        html_day1 = reporter.generate_html_report(
            report_data_day1,
            ai_summary=None,
            recipient_name="Test User",
            embed_chart_data=True,  # Embed chart as base64 for viewing in browser
        )

        # Save first day report
        output_dir = Path(__file__).parent.parent / "sample_reports"
        output_dir.mkdir(exist_ok=True)
        output_path_day1 = output_dir / "sample_report_first_day.html"
        with open(output_path_day1, "w") as f:
            f.write(html_day1)
        console.print(f"[green]✓[/green] Saved: {output_path_day1}")

        # Generate second day report (with deltas)
        console.print("\n[bold]Generating second day sample report (with deltas)...[/bold]")
        report_data_day2 = reporter.calculate_deltas(snapshot_day2, snapshot_day1)

        # Generate AI summary for second day report
        ai_summary = """Your portfolio grew by $6,205 (0.46%) primarily driven by \
positive equity markets and retirement fund performance. The Retirement Account \
gained $2,400 (1.2%) and Investment Account - Stocks rose $1,575 (1.5%), reflecting \
broad market strength. However, Crypto Wallet declined significantly by $3,125 \
(-12.5%), highlighting continued volatility in digital assets.

Watch the crypto allocation carefully - at 12.5% decline in a single day, this \
asset class is experiencing elevated volatility. Consider whether your overall \
crypto exposure aligns with your risk tolerance. The modest debt reduction ($80 \
across mortgage and auto loan) continues to improve your leverage position incrementally.

Action: Review your crypto holdings as part of next portfolio rebalancing - the \
12.5% daily swing suggests this allocation may warrant adjustment based on your \
risk profile."""

        html_day2 = reporter.generate_html_report(
            report_data_day2,
            ai_summary=ai_summary,
            recipient_name="Test User",
            embed_chart_data=True,  # Embed chart as base64 for viewing in browser
        )

        # Save second day report
        output_path_day2 = output_dir / "sample_report_with_deltas.html"
        with open(output_path_day2, "w") as f:
            f.write(html_day2)
        console.print(f"[green]✓[/green] Saved: {output_path_day2}")

        console.print("\n[bold green]Done![/bold green] Sample reports regenerated successfully!")
        console.print("[dim]All data is synthetic with embedded pie charts[/dim]")
        console.print("[dim]Reports can be viewed directly in a browser[/dim]")

    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--email",
    help="Email address to send to (uses KUBERA_REPORT_EMAIL env if not set)",
)
@click.option(
    "--name",
    help="Recipient name for personalization (uses KUBERA_REPORT_NAME env if not set)",
)
def send_sample(email: str | None, name: str | None) -> None:
    """Send sample report with deltas via email."""
    import json
    import os

    try:
        # Get email from env if not provided
        if not email:
            email = os.environ.get("KUBERA_REPORT_EMAIL")
            if not email:
                console.print(
                    "[red]Error:[/red] Email not provided. "
                    "Use --email or set KUBERA_REPORT_EMAIL environment variable."
                )
                sys.exit(1)

        # Get recipient name from env if not provided
        if not name:
            name = os.environ.get("KUBERA_REPORT_NAME")

        console.print(f"[bold]Sending sample report to {email}...[/bold]\n")

        # Load fixtures
        fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"

        with open(fixtures_dir / "snapshot_2025-01-15.json") as f:
            snapshot_day1 = json.load(f)

        with open(fixtures_dir / "snapshot_2025-01-16.json") as f:
            snapshot_day2 = json.load(f)

        console.print("[green]✓[/green] Loaded test fixtures")

        # Generate report with deltas
        reporter = PortfolioReporter()
        report_data = reporter.calculate_deltas(snapshot_day2, snapshot_day1)

        # Generate allocation chart as bytes (not embedded)
        allocation = reporter.calculate_asset_allocation(snapshot_day2)
        chart_bytes = reporter.generate_allocation_chart(allocation)
        console.print("[green]✓[/green] Generated allocation chart")

        # AI summary (same as regenerate_samples)
        ai_summary = (
            "The net worth rose $6,205 (0.46%) today, primarily driven by gains in the "
            "Retirement Account - 401k - 9999 (+$2,400, 1.19%) and Investment Account - Stocks - "
            "1234 (+$1,575, 1.43%), alongside cash inflows to the Checking Account (+$500, 3.33%) "
            "and minor debt reductions on the Mortgage - Primary Residence (-$50) and Auto Loan - "
            "Vehicle 1 (-$30), which offset a sharp $3,125 (12.5%) decline in the Crypto Wallet. "
            "This movement underscores the portfolio's heavy 60.42% real estate concentration, "
            "which remained flat at zero change, amplifying the relative impact of volatility in "
            "the smaller 22.39% stocks and 1.55% crypto allocations and exposing concentration "
            "risks in illiquid assets amid diversified daily swings. Watch the stark divergence in "
            "crypto's outsized drop versus steady equity and cash gains, signaling potential "
            "broader market rotation away from high-risk assets. Review the Crypto Wallet position "
            "immediately to assess underlying causes like price volatility or transaction errors, "
            "considering a tactical reduction if it persists."
        )

        # Generate HTML report (without embedded chart, since we'll attach it separately)
        html_content = reporter.generate_html_report(
            report_data,
            ai_summary=ai_summary,
            recipient_name=name or "Investor",
            embed_chart_data=False,  # Don't embed - we'll attach separately for email
        )
        console.print("[green]✓[/green] Generated HTML report")

        # Send email
        emailer = EmailSender(recipient=email)
        emailer.send_html_email(
            subject="Sample Kubera Portfolio Report (Daily)",
            html_content=html_content,
            chart_image=chart_bytes,
        )

        console.print(f"\n[bold green]✓ Email sent successfully to {email}![/bold green]")
        console.print("[dim]This is synthetic test data from fixtures[/dim]")

    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
