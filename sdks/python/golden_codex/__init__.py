"""
Golden Codex SDK for Python

AI-powered image enrichment and provenance tracking.

Example:
    >>> from golden_codex import GoldenCodex
    >>>
    >>> gcx = GoldenCodex(api_key="gcx_live_...")
    >>>
    >>> job = gcx.jobs.create(
    ...     image_url="https://example.com/artwork.jpg",
    ...     operations=["nova", "flux", "atlas"]
    ... )
    >>>
    >>> result = gcx.jobs.wait(job["job_id"])
    >>> print(result["results"]["golden_codex"])
"""

from .client import GoldenCodex, GoldenCodexAsync
from .errors import (
    GoldenCodexError,
    APIError,
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    NotFoundError,
    ValidationError,
    TimeoutError,
    JobFailedError,
)
from .webhooks import verify_webhook_signature

__version__ = "1.0.0"

__all__ = [
    "GoldenCodex",
    "GoldenCodexAsync",
    "GoldenCodexError",
    "APIError",
    "AuthenticationError",
    "InsufficientCreditsError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
    "TimeoutError",
    "JobFailedError",
    "verify_webhook_signature",
]
