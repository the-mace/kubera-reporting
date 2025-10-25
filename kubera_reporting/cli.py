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
    report_date: datetime | None = None,
    dry_run: bool = False,
    hide_amounts: bool = False,
) -> None:
    """Helper function to generate and send a single report.

    Args:
        current_snapshot: Current portfolio snapshot
        previous_snapshot: Previous portfolio snapshot (may be None)
        report_type: Type of report to generate
        email: Email address to send to
        recipient_name: Optional recipient name for personalization
        generate_ai: Whether to generate AI insights (default: True)
        report_date: Optional date for the report (defaults to today)
        dry_run: If True, generate report but don't send email (default: False)
        hide_amounts: If True, mask dollar amounts in report (default: False)
    """
    reporter = PortfolioReporter()
    report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

    # Generate AI summary if we have previous data and AI is enabled
    ai_summary = None
    if previous_snapshot and generate_ai:
        console.print(f"[bold]Generating AI insights for {report_type.value} report...[/bold]")
        ai_summary = reporter.generate_ai_summary(
            report_data, report_type, hide_amounts=hide_amounts
        )
        if ai_summary:
            console.print(f"[green]✓[/green] AI insights generated for {report_type.value} report")

    # Generate HTML report with embedded chart (base64 for better forwarding)
    html_report = reporter.generate_html_report(
        report_data,
        report_type=report_type,
        ai_summary=ai_summary,
        recipient_name=recipient_name,
        hide_amounts=hide_amounts,
    )

    console.print(f"[green]✓[/green] {report_type.value.capitalize()} report generated")

    # Send email (unless dry-run)
    if dry_run:
        console.print(
            f"[yellow]⊘[/yellow] {report_type.value.capitalize()} report NOT sent (dry-run mode)"
        )
    else:
        emailer = EmailSender(email)
        date_to_use = report_date if report_date else datetime.now()
        report_date_str = date_to_use.strftime("%b %d")

        # Format subject based on report type
        period_descriptions = {
            ReportType.DAILY: "balance activity",
            ReportType.WEEKLY: "weekly summary",
            ReportType.MONTHLY: "monthly summary",
            ReportType.QUARTERLY: "quarterly summary",
            ReportType.YEARLY: "yearly summary",
        }
        period_desc = period_descriptions.get(report_type, "balance activity")
        subject = f"Your portfolio {period_desc} for {report_date_str}"

        emailer.send_html_email(subject, html_report)
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
@click.option(
    "--date",
    required=True,
    help="Date of snapshot to send report for (YYYY-MM-DD)",
)
@click.option(
    "--email", help="Email address to send report to (uses KUBERA_REPORT_EMAIL env if not set)"
)
@click.option(
    "--name",
    help="Recipient name for personalization (uses KUBERA_REPORT_NAME env if not set)",
)
@click.option("--data-dir", help="Data directory (default: ~/.kubera-reporting/data)")
@click.option(
    "--no-ai",
    is_flag=True,
    help="Skip AI insights generation",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Generate report without sending email (for testing)",
)
@click.option(
    "--hide-amounts",
    is_flag=True,
    help="Mask dollar amounts in report (shows percentages only)",
)
def send(
    date: str,
    email: str | None,
    name: str | None,
    data_dir: str | None,
    no_ai: bool,
    dry_run: bool,
    hide_amounts: bool,
) -> None:
    """Send email report for a specific historical date."""
    try:
        import os

        # Parse the date
        try:
            snapshot_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print(
                "[red]Error:[/red] Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15)"
            )
            sys.exit(1)

        # Initialize storage
        storage = SnapshotStorage(data_dir)

        # Load snapshot for the specified date
        current_snapshot = storage.load_snapshot(snapshot_date)
        if not current_snapshot:
            console.print(f"[red]Error:[/red] No snapshot found for {date}")
            console.print(
                f"\nUse 'kubera-report list-snapshots' to see available dates, "
                f"or 'kubera-report show --date {date}' to fetch and save this snapshot first."
            )
            sys.exit(1)

        console.print(
            f"[green]✓[/green] Loaded snapshot for {date} "
            f"(Net Worth: ${current_snapshot['net_worth']['amount']:,.2f})"
        )

        # Get email address (not required for dry-run)
        if not dry_run:
            if not email:
                email = os.getenv("KUBERA_REPORT_EMAIL")
                if not email:
                    console.print(
                        "[red]Error:[/red] No email address specified. "
                        "Use --email or set KUBERA_REPORT_EMAIL environment variable."
                    )
                    sys.exit(1)
        else:
            # Dry-run mode: use placeholder if no email provided
            if not email:
                email = os.getenv("KUBERA_REPORT_EMAIL", "dry-run@example.com")
            console.print("[yellow]Dry-run mode:[/yellow] Report will be generated but not sent")

        # Get recipient name for personalization
        if not name:
            name = os.getenv("KUBERA_REPORT_NAME")

        # Determine which report types to generate for this date
        report_types = storage.get_milestone_types(snapshot_date)
        console.print(
            f"[bold]Generating {len(report_types)} report(s): "
            f"{', '.join(rt.value for rt in report_types)}[/bold]"
        )

        # Generate and send each report type
        for report_type in report_types:
            console.print(f"\n[bold cyan]--- {report_type.value.upper()} REPORT ---[/bold cyan]")

            # Get appropriate comparison snapshot for this report type
            previous_snapshot = storage.get_comparison_snapshot(snapshot_date, report_type)

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
                name,
                generate_ai=not no_ai,
                report_date=snapshot_date,
                dry_run=dry_run,
                hide_amounts=hide_amounts,
            )

        if dry_run:
            console.print(
                f"\n[bold green]Done![/bold green] Generated {len(report_types)} report(s) "
                f"(dry-run, no emails sent)"
            )
        else:
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
    "--date",
    required=True,
    help="Date of snapshot to export report for (YYYY-MM-DD)",
)
@click.option("--output", "-o", help="Output file path (default: ./report_<date>.html)")
@click.option(
    "--name",
    help="Recipient name for personalization (uses KUBERA_REPORT_NAME env if not set)",
)
@click.option("--data-dir", help="Data directory (default: ~/.kubera-reporting/data)")
@click.option(
    "--no-ai",
    is_flag=True,
    help="Skip AI insights generation",
)
@click.option(
    "--report-type",
    type=click.Choice(["daily", "weekly", "monthly", "quarterly", "yearly"]),
    help="Report type to generate (default: auto-detect based on date)",
)
@click.option(
    "--hide-amounts",
    is_flag=True,
    help="Mask dollar amounts in report (shows percentages only)",
)
def export(
    date: str,
    output: str | None,
    name: str | None,
    data_dir: str | None,
    no_ai: bool,
    report_type: str | None,
    hide_amounts: bool,
) -> None:
    """Export HTML report for a specific date to a file."""
    try:
        import os

        # Parse the date
        try:
            snapshot_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print(
                "[red]Error:[/red] Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15)"
            )
            sys.exit(1)

        # Initialize storage
        storage = SnapshotStorage(data_dir)

        # Load snapshot for the specified date
        current_snapshot = storage.load_snapshot(snapshot_date)
        if not current_snapshot:
            console.print(f"[red]Error:[/red] No snapshot found for {date}")
            console.print("\nUse 'kubera-report list-snapshots' to see available dates.")
            sys.exit(1)

        console.print(
            f"[green]✓[/green] Loaded snapshot for {date} "
            f"(Net Worth: ${current_snapshot['net_worth']['amount']:,.2f})"
        )

        # Get recipient name for personalization
        if not name:
            name = os.getenv("KUBERA_REPORT_NAME")

        # Determine report type
        if report_type:
            # User specified report type
            report_types = [ReportType(report_type)]
        else:
            # Auto-detect based on date (just use the first one if multiple)
            report_types = storage.get_milestone_types(snapshot_date)

        # Use the first report type (or only one if user specified)
        selected_report_type = report_types[0]

        console.print(f"[bold]Generating {selected_report_type.value} report...[/bold]")

        # Get appropriate comparison snapshot
        previous_snapshot = storage.get_comparison_snapshot(snapshot_date, selected_report_type)

        if not previous_snapshot:
            console.print(
                "[yellow]Note:[/yellow] No comparison snapshot found. "
                "Generating report with current balances only."
            )

        # Generate report
        reporter = PortfolioReporter()
        report_data = reporter.calculate_deltas(current_snapshot, previous_snapshot)

        # Generate AI summary if we have previous data and AI is enabled
        ai_summary = None
        if previous_snapshot and not no_ai:
            console.print("[bold]Generating AI insights...[/bold]")
            ai_summary = reporter.generate_ai_summary(
                report_data, selected_report_type, hide_amounts=hide_amounts
            )
            if ai_summary:
                console.print("[green]✓[/green] AI insights generated")

        # Generate HTML report with collapse/expand functionality
        html_report = reporter.generate_html_report(
            report_data,
            report_type=selected_report_type,
            ai_summary=ai_summary,
            recipient_name=name,
            hide_amounts=hide_amounts,
            is_export=True,
        )

        # Determine output file path
        if not output:
            output = f"report_{date}.html"

        output_path = Path(output).resolve()

        # Write to file
        with open(output_path, "w") as f:
            f.write(html_report)

        console.print(f"\n[bold green]✓ Report exported to:[/bold green] {output_path}")

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

        # Generate HTML report with embedded base64 chart
        html_content = reporter.generate_html_report(
            report_data,
            ai_summary=ai_summary,
            recipient_name=name or "Investor",
        )
        console.print("[green]✓[/green] Generated HTML report with embedded chart")

        # Send email
        emailer = EmailSender(recipient=email)
        emailer.send_html_email(
            subject="Sample Kubera Portfolio Report (Daily)",
            html_content=html_content,
        )

        console.print(f"\n[bold green]✓ Email sent successfully to {email}![/bold green]")
        console.print("[dim]This is synthetic test data from fixtures[/dim]")

    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
