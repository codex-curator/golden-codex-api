"""Jobs API router."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from ..models import (
    CreateJobRequest,
    CreateJobResponse,
    Job,
    JobCost,
    JobLinks,
    JobStatus,
    ListJobsResponse,
    Operation,
)
from ..services.auth import AuthContext
from ..services.jobs import cancel_job, create_job, get_job, list_jobs
from ..services.rate_limit import RateLimitedAuth, add_rate_limit_headers

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=CreateJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create enhancement job",
    description="Create a new image enhancement job. The job runs asynchronously.",
)
async def create_job_endpoint(
    request: Request,
    response: Response,
    body: CreateJobRequest,
    auth: RateLimitedAuth,
    x_request_id: Annotated[str | None, Header()] = None,
):
    """Create a new enhancement job."""
    add_rate_limit_headers(response, request)

    result = await create_job(
        user_id=auth.user_id,
        api_key_id=auth.key_id,
        image_url=str(body.image_url),
        operations=body.operations,
        options=body.options,
        webhook_url=str(body.webhook_url) if body.webhook_url else None,
        client_metadata=body.metadata,
        request_id=x_request_id,
        is_test_mode=auth.is_test_mode,
    )

    return CreateJobResponse(
        job_id=result["job_id"],
        status=JobStatus(result["status"]),
        operations=[Operation(op) for op in result["operations"]],
        cost=JobCost(estimated_gcx=result["cost"]["estimated_gcx"]),
        created_at=result["created_at"],
        links=JobLinks(
            self=result["links"]["self"],
            cancel=result["links"]["cancel"],
        ),
    )


@router.get(
    "",
    response_model=ListJobsResponse,
    summary="List jobs",
    description="List your jobs with pagination and filtering.",
)
async def list_jobs_endpoint(
    request: Request,
    response: Response,
    auth: RateLimitedAuth,
    limit: int = Query(default=20, ge=1, le=100, description="Maximum jobs to return"),
    offset: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    status_filter: JobStatus | None = Query(default=None, alias="status", description="Filter by status"),
):
    """List jobs with pagination."""
    add_rate_limit_headers(response, request)

    jobs, pagination = await list_jobs(
        user_id=auth.user_id,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )

    return ListJobsResponse(jobs=jobs, pagination=pagination)


@router.get(
    "/{job_id}",
    response_model=Job,
    summary="Get job",
    description="Get the status and results of a job.",
)
async def get_job_endpoint(
    request: Request,
    response: Response,
    job_id: str,
    auth: RateLimitedAuth,
):
    """Get a job by ID."""
    add_rate_limit_headers(response, request)

    job = await get_job(job_id, auth.user_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "job_not_found",
                    "message": f"Job {job_id} not found",
                }
            },
        )

    return job


@router.get(
    "/{job_id}/codex",
    summary="Download Golden Codex JSON",
    description="Returns the Golden Codex metadata as a downloadable JSON object.",
)
async def get_job_codex_endpoint(
    request: Request,
    response: Response,
    job_id: str,
    auth: RateLimitedAuth,
):
    """Get the Golden Codex JSON for a completed job."""
    add_rate_limit_headers(response, request)

    job = await get_job(job_id, auth.user_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "job_not_found", "message": f"Job {job_id} not found"}},
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "job_not_complete", "message": f"Job {job_id} is {job.status.value}"}},
        )

    if not job.results or not job.results.golden_codex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "no_codex", "message": "No Golden Codex metadata available"}},
        )

    return {
        "job_id": job_id,
        "golden_codex": job.results.golden_codex,
        "provenance": job.results.provenance,
        "urls": job.results.urls,
    }


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel job",
    description="Cancel a pending job. Cannot cancel jobs already processing.",
)
async def cancel_job_endpoint(
    request: Request,
    response: Response,
    job_id: str,
    auth: RateLimitedAuth,
):
    """Cancel a pending job."""
    add_rate_limit_headers(response, request)

    cancelled = await cancel_job(job_id, auth.user_id)

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "job_not_found",
                    "message": f"Job {job_id} not found or cannot be cancelled",
                }
            },
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
