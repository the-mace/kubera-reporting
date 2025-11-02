# Kubera Reporting

[![CI](https://github.com/the-mace/kubera-reporting/actions/workflows/ci.yml/badge.svg)](https://github.com/the-mace/kubera-reporting/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Daily, weekly, monthly, quarterly, and yearly portfolio reporting with AI-powered analysis for Kubera data.

## Features

- 📊 **Multi-Period Reports** - Daily, weekly, monthly, quarterly, and yearly portfolio summaries
- 🤖 **AI Analysis** - Ask questions about your portfolio using natural language
- 📈 **Change Tracking** - Compare snapshots across different time periods
- 💱 **Multi-Currency Support** - Works with USD, EUR, GBP, and other currencies
- 📧 **Email Integration** - Beautiful HTML emails sent via local mail
- 💾 **Smart Storage** - Intelligent snapshot retention (keeps milestones, cleans up old data)
- 🎯 **Easy to Use** - Simple CLI interface with automatic milestone detection
- 🔒 **Type Safe** - Comprehensive type hints
- 🧪 **Well Tested** - Test coverage for core functionality

## Installation

### Prerequisites

- Python 3.10 or higher
- Kubera API credentials (get yours at [kubera.com](https://www.kubera.com/))
- Local mail client configured (e.g., `mail` command on macOS/Linux)

### Install from Source

```bash
git clone https://github.com/the-mace/kubera-reporting.git
cd kubera-reporting
pip install -e ".[dev]"
```

This automatically installs [kubera-python-api](https://github.com/the-mace/kubera-python-api), the underlying Python client library for the Kubera API.

## Quick Start

### Setup Credentials

Add your credentials to `~/.env`:

```bash
# Kubera API credentials
KUBERA_API_KEY=your_api_key_here
KUBERA_SECRET=your_secret_here

# Portfolio to use (run 'kubera list' to see available portfolios and their indexes)
KUBERA_REPORT_PORTFOLIO_INDEX=1

# Email for reports
KUBERA_REPORT_EMAIL=your-email@example.com

# Optional: Name to use in report greeting (default: "Portfolio Report")
KUBERA_REPORT_NAME=Your Name

# AI/LLM API key (for xAI Grok)
GROK_API_KEY=your_grok_api_key
# or use another provider
# ANTHROPIC_API_KEY=your_anthropic_key
# OPENAI_API_KEY=your_openai_key

# Optional: Override default AI model
KUBERA_REPORT_LLM_MODEL=xai/grok-4-fast-reasoning
```

**Finding Your Portfolio Index:**

The installation includes the `kubera` CLI from [kubera-python-api](https://github.com/the-mace/kubera-python-api) which you can use to list your portfolios:

```bash
# List your portfolios with indexes (requires KUBERA_API_KEY and KUBERA_SECRET in ~/.env)
kubera list

# Output will show something like:
# Portfolios:
# 1. Personal Portfolio (USD)
# 2. Business Portfolio (USD)
# 3. Joint Account (USD)
# 4. Investment Portfolio (USD)  ← Use this index in KUBERA_REPORT_PORTFOLIO_INDEX
```

### First Run - Daily Reports

Just run this command daily - it handles everything automatically:

```bash
kubera-report report
```

The first run will send an email with current balances only (no deltas). Subsequent runs will include changes from the previous day.

**Optional**: If you want to build history without receiving emails first:

```bash
# Day 1
kubera-report report --save-only

# Day 2 (wait 24 hours)
kubera-report report --save-only

# Day 3+ - generate reports with deltas
kubera-report report
```

### Test Report (No API Call Required)

Before setting up your portfolio, you can send yourself a test report to see what the emails look like:

```bash
# Send test report using sample data
kubera-report report --test --email your-email@example.com

# Or use KUBERA_REPORT_EMAIL from ~/.env
kubera-report report --test
```

The test report includes:
- Sample portfolio data with realistic changes
- AI-generated insights
- Asset allocation pie chart
- Proper email formatting

### Automation

For daily automated reports, see the [Automation with Cron](#automation-with-cron) section below.

**Smart Caching**: The report command automatically checks if today's snapshot already exists:
- **First run today**: Fetches from Kubera API and saves snapshot
- **Subsequent runs today**: Uses cached data (no API call)
- This protects against rate limits and unnecessary API calls
- You can safely run the report multiple times per day

## Kubera Configuration Best Practices

### ⚠️ Account and Section Naming

**IMPORTANT**: In Kubera, ensure that your **account names do not exactly match your section names**. The reporting system filters out accounts where the name matches the section name to prevent double-counting parent accounts with their holdings.

**Problem Example:**
```
Sheet: Investment Accounts
├── Section: "Brokerage - Trading"
│   └── Account: "Brokerage - Trading" ❌ (account skipped - matches section name!)
│       └── Holdings...
```

**Correct Example:**
```
Sheet: Investment Accounts
├── Section: "Trading"
│   └── Account: "Brokerage - Trading" ✓ (account included - different from section)
│       └── Holdings...
```

**How to Fix:**
1. Log into Kubera
2. Go to your account settings
3. Rename sections to be distinct from account names (e.g., "Trading" instead of "Brokerage - Trading")

**Why this matters:** If an account name matches its section name exactly, the entire account (including all holdings) will be hidden from reports, potentially excluding significant portions of your portfolio.

## Multi-Period Reporting

The system automatically generates **multiple report types** based on the current date:

### Report Types

- **Daily** (Every day): Compares today vs yesterday
- **Weekly** (Every Monday): Compares today vs last Monday (7 days ago)
- **Monthly** (1st of month): Compares today vs 1st of previous month
- **Quarterly** (Jan 1, Apr 1, Jul 1, Oct 1): Compares today vs 1st of previous quarter
- **Yearly** (Jan 1): Compares today vs Jan 1 of previous year

### Examples

**Regular Tuesday (e.g., Jan 21)**:
- Sends **1 email**: Daily report

**Monday (e.g., Jan 20)**:
- Sends **2 emails**: Daily report + Weekly report

**First of month (e.g., Feb 1, a Saturday)**:
- Sends **2 emails**: Daily report + Monthly report

**Quarter start (e.g., Apr 1, a Tuesday)**:
- Sends **3 emails**: Daily report + Monthly report + Quarterly report

**Year start (e.g., Jan 1, a Wednesday)**:
- Sends **4 emails**: Daily report + Monthly report + Quarterly report + Yearly report

**Monday on quarter start (e.g., if Apr 1 falls on a Monday)**:
- Sends **4 emails**: Daily + Weekly + Monthly + Quarterly reports

### Smart Data Retention

The system keeps historical data efficiently:

- **Last 60 days**: All daily snapshots retained
- **Milestone dates**: Kept indefinitely (Mondays, 1st of month, quarter/year starts)
- **Today & yesterday**: Always retained for daily reports
- **Automatic cleanup**: Runs after each report, removes old non-milestone snapshots

This ensures you have complete data for weekly/monthly/quarterly/yearly comparisons while minimizing storage usage.

### AI Queries

Ask questions about your portfolio:

```bash
kubera-report query "What's my largest asset?"
kubera-report query "How did my portfolio perform yesterday?"
kubera-report query "What percentage is invested in stocks?"
```

### View Portfolio

```bash
# Show current portfolio
kubera-report show

# Show historical snapshot
kubera-report show --date 2025-01-15

# Send email report for a historical date
kubera-report send --date 2025-01-15

# List all snapshots
kubera-report list-snapshots
```

## Multi-Currency Support

Kubera Reporting automatically detects and displays the correct currency symbol based on your portfolio's currency setting in Kubera. The system supports all major currencies including:

- **USD** ($) - US Dollar
- **EUR** (€) - Euro
- **GBP** (£) - British Pound
- **JPY** (¥) - Japanese Yen
- And many more...

The currency is automatically:
- Displayed with the correct symbol in reports and CLI output
- Included in AI analysis prompts for context-aware insights
- Formatted consistently across HTML emails and console output

No additional configuration needed - the system reads the currency directly from your Kubera portfolio data.

## Command Reference

### `kubera-report report`

Generate and send daily portfolio report.

```bash
kubera-report report [OPTIONS]

Options:
  --portfolio-id TEXT  Portfolio ID to report on
  --email TEXT         Email address to send to
  --save-only          Only save snapshot, don't send report
  --test               Send test report using sample data (no API call)
  --data-dir TEXT      Data directory (default: ~/.kubera-reporting/data)
```

### `kubera-report show`

Show portfolio snapshot.

```bash
kubera-report show [OPTIONS]

Options:
  --portfolio-id TEXT  Portfolio ID to show
  --date TEXT          Show snapshot for date (YYYY-MM-DD)
  --data-dir TEXT      Data directory
```

### `kubera-report send`

Send email report for a historical date.

```bash
kubera-report send --date YYYY-MM-DD [OPTIONS]

Options:
  --date TEXT          Date of snapshot to send report for (required)
  --email TEXT         Email address to send to
  --name TEXT          Recipient name for personalization
  --no-ai              Skip AI insights generation
  --dry-run            Generate report without sending email (for testing)
  --data-dir TEXT      Data directory
```

This command is useful for:
- Re-sending a report for a past date
- Sending a report to someone else
- Generating reports for dates you missed
- Testing report generation without sending email (`--dry-run`)

**Note:** The command uses saved snapshots, so no API call is made. The snapshot for the specified date must already exist.

### `kubera-report query`

Ask AI questions about your portfolio.

```bash
kubera-report query QUESTION [OPTIONS]

Options:
  --portfolio-id TEXT  Portfolio ID to query
  --model TEXT         LLM model to use
  --data-dir TEXT      Data directory
```

### `kubera-report list-snapshots`

List all saved snapshots.

```bash
kubera-report list-snapshots [OPTIONS]

Options:
  --data-dir TEXT      Data directory
```

## Report Format

Reports include:

- **Net worth summary** with change indicator
- **Top asset movers** sorted by absolute change
- **Top debt movers** sorted by absolute change
- **Color coding** - green for gains, red for losses
- **Clean HTML email** with responsive design

Example:

```
Net worth: $1,359,205  +$6,205

Assets:
  Investment Account - Stocks    $105,000    +$1,575
  Retirement Account - 401k      $202,400    +$2,400
  Savings Account                $50,000     +$150
  ...

Liabilities:
  Mortgage                       $424,950    -$80
  Auto Loan                      $14,970     $0
  ...
```

## Automation with Cron

Add to your crontab to run daily before market open:

```bash
# Run at 5 AM every day (before market open at 9:30 AM ET)
0 5 * * * /path/to/venv/bin/kubera-report report

# This captures end-of-previous-day balances before markets open
# Adjust timing based on your timezone and preferences
```

**Why before market open?**
- Captures complete previous day's portfolio state
- Reports reflect actual closing balances before new trading day
- Consistent timing regardless of market volatility
- Avoids mid-day data that's incomplete or in flux

**Timezone considerations:**
- If you're in PST/PDT: 5 AM works well (8 AM ET, before 9:30 AM market open)
- If you're in EST/EDT: 5 AM is ideal (before 9:30 AM market open)
- Adjust as needed for your timezone and preferences

## Python Library Usage

You can also use Kubera Reporting as a Python library:

```python
from datetime import datetime, timedelta
from kubera_reporting.fetcher import KuberaFetcher
from kubera_reporting.storage import SnapshotStorage
from kubera_reporting.reporter import PortfolioReporter
from kubera_reporting.emailer import EmailSender

# Fetch current data
with KuberaFetcher() as fetcher:
    current = fetcher.fetch_snapshot()

# Load previous snapshot
storage = SnapshotStorage()
yesterday = datetime.now() - timedelta(days=1)
previous = storage.load_snapshot(yesterday)

# Generate report
reporter = PortfolioReporter()
report_data = reporter.calculate_deltas(current, previous)
html = reporter.generate_html_report(report_data)

# Send email
emailer = EmailSender("your-email@example.com")
emailer.send_html_email("Portfolio Report", html)
```

### AI Queries

```python
from kubera_reporting.llm_client import LLMClient

llm = LLMClient()

# Ask questions
response = llm.query_portfolio(
    "What's my asset allocation?",
    current_snapshot,
    report_data
)
print(response)

# Generate AI summary
summary = llm.summarize_changes(report_data)
print(summary)
```

## Data Storage

### ⚠️ Security Notice

**IMPORTANT**: The `~/.kubera-reporting/data/` directory contains **real financial data** including:
- Actual account balances and net worth
- Institution names and account numbers
- Complete portfolio holdings
- Historical financial records

**Security measures:**
- Directory and files are created with `700` permissions (user-only access)
- Data is stored locally on your machine (not uploaded anywhere)
- Consider encrypting your home directory or using full-disk encryption
- **Do NOT commit this directory to version control**
- **Do NOT share these files** - they contain your complete financial picture

### Storage Location

Snapshots are stored as JSON files in `~/.kubera-reporting/data/`:

```
~/.kubera-reporting/data/
  snapshot_2025-01-06.json  (Monday - kept as milestone)
  snapshot_2025-01-13.json  (Monday - kept as milestone)
  snapshot_2025-01-20.json  (Monday - kept as milestone)
  snapshot_2025-02-01.json  (1st of month - kept as milestone)
  snapshot_2025-02-02.json  (Within 60 days - kept)
  snapshot_2025-02-03.json  (Within 60 days - kept)
  ...
```

### Retention Strategy

The system uses **smart retention** to balance historical data needs with storage efficiency:

**Always Kept:**
- **Last 60 days**: All daily snapshots (for daily reports)
- **Mondays**: All Mondays indefinitely (for weekly reports)
- **1st of month**: All month starts indefinitely (for monthly reports)
- **Quarter starts**: Jan 1, Apr 1, Jul 1, Oct 1 (for quarterly reports)
- **Year starts**: Every Jan 1 (for yearly reports)

**Automatically Cleaned:**
- Non-milestone days older than 60 days (e.g., old Tuesdays, Wednesdays, etc.)

### Expected File Count

After running daily for a year, you'll have approximately:

- **Recent data** (last 60 days): ~60 files
- **Weekly milestones** (Mondays): ~52 files per year
- **Monthly milestones** (1st of month): ~12 files per year
- **Quarterly milestones**: 4 files per year
- **Yearly milestones**: 1 file per year

**Total after 1 year**: ~130-140 files (not 365!)

The cleanup runs automatically after each report, so you don't need to manually manage storage.

### File Format

Each snapshot contains:
- Portfolio metadata (ID, name, currency)
- Net worth, total assets, total debts
- All account details (name, value, institution)
- Timestamp

Example snapshot structure:
```json
{
  "timestamp": "2025-01-20T20:00:00+00:00",
  "portfolio_id": "uuid-12345",
  "portfolio_name": "My Portfolio",
  "currency": "USD",
  "net_worth": {
    "amount": 1359205.0,
    "currency": "USD"
  },
  "total_assets": {
    "amount": 1784155.0,
    "currency": "USD"
  },
  "total_debts": {
    "amount": 424950.0,
    "currency": "USD"
  },
  "accounts": [
    {
      "id": "uuid-001",
      "name": "Investment Account",
      "institution": "Brokerage Firm",
      "value": {"amount": 105000.0, "currency": "USD"},
      "category": "asset",
      "sheet_name": "Investments"
    }
  ]
}
```

### Manual Cleanup

If you want to adjust the retention period:

```python
from kubera_reporting.storage import SnapshotStorage

storage = SnapshotStorage()

# Keep only last 30 days (instead of default 60)
deleted = storage.cleanup_old_snapshots(retention_days=30)
print(f"Removed {deleted} old snapshots")
```

### Storage Size

Each snapshot is typically 5-50 KB depending on portfolio complexity:
- Simple portfolio (10 accounts): ~5 KB
- Medium portfolio (50 accounts): ~20 KB
- Large portfolio (200+ accounts): ~50 KB

After 1 year with smart retention: ~7-10 MB total

### Backup Considerations

Since this directory contains your **real financial history**:

**Recommended:**
- ✅ Include in your regular encrypted backup strategy
- ✅ Store backups securely (encrypted external drive, encrypted cloud backup)
- ✅ Verify file permissions remain `600` (user read/write only)

**NOT Recommended:**
- ❌ Backing up to unencrypted cloud storage (Dropbox, Google Drive, etc.)
- ❌ Storing on shared computers or network drives
- ❌ Committing to Git repositories (even private ones)

### Deleting Your Data

To completely remove all stored financial data:

```bash
# Remove all snapshots
rm -rf ~/.kubera-reporting/data/

# This will delete your entire financial history
# Weekly/monthly/yearly reports will no longer work until you rebuild history
```

## Future Enhancements

Completed features:

- ✅ Daily reports
- ✅ Weekly summary reports
- ✅ Monthly performance reports
- ✅ Quarterly reports
- ✅ Annual reports with year-over-year comparison
- ✅ Percentage changes in addition to dollar amounts
- ✅ Portfolio allocation insights (pie charts)
- ✅ AI-powered portfolio analysis

Potential future enhancements:

### Trend Analysis & Historical Charts
- ⬜ Net worth trend line charts (30-day, 90-day, 1-year views)
- ⬜ Asset allocation changes over time (stacked area charts)
- ⬜ Account-level performance trends
- ⬜ Moving averages and volatility metrics
- ⬜ Year-over-year comparison charts

### Smart Signals & Alerts
- ⬜ **Allocation drift detection**: Alert when asset allocation deviates from target
- ⬜ **Large change alerts**: Notify on significant account movements (>10%)
- ⬜ **Milestone celebrations**: Track new net worth highs and FIRE milestones
- ⬜ **Unusual activity detection**: Flag abnormal patterns across multiple accounts
- ⬜ **Threshold notifications**: Custom alerts (e.g., "crypto allocation > 15%")
- ⬜ **Market correlation signals**: Detect when portfolio moves against market trends

### Rebalance Recommendations
- ⬜ **Target allocation tracking**: Define and monitor desired asset mix (e.g., 60/30/10 stocks/bonds/cash)
- ⬜ **Automatic rebalance suggestions**: Calculate specific trades needed to reach target allocation
- ⬜ **Rebalancing triggers**: Alert when drift exceeds configured threshold (e.g., >5%)
- ⬜ **Tax-aware recommendations**: Prioritize taxable vs. tax-advantaged accounts
- ⬜ **Dollar-cost averaging scheduler**: Suggest optimal times for regular investments
- ⬜ **Portfolio optimization**: AI-powered suggestions based on risk tolerance and goals

### Other Enhancements
- ⬜ Custom report templates
- ⬜ Web dashboard interface
- ⬜ Export to CSV/Excel for tax reporting
- ⬜ Integration with other financial tools
- ⬜ Multi-portfolio comparison reports

## Development

### Setup Development Environment

```bash
git clone https://github.com/the-mace/kubera-reporting.git
cd kubera-reporting
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
pytest --cov=kubera_reporting --cov-report=term-missing
```

### Code Quality

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Type checking
mypy kubera_reporting
```

## Troubleshooting

### Email Not Sending

Ensure your local mail client is configured:

```bash
# Test mail command
echo "Test email" | mail -s "Test Subject" your-email@example.com
```

On macOS, you may need to configure Postfix or use an alternative mail client.

### No Previous Snapshot

Run `kubera-report report --save-only` for at least two consecutive days to build history before generating comparison reports.

### API Errors

Check your Kubera API credentials in `~/.env`. Ensure your API key has the necessary permissions and isn't IP-restricted.

### Rate Limits

Kubera API has the following rate limits:
- **30 requests per minute** (global)
- **100 requests per day** (Essential tier)
- **1000 requests per day** (Black tier)

The smart caching feature automatically prevents redundant API calls by reusing today's snapshot. If you hit rate limits:
- Use `--save-only` to fetch data once
- View historical data with `show --date YYYY-MM-DD`
- AI queries use cached data and don't count against limits

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Related Projects

This project is built on top of:
- **[kubera-python-api](https://github.com/the-mace/kubera-python-api)** - Python client library for the Kubera API (automatically installed as a dependency)

Other projects by the same author:
- [osx-file-renamer](https://github.com/the-mace/osx-file-renamer) - AI-powered file renaming tool

## Support

For issues and questions:
- [GitHub Issues](https://github.com/the-mace/kubera-reporting/issues)
- [Kubera API Documentation](https://www.kubera.com/)
