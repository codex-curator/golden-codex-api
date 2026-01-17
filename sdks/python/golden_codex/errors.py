"""Custom exception classes for the Golden Codex SDK."""

from typing import Any, Optional


class GoldenCodexError(Exception):
    """Base exception for all Golden Codex errors."""

    pass


class APIError(GoldenCodexError):
    """Exception raised when an API request fails."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.status}] {self.code}: {self.message}"


class AuthenticationError(APIError):
    """Exception raised when authentication fails (401)."""

    def __init__(self, code: str, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(401, code, message, details)


class InsufficientCreditsError(APIError):
    """Exception raised when the account has insufficient credits (402)."""

    def __init__(
        self,
        code: str,
        message: str,
        balance: int,
        required: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(402, code, message, details)
        self.balance = balance
        self.required = required

    def __str__(self) -> str:
        return f"Insufficient credits: have {self.balance} GCX, need {self.required} GCX"


class RateLimitError(APIError):
    """Exception raised when rate limited (429)."""

    def __init__(
        self,
        code: str,
        message: str,
        retry_after: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(429, code, message, details)
        self.retry_after = retry_after

    def __str__(self) -> str:
        return f"Rate limited. Retry after {self.retry_after} seconds."


class NotFoundError(APIError):
    """Exception raised when a resource is not found (404)."""

    def __init__(self, code: str, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(404, code, message, details)


class ValidationError(APIError):
    """Exception raised when validation fails (400)."""

    def __init__(self, code: str, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(400, code, message, details)


class TimeoutError(GoldenCodexError):
    """Exception raised when waiting for a job times out."""

    def __init__(self, job_id: str, timeout: float):
        super().__init__(f"Job {job_id} did not complete within {timeout}s")
        self.job_id = job_id
        self.timeout = timeout


class JobFailedError(GoldenCodexError):
    """Exception raised when a job fails."""

    def __init__(self, job_id: str, code: str, message: str, stage: Optional[str] = None):
        super().__init__(f"Job {job_id} failed: {message}")
        self.job_id = job_id
        self.code = code
        self.error_message = message
        self.stage = stage
