"""Generate portfolio reports."""

import io
import json
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
from jinja2 import Template

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

        Raw API data contains both parent accounts (e.g., "Kelli Trust - Bonds - 2172")
        and their individual holdings (e.g., 500 stocks with IDs like {uuid}_isin-xxx).

        We want to show only the parent accounts with their aggregate values,
        excluding individual holdings and accounts with zero value.

        Args:
            snapshot: Snapshot containing raw API data with both parents and holdings

        Returns:
            Snapshot with only parent accounts (holdings and zero-value accounts removed)
        """
        # Build set of parent account UUIDs
        parent_uuids = set()

        # First pass: identify all parent accounts
        # A parent account is one that has holdings (children with IDs like {parent_id}_xxx)
        for account in snapshot["accounts"]:
            acc_id = account["id"]
            # Check if this looks like a holding (has underscore + suffix)
            if "_" in acc_id and (
                "isin-" in acc_id.lower() or "cusip-" in acc_id.lower() or acc_id.endswith("_0")
            ):
                # This is a holding - extract parent UUID
                parent_uuid = acc_id.split("_")[0]
                parent_uuids.add(parent_uuid)

        # Second pass: keep only parent accounts and standalone accounts
        # Skip individual holdings and zero-value accounts
        filtered_accounts = []

        for account in snapshot["accounts"]:
            acc_id = account["id"]

            # Check if this is a holding (should be skipped)
            is_holding = "_" in acc_id and (
                "isin-" in acc_id.lower() or "cusip-" in acc_id.lower() or acc_id.endswith("_0")
            )

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
        # Aggregate holdings into parent accounts (handles old cached data)
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
        """Calculate asset allocation by category.

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

        for account in snapshot["accounts"]:
            if account["category"] != "asset":
                continue

            amount = account["value"]["amount"]
            sheet = account["sheet_name"].lower()
            name = account["name"].lower()

            # Categorize based on sheet name and account name
            if "crypto" in sheet or "crypto" in name:
                categories["Crypto"] += amount
            elif "bond" in name or "bond" in sheet:
                categories["Bonds"] += amount
            elif "real estate" in sheet or "property" in sheet:
                categories["Real Estate"] += amount
            elif "bank" in sheet or "cash" in sheet or "checking" in name or "savings" in name:
                categories["Cash"] += amount
            elif any(
                keyword in sheet
                for keyword in ["investment", "brokerage", "retirement", "ira", "401k"]
            ):
                # Assume retirement/investment accounts are primarily stocks
                categories["Stocks"] += amount
            else:
                categories["Other"] += amount

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

            # Build context for AI
            top_asset_movers = [
                {
                    "name": d["name"],
                    "sheet": d["sheet_name"],
                    "change": d["change"]["amount"],
                    "percent": d["change_percent"],
                }
                for d in report_data["asset_changes"][:10]
            ]
            top_debt_movers = [
                {
                    "name": d["name"],
                    "change": d["change"]["amount"],
                }
                for d in report_data["debt_changes"][:5]
            ]

            # Calculate asset allocation
            allocation = self.calculate_asset_allocation(report_data["current"])

            # Build comprehensive portfolio data for prompt
            if hide_amounts:
                # Omit dollar amounts, include only percentages
                portfolio_data = {
                    "net_worth": {
                        "change_percent": (
                            (net_worth_change["amount"] / previous["net_worth"]["amount"] * 100)
                            if previous["net_worth"]["amount"] != 0
                            else 0
                        ),
                    },
                    "asset_allocation": allocation,
                    "top_asset_movers": [
                        {
                            "name": d["name"],
                            "sheet": d["sheet_name"],
                            "percent": d["change_percent"],
                        }
                        for d in report_data["asset_changes"][:10]
                    ],
                    "top_debt_movers": [
                        {
                            "name": d["name"],
                        }
                        for d in report_data["debt_changes"][:5]
                    ],
                }

                prompt = f"""Analyze this {period} portfolio report and provide a concise, \
actionable insights paragraph (3-4 sentences max). Focus on:

1. **What happened**: Identify the primary driver of net worth change over this {period} period - \
be specific about which accounts/categories dominated the movement
2. **Why it matters**: Connect {period} movements to portfolio structure (asset allocation \
percentages) and highlight concentration risks or opportunities
3. **What to watch**: Flag notable anomalies, divergences between asset classes, or \
emerging patterns that warrant attention
4. **Action consideration**: Suggest one specific review action based on the data (e.g., \
rebalancing, investigating outliers, sector analysis)

IMPORTANT: Do NOT mention specific dollar amounts. Use only percentages and relative terms like \
"significant", "modest", "substantial", etc. Write in a confident, analytical tone that assumes \
financial literacy.

Portfolio Data:
{json.dumps(portfolio_data, indent=2)}"""
            else:
                # Include full dollar amounts
                portfolio_data = {
                    "net_worth": {
                        "current": report_data["current"]["net_worth"]["amount"],
                        "change": net_worth_change["amount"],
                        "change_percent": (
                            (net_worth_change["amount"] / previous["net_worth"]["amount"] * 100)
                            if previous["net_worth"]["amount"] != 0
                            else 0
                        ),
                    },
                    "asset_allocation": allocation,
                    "top_asset_movers": top_asset_movers,
                    "top_debt_movers": top_debt_movers,
                }

                prompt = f"""Analyze this {period} portfolio report and provide a concise, \
actionable insights paragraph (3-4 sentences max). Focus on:

1. **What happened**: Identify the primary driver of net worth change over this {period} period - \
be specific about which accounts/categories dominated the movement
2. **Why it matters**: Connect {period} movements to portfolio structure (asset allocation \
percentages) and highlight concentration risks or opportunities
3. **What to watch**: Flag notable anomalies, divergences between asset classes, or \
emerging patterns that warrant attention
4. **Action consideration**: Suggest one specific review action based on the data (e.g., \
rebalancing, investigating outliers, sector analysis)

Avoid generic statements. Use specific numbers, percentages, and account names. Write in a \
confident, analytical tone that assumes financial literacy.

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
    ) -> str:
        """Generate HTML email report with embedded base64 charts for better forwarding.

        Args:
            report_data: Report data
            report_type: Type of report (daily, weekly, monthly, etc.)
            top_n: Number of top movers to show (default: 20)
            ai_summary: Optional AI-generated summary
            recipient_name: Optional name for greeting (default: "Portfolio Report")
            hide_amounts: If True, mask dollar amounts (show "$XX" instead)

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

            # Calculate asset allocation
            allocation = self.calculate_asset_allocation(report_data["current"])

            # Always embed chart as base64 data URL for better forwarding compatibility
            chart_src = ""
            if allocation:
                import base64

                chart_bytes = self.generate_allocation_chart(allocation)
                chart_b64 = base64.b64encode(chart_bytes).decode("utf-8")
                chart_src = f"data:image/png;base64,{chart_b64}"

            # Format greeting based on recipient name
            greeting = f"Hi {recipient_name}," if recipient_name else "Portfolio Report"

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
                ai_summary=ai_summary,
                recipient_name=greeting,
                report_date=datetime.now().strftime("%b %d, %Y"),
                report_type=report_type_display,
                format_money=format_money_wrapper,
                format_net_worth=format_net_worth_wrapper,
                format_change=format_change_wrapper,
            )
        except Exception as e:
            raise ReportGenerationError(f"Failed to generate HTML report: {e}") from e

    def _format_money(self, value: MoneyValue, hide_amounts: bool = False) -> str:
        """Format money value.

        Args:
            value: Money value to format
            hide_amounts: If True, return "$XX" instead of actual amount

        Returns:
            Formatted money string
        """
        symbol = "$" if value["currency"] == "USD" else value["currency"]
        if hide_amounts:
            return f"{symbol}XX"
        return f"{symbol}{value['amount']:,.0f}"

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
            hide_amounts: If True, mask dollar amounts but show percentage

        Returns:
            Tuple of (formatted_string, color)
        """
        symbol = "$" if change["currency"] == "USD" else change["currency"]
        amount = change["amount"]

        # Format the base change amount
        if amount > 0:
            if hide_amounts:
                base_text = f"↑ {symbol}XX"
            else:
                base_text = f"↑ {symbol}{amount:,.0f}"
            color = "#00b383"  # Green with up arrow
        elif amount < 0:
            if hide_amounts:
                base_text = f"↓ {symbol}XX"
            else:
                base_text = f"↓ {symbol}{abs(amount):,.0f}"
            color = "#e63946"  # Red with down arrow
        else:
            if hide_amounts:
                base_text = f"{symbol}XX"
            else:
                base_text = f"{symbol}{amount:,.0f}"
            color = "#666666"  # Gray

        # Add percentage if provided
        if change_percent is not None:
            if change_percent > 0:
                base_text += f" (+{change_percent:.2f}%)"
            elif change_percent < 0:
                base_text += f" ({change_percent:.2f}%)"
            else:
                base_text += " (0.00%)"

        return base_text, color

    def _get_html_template(self) -> str:
        """Get HTML email template with inline styles for better forwarding compatibility."""
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; \
margin: 0; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; \
padding: 30px;">
        <h1 style="color: #333; font-size: 24px; margin-bottom: 10px;">{{ recipient_name }}</h1>
        {% if previous %}
        <div style="color: #666; font-size: 14px; margin-bottom: 30px;">
            <strong>{{ report_type }} Report</strong> -
            {% if report_type == "Daily" %}
            Here's a recap of account balances that changed yesterday.
            {% elif report_type == "Weekly" %}
            Here's a recap of changes over the past week.
            {% elif report_type == "Monthly" %}
            Here's a recap of changes over the past month.
            {% elif report_type == "Quarterly" %}
            Here's a recap of changes over the past quarter.
            {% elif report_type == "Yearly" %}
            Here's a recap of changes over the past year.
            {% endif %}
        </div>
        {% else %}
        <div style="color: #666; font-size: 14px; margin-bottom: 30px;">
            <strong>{{ report_type }} Report</strong> - Here's a snapshot of your current
            account balances.
        </div>
        {% endif %}

        {% if ai_summary %}
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; \
margin-bottom: 20px; border-left: 4px solid #00b383;">
            <div style="color: #666; font-size: 12px; font-weight: 600; \
margin-bottom: 8px;">AI INSIGHTS</div>
            <div style="color: #333; font-size: 14px; line-height: 1.6;">{{ ai_summary }}</div>
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
            <div style="font-size: 18px; font-weight: 600; color: #333; margin-bottom: 15px; \
border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; display: flex; justify-content: \
space-between; align-items: center;">
                <span>Assets</span>
                <span style="font-size: 16px; font-weight: 600;">
                    Total: {{ format_money(current.total_assets) }}
                    {% if previous and total_asset_change %}
                    {% set change_text, change_color = format_change(
                        {'amount': total_asset_change, 'currency': current.currency},
                        total_asset_change_percent) %}
                    <span style="color: {{ change_color }}; margin-left: 10px;">\
{{ change_text }}</span>
                    {% endif %}
                </span>
            </div>

            {% for sheet_name, sheet_sections in assets_by_sheet.items() %}
            <div style="margin-top: 20px;">
                <!-- Sheet-level header -->
                <div style="font-size: 16px; font-weight: 600; color: #555; \
margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #e0e0e0;">
                    {{ sheet_name }}
                    <span style="font-size: 14px; color: #777; font-weight: 500;">
                        ({{ sheet_totals[sheet_name].count }} account\
{{ 's' if sheet_totals[sheet_name].count != 1 else '' }})
                    </span>
                    <span style="float: right; font-size: 14px;">
                        {{ format_money({'amount': sheet_totals[sheet_name].total_value, \
'currency': current.currency}) }}
                        {% if previous and sheet_totals[sheet_name].total_change %}
                        {% set sheet_change_text, sheet_change_color = format_change(
                            {'amount': sheet_totals[sheet_name].total_change, \
'currency': current.currency},
                            sheet_totals[sheet_name].change_percent) %}
                        <span style="color: {{ sheet_change_color }}; margin-left: 8px; \
font-size: 13px;">
                            {{ sheet_change_text }}
                        </span>
                        {% endif %}
                    </span>
                </div>

                <!-- Section-level grouping within sheet (only if multiple sections) -->
                {% if sheet_sections|length > 1 %}
                    {% for section_name, accounts in sheet_sections.items() %}
                    {% set section = section_totals[sheet_name][section_name] %}
                    <div style="margin-left: 15px; margin-top: 15px;">
                        <div style="font-size: 14px; font-weight: 600; color: #666; \
margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #f0f0f0;">
                            {{ section_name }}
                            <span style="font-size: 13px; color: #888; font-weight: 500;">
                                ({{ section.count }} account{{ 's' if section.count != 1 else '' }})
                            </span>
                            <span style="float: right; font-size: 13px;">
                                {{ format_money({'amount': section.total_value, \
'currency': current.currency}) }}
                                {% if previous and section.total_change %}
                                {% set section_change_text, section_change_color = format_change(
                                    {'amount': section.total_change, 'currency': current.currency},
                                    section.change_percent) %}
                                <span style="color: {{ section_change_color }}; \
margin-left: 6px; font-size: 12px;">
                                    {{ section_change_text }}
                                </span>
                                {% endif %}
                            </span>
                        </div>

                        <!-- Individual accounts within section -->
                        {% for account in accounts %}
                        <div style="display: flex; justify-content: space-between; \
align-items: center; padding: 12px 0 12px 15px; border-bottom: 1px solid #f8f8f8;">
                            <div style="flex: 1;">
                                <div style="font-weight: 500; color: #333; font-size: 13px;">\
{{ account.name }}</div>
                                {% if account.institution %}
                                <div style="font-size: 11px; color: #999;">\
{{ account.institution }}</div>
                                {% endif %}
                            </div>
                            <div style="text-align: right;">
                                <div style="font-weight: 600; color: #333; font-size: 13px;">\
{{ format_money(account.current_value) }}</div>
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
                    {% endfor %}
                {% else %}
                    <!-- Single section: skip section header, show accounts directly -->
                    {% for section_name, accounts in sheet_sections.items() %}
                        {% for account in accounts %}
                        <div style="display: flex; justify-content: space-between; \
align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                            <div style="flex: 1;">
                                <div style="font-weight: 500; color: #333;">\
{{ account.name }}</div>
                                {% if account.institution %}
                                <div style="font-size: 12px; color: #999;">\
{{ account.institution }}</div>
                                {% endif %}
                            </div>
                            <div style="text-align: right;">
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
            {% endfor %}
        </div>
        {% endif %}

        {% if debt_movers %}
        <div style="margin-bottom: 30px;">
            <div style="font-size: 18px; font-weight: 600; color: #333; margin-bottom: 15px; \
border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; display: flex; justify-content: \
space-between; align-items: center;">
                <span>Liabilities</span>
                <span style="font-size: 16px; font-weight: 600;">
                    Total: {{ format_money(current.total_debts) }}
                    {% if previous and total_debt_change %}
                    {% set change_text, change_color = format_change(
                        {'amount': total_debt_change, 'currency': current.currency},
                        total_debt_change_percent) %}
                    <span style="color: {{ change_color }}; margin-left: 10px;">\
{{ change_text }}</span>
                    {% endif %}
                </span>
            </div>
            {% for account in debt_movers %}
            <div style="display: flex; justify-content: space-between; align-items: center; \
padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                <div style="flex: 1;">
                    <div style="font-weight: 500; color: #333;">{{ account.name }}</div>
                    {% if account.institution %}
                    <div style="font-size: 12px; color: #999;">{{ account.institution }}</div>
                    {% endif %}
                </div>
                <div style="text-align: right;">
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
</body>
</html>"""
