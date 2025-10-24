"""Custom exceptions for Kubera Reporting."""


class KuberaReportingError(Exception):
    """Base exception for all Kubera Reporting errors."""

    pass


class DataFetchError(KuberaReportingError):
    """Raised when fetching data from Kubera API fails."""

    pass


class StorageError(KuberaReportingError):
    """Raised when storage operations fail."""

    pass


class ReportGenerationError(KuberaReportingError):
    """Raised when report generation fails."""

    pass


class EmailError(KuberaReportingError):
    """Raised when email sending fails."""

    pass


class AIError(KuberaReportingError):
    """Raised when AI/LLM operations fail."""

    pass
