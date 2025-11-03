"""HTML formatting utilities for portfolio reports."""

from kubera_reporting import currency_format
from kubera_reporting.types import MoneyValue


def get_fire_category(amount: float) -> str | None:
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


def format_money(value: MoneyValue, hide_amounts: bool = False) -> str:
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


def format_net_worth(value: MoneyValue, hide_amounts: bool = False) -> str:
    """Format net worth value with FIRE category indicator.

    Args:
        value: Net worth value
        hide_amounts: If True, mask the dollar amount but keep FIRE category

    Returns:
        Formatted string like "$1,234,567 (Fat FIRE)" or "$750,000" or "$XX (Fat FIRE)"
    """
    formatted_money = format_money(value, hide_amounts=hide_amounts)
    category = get_fire_category(value["amount"])

    if category:
        return f"{formatted_money} ({category})"
    return formatted_money


def format_change(
    change: MoneyValue, change_percent: float | None = None, hide_amounts: bool = False
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
