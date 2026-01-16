"""Cost estimation router."""

from fastapi import APIRouter, Request, Response

from ..models import CostBreakdownItem, CostEstimate, EstimateCostRequest
from ..services.rate_limit import RateLimitedAuth, add_rate_limit_headers
from ..services.tokens import calculate_cost

router = APIRouter(tags=["Utilities"])


@router.post(
    "/estimate",
    response_model=CostEstimate,
    summary="Estimate cost",
    description="Calculate the cost of operations before creating a job.",
)
async def estimate_cost_endpoint(
    request: Request,
    response: Response,
    body: EstimateCostRequest,
    auth: RateLimitedAuth,
):
    """Estimate the cost of operations."""
    add_rate_limit_headers(response, request)

    total_cost, breakdown = calculate_cost(body.operations, body.options)

    # Transform breakdown to response format
    breakdown_items = {
        op: CostBreakdownItem(**details)
        for op, details in breakdown.items()
    }

    return CostEstimate(
        estimated_aet=total_cost,
        breakdown=breakdown_items,
        current_balance=auth.balance,
        sufficient_balance=auth.balance >= total_cost,
    )
