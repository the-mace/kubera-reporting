"""LLM client for AI-powered portfolio analysis."""

import json
import os

from litellm import completion

from kubera_reporting.exceptions import AIError
from kubera_reporting.types import PortfolioSnapshot, ReportData

# Default models
DEFAULT_MODEL = "xai/grok-4-fast-reasoning"  # Best performance/cost balance
ENV_FILE_PATH = "~/.env"


def load_env_file() -> None:
    """Load environment variables from ~/.env file.

    Supports provider-specific API keys (GROK_API_KEY, ANTHROPIC_API_KEY, etc.)
    and generic LLM_API_KEY as fallback.
    """
    env_file = os.path.expanduser(ENV_FILE_PATH)
    if os.path.exists(env_file):
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        # Handle both "export KEY=value" and "KEY=value" formats
                        if line.startswith("export "):
                            line = line[7:]  # Remove 'export ' prefix

                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip("\"'")  # Remove quotes
                        if key and not os.getenv(key):  # Only set if not already in environment
                            os.environ[key] = value
        except Exception as e:
            print(f"Warning: Could not read ~/.env file: {e}")

    # LiteLLM compatibility: Map GROK_API_KEY to XAI_API_KEY if needed
    if os.getenv("GROK_API_KEY") and not os.getenv("XAI_API_KEY"):
        os.environ["XAI_API_KEY"] = os.getenv("GROK_API_KEY", "")


class LLMClient:
    """Client for AI-powered portfolio analysis."""

    def __init__(self, model: str | None = None) -> None:
        """Initialize LLM client.

        Args:
            model: Model to use (defaults to KUBERA_REPORT_LLM_MODEL env var or DEFAULT_MODEL)
        """
        # Load environment variables
        load_env_file()

        # Determine model to use
        self.model = model or os.getenv("KUBERA_REPORT_LLM_MODEL", DEFAULT_MODEL)

        # Convert legacy model names to current format
        model_mapping = {
            "grok-4-fast-reasoning": "xai/grok-4-fast-reasoning",
            "grok-beta": "xai/grok-4-fast-reasoning",
            "grok-2-1212": "xai/grok-4-fast-reasoning",
        }
        self.model = model_mapping.get(self.model, self.model)

    def query_portfolio(
        self,
        query: str,
        current_snapshot: PortfolioSnapshot,
        report_data: ReportData | None = None,
    ) -> str:
        """Ask questions about portfolio data.

        Args:
            query: Question to ask
            current_snapshot: Current portfolio snapshot
            report_data: Optional report data with deltas

        Returns:
            AI response

        Raises:
            AIError: If query fails
        """
        try:
            # Build context
            context_parts = ["Current Portfolio Data:", json.dumps(current_snapshot, indent=2)]

            if report_data and report_data["previous"]:
                context_parts.extend(
                    [
                        "\nPrevious Portfolio Data:",
                        json.dumps(report_data["previous"], indent=2),
                        "\nChanges:",
                        f"Net Worth Change: {report_data['net_worth_change']}",
                        f"\nTop Asset Changes ({len(report_data['asset_changes'])} total):",
                        json.dumps(report_data["asset_changes"][:10], indent=2),
                        f"\nTop Debt Changes ({len(report_data['debt_changes'])} total):",
                        json.dumps(report_data["debt_changes"][:10], indent=2),
                    ]
                )

            context = "\n".join(context_parts)

            # Build prompt
            prompt = f"""You are a financial advisor analyzing portfolio data.
You have access to current and historical portfolio information.

{context}

User Question: {query}

Please provide a clear, helpful answer based on the portfolio data provided.
Include specific numbers and percentages where relevant."""

            # Call LLM
            response = completion(
                model=self.model, messages=[{"role": "user", "content": prompt}], stream=False
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            raise AIError(f"Failed to query LLM: {e}") from e

    def summarize_changes(self, report_data: ReportData) -> str:
        """Generate AI summary of portfolio changes.

        Args:
            report_data: Report data with deltas

        Returns:
            AI-generated summary

        Raises:
            AIError: If summarization fails
        """
        try:
            if not report_data["previous"]:
                return "No previous data available for comparison."

            # Build context
            context = f"""Current Portfolio:
Net Worth: {report_data["current"]["net_worth"]}
Total Assets: {report_data["current"]["total_assets"]}
Total Debts: {report_data["current"]["total_debts"]}

Changes:
Net Worth Change: {report_data["net_worth_change"]}

Top Asset Changes:
{json.dumps(report_data["asset_changes"][:5], indent=2)}

Top Debt Changes:
{json.dumps(report_data["debt_changes"][:5], indent=2)}
"""

            prompt = f"""You are a financial advisor. Provide a brief, insightful summary of the
portfolio changes below. Focus on the most significant changes and what they mean.
Keep it concise (2-3 paragraphs).

{context}

Summary:"""

            # Call LLM
            response = completion(
                model=self.model, messages=[{"role": "user", "content": prompt}], stream=False
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            raise AIError(f"Failed to generate summary: {e}") from e

    def analyze_trends(self, snapshots: list[PortfolioSnapshot], period: str = "week") -> str:
        """Analyze trends across multiple snapshots.

        Args:
            snapshots: List of snapshots (ordered by time)
            period: Time period (e.g., "week", "month")

        Returns:
            AI-generated trend analysis

        Raises:
            AIError: If analysis fails
        """
        try:
            if len(snapshots) < 2:
                return "Not enough historical data for trend analysis."

            # Build context with key metrics
            metrics = []
            for snapshot in snapshots:
                metrics.append(
                    {
                        "date": snapshot["timestamp"],
                        "net_worth": snapshot["net_worth"]["amount"],
                        "total_assets": snapshot["total_assets"]["amount"],
                        "total_debts": snapshot["total_debts"]["amount"],
                    }
                )

            context = json.dumps(metrics, indent=2)

            prompt = f"""You are a financial advisor. Analyze the portfolio trends below over \
the past {period}. Identify key patterns, growth trends, and any areas of concern.
Keep it concise (2-3 paragraphs).

Portfolio Metrics Over Time:
{context}

Trend Analysis:"""

            # Call LLM
            response = completion(
                model=self.model, messages=[{"role": "user", "content": prompt}], stream=False
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            raise AIError(f"Failed to analyze trends: {e}") from e
