"""Type definitions for Kubera Reporting."""

from enum import Enum
from typing import Literal, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class ReportType(Enum):
    """Type of portfolio report."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class MoneyValue(TypedDict):
    """Represents a monetary value with currency."""

    amount: float
    currency: str


class AccountSnapshot(TypedDict):
    """Snapshot of a single account."""

    id: str
    name: str
    institution: str | None
    value: MoneyValue
    category: Literal["asset", "debt"]
    sheet_name: str
    subsheet_name: NotRequired[str | None]  # Optional: section within a sheet


class PortfolioSnapshot(TypedDict):
    """Complete portfolio snapshot at a point in time."""

    timestamp: str  # ISO 8601 format
    portfolio_id: str
    portfolio_name: str
    currency: str
    net_worth: MoneyValue
    total_assets: MoneyValue
    total_debts: MoneyValue
    accounts: list[AccountSnapshot]


class AccountDelta(TypedDict):
    """Change in account value between two snapshots."""

    id: str
    name: str
    institution: str | None
    category: Literal["asset", "debt"]
    sheet_name: str
    subsheet_name: NotRequired[str | None]  # Optional: section within a sheet
    current_value: MoneyValue
    previous_value: MoneyValue
    change: MoneyValue
    change_percent: float | None


class ReportData(TypedDict):
    """Data for generating a report."""

    current: PortfolioSnapshot
    previous: PortfolioSnapshot | None
    net_worth_change: MoneyValue | None
    asset_changes: list[AccountDelta]
    debt_changes: list[AccountDelta]
