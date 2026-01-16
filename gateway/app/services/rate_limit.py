"""Rate limiting service."""

import time
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from ..config import get_settings
from ..models import SubscriptionTier
from .auth import Auth, AuthContext


@dataclass
class RateLimitWindow:
    """Rate limit tracking for a time window."""

    count: int = 0
    window_start: int = 0


# In-memory rate limit store (for MVP - production should use Redis)
_rate_limits: dict[str, RateLimitWindow] = {}


def get_rate_limit_for_tier(tier: SubscriptionTier) -> int:
    """Get the rate limit (requests per minute) for a subscription tier."""
    settings = get_settings()
    limits = {
        SubscriptionTier.FREE_TRIAL: settings.rate_limit_free,
        SubscriptionTier.CURATOR: settings.rate_limit_curator,
        SubscriptionTier.STUDIO: settings.rate_limit_studio,
        SubscriptionTier.GALLERY: settings.rate_limit_gallery,
    }
    return limits.get(tier, settings.rate_limit_free)


def check_rate_limit(auth: AuthContext) -> tuple[int, int, int]:
    """
    Check and update rate limit for a request.

    Returns:
        Tuple of (limit, remaining, reset_timestamp)

    Raises:
        HTTPException: If rate limit is exceeded
    """
    key_id = auth.key_id
    limit = get_rate_limit_for_tier(auth.tier)

    now = int(time.time())
    window_start = (now // 60) * 60  # Round to minute
    window_reset = window_start + 60

    # Get or create rate limit window
    if key_id not in _rate_limits or _rate_limits[key_id].window_start != window_start:
        _rate_limits[key_id] = RateLimitWindow(count=0, window_start=window_start)

    window = _rate_limits[key_id]
    window.count += 1

    remaining = max(0, limit - window.count)

    if window.count > limit:
        retry_after = window_reset - now
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "rate_limited",
                    "message": f"Rate limit exceeded. {limit} requests per minute allowed.",
                    "retry_after": retry_after,
                }
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(window_reset),
                "Retry-After": str(retry_after),
            },
        )

    return limit, remaining, window_reset


async def rate_limit_middleware(
    request: Request,
    auth: Auth,
) -> AuthContext:
    """
    Dependency that enforces rate limits.

    Use this instead of Auth when rate limiting is required.
    """
    limit, remaining, reset = check_rate_limit(auth)

    # Store rate limit info for response headers
    request.state.rate_limit = {
        "limit": limit,
        "remaining": remaining,
        "reset": reset,
    }

    return auth


def add_rate_limit_headers(response: Response, request: Request) -> None:
    """Add rate limit headers to response."""
    if hasattr(request.state, "rate_limit"):
        rl = request.state.rate_limit
        response.headers["X-RateLimit-Limit"] = str(rl["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rl["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rl["reset"])


# Dependency for rate-limited routes
RateLimitedAuth = Annotated[AuthContext, Depends(rate_limit_middleware)]
