# Testing Guide

## Overview

All tests use anonymized fixture data - **no API calls required** during development and testing.

## Test Data

### Real Data (Saved Once)
- Location: `~/.kubera-reporting/data/snapshot_2025-10-24.json`
- **Use this for manual testing only** (already fetched, no more API calls needed)

### Anonymized Fixtures (For Automated Tests)
- `tests/fixtures/snapshot_2025-01-15.json` - Previous day snapshot
- `tests/fixtures/snapshot_2025-01-16.json` - Current day snapshot
- **No PII** - all names, institutions, and values are anonymized
- Realistic changes: +$65,979 net worth, top movers range from +$43K to -$645

## Running Tests

### All Tests
```bash
pytest -v
```

**Result:** 16 tests pass
- 5 end-to-end tests (using fixtures)
- 4 example validation tests (mocked APIs)
- 3 reporter tests
- 4 storage tests

### Specific Test Files
```bash
# End-to-end tests
pytest tests/test_end_to_end.py -v

# Example code validation
pytest tests/test_examples.py -v
```

### Generate Sample Reports
```bash
pytest tests/test_end_to_end.py::test_html_report_export -v
```

**Output:** `sample_reports/` directory with:
- `sample_report_first_day.html` - First day report (no deltas)
- `sample_report_with_deltas.html` - Second day report (with changes)

## Test Coverage

### Core Functionality Tests

1. **First Day Report (No Previous Data)**
   - Shows current balances only
   - No delta indicators
   - Message: "Here's a snapshot of your current account balances"

2. **Second Day Report (With Deltas)**
   - Shows changes from previous day
   - Color-coded changes (green/red)
   - Message: "Here's a recap of account balances that changed yesterday"
   - Top movers sorted by absolute change

3. **Storage Round Trip**
   - Save and load snapshots
   - JSON serialization/deserialization

4. **Negative Changes**
   - Crypto Wallet: -$645 (tested explicitly)
   - Credit cards increasing (spending)

5. **Multiple Account Types**
   - Banks (checking, savings)
   - Investments (brokerage, trust accounts)
   - Retirement (IRA, 401K)
   - Cryptocurrency (exchange, wallet)
   - Real Estate (residence)
   - Vehicles
   - Debts (credit cards, auto loan)

### Example Code Validation Tests

The test suite includes validation for all example code in `examples/`:

1. **basic_usage.py** - Tested with fixture data
   - Mock KuberaFetcher to avoid API calls
   - Verify snapshot saving and loading
   - Test delta calculation with previous data
   - Ensure top movers are sorted correctly

2. **ai_query.py** - Tested with mocked LLM
   - Mock both KuberaFetcher and LLMClient
   - Verify multiple questions can be asked
   - Ensure report data is built correctly
   - No real API calls to Kubera or LLM services

3. **Import validation**
   - Verify all examples can be imported without errors
   - Ensures no syntax errors or missing dependencies

**Why this matters:** Example code often becomes outdated as APIs evolve. These tests catch breaking changes immediately and ensure documentation stays accurate.

## Sample Reports

View the generated HTML reports:

```bash
open sample_reports/sample_report_first_day.html
open sample_reports/sample_report_with_deltas.html
```

These show exactly what users will receive via email.

## Development Workflow

### No API Calls Needed!

All development and testing uses the fixtures:

```bash
# Run tests (uses fixtures)
pytest

# Generate sample reports (uses fixtures)
pytest tests/test_end_to_end.py::test_html_report_export

# Manual testing with real data (already saved)
python -m kubera_reporting.cli show --date 2025-10-24
```

### When You Need Fresh Data

To fetch fresh data from the API:

```bash
python -m kubera_reporting.cli report --save-only --portfolio-id 1
```

**Smart caching**: The command automatically caches today's snapshot, so you can run it multiple times per day without hitting API limits. It only fetches from Kubera once per day, then reuses the cached data for subsequent runs.

## Continuous Integration

All tests run without API access:
- Uses fixture data only
- No credentials required
- Fast execution (~0.08s)

See `.github/workflows/ci.yml` for CI configuration.

## Adding New Tests

To add tests, use the existing fixtures:

```python
import json
from pathlib import Path

@pytest.fixture
def snapshot_fixture():
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / "snapshot_2025-01-16.json") as f:
        return json.load(f)

def test_my_feature(snapshot_fixture):
    # Your test here
    pass
```

## Fixture Data Details

The anonymized fixtures contain:
- **Net Worth:** $2.84M (Jan 15) → $2.88M (Jan 16)
- **Assets:** $2.92M → $2.96M (+$42K)
- **Debts:** $76.2K → $76.8K (+$675)
- **Accounts:** 22 total (17 assets, 5 debts)

### Top Changes (Jan 15 → Jan 16)
1. Brokerage Account 1: +$18,500 (+2.26%)
2. Brokerage Account 2: +$7,700 (+2.00%)
3. IRA Account: +$6,300 (+2.00%)
4. 401K Account: +$4,500 (+2.00%)
5. Trust Account - Stocks: +$3,700 (+2.00%)

### Negative Changes
- Crypto Wallet: -$3,120 (-6.00%)
- Cryptocurrency Exchange: -$1,920 (-6.00%)
- Auto Loan: -$250 (payment)

## Summary

✅ **12 tests passing**
✅ **No API calls during testing**
✅ **Sample HTML reports generated**
✅ **Realistic anonymized data**
✅ **Both first-day and delta scenarios covered**
