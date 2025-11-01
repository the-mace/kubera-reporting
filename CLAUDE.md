# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_storage.py

# Run with coverage
pytest --cov=kubera_reporting --cov-report=term-missing

# Run single test
pytest tests/test_storage.py::test_save_and_load_snapshot
```

### Code Quality
```bash
# Format code
ruff format .

# Check linting
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Type checking
mypy kubera_reporting

# Run all quality checks (lint, format, type, test)
ruff check . && ruff format . && mypy kubera_reporting && pytest
```

### Running the Application
```bash
# Main CLI command (after pip install -e ".[dev]")
kubera-report --help

# Or via Python module
python -m kubera_reporting.cli --help

# Generate report (uses cached data if available for today)
kubera-report report

# Save snapshot only (no report)
kubera-report report --save-only

# Send test report (no API call, uses fixtures)
kubera-report report --test

# View historical snapshot (no API call)
kubera-report show --date 2025-01-15

# Send email report for a historical date (no API call, uses saved snapshot)
kubera-report send --date 2025-01-15

# Send to specific email and skip AI insights
kubera-report send --date 2025-01-15 --email user@example.com --no-ai

# Send report with masked dollar amounts (shows percentages only)
kubera-report send --date 2025-01-15 --hide-amounts

# Export HTML report to file (no email sent)
kubera-report export --date 2025-10-25 -o report.html

# Export without AI insights
kubera-report export --date 2025-10-25 --no-ai -o report.html

# Export with hidden amounts (for privacy when sharing)
kubera-report export --date 2025-10-25 --hide-amounts -o report.html

# List all snapshots
kubera-report list-snapshots

# AI query (uses API)
kubera-report query "What's my largest asset?"

# Regenerate sample reports (saves to sample_reports/)
kubera-report regenerate-samples

# Send sample report via email (uses test fixtures, no API call)
kubera-report send-sample

# Send to specific email
kubera-report send-sample --email user@example.com --name "John Doe"
```

## Architecture

### Multi-Period Reporting

The system supports **daily, weekly, monthly, quarterly, and yearly reports**. When you run the `report` command, it automatically detects if today is a milestone date and generates appropriate reports:

- **Daily**: Every day (compares today vs yesterday)
- **Weekly**: Every Monday (compares today vs last Monday)
- **Monthly**: 1st of every month (compares today vs 1st of last month)
- **Quarterly**: 1st of Jan/Apr/Jul/Oct (compares today vs 1st of previous quarter)
- **Yearly**: Jan 1st (compares today vs Jan 1st of previous year)

**Important**: Weekly, monthly, quarterly, and yearly reports are **only sent when comparison data exists**. If there's no previous snapshot for that period (e.g., no snapshot from last Monday for a weekly report), that report is automatically skipped. Daily reports are always sent to show current balances even on the first day.

**Example**: On Monday, April 1st, assuming you have all historical data:
1. Daily report (vs yesterday, March 31st)
2. Weekly report (vs last Monday, March 24th) - only if March 24th snapshot exists
3. Monthly report (vs March 1st) - only if March 1st snapshot exists
4. Quarterly report (vs January 1st) - only if January 1st snapshot exists

**First-time use**: On your first Monday, you'll only get a daily report. Once you have snapshots from previous Mondays, you'll start receiving weekly reports too.

### Smart Data Retention

To avoid storing every daily snapshot forever, the system uses an intelligent cleanup strategy:
- Keeps **all snapshots from the last 60 days** (configurable)
- Keeps **all milestone dates** (Mondays, 1st of month, quarter starts, year starts) indefinitely
- Always keeps **today and yesterday** for daily reports
- Automatically runs cleanup after each report generation

This means you'll have complete historical data for weekly/monthly/quarterly/yearly reports while minimizing storage usage.

### Core Components

**Data Flow**: Kubera API → Fetcher → Storage (JSON) → Reporter → Emailer

1. **fetcher.py** - Fetches portfolio data from Kubera API
   - `KuberaFetcher`: Wraps kubera-python-api client
   - Returns `PortfolioSnapshot` with accounts (both assets and debts)
   - Handles portfolio ID resolution (supports both indexes like "4" and GUIDs)

2. **storage.py** - JSON-based snapshot persistence
   - `SnapshotStorage`: Saves/loads daily snapshots to `~/.kubera-reporting/data/`
   - File naming: `snapshot_YYYY-MM-DD.json`
   - No database - simple JSON files for portability
   - **Multi-period support**:
     - `is_milestone_date(date)`: Checks if date is a milestone (Monday, 1st of month, etc.)
     - `get_milestone_types(date)`: Returns list of report types to generate for a date
     - `get_comparison_snapshot(date, report_type)`: Finds appropriate comparison snapshot
     - `cleanup_old_snapshots(retention_days)`: Removes old non-milestone snapshots

3. **reporter.py** - Report generation and delta calculation
   - `PortfolioReporter`: Core business logic
   - `_aggregate_holdings_to_accounts()`: Filters out individual stock holdings (IDs like `{uuid}_isin-xxx`) to show only parent accounts
   - `calculate_deltas()`: Compares current vs previous snapshots
   - `generate_html_report(report_data, report_type=ReportType.DAILY, ...)`: Creates formatted HTML emails with balance changes, now accepts report type
   - `calculate_asset_allocation()`: Groups assets by sheet_name for pie chart
   - `generate_allocation_chart()`: Creates matplotlib pie chart (can embed as base64 or return bytes)
   - `generate_ai_summary(report_data, report_type=ReportType.DAILY)`: Calls LLM for portfolio insights, context-aware of report period

4. **emailer.py** - Email delivery via local mail command
   - `EmailSender`: Sends MIME multipart HTML emails
   - Uses subprocess to call local `mail` command (macOS/Linux)
   - Supports inline images (pie charts) via CID attachment

5. **llm_client.py** - AI-powered analysis via LiteLLM
   - `LLMClient`: Unified interface for multiple LLM providers
   - Supports xAI Grok (default), Anthropic Claude, OpenAI
   - Loads API keys from `~/.env` (GROK_API_KEY, ANTHROPIC_API_KEY, etc.)
   - Two main methods:
     - `summarize_changes()`: Generates insights for email reports
     - `query_portfolio()`: Answers user questions about portfolio

6. **cli.py** - Click-based command-line interface
   - Commands: `report`, `show`, `query`, `list-snapshots`, `regenerate-samples`
   - Uses Rich library for formatted console output
   - Smart caching: Checks for today's snapshot before making API call
   - **Multi-period logic**:
     - Detects milestone dates and generates multiple reports in one run
     - Automatically cleans up old snapshots after report generation
     - Helper function `_generate_and_send_report()` handles individual report generation

7. **types.py** - Type definitions
   - `ReportType`: Enum for report types (DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY)
   - `PortfolioSnapshot`: Complete portfolio state at point in time
   - `AccountSnapshot`: Single account (has `sheet_name` for grouping, optional `section_name`)
   - `AccountDelta`: Change between two snapshots
   - `ReportData`: Calculated deltas for report generation

### Key Design Decisions

**Holdings Aggregation**: Raw Kubera API returns both parent accounts (e.g., "Account Name - Bonds") and individual holdings (500 stocks with IDs like `{parent_id}_isin-AAPL`). The reporter filters to show only parent accounts with their aggregate values. This logic is in `_aggregate_holdings_to_accounts()`.

**Sheet-Based Allocation**: Asset allocation uses `sheet_name` field from Kubera API (e.g., "Trust", "Retirement", "Bank"). The optional `section_name` field (from API's `sectionName`) provides additional categorization within sheets (e.g., "Taxable", "Tax Deferred", "Section 1") but is not currently used in allocation charts.

**Smart Caching**: The `report` command checks if today's snapshot already exists before calling the API. This prevents unnecessary API calls and respects rate limits (30/min, 100-1000/day depending on tier).

**Zero-Value Filtering**: Accounts with zero value are excluded from reports to reduce noise.

**Test Mode**: The `--test` flag uses synthetic fixture data to generate sample reports without making API calls. Useful for testing email formatting and AI insights.

## Testing Strategy

All tests use anonymized fixtures in `tests/fixtures/`:
- `snapshot_2025-01-15.json` - Previous day
- `snapshot_2025-01-16.json` - Current day

**No API calls needed during testing** - all data is from fixtures.

### Test Coverage

**Core functionality** (`test_end_to_end.py`, `test_reporter.py`, `test_storage.py`):
- First day report (no deltas)
- Second day report (with deltas)
- Storage round-trip (save/load)
- Negative changes
- Multiple account types

**Multi-period reporting** (`test_multi_period.py`):
- Milestone date detection (Mondays, 1st of month, quarter starts, year starts)
- Report type determination for each date
- Comparison snapshot logic for each report type
- Snapshot cleanup (keeps milestones, removes old non-milestones)
- Combined report scenarios (e.g., Monday + 1st of month)

**Example code validation** (`test_examples.py`):
- Verifies `examples/basic_usage.py` works with fixture data
- Verifies `examples/ai_query.py` works with mocked LLM
- Ensures examples can be imported without errors
- Uses mocks to avoid API calls (KuberaFetcher, LLMClient)

**Send command testing** (`test_send_command.py`):
- Tests the `send` command with `--dry-run` flag
- Verifies multi-period report detection (daily, weekly, etc.)
- Tests error handling (missing snapshots, invalid dates)
- NO emails are sent during tests (uses --dry-run)

Sample reports are generated to `sample_reports/`:
- `sample_report_first_day.html` - No deltas
- `sample_report_with_deltas.html` - With changes and AI insights

### Email Testing Guidelines

**CRITICAL**: Never send real emails during testing or development unless explicitly requested by a live user.

**Rules**:
1. **Always use `--dry-run` flag** when testing email-related commands
2. **Never use CliRunner without `--dry-run`** for commands that send emails
3. **Mock EmailSender** in unit tests that don't use CLI
4. **Use `--test` flag** for the `report` command when testing (uses fixtures, sends to configured email)
5. **Fixture emails must use reserved domains**: test@example.com, user@example.org (RFC 2606)

**Example - Correct Testing**:
```bash
# Testing send command - use --dry-run
kubera-report send --date 2025-01-15 --dry-run --no-ai

# Testing report command - use --test flag
kubera-report report --test
```

**Example - Correct Test Code**:
```python
# Good: Uses --dry-run flag
runner.invoke(cli, ["send", "--date", "2025-01-15", "--dry-run"])

# Good: Mocks the email sender
with patch("kubera_reporting.cli.EmailSender") as mock_emailer:
    runner.invoke(cli, ["send", "--date", "2025-01-15"])
```

**Example - INCORRECT (DO NOT DO THIS)**:
```python
# BAD: Will send real email!
runner.invoke(cli, ["send", "--date", "2025-01-15"])

# BAD: Will attempt to send to test@example.com
runner.invoke(cli, ["send", "--date", "2025-01-15", "--email", "test@example.com"])
```

**Why this matters**:
- Avoids spamming real email addresses during development
- Prevents accidental emails to users during testing
- Respects email server rate limits
- Maintains professional development practices

## Development Workflow

### Scratch Directory
Use `scratch/` for temporary test scripts - it's excluded from git. Write test files there instead of piping code to Python.

### Before Committing

**CRITICAL**: Always run ALL quality checks before committing. GitHub Actions will fail if any of these fail.

1. **FIRST: Auto-fix linting and formatting** (do this BEFORE checking):
   ```bash
   # Fix any auto-fixable linting issues (import sorting, etc.)
   ruff check --fix .

   # Format all code
   ruff format .
   ```

2. **THEN: Run verification checks** (do NOT skip any of these):
   ```bash
   # Verify linting (should pass after step 1)
   ruff check .

   # Verify type annotations - THIS IS CRITICAL!
   mypy kubera_reporting

   # Run all tests
   pytest
   ```

3. **Or run all at once** (stops at first failure):
   ```bash
   ruff check --fix . && ruff format . && ruff check . && mypy kubera_reporting && pytest
   ```

4. If you modified report formats, regenerate samples: `kubera-report regenerate-samples`

5. Include CLAUDE.md changes in the commit if you updated it

**Important Notes**:
- Always run `ruff check --fix` and `ruff format` BEFORE checking - they may modify files
- The mypy check validates type correctness for Python 3.10+ compatibility
- Many type errors won't show up in tests but will fail in CI
- Import sorting errors (I001) require `ruff check --fix` to auto-fix

### API Rate Limits
**IMPORTANT**: Only fetch from Kubera API once per day!
- Use `report --save-only` to build historical data
- Use `show --date YYYY-MM-DD` to view historical snapshots (no API call)
- Use `query` command (fetches once, then uses cached data)
- The `report` command auto-caches today's snapshot

## Configuration

All config lives in `~/.env`:
```bash
# Required: Kubera API credentials
KUBERA_API_KEY=your_api_key
KUBERA_SECRET=your_secret

# Required: Portfolio to report on (run 'kubera list' to see indexes)
KUBERA_REPORT_PORTFOLIO_INDEX=1

# Required: Email for reports
KUBERA_REPORT_EMAIL=your-email@example.com

# Optional: Recipient name for personalization
KUBERA_REPORT_NAME=Your Name

# Optional: AI/LLM API keys (for portfolio analysis)
GROK_API_KEY=your_grok_key          # xAI Grok (default)
ANTHROPIC_API_KEY=your_anthropic_key # Claude
OPENAI_API_KEY=your_openai_key      # GPT

# Optional: Override default model
KUBERA_REPORT_LLM_MODEL=xai/grok-4-fast-reasoning
```

## Dependencies

- **kubera-api**: Installed from GitHub (the-mace/kubera-python-api)
- **click**: CLI framework
- **rich**: Terminal formatting
- **python-dotenv**: Not actually used - custom env loading in llm_client.py
- **litellm**: Multi-provider LLM interface
- **jinja2**: HTML template rendering
- **matplotlib**: Pie chart generation

Dev dependencies:
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **ruff**: Linting and formatting
- **mypy**: Type checking

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
- Tests on Python 3.10, 3.11, 3.12
- Runs ruff (lint + format), mypy, pytest
- Uploads coverage to Codecov
- All tests use fixtures (no API credentials needed)
- be sure to run the ruff checks before committing code
- always write scratch code into the scratch directory. If you are going to write python code for scratch work, make a file in scratch and then execute it.
- always clean up scratch files in scratch directory before committing code
- always check for any real data or PII before committing code
- when debugging/working on the reports and a fix is ready, generate a real html report and open it in the default browser so the user can see the changes
- Review all changes to make sure there's no PII (person names, account names, brokerage names, etc) before every commit