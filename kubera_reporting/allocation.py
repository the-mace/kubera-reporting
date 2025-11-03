"""Asset allocation calculation logic."""

from kubera_reporting.types import PortfolioSnapshot


def calculate_asset_allocation(snapshot: PortfolioSnapshot) -> dict[str, float]:
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
