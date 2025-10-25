"""Fetch portfolio data from Kubera API."""

import sys
from datetime import datetime, timezone
from typing import Any

from kubera import KuberaClient
from kubera.cache import resolve_portfolio_id, save_portfolio_cache
from kubera.exceptions import KuberaAPIError

from kubera_reporting.exceptions import DataFetchError
from kubera_reporting.types import AccountSnapshot, PortfolioSnapshot


class KuberaFetcher:
    """Fetches portfolio data from Kubera API."""

    def __init__(self, api_key: str | None = None, secret: str | None = None) -> None:
        """Initialize the fetcher.

        Args:
            api_key: Kubera API key (optional, loads from ~/.env if not provided)
            secret: Kubera API secret (optional, loads from ~/.env if not provided)
        """
        try:
            if api_key and secret:
                self.client = KuberaClient(api_key=api_key, secret=secret)
            else:
                self.client = KuberaClient()
        except Exception as e:
            raise DataFetchError(f"Failed to initialize Kubera client: {e}") from e

    def fetch_snapshot(self, portfolio_id: str | None = None) -> PortfolioSnapshot:
        """Fetch current portfolio snapshot.

        Args:
            portfolio_id: Portfolio ID/index to fetch (if None, uses first portfolio)

        Returns:
            Current portfolio snapshot

        Raises:
            DataFetchError: If fetching fails
        """
        try:
            # Get portfolios and update cache
            portfolios = self.client.get_portfolios()
            if not portfolios:
                raise DataFetchError("No portfolios found")

            # Save to cache for index resolution
            save_portfolio_cache(portfolios)  # type: ignore[arg-type]

            # Resolve portfolio ID (handles both indexes like "4" and GUIDs)
            if portfolio_id is not None:
                resolved_id = resolve_portfolio_id(portfolio_id)
                if resolved_id is None:
                    raise DataFetchError(
                        f"Portfolio '{portfolio_id}' not found. "
                        "Run 'kubera list' to see available portfolios."
                    )
                portfolio_id = resolved_id
            else:
                # Use first portfolio if not specified
                portfolio_id = portfolios[0]["id"]
                print(
                    f"Using first portfolio: {portfolios[0]['name']} ({portfolio_id})",
                    file=sys.stderr,
                )

            # Get detailed portfolio data
            portfolio: dict[str, Any] = self.client.get_portfolio(portfolio_id)  # type: ignore[assignment]

            # Extract ALL accounts from assets and debts (raw data)
            # The reporter will handle aggregation/filtering as needed
            accounts: list[AccountSnapshot] = []

            # Process assets - save ALL raw data from API
            for asset in portfolio.get("assets", portfolio.get("asset", [])):
                accounts.append(
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "institution": asset.get("connection", {}).get("providerName"),
                        "value": asset["value"],
                        "category": "asset",
                        "sheet_name": asset["sheetName"],
                        "section_name": asset.get("sectionName"),
                        "sub_type": asset.get("subType"),
                        "asset_class": asset.get("assetClass"),
                        "account_type": asset.get("type"),
                        "geography": asset.get("geography"),
                    }
                )

            # Process debts - save ALL raw data from API
            for debt in portfolio.get("debts", portfolio.get("debt", [])):
                accounts.append(
                    {
                        "id": debt["id"],
                        "name": debt["name"],
                        "institution": debt.get("connection", {}).get("providerName"),
                        "value": debt["value"],
                        "category": "debt",
                        "sheet_name": debt["sheetName"],
                        "section_name": debt.get("sectionName"),
                        "sub_type": debt.get("subType"),
                        "asset_class": debt.get("assetClass"),
                        "account_type": debt.get("type"),
                        "geography": debt.get("geography"),
                    }
                )

            # Get portfolio info for name and currency
            portfolio_info = next((p for p in portfolios if p["id"] == portfolio_id), None)

            if not portfolio_info:
                raise DataFetchError(f"Portfolio {portfolio_id} not found in portfolio list")

            # Get currency from portfolio info
            currency = portfolio_info.get("currency", "USD")

            # Create snapshot (API returns numeric values, not objects)
            snapshot: PortfolioSnapshot = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio_info.get("name", "Unknown Portfolio"),
                "currency": currency,
                "net_worth": {
                    "amount": portfolio.get("net_worth", portfolio.get("netWorth", 0.0)),
                    "currency": currency,
                },
                "total_assets": {
                    "amount": portfolio.get("asset_total", portfolio.get("assetTotal", 0.0)),
                    "currency": currency,
                },
                "total_debts": {
                    "amount": portfolio.get("debt_total", portfolio.get("debtTotal", 0.0)),
                    "currency": currency,
                },
                "accounts": accounts,
            }

            return snapshot

        except KuberaAPIError as e:
            raise DataFetchError(f"Kubera API error: {e.message}") from e
        except Exception as e:
            raise DataFetchError(f"Failed to fetch portfolio data: {e}") from e

    def close(self) -> None:
        """Close the Kubera client."""
        self.client.close()

    def __enter__(self) -> "KuberaFetcher":
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()
