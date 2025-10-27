"""Currency formatting utilities with locale-aware support."""

from babel.numbers import get_currency_symbol as babel_get_currency_symbol


def format_money(amount: float, currency: str, hide_amounts: bool = False) -> str:
    """Format a monetary amount with the appropriate currency symbol and locale.

    Args:
        amount: The monetary amount to format
        currency: ISO 4217 currency code (USD, EUR, GBP, etc.)
        hide_amounts: If True, return masked amount like "$XX" or "€XX"

    Returns:
        Formatted money string like "$1,234" or "€1.234" or "£1,234"

    Examples:
        >>> format_money(1234.56, "USD")
        "$1,235"
        >>> format_money(1234.56, "EUR")
        "€1,235"
        >>> format_money(1234.56, "GBP")
        "£1,235"
        >>> format_money(1234.56, "USD", hide_amounts=True)
        "$XX"
    """
    symbol = babel_get_currency_symbol(currency, locale="en_US")

    if hide_amounts:
        return f"{symbol}XX"

    # Format with no decimal places (matching existing behavior)
    # We manually format to avoid babel's automatic decimal places for currencies
    return f"{symbol}{amount:,.0f}"


def format_change(
    amount: float,
    currency: str,
    percent: float | None = None,
    hide_amounts: bool = False,
) -> tuple[str, str]:
    """Format a change amount with currency symbol, arrows, and color.

    Args:
        amount: The change amount
        currency: ISO 4217 currency code (USD, EUR, GBP, etc.)
        percent: Optional percentage change
        hide_amounts: If True, mask dollar amounts but show percentage

    Returns:
        Tuple of (formatted_string, color_code)
        - formatted_string: Like "↑ $1,234 (+5.2%)" or "↓ €1,234 (-3.1%)"
        - color_code: HTML color code (#00b383 for positive, #e53935 for negative)

    Examples:
        >>> format_change(1234.56, "USD", 5.2)
        ("↑ $1,235 (+5.20%)", "#00b383")
        >>> format_change(-1234.56, "EUR", -3.1)
        ("↓ €1,235 (-3.10%)", "#e53935")
        >>> format_change(0, "GBP", 0)
        ("£0 (0.00%)", "#666666")
    """
    symbol = babel_get_currency_symbol(currency, locale="en_US")

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
        color = "#e53935"  # Red with down arrow
    else:
        if hide_amounts:
            base_text = f"{symbol}XX"
        else:
            base_text = f"{symbol}0"
        color = "#666666"  # Gray for no change

    # Add percentage if provided
    if percent is not None:
        if percent > 0:
            result = f"{base_text} (+{percent:.2f}%)"
        elif percent < 0:
            result = f"{base_text} ({percent:.2f}%)"
        else:
            result = f"{base_text} (0.00%)"
    else:
        result = base_text

    return result, color


def get_locale_for_currency(currency: str) -> str:
    """Get the best locale for a given currency.

    Args:
        currency: ISO 4217 currency code

    Returns:
        Locale string like "en_US", "de_DE", "en_GB"

    Note:
        We use specific locales to get proper number formatting:
        - USD: en_US (1,234.56)
        - EUR: de_DE (1.234,56) but we'll use en_US for consistency
        - GBP: en_GB (1,234.56)
        - JPY: ja_JP (no decimal places)

        For simplicity and consistency across reports, we use en_US style
        formatting (comma thousands separator, period decimal) for all
        currencies, just changing the symbol. This ensures USD users
        don't see confusing European number formats.
    """
    # Map currencies to locales
    # Using en_US for all to maintain consistent number formatting
    # Only the currency symbol changes
    locale_map = {
        "USD": "en_US",
        "EUR": "en_US",  # Using en_US style (1,234 not 1.234)
        "GBP": "en_US",  # Using en_US style for consistency
        "JPY": "en_US",
        "CAD": "en_US",
        "AUD": "en_US",
        "CHF": "en_US",
        "CNY": "en_US",
        "INR": "en_US",
    }

    return locale_map.get(currency, "en_US")


def get_currency_symbol(currency_code: str) -> str:
    """Get the currency symbol for a given currency code.

    Args:
        currency_code: ISO 4217 currency code (USD, EUR, GBP, etc.)

    Returns:
        Currency symbol like "$", "€", "£"

    Examples:
        >>> get_currency_symbol("USD")
        "$"
        >>> get_currency_symbol("EUR")
        "€"
        >>> get_currency_symbol("GBP")
        "£"
    """
    return babel_get_currency_symbol(currency_code, locale="en_US")
