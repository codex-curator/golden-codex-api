"""Account API router."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response
from google.cloud import firestore

from ..models import (
    Account,
    AccountBalance,
    RateLimit,
    SubscriptionTier,
    UsageByOperation,
    UsageByStatus,
    UsageStats,
)
from ..services.auth import get_db
from ..services.rate_limit import RateLimitedAuth, add_rate_limit_headers, get_rate_limit_for_tier

router = APIRouter(prefix="/account", tags=["Account"])


@router.get(
    "",
    response_model=Account,
    summary="Get account",
    description="Get current account information and balance.",
)
async def get_account_endpoint(
    request: Request,
    response: Response,
    auth: RateLimitedAuth,
):
    """Get account information."""
    add_rate_limit_headers(response, request)

    db = get_db()
    user_doc = db.collection("users").document(auth.user_id).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    # Get balance
    tokens = user_data.get("tokens", {})
    balance = tokens.get("balance", 0)
    if balance == 0:
        balance = user_data.get("credits_available", 0)

    # Get storage
    storage = user_data.get("storage", {})
    storage_used = storage.get("usedBytes", 0)
    storage_limit = storage.get("limitBytes", 10 * 1024 * 1024 * 1024)  # 10GB default

    return Account(
        user_id=auth.user_id,
        email=user_data.get("email", ""),
        tier=auth.tier,
        balance=AccountBalance(
            aet=int(balance),
            storage_used_bytes=storage_used,
            storage_limit_bytes=storage_limit,
        ),
        rate_limit=RateLimit(
            requests_per_minute=get_rate_limit_for_tier(auth.tier),
            concurrent_jobs=10,  # Default
        ),
    )


@router.get(
    "/usage",
    response_model=UsageStats,
    summary="Get usage statistics",
    description="Get usage statistics for the last 30 days.",
)
async def get_usage_endpoint(
    request: Request,
    response: Response,
    auth: RateLimitedAuth,
):
    """Get usage statistics."""
    add_rate_limit_headers(response, request)

    db = get_db()

    # Calculate date range
    now = datetime.utcnow()
    period_start = now - timedelta(days=30)

    # Query jobs in the period
    jobs_query = (
        db.collection("api_jobs")
        .where("user_id", "==", auth.user_id)
        .where("created_at", ">=", period_start)
    )

    jobs = list(jobs_query.stream())

    # Calculate statistics
    jobs_created = len(jobs)
    completed = 0
    failed = 0
    cancelled = 0
    aet_spent = 0
    aet_nova = 0
    aet_flux = 0
    aet_atlas = 0

    for job_doc in jobs:
        job = job_doc.to_dict()
        status = job.get("status")

        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        elif status == "cancelled":
            cancelled += 1

        cost = job.get("cost", {})
        charged = cost.get("charged", 0)
        refunded = cost.get("refunded", 0)
        net_cost = charged - refunded
        aet_spent += net_cost

        # Estimate per-operation costs (simplified)
        operations = job.get("operations", [])
        if "nova" in operations:
            aet_nova += 2
        if "flux" in operations:
            aet_flux += 2
        if "atlas" in operations:
            aet_atlas += 1

    return UsageStats(
        period_start=period_start,
        period_end=now,
        jobs_created=jobs_created,
        jobs_by_status=UsageByStatus(
            completed=completed,
            failed=failed,
            cancelled=cancelled,
        ),
        aet_spent=aet_spent,
        aet_by_operation=UsageByOperation(
            nova=aet_nova,
            flux=aet_flux,
            atlas=aet_atlas,
        ),
    )
