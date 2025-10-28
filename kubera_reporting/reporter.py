"""Generate portfolio reports."""

import io
import json
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
from jinja2 import Template

from kubera_reporting import currency_format
from kubera_reporting.exceptions import ReportGenerationError
from kubera_reporting.types import (
    AccountDelta,
    MoneyValue,
    PortfolioSnapshot,
    ReportData,
    ReportType,
)

# Use non-interactive backend for matplotlib
matplotlib.use("Agg")


class PortfolioReporter:
    """Generates portfolio reports."""

    def _aggregate_holdings_to_accounts(self, snapshot: PortfolioSnapshot) -> PortfolioSnapshot:
        """Filter out individual holdings and zero-value accounts, keeping only parent accounts.

        Raw API data contains both parent accounts (e.g., "Account Name - Bonds - 1234")
        and their individual holdings (e.g., 500 stocks with IDs like {uuid}_isin-xxx).

        We want to show only the parent accounts with their aggregate values,
        excluding individual holdings and accounts with zero value.

        Args:
            snapshot: Snapshot containing raw API data with both parents and holdings

        Returns:
            Snapshot with only parent accounts (holdings and zero-value accounts removed)
        """
        # Filter out holdings and zero-value accounts
        filtered_accounts = []

        for account in snapshot["accounts"]:
            acc_id = account["id"]

            # Check if this is a holding (should be skipped)
            # All holdings have underscore in ID (parent_child pattern)
            # Parent accounts are pure UUIDs without underscores
            is_holding = "_" in acc_id

            # Check if account has zero value (should be skipped)
            has_zero_value = account["value"]["amount"] == 0

            if not is_holding and not has_zero_value:
                # This is either a parent account or standalone account with value - keep it
                filtered_accounts.append(account)

        # Return new snapshot with filtered accounts
        return {
            **snapshot,
            "accounts": filtered_accounts,
        }

    def calculate_deltas(
        self, current: PortfolioSnapshot, previous: PortfolioSnapshot | None
    ) -> ReportData:
        """Calculate changes between current and previous snapshots.

        Args:
            current: Current snapshot
            previous: Previous snapshot (may be None)

        Returns:
            Report data with calculated deltas
        """
        # Save original snapshot for allocation (needs child holdings with detailed subTypes)
        current_original = current

        # Aggregate holdings into parent accounts for delta calculations
        current = self._aggregate_holdings_to_accounts(current)
        if previous:
            previous = self._aggregate_holdings_to_accounts(previous)

        # Calculate net worth change and percentage
        net_worth_change: MoneyValue | None = None
        net_worth_change_percent: float | None = None
        if previous:
            net_worth_change = {
                "amount": current["net_worth"]["amount"] - previous["net_worth"]["amount"],
                "currency": current["currency"],
            }
            if previous["net_worth"]["amount"] != 0:
                net_worth_change_percent = (
                    net_worth_change["amount"] / abs(previous["net_worth"]["amount"])
                ) * 100

        # Build account lookup for previous snapshot
        prev_accounts = {}
        if previous:
            for account in previous["accounts"]:
                prev_accounts[account["id"]] = account

        # Calculate account deltas
        asset_changes: list[AccountDelta] = []
        debt_changes: list[AccountDelta] = []

        for account in current["accounts"]:
            prev_account = prev_accounts.get(account["id"])

            if prev_account:
                change_amount = account["value"]["amount"] - prev_account["value"]["amount"]
                change_percent = None
                if prev_account["value"]["amount"] != 0:
                    change_percent = (change_amount / abs(prev_account["value"]["amount"])) * 100

                delta: AccountDelta = {
                    "id": account["id"],
                    "name": account["name"],
                    "institution": account["institution"],
                    "category": account["category"],
                    "sheet_name": account["sheet_name"],
                    "section_name": account.get("section_name"),
                    "sub_type": account.get("sub_type"),
                    "asset_class": account.get("asset_class"),
                    "account_type": account.get("account_type"),
                    "geography": account.get("geography"),
                    "current_value": account["value"],
                    "previous_value": prev_account["value"],
                    "change": {"amount": change_amount, "currency": current["currency"]},
                    "change_percent": change_percent,
                }
            else:
                # New account
                delta = {
                    "id": account["id"],
                    "name": account["name"],
                    "institution": account["institution"],
                    "category": account["category"],
                    "sheet_name": account["sheet_name"],
                    "section_name": account.get("section_name"),
                    "sub_type": account.get("sub_type"),
                    "asset_class": account.get("asset_class"),
                    "account_type": account.get("account_type"),
                    "geography": account.get("geography"),
                    "current_value": account["value"],
                    "previous_value": {"amount": 0.0, "currency": current["currency"]},
                    "change": account["value"],
                    "change_percent": None,
                }

            if account["category"] == "asset":
                asset_changes.append(delta)
            else:
                debt_changes.append(delta)

        # Sort by absolute change amount (largest first)
        asset_changes.sort(key=lambda x: abs(x["change"]["amount"]), reverse=True)
        debt_changes.sort(key=lambda x: abs(x["change"]["amount"]), reverse=True)

        return {
            "current": current,
            "current_unaggregated": current_original,
            "previous": previous,
            "net_worth_change": net_worth_change,
            "net_worth_change_percent": net_worth_change_percent,
            "asset_changes": asset_changes,
            "debt_changes": debt_changes,
        }

    def generate_allocation_chart(self, allocation: dict[str, float]) -> bytes:
        """Generate pie chart image for asset allocation.

        Args:
            allocation: Dictionary with allocation percentages

        Returns:
            PNG image as bytes
        """
        # Define colors for each category
        colors = {
            "Stocks": "#4CAF50",  # Green
            "Bonds": "#2196F3",  # Blue
            "Crypto": "#FF9800",  # Orange
            "Real Estate": "#9C27B0",  # Purple
            "Cash": "#00BCD4",  # Cyan
            "Other": "#795548",  # Brown
        }

        labels = list(allocation.keys())
        values = list(allocation.values())
        chart_colors = [colors.get(label, "#999999") for label in labels]

        # Create figure with better layout
        fig, ax = plt.subplots(figsize=(10, 7))

        # Function to only show percentages for slices >= 5%
        def autopct_format(pct: float) -> str:
            return f"{pct:.1f}%" if pct >= 5 else ""

        # Create pie chart with conditional percentages
        pie_result = ax.pie(
            values,
            labels=None,  # No labels on pie - use legend instead
            colors=chart_colors,
            autopct=autopct_format,
            startangle=90,
            textprops={"fontsize": 14, "weight": "bold"},
            pctdistance=0.75,  # Move percentages closer to center
        )
        wedges, texts, autotexts = pie_result  # type: ignore[misc]

        # Make percentage text white for better visibility
        for autotext in autotexts:
            autotext.set_color("white")

        # Add legend below the chart with percentages
        legend_labels = [f"{label} ({value:.1f}%)" for label, value in zip(labels, values)]
        ax.legend(
            wedges,
            legend_labels,
            loc="center",
            bbox_to_anchor=(0.5, -0.1),
            ncol=3,
            fontsize=12,
            frameon=False,
        )

        ax.axis("equal")

        # Save to bytes buffer with extra padding for legend
        buf = io.BytesIO()
        plt.savefig(
            buf, format="png", dpi=150, bbox_inches="tight", facecolor="white", pad_inches=0.3
        )
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    def calculate_asset_allocation(self, snapshot: PortfolioSnapshot) -> dict[str, float]:
        """Calculate asset allocation by category using subType metadata from Kubera API.

        Uses structured metadata (subType, assetClass) instead of parsing account names.
        Only counts leaf nodes (individual holdings) to avoid double-counting parent accounts.

        Args:
            snapshot: Portfolio snapshot

        Returns:
            Dictionary with allocation percentages
        """
        categories = {
            "Stocks": 0.0,
            "Bonds": 0.0,
            "Crypto": 0.0,
            "Real Estate": 0.0,
            "Cash": 0.0,
            "Other": 0.0,
        }

        # Map Kubera subTypes to our categories
        subtype_to_category = {
            "stock": "Stocks",
            "etf": "Stocks",
            "bond": "Bonds",
            "cash": "Cash",
            "crypto": "Crypto",
            "cryptocurrency": "Crypto",
            "real estate": "Real Estate",
            "property": "Real Estate",
            "primary residence": "Real Estate",
            "investment property": "Real Estate",
        }

        for account in snapshot["accounts"]:
            if account["category"] != "asset":
                continue

            # Skip parent accounts with children - only count leaf holdings
            # Parent accounts have aggregate values; their children have the actual holdings
            # Both parent and children are in the accounts list (from API), so we filter parents
            account_id = account["id"]
            if "_" not in account_id:
                # This is a parent account (pure UUID, no underscore)
                # Check if there are any child holdings
                has_children = any(
                    a["id"].startswith(f"{account_id}_")
                    for a in snapshot["accounts"]
                    if a["category"] == "asset"
                )
                # Skip parent accounts that have children (to avoid double-counting)
                # Keep standalone accounts (no children)
                if has_children:
                    continue

            amount = account["value"]["amount"]

            # Skip zero-value accounts
            if amount == 0:
                continue

            # Get metadata fields (may not exist in old snapshots)
            sub_type_raw = account.get("sub_type")
            sub_type = sub_type_raw.lower() if sub_type_raw else ""
            asset_class_raw = account.get("asset_class")
            asset_class = asset_class_raw.lower() if asset_class_raw else ""
            account_type_raw = account.get("account_type")
            account_type = account_type_raw.lower() if account_type_raw else ""
            sheet = account["sheet_name"].lower()
            name = account["name"].lower()

            category = None

            # Try subType first (most reliable)
            if sub_type in subtype_to_category:
                category = subtype_to_category[sub_type]

            # Special handling for mutual funds - check name to distinguish bond vs stock funds
            if sub_type == "mutual fund" or asset_class == "fund":
                bond_keywords = [
                    "bond",
                    "fixed income",
                    "yield",
                    "yld",  # Abbreviated yield
                    "floating rate",
                    "floating-rate",
                    "high income",
                    "high-income",
                    "high-inc",
                    "income fund",
                    "income builder",
                    "mortgage",
                    "treasury",
                    "municipal",
                    "corporate debt",
                    "balanced income",  # Balanced funds with "income" are typically bond-heavy
                ]
                if any(kw in name for kw in bond_keywords):
                    category = "Bonds"
                else:
                    category = "Stocks"  # Default funds to stocks

            # Check assetClass for direct mappings (if not already categorized)
            if category is None and asset_class in subtype_to_category:
                category = subtype_to_category[asset_class]

            # Check assetClass for stock/crypto (when subType is generic)
            if category is None:
                if asset_class == "stock":
                    category = "Stocks"
                elif asset_class == "crypto":
                    category = "Crypto"

            # Fallback: check sheet name for crypto or real estate (for manually entered assets)
            if category is None:
                if "crypto" in sheet:
                    category = "Crypto"
                elif "real estate" in sheet or account_type == "property":
                    category = "Real Estate"

            # Last resort: parse names (backward compatibility for old snapshots without subType)
            if category is None:
                if "crypto" in name:
                    category = "Crypto"
                elif "bond" in name:
                    category = "Bonds"
                elif "real estate" in sheet or "property" in sheet:
                    category = "Real Estate"
                elif "bank" in sheet or "cash" in name or "checking" in name or "savings" in name:
                    category = "Cash"
                else:
                    # Check for investment keywords
                    investment_keywords = [
                        "investment",
                        "brokerage",
                        "ira",
                        "401k",
                        "stock",
                        "equity",
                    ]
                    if any(kw in sheet or kw in name for kw in investment_keywords):
                        category = "Stocks"

            # Default to Other if still not categorized
            if category is None:
                category = "Other"

            categories[category] += amount

        # Convert to percentages
        total = sum(categories.values())
        if total > 0:
            return {k: (v / total * 100) for k, v in categories.items() if v > 0}
        return {}

    def generate_ai_summary(
        self,
        report_data: ReportData,
        report_type: ReportType = ReportType.DAILY,
        hide_amounts: bool = False,
    ) -> str | None:
        """Generate AI summary of portfolio changes.

        Args:
            report_data: Report data with deltas
            report_type: Type of report being generated
            hide_amounts: If True, ask LLM to avoid specific dollar amounts

        Returns:
            AI-generated summary or None if generation fails
        """
        try:
            from kubera_reporting.llm_client import LLMClient

            # Only generate summary if we have previous data
            if not report_data["previous"] or not report_data["net_worth_change"]:
                return None

            llm = LLMClient()

            # Format period description based on report type
            period_descriptions = {
                ReportType.DAILY: "daily",
                ReportType.WEEKLY: "weekly",
                ReportType.MONTHLY: "monthly",
                ReportType.QUARTERLY: "quarterly",
                ReportType.YEARLY: "yearly",
            }
            period = period_descriptions.get(report_type, "daily")

            # Type narrowing - we know net_worth_change is not None here
            net_worth_change = report_data["net_worth_change"]
            previous = report_data["previous"]

            # For AI summary, calculate deltas on UNAGGREGATED data to capture individual holdings
            # This allows AI to see big moves in individual stocks/crypto, not just parent accounts
            current_unagg = report_data.get("current_unaggregated", report_data["current"])

            # Build lookup for previous accounts (unaggregated)
            prev_accounts_lookup = {}
            if previous:
                for account in previous["accounts"]:
                    prev_accounts_lookup[account["id"]] = account

            # Calculate deltas for ALL accounts (including individual holdings)
            # Exclude physical assets (real estate, cars, domains) - no daily volatility
            all_asset_deltas = []
            for account in current_unagg["accounts"]:
                if account["category"] != "asset":
                    continue

                # Skip physical assets - no meaningful daily volatility
                account_type = (account.get("account_type") or "").lower()
                sub_type = (account.get("sub_type") or "").lower()
                sheet_name = (account.get("sheet_name") or "").lower()

                # Filter out real estate
                if account_type == "property":
                    continue
                if "real estate" in sheet_name:
                    continue
                if sub_type in ["primary residence", "investment property"]:
                    continue

                # Filter out vehicles
                if "vehicle" in sub_type or "car" in sub_type:
                    continue

                # Filter out domain names and other digital property
                if "domain" in sub_type or "domain" in account["name"].lower():
                    continue

                prev_account = prev_accounts_lookup.get(account["id"])
                if not prev_account:
                    continue  # Skip new accounts for AI summary (focus on changes)

                change_amount = account["value"]["amount"] - prev_account["value"]["amount"]
                if change_amount == 0:
                    continue  # Skip accounts with no change

                change_percent = None
                if prev_account["value"]["amount"] != 0:
                    change_percent = (change_amount / abs(prev_account["value"]["amount"])) * 100

                all_asset_deltas.append(
                    {
                        "name": account["name"],
                        "sheet": account["sheet_name"],
                        "current_value": account["value"]["amount"],
                        "previous_value": prev_account["value"]["amount"],
                        "change": change_amount,
                        "percent": change_percent,
                        "is_holding": "_"
                        in account["id"],  # Individual holding if ID has underscore
                    }
                )

            # Build TWO perspectives for AI:
            # 1. Top movers by dollar amount (what drove net worth change)
            # 2. Top movers by percentage (what had notable swings, even if small positions)

            # Sort by absolute change amount for net worth impact
            by_dollar = sorted(
                all_asset_deltas,
                key=lambda x: abs(float(x["change"])),  # type: ignore[arg-type]
                reverse=True,
            )

            # Sort by absolute percentage change for notable moves
            by_percent = sorted(
                [d for d in all_asset_deltas if d["percent"] is not None],
                key=lambda x: abs(float(x["percent"])),  # type: ignore[arg-type]
                reverse=True,
            )

            # Build context for AI with both perspectives
            top_dollar_movers = [
                {
                    "name": d["name"],
                    "sheet": d["sheet"],
                    "current_value": round(float(d["current_value"]), 2),  # type: ignore[arg-type]
                    "previous_value": round(float(d["previous_value"]), 2),  # type: ignore[arg-type]
                    "change": round(float(d["change"]), 2),  # type: ignore[arg-type]
                    "percent": (
                        round(float(d["percent"]), 2)  # type: ignore[arg-type]
                        if d["percent"] is not None
                        else None
                    ),
                    "is_holding": d["is_holding"],
                }
                for d in by_dollar[:3]
            ]

            top_percent_movers = [
                {
                    "name": d["name"],
                    "sheet": d["sheet"],
                    "current_value": round(float(d["current_value"]), 2),  # type: ignore[arg-type]
                    "change": round(float(d["change"]), 2),  # type: ignore[arg-type]
                    "percent": round(float(d["percent"]), 2),  # type: ignore[arg-type]
                    "is_holding": d["is_holding"],
                }
                for d in by_percent[:3]
            ]

            # Note: For now, debt movers use aggregated data (less common to have individual debts)
            top_debt_movers = [
                {
                    "name": d["name"],
                    "current_value": round(d["current_value"]["amount"], 2),
                    "previous_value": round(d["previous_value"]["amount"], 2),
                    "change": round(d["change"]["amount"], 2),
                    "percent": (
                        round(d["change_percent"], 2) if d["change_percent"] is not None else None
                    ),
                }
                for d in report_data["debt_changes"][:3]
            ]

            # Calculate asset allocation (use unaggregated for accurate categorization)
            snapshot_for_allocation = report_data.get(
                "current_unaggregated", report_data["current"]
            )
            allocation = self.calculate_asset_allocation(snapshot_for_allocation)

            # Build comprehensive portfolio data for prompt
            # Round allocation percentages to 2 decimal places
            allocation_rounded = {k: round(v, 2) for k, v in allocation.items()}

            # Get currency from report data
            currency = report_data["current"]["currency"]
            currency_symbol = currency_format.get_currency_symbol(currency)

            if hide_amounts:
                # Omit dollar amounts, include only percentages
                portfolio_data = {
                    "currency": currency,
                    "net_worth": {
                        "change_percent": round(
                            (net_worth_change["amount"] / previous["net_worth"]["amount"] * 100)
                            if previous["net_worth"]["amount"] != 0
                            else 0,
                            2,
                        ),
                    },
                    "asset_allocation": allocation_rounded,
                    "top_dollar_movers": [
                        {
                            "name": d["name"],
                            "sheet": d["sheet"],
                            "percent": d["percent"],
                            "is_holding": d["is_holding"],
                        }
                        for d in top_dollar_movers
                    ],
                    "top_percent_movers": [
                        {
                            "name": d["name"],
                            "sheet": d["sheet"],
                            "percent": d["percent"],
                            "is_holding": d["is_holding"],
                        }
                        for d in top_percent_movers
                    ],
                    "top_debt_movers": [
                        {
                            "name": d["name"],
                            "percent": (
                                round(d["change_percent"], 2)
                                if d["change_percent"] is not None
                                else None
                            ),
                        }
                        for d in report_data["debt_changes"][:3]
                    ],
                }

                prompt = f"""Analyze this {period} portfolio report (currency: {currency}).

Format your response as:
1. First sentence: Overall net worth change summary (percentage only)
2. Blank line
3. "Key drivers:" followed by bullet points for top_dollar_movers (biggest impact on net worth)
4. If any top_percent_movers are NOT in top_dollar_movers AND have notable % changes (>5%):
   - Blank line
   - "Also notable:" followed by bullet points for those percentage movers

Note: "is_holding": true means individual stock/crypto/asset within a larger account.

CRITICAL RULES:
- Do NOT mention specific amounts - use only percentages
- Format bullets with "• " character
- Do NOT suggest actions or what to watch
- Do NOT mention asset allocation (shown in pie chart)
- ONLY use data provided - do not infer
- Keep factual and concise
- Only include "Also notable:" section if there are items to show

Portfolio Data:
{json.dumps(portfolio_data, indent=2)}"""
            else:
                # Include full amounts with currency
                portfolio_data = {
                    "currency": currency,
                    "net_worth": {
                        "current": round(report_data["current"]["net_worth"]["amount"], 2),
                        "change": round(net_worth_change["amount"], 2),
                        "change_percent": round(
                            (net_worth_change["amount"] / previous["net_worth"]["amount"] * 100)
                            if previous["net_worth"]["amount"] != 0
                            else 0,
                            2,
                        ),
                    },
                    "asset_allocation": allocation_rounded,
                    "top_dollar_movers": top_dollar_movers,
                    "top_percent_movers": top_percent_movers,
                    "top_debt_movers": top_debt_movers,
                }

                prompt = f"""Analyze this {period} portfolio report (currency: {currency}).

Format your response as:
1. First sentence: Overall net worth change summary
2. Blank line
3. "Key drivers:" followed by bullet points for top_dollar_movers (biggest impact on net worth)
4. If any top_percent_movers are NOT in top_dollar_movers AND have notable % changes (>5%):
   - Blank line
   - "Also notable:" followed by bullet points for those percentage movers

Note: "is_holding": true means individual stock/crypto/asset within a larger account.

CRITICAL RULES:
- Use exact names from the data
- Use {currency_symbol} symbol for amounts (this portfolio uses {currency})
- Format amounts WITHOUT decimals (e.g., {currency_symbol}1,234 not {currency_symbol}1,234.56)
- Format percentages with 2 decimal places (e.g., 5.13%)
- Format bullets with "• " character
- Do NOT suggest actions or what to watch
- Do NOT mention asset allocation (shown in pie chart)
- ONLY use data provided - do not infer
- Keep factual and concise
- Only include "Also notable:" section if there are items to show

Portfolio Data:
{json.dumps(portfolio_data, indent=2)}"""

            # Generate summary
            from litellm import completion

            response = completion(
                model=llm.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )

            return response.choices[0].message.content

        except Exception as e:
            # If AI generation fails, just skip it
            print(f"Warning: AI summary generation failed: {e}")
            return None

    def generate_html_report(
        self,
        report_data: ReportData,
        report_type: ReportType = ReportType.DAILY,
        top_n: int = 20,
        ai_summary: str | None = None,
        recipient_name: str | None = None,
        hide_amounts: bool = False,
        is_export: bool = False,
    ) -> str:
        """Generate HTML email report with embedded base64 charts for better forwarding.

        Args:
            report_data: Report data
            report_type: Type of report (daily, weekly, monthly, etc.)
            top_n: Number of top movers to show (default: 20)
            ai_summary: Optional AI-generated summary
            recipient_name: Optional name for greeting (default: "Portfolio Report")
            hide_amounts: If True, mask dollar amounts (show "$XX" instead)
            is_export: If True, add collapse/expand functionality for local viewing (default: False)

        Returns:
            HTML report string with inline styles and base64-embedded charts

        Raises:
            ReportGenerationError: If generation fails
        """
        try:
            # Group assets by sheet > section (two-level hierarchy)
            from collections import defaultdict

            # First level: sheet_name
            assets_by_sheet: dict[str, dict[str, list[AccountDelta]]] = defaultdict(
                lambda: defaultdict(list)
            )

            for asset in report_data["asset_changes"]:
                sheet = asset["sheet_name"] or "Uncategorized"
                # Use section_name for sub-grouping, fall back to "Default" if not available
                section = asset.get("section_name") or "Default"

                # Skip accounts whose name matches the section name (prevents double-counting)
                # Example: parent account with same name as section shows redundant line item
                if asset["name"] == section:
                    continue

                assets_by_sheet[sheet][section].append(asset)

            # Sort accounts within each section by value
            for sheet_sections in assets_by_sheet.values():
                for section_accounts in sheet_sections.values():
                    section_accounts.sort(key=lambda x: x["current_value"]["amount"], reverse=True)

            # Calculate totals for both sheet and section levels
            sheet_totals = {}
            section_totals: dict[str, dict[str, dict[str, float | int | None]]] = defaultdict(dict)

            for sheet_name, sheet_sections in assets_by_sheet.items():
                sheet_current_total = 0.0
                sheet_change_total = 0.0 if report_data["previous"] else None
                sheet_previous_total = 0.0
                sheet_account_count = 0

                for section_name, accounts in sheet_sections.items():
                    # Calculate section-level totals
                    section_current = sum(a["current_value"]["amount"] for a in accounts)
                    section_change = (
                        sum(a["change"]["amount"] for a in accounts)
                        if report_data["previous"]
                        else None
                    )
                    section_previous = sum(a["previous_value"]["amount"] for a in accounts)

                    # Calculate section percentage change
                    section_change_percent = None
                    if (
                        report_data["previous"]
                        and section_change is not None
                        and section_previous != 0
                    ):
                        section_change_percent = (section_change / section_previous) * 100

                    section_totals[sheet_name][section_name] = {
                        "count": len(accounts),
                        "total_value": section_current,
                        "total_change": section_change,
                        "change_percent": section_change_percent,
                    }

                    # Accumulate for sheet totals
                    sheet_current_total += section_current
                    if sheet_change_total is not None and section_change is not None:
                        sheet_change_total += section_change
                    sheet_previous_total += section_previous
                    sheet_account_count += len(accounts)

                # Calculate sheet-level percentage change
                sheet_change_percent = None
                if (
                    report_data["previous"]
                    and sheet_change_total is not None
                    and sheet_previous_total != 0
                ):
                    sheet_change_percent = (sheet_change_total / sheet_previous_total) * 100

                sheet_totals[sheet_name] = {
                    "count": sheet_account_count,
                    "total_value": sheet_current_total,
                    "total_change": sheet_change_total,
                    "change_percent": sheet_change_percent,
                }

            # Keep top movers for backwards compatibility
            asset_movers = report_data["asset_changes"][:top_n]
            debt_movers = report_data["debt_changes"][:top_n]

            # Calculate total changes and percentages
            total_asset_change = sum(d["change"]["amount"] for d in report_data["asset_changes"])
            total_debt_change = sum(d["change"]["amount"] for d in report_data["debt_changes"])

            # Calculate percentage changes for totals
            total_asset_change_percent = None
            total_debt_change_percent = None
            if report_data["previous"]:
                prev_total_assets = report_data["previous"]["total_assets"]["amount"]
                if prev_total_assets != 0:
                    total_asset_change_percent = (total_asset_change / prev_total_assets) * 100

                prev_total_debts = report_data["previous"]["total_debts"]["amount"]
                if prev_total_debts != 0:
                    total_debt_change_percent = (total_debt_change / prev_total_debts) * 100

            # Calculate asset allocation (use unaggregated for accurate categorization)
            snapshot_for_allocation = report_data.get(
                "current_unaggregated", report_data["current"]
            )
            allocation = self.calculate_asset_allocation(snapshot_for_allocation)

            # Always embed chart as base64 data URL for better forwarding compatibility
            chart_src = ""
            if allocation:
                import base64

                chart_bytes = self.generate_allocation_chart(allocation)
                chart_b64 = base64.b64encode(chart_bytes).decode("utf-8")
                chart_src = f"data:image/png;base64,{chart_b64}"

            # Format greeting based on recipient name and report type
            if recipient_name:
                name_part = f"Hi {recipient_name},"
            else:
                name_part = "Hi,"

            if report_data["previous"]:
                # With comparison data - mention the period
                if report_type == ReportType.DAILY:
                    period_desc = "here's a recap of account balances that changed yesterday"
                elif report_type == ReportType.WEEKLY:
                    period_desc = "here's a recap of changes over the past week"
                elif report_type == ReportType.MONTHLY:
                    period_desc = "here's a recap of changes over the past month"
                elif report_type == ReportType.QUARTERLY:
                    period_desc = "here's a recap of changes over the past quarter"
                elif report_type == ReportType.YEARLY:
                    period_desc = "here's a recap of changes over the past year"
                else:
                    period_desc = "here's your portfolio report"
                greeting = f"{name_part} {period_desc}."
            else:
                # No comparison - just show snapshot
                greeting = f"{name_part} here's a snapshot of your current account balances."

            # Sort sheets by total value (descending)
            sorted_sheets = dict(
                sorted(
                    assets_by_sheet.items(),
                    key=lambda x: sheet_totals[x[0]]["total_value"] or 0,
                    reverse=True,
                )
            )

            # Format report type for display
            report_type_display = report_type.value.capitalize()

            # Create wrapper functions that respect hide_amounts flag
            def format_money_wrapper(value: MoneyValue) -> str:
                return self._format_money(value, hide_amounts=hide_amounts)

            def format_net_worth_wrapper(value: MoneyValue) -> str:
                return self._format_net_worth(value, hide_amounts=hide_amounts)

            def format_change_wrapper(
                change: MoneyValue, change_percent: float | None = None
            ) -> tuple[str, str]:
                return self._format_change(change, change_percent, hide_amounts=hide_amounts)

            # Convert AI summary newlines to HTML <br> tags for email compatibility
            # Email clients don't reliably support white-space: pre-line
            ai_summary_html = ai_summary.replace("\n", "<br>") if ai_summary else None

            template = Template(self._get_html_template())
            return template.render(
                current=report_data["current"],
                previous=report_data["previous"],
                net_worth_change=report_data["net_worth_change"],
                net_worth_change_percent=report_data["net_worth_change_percent"],
                asset_movers=asset_movers,
                debt_movers=debt_movers,
                assets_by_sheet=sorted_sheets,
                sheet_totals=sheet_totals,
                section_totals=section_totals,
                total_asset_change=total_asset_change,
                total_asset_change_percent=total_asset_change_percent,
                total_debt_change=total_debt_change,
                total_debt_change_percent=total_debt_change_percent,
                allocation=allocation,
                chart_src=chart_src,
                ai_summary=ai_summary_html,
                greeting=greeting,
                report_date=datetime.now().strftime("%b %d, %Y"),
                report_type=report_type_display,
                format_money=format_money_wrapper,
                format_net_worth=format_net_worth_wrapper,
                format_change=format_change_wrapper,
                is_export=is_export,
            )
        except Exception as e:
            raise ReportGenerationError(f"Failed to generate HTML report: {e}") from e

    def _format_money(self, value: MoneyValue, hide_amounts: bool = False) -> str:
        """Format money value with currency-aware symbols.

        Args:
            value: Money value to format
            hide_amounts: If True, return "$XX" or "€XX" instead of actual amount

        Returns:
            Formatted money string like "$1,234" or "€1,234"
        """
        return currency_format.format_money(
            value["amount"], value["currency"], hide_amounts=hide_amounts
        )

    def _get_fire_category(self, amount: float) -> str | None:
        """Get FIRE category based on net worth amount.

        Args:
            amount: Net worth amount

        Returns:
            FIRE category string or None if under $800k
        """
        if amount < 800_000:
            return None
        elif amount < 1_500_000:
            return "Lean FIRE"
        elif amount < 2_000_000:
            return "Coast FIRE"
        elif amount < 2_500_000:
            return "FIRE"
        else:
            return "Fat FIRE"

    def _format_net_worth(self, value: MoneyValue, hide_amounts: bool = False) -> str:
        """Format net worth value with FIRE category indicator.

        Args:
            value: Net worth value
            hide_amounts: If True, mask the dollar amount but keep FIRE category

        Returns:
            Formatted string like "$1,234,567 (Fat FIRE)" or "$750,000" or "$XX (Fat FIRE)"
        """
        formatted_money = self._format_money(value, hide_amounts=hide_amounts)
        category = self._get_fire_category(value["amount"])

        if category:
            return f"{formatted_money} ({category})"
        return formatted_money

    def _format_change(
        self, change: MoneyValue, change_percent: float | None = None, hide_amounts: bool = False
    ) -> tuple[str, str]:
        """Format change value with color and optional percentage.

        Args:
            change: Money change amount
            change_percent: Optional percentage change
            hide_amounts: If True, mask amounts but show percentage

        Returns:
            Tuple of (formatted_string, color) like ("↑ $1,234 (+5.2%)", "#00b383")
        """
        return currency_format.format_change(
            change["amount"], change["currency"], change_percent, hide_amounts=hide_amounts
        )

    def _get_html_template(self) -> str:
        """Get HTML email template with inline styles for better email client compatibility."""
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* Mobile-responsive styles - uses !important to override inline styles */
        /* Note: Not all email clients support media queries (e.g., Outlook) */
        /* Inline styles below are mobile-first for graceful degradation */
        @media only screen and (max-width: 640px) {
            body {
                padding: 10px !important;
            }
            .email-container {
                padding: 20px !important;
            }
            .section-header-row {
                display: block !important;
            }
            .section-header-title {
                display: block !important;
                margin-bottom: 8px;
            }
            .section-header-total {
                display: block !important;
                text-align: left !important;
                font-size: 14px !important;
            }
            .section-header-total > div {
                display: block;
                margin-bottom: 4px;
            }
            .sheet-header-row {
                display: block !important;
            }
            .sheet-header-title {
                display: block !important;
                margin-bottom: 6px;
            }
            .sheet-header-total {
                display: block !important;
                text-align: left !important;
                padding-left: 20px;
                font-size: 13px !important;
            }
            .sheet-header-total > div {
                display: block;
                margin-bottom: 3px;
            }
            .subsection-header-row {
                display: block !important;
            }
            .subsection-header-title {
                display: block !important;
                margin-bottom: 5px;
            }
            .subsection-header-total {
                display: block !important;
                text-align: left !important;
                padding-left: 20px;
                font-size: 12px !important;
            }
            .subsection-header-total > div {
                display: block;
                margin-bottom: 2px;
            }
            .account-row {
                display: block !important;
            }
            .account-name {
                display: block !important;
                margin-bottom: 6px;
            }
            .account-value {
                display: block !important;
                text-align: left !important;
            }
        }
        {% if is_export %}
        .collapsible-header {
            cursor: pointer;
            user-select: none;
        }
        .collapsible-header:hover {
            background-color: #f5f5f5;
        }
        .toggle-indicator {
            display: inline-block;
            width: 16px;
            height: 16px;
            margin-right: 4px;
            font-size: 12px;
            transition: transform 0.2s;
        }
        .collapsed .toggle-indicator {
            transform: rotate(-90deg);
        }
        .collapsible-content {
            display: none;
        }
        .collapsible-content.expanded {
            display: block;
        }
        {% endif %}
    </style>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; \
margin: 0; padding: 20px; background-color: #f5f5f5;">
    <div class="email-container" style="max-width: 600px; margin: 0 auto; background-color: white; \
border-radius: 8px; padding: 30px;">
        <div style="color: #666; font-size: 18px; margin-bottom: 30px; line-height: 1.6; \
font-weight: normal;">{{ greeting }}</div>

        {% if ai_summary %}
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; \
margin-bottom: 20px; border-left: 4px solid #00b383;">
            <div style="color: #666; font-size: 12px; font-weight: 600; \
margin-bottom: 8px;">AI INSIGHTS</div>
            <div style="color: #333; font-size: 14px; line-height: 1.6;">\
{{ ai_summary|safe }}</div>
        </div>
        {% endif %}

        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; \
margin-bottom: 30px;">
            <div style="color: #666; font-size: 14px; margin-bottom: 5px;">Net worth</div>
            <div style="font-size: 32px; font-weight: bold; color: #333;">\
{{ format_net_worth(current.net_worth) }}</div>
            {% if net_worth_change %}
            {% set change_text, change_color = format_change(
                net_worth_change, net_worth_change_percent) %}
            <div style="font-size: 18px; font-weight: 600; margin-top: 5px; color: \
{{ change_color }};">{{ change_text }}</div>
            {% endif %}
        </div>

        {% if assets_by_sheet %}
        <div style="margin-bottom: 30px;">
            <div class="section-header-row" style="font-size: 18px; font-weight: 600; color: #333; \
margin-bottom: 15px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; display: table; \
width: 100%;">
                <div class="section-header-title" \
style="display: table-cell; vertical-align: middle;">
                    Assets
                </div>
                <div class="section-header-total" \
style="display: table-cell; vertical-align: middle; text-align: right; \
font-size: 16px; font-weight: 600; white-space: nowrap;">
                    <div>Total: {{ format_money(current.total_assets) }}</div>
                    {% if previous and total_asset_change %}
                    {% set change_text, change_color = format_change(
                        {'amount': total_asset_change, 'currency': current.currency},
                        total_asset_change_percent) %}
                    <div style="color: {{ change_color }};">{{ change_text }}</div>
                    {% endif %}
                </div>
            </div>

            {% for sheet_name, sheet_sections in assets_by_sheet.items() %}
            {% set sheet_id = loop.index %}
            <div style="margin-top: 20px;" class="sheet-container">
                <!-- Sheet-level header -->
                <div {% if is_export %}class="collapsible-header collapsed sheet-header-row" \
onclick="toggleSheet({{ sheet_id }})"{% else %}class="sheet-header-row"{% endif %} \
style="font-size: 16px; font-weight: 600; color: #555; margin-bottom: 10px; \
padding-bottom: 8px; border-bottom: 1px solid #e0e0e0; display: table; width: 100%;">
                    <div class="sheet-header-title" \
style="display: table-cell; vertical-align: middle;">
                        {% if is_export %}<span class="toggle-indicator">▼</span>{% endif %}
                        {{ sheet_name }}
                        <span style="font-size: 14px; color: #777; font-weight: 500;">
                            ({{ sheet_totals[sheet_name].count }} account\
{{ 's' if sheet_totals[sheet_name].count != 1 else '' }})
                        </span>
                    </div>
                    <div class="sheet-header-total" \
style="display: table-cell; vertical-align: middle; text-align: right; \
font-size: 14px; white-space: nowrap;">
                        <div>{{ format_money({'amount': sheet_totals[sheet_name].total_value, \
'currency': current.currency}) }}</div>
                        {% if previous and sheet_totals[sheet_name].total_change %}
                        {% set sheet_change_text, sheet_change_color = format_change(
                            {'amount': sheet_totals[sheet_name].total_change, \
'currency': current.currency},
                            sheet_totals[sheet_name].change_percent) %}
                        <div style="color: {{ sheet_change_color }}; font-size: 13px;">
                            {{ sheet_change_text }}
                        </div>
                        {% endif %}
                    </div>
                </div>

                <!-- Sheet content (collapsible in export mode) -->
                <div id="sheet-{{ sheet_id }}" class="collapsible-content">
                    <!-- Section-level grouping within sheet (only if multiple sections) -->
                    {% if sheet_sections|length > 1 %}
                        {% for section_name, accounts in sheet_sections.items() %}
                        {% set section_id = sheet_id ~ '_' ~ loop.index %}
                        {% set section = section_totals[sheet_name][section_name] %}
                        <div style="margin-left: 15px; margin-top: 15px;">
                            <div {% if is_export %}\
class="collapsible-header collapsed subsection-header-row" \
onclick="toggleSection('{{ section_id }}')"{% else %}class="subsection-header-row"{% endif %} \
style="font-size: 14px; font-weight: 600; color: #666; margin-bottom: 8px; \
padding-bottom: 6px; border-bottom: 1px solid #f0f0f0; display: table; width: 100%;">
                                <div class="subsection-header-title" style="display: table-cell; \
vertical-align: middle;">
                                    {% if is_export %}<span class="toggle-indicator">▼</span>\
{% endif %}
                                    {{ section_name }}
                                    <span style="font-size: 13px; color: #888; font-weight: 500;">
                                        ({{ section.count }} account\
{{ 's' if section.count != 1 else '' }})
                                    </span>
                                </div>
                                <div class="subsection-header-total" style="display: table-cell; \
vertical-align: middle; text-align: right; font-size: 13px; white-space: nowrap;">
                                    <div>{{ format_money({'amount': section.total_value, \
'currency': current.currency}) }}</div>
                                    {% if previous and section.total_change %}
                                    {% set section_change_text, section_change_color = \
format_change(
                                        {'amount': section.total_change, \
'currency': current.currency},
                                        section.change_percent) %}
                                    <div style="color: {{ section_change_color }}; \
font-size: 12px;">
                                        {{ section_change_text }}
                                    </div>
                                    {% endif %}
                                </div>
                            </div>

                            <!-- Section content (collapsible in export mode) -->
                            <div id="section-{{ section_id }}" class="collapsible-content">
                                <!-- Individual accounts within section -->
                                {% for account in accounts %}
                                <div class="account-row" style="display: table; width: 100%; \
padding: 12px 0 12px 15px; border-bottom: 1px solid #f8f8f8;">
                                    <div class="account-name" style="display: table-cell; \
vertical-align: middle;">
                                        <div style="font-weight: 500; color: #333; \
font-size: 13px;">{{ account.name }}</div>
                                        {% if account.institution %}
                                        <div style="font-size: 11px; color: #999;">\
{{ account.institution }}</div>
                                        {% endif %}
                                    </div>
                                    <div class="account-value" style="display: table-cell; \
vertical-align: middle; text-align: right; white-space: nowrap;">
                                        <div style="font-weight: 600; color: #333; \
font-size: 13px;">{{ format_money(account.current_value) }}</div>
                                        {% if previous %}
                                        {% set change_text, change_color = format_change(
                                            account.change, account.change_percent) %}
                                        <div style="font-size: 12px; font-weight: 600; \
color: {{ change_color }};">{{ change_text }}</div>
                                        {% endif %}
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <!-- Single section: skip section header, show accounts directly -->
                        {% for section_name, accounts in sheet_sections.items() %}
                            {% for account in accounts %}
                            <div class="account-row" style="display: table; width: 100%; \
padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                                <div class="account-name" style="display: table-cell; \
vertical-align: middle;">
                                    <div style="font-weight: 500; color: #333;">\
{{ account.name }}</div>
                                    {% if account.institution %}
                                    <div style="font-size: 12px; color: #999;">\
{{ account.institution }}</div>
                                    {% endif %}
                                </div>
                                <div class="account-value" style="display: table-cell; \
vertical-align: middle; text-align: right; white-space: nowrap;">
                                    <div style="font-weight: 600; color: #333;">\
{{ format_money(account.current_value) }}</div>
                                    {% if previous %}
                                    {% set change_text, change_color = format_change(
                                        account.change, account.change_percent) %}
                                    <div style="font-size: 14px; font-weight: 600; \
color: {{ change_color }};">{{ change_text }}</div>
                                    {% endif %}
                                </div>
                            </div>
                            {% endfor %}
                        {% endfor %}
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if debt_movers %}
        <div style="margin-bottom: 30px;">
            <div class="section-header-row" style="font-size: 18px; font-weight: 600; color: #333; \
margin-bottom: 15px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; display: table; \
width: 100%;">
                <div class="section-header-title" \
style="display: table-cell; vertical-align: middle;">
                    Liabilities
                </div>
                <div class="section-header-total" \
style="display: table-cell; vertical-align: middle; text-align: right; \
font-size: 16px; font-weight: 600; white-space: nowrap;">
                    <div>Total: {{ format_money(current.total_debts) }}</div>
                    {% if previous and total_debt_change %}
                    {% set change_text, change_color = format_change(
                        {'amount': total_debt_change, 'currency': current.currency},
                        total_debt_change_percent) %}
                    <div style="color: {{ change_color }};">{{ change_text }}</div>
                    {% endif %}
                </div>
            </div>
            {% for account in debt_movers %}
            <div class="account-row" style="display: table; width: 100%; \
padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                <div class="account-name" style="display: table-cell; vertical-align: middle;">
                    <div style="font-weight: 500; color: #333;">{{ account.name }}</div>
                    {% if account.institution %}
                    <div style="font-size: 12px; color: #999;">{{ account.institution }}</div>
                    {% endif %}
                </div>
                <div class="account-value" style="display: table-cell; vertical-align: middle; \
text-align: right; white-space: nowrap;">
                    <div style="font-weight: 600; color: #333;">\
{{ format_money(account.current_value) }}</div>
                    {% if previous %}
                    {% set change_text, change_color = format_change(
                        account.change, account.change_percent) %}
                    <div style="font-size: 14px; font-weight: 600; color: {{ change_color }};">\
{{ change_text }}</div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if allocation %}
        <div style="margin-bottom: 30px;">
            <div style="font-size: 18px; font-weight: 600; color: #333; margin-bottom: 15px; \
border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">Asset Allocation</div>
            <div style="text-align: center;">
                <img src="{{ chart_src }}" alt="Asset Allocation Chart" \
style="max-width: 100%; height: auto;" />
            </div>
        </div>
        {% endif %}

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; \
color: #999; font-size: 12px; text-align: center;">
            Report generated on {{ report_date }}<br>
            <a href="https://github.com/the-mace/kubera-reporting" \
style="color: #0066cc; text-decoration: none;">kubera-reporting on GitHub</a>
        </div>
    </div>

    {% if is_export %}
    <script>
        function toggleSheet(sheetId) {
            const header = event.currentTarget;
            const content = document.getElementById('sheet-' + sheetId);

            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                header.classList.add('collapsed');
            } else {
                content.classList.add('expanded');
                header.classList.remove('collapsed');
            }
        }

        function toggleSection(sectionId) {
            const header = event.currentTarget;
            const content = document.getElementById('section-' + sectionId);

            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                header.classList.add('collapsed');
            } else {
                content.classList.add('expanded');
                header.classList.remove('collapsed');
            }
        }
    </script>
    {% endif %}
</body>
</html>"""
