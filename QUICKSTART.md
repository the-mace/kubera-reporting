# Quick Start Guide

Get kubera-reporting running in 3 steps.

## 1. Install

```bash
git clone https://github.com/the-mace/kubera-reporting.git
cd kubera-reporting
pip install -e ".[dev]"
```

## 2. Configure

Create `~/.env` with your credentials:

```bash
# Required
KUBERA_API_KEY=your_api_key_here
KUBERA_SECRET=your_secret_here
KUBERA_REPORT_PORTFOLIO_INDEX=1  # Run 'kubera list' to find your index
KUBERA_REPORT_EMAIL=your-email@example.com

# Optional (for AI features)
GROK_API_KEY=your_grok_api_key
```

## 3. Run

### Try a test report (no API call needed)
```bash
kubera-report report --test
```

### Daily reports
```bash
# Just run this daily - it handles everything automatically!
kubera-report report

# The first run will send an email with current balances only (no deltas)
# Subsequent runs will include changes from the previous day
```

**Optional**: If you want to build history without receiving emails first:
```bash
# Day 1
kubera-report report --save-only

# Day 2 (wait 24 hours)
kubera-report report --save-only

# Day 3+ - generate reports with deltas
kubera-report report
```

**Smart caching**: The command automatically caches today's snapshot, so you can safely run it multiple times per day without hitting API rate limits. It only fetches from Kubera once per day.

## Done!

For complete documentation, see [README.md](README.md).

For development guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

For testing information, see [TESTING.md](TESTING.md).
