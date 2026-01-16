"""Job management service."""

import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
from google.cloud import firestore

from ..config import get_settings
from ..models import (
    Job,
    JobCost,
    JobProgress,
    JobResults,
    JobStatus,
    JobUrls,
    Operation,
    OperationOptions,
    Pagination,
)
from .auth import get_db
from .tokens import calculate_cost, deduct_tokens, refund_tokens


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return f"job_{uuid.uuid4().hex[:12]}"


async def create_job(
    user_id: str,
    api_key_id: str,
    image_url: str,
    operations: list[Operation],
    options: OperationOptions | None,
    webhook_url: str | None,
    client_metadata: dict[str, Any] | None,
    request_id: str | None,
    is_test_mode: bool,
) -> dict[str, Any]:
    """
    Create a new enhancement job.

    1. Calculate cost
    2. Check idempotency (request_id)
    3. Deduct tokens
    4. Create job document
    5. Trigger pipeline

    Returns:
        Job creation response dict
    """
    db = get_db()
    settings = get_settings()

    # Calculate cost
    total_cost, breakdown = calculate_cost(operations, options)

    # Check idempotency
    if request_id:
        existing_query = (
            db.collection("api_jobs")
            .where("user_id", "==", user_id)
            .where("request_id", "==", request_id)
            .limit(1)
        )
        existing_docs = list(existing_query.stream())
        if existing_docs:
            existing = existing_docs[0].to_dict()
            return {
                "job_id": existing["job_id"],
                "status": existing["status"],
                "operations": existing["operations"],
                "cost": {"estimated_aet": existing["cost"]["estimated"]},
                "created_at": existing["created_at"],
                "links": {
                    "self": f"/v1/jobs/{existing['job_id']}",
                    "cancel": f"/v1/jobs/{existing['job_id']}",
                },
                "message": "Job already created for this request_id",
            }

    # Deduct tokens
    job_id = generate_job_id()
    deduct_tokens(user_id, total_cost, "api_job", job_id)

    # Create job document
    now = datetime.utcnow()
    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "api_key_id": api_key_id,
        "request_id": request_id,
        "status": JobStatus.PENDING.value,
        "image_url": str(image_url),
        "operations": [op.value for op in operations],
        "options": {
            "nova": options.nova.model_dump() if options and options.nova else None,
            "flux": options.flux.model_dump() if options and options.flux else None,
            "atlas": options.atlas.model_dump() if options and options.atlas else None,
        } if options else {},
        "webhook_url": str(webhook_url) if webhook_url else None,
        "client_metadata": client_metadata or {},
        "cost": {
            "estimated": total_cost,
            "charged": total_cost,
            "refunded": 0,
        },
        "progress": {
            "nova": JobStatus.PENDING.value if Operation.NOVA in operations else None,
            "flux": JobStatus.PENDING.value if Operation.FLUX in operations else None,
            "atlas": JobStatus.PENDING.value if Operation.ATLAS in operations else None,
        },
        "results": None,
        "error": None,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "is_test_mode": is_test_mode,
    }

    db.collection("api_jobs").document(job_id).set(job_data)

    # Trigger pipeline asynchronously
    await trigger_pipeline(job_id, str(image_url), operations, options, user_id)

    return {
        "job_id": job_id,
        "status": JobStatus.PENDING.value,
        "operations": [op.value for op in operations],
        "cost": {"estimated_aet": total_cost},
        "created_at": now.isoformat(),
        "links": {
            "self": f"/v1/jobs/{job_id}",
            "cancel": f"/v1/jobs/{job_id}",
        },
    }


async def get_job(job_id: str, user_id: str) -> Job | None:
    """Get a job by ID, verifying ownership."""
    db = get_db()
    job_doc = db.collection("api_jobs").document(job_id).get()

    if not job_doc.exists:
        return None

    job_data = job_doc.to_dict()

    # Verify ownership
    if job_data["user_id"] != user_id:
        return None

    return _transform_job(job_data)


async def list_jobs(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    status_filter: JobStatus | None = None,
) -> tuple[list[Job], Pagination]:
    """List jobs for a user with pagination."""
    db = get_db()

    # Base query
    query = (
        db.collection("api_jobs")
        .where("user_id", "==", user_id)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
    )

    if status_filter:
        query = query.where("status", "==", status_filter.value)

    # Get total count (expensive, consider caching in production)
    all_docs = list(query.stream())
    total = len(all_docs)

    # Apply pagination
    paginated_docs = all_docs[offset : offset + limit]
    jobs = [_transform_job(doc.to_dict()) for doc in paginated_docs]

    pagination = Pagination(total=total, limit=limit, offset=offset)

    return jobs, pagination


async def cancel_job(job_id: str, user_id: str) -> bool:
    """
    Cancel a pending job.

    Returns True if cancelled, False if not found or not cancellable.
    """
    db = get_db()
    job_ref = db.collection("api_jobs").document(job_id)
    job_doc = job_ref.get()

    if not job_doc.exists:
        return False

    job_data = job_doc.to_dict()

    # Verify ownership
    if job_data["user_id"] != user_id:
        return False

    # Can only cancel pending jobs
    if job_data["status"] != JobStatus.PENDING.value:
        return False

    # Update status
    job_ref.update({
        "status": JobStatus.CANCELLED.value,
        "completed_at": datetime.utcnow(),
    })

    # Refund tokens
    cost = job_data["cost"]["charged"]
    if cost > 0:
        refund_tokens(user_id, cost, "job_cancelled", job_id)
        job_ref.update({"cost.refunded": cost})

    return True


async def update_job_status(
    job_id: str,
    status: JobStatus,
    progress: dict[str, str] | None = None,
    results: dict | None = None,
    error: dict | None = None,
) -> None:
    """Update job status (called by pipeline agents)."""
    db = get_db()
    job_ref = db.collection("api_jobs").document(job_id)

    update_data: dict[str, Any] = {
        "status": status.value,
    }

    if progress:
        for op, op_status in progress.items():
            update_data[f"progress.{op}"] = op_status

    if status == JobStatus.PROCESSING:
        update_data["started_at"] = datetime.utcnow()

    if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        update_data["completed_at"] = datetime.utcnow()

    if results:
        update_data["results"] = results

    if error:
        update_data["error"] = error

    job_ref.update(update_data)


async def trigger_pipeline(
    job_id: str,
    image_url: str,
    operations: list[Operation],
    options: OperationOptions | None,
    user_id: str,
) -> None:
    """
    Trigger the enhancement pipeline.

    This is a simplified implementation that calls agents directly.
    In production, consider using Cloud Tasks for reliability.
    """
    settings = get_settings()
    db = get_db()
    job_ref = db.collection("api_jobs").document(job_id)

    # Update status to processing
    job_ref.update({
        "status": JobStatus.PROCESSING.value,
        "started_at": datetime.utcnow(),
    })

    try:
        results: dict[str, Any] = {
            "urls": {"original": image_url},
        }
        current_image_url = image_url

        async with httpx.AsyncClient(timeout=300.0) as client:
            # Nova - AI Metadata
            if Operation.NOVA in operations:
                job_ref.update({"progress.nova": JobStatus.PROCESSING.value})

                nova_options = options.nova if options else None
                nova_response = await client.post(
                    f"{settings.nova_agent_url}/enrich",
                    json={
                        "image_url": current_image_url,
                        "user_id": user_id,
                        "job_id": job_id,
                        "parameters": {
                            "analysis_depth": "full" if nova_options and nova_options.tier == "full_gcx" else "standard",
                            "metadata_tier": nova_options.tier if nova_options else "standard",
                        },
                    },
                )
                nova_response.raise_for_status()
                nova_data = nova_response.json()
                results["golden_codex"] = nova_data.get("golden_codex", {})
                job_ref.update({"progress.nova": JobStatus.COMPLETED.value})

            # Flux - Upscaling
            if Operation.FLUX in operations:
                job_ref.update({"progress.flux": JobStatus.PROCESSING.value})

                flux_options = options.flux if options else None
                flux_response = await client.post(
                    f"{settings.flux_agent_url}/upscale",
                    json={
                        "image_url": current_image_url,
                        "user_id": user_id,
                        "job_id": job_id,
                        "parameters": {
                            "model": flux_options.model if flux_options else "4x",
                        },
                    },
                )
                flux_response.raise_for_status()
                flux_data = flux_response.json()
                upscaled_url = flux_data.get("upscaled_image_url")
                if upscaled_url:
                    results["urls"]["upscaled"] = upscaled_url
                    current_image_url = upscaled_url
                job_ref.update({"progress.flux": JobStatus.COMPLETED.value})

            # Atlas - Metadata Infusion
            if Operation.ATLAS in operations:
                job_ref.update({"progress.atlas": JobStatus.PROCESSING.value})

                atlas_options = options.atlas if options else None
                atlas_response = await client.post(
                    f"{settings.atlas_agent_url}/infuse",
                    json={
                        "image_url": current_image_url,
                        "user_id": user_id,
                        "job_id": job_id,
                        "golden_codex": results.get("golden_codex", {}),
                        "metadata_mode": "full_gcx",
                        "output_format": atlas_options.format if atlas_options else "png",
                    },
                )
                atlas_response.raise_for_status()
                atlas_data = atlas_response.json()
                final_url = atlas_data.get("final_url")
                if final_url:
                    results["urls"]["final"] = final_url
                job_ref.update({"progress.atlas": JobStatus.COMPLETED.value})

        # Job completed successfully
        job_ref.update({
            "status": JobStatus.COMPLETED.value,
            "results": results,
            "completed_at": datetime.utcnow(),
        })

        # Trigger webhook if configured
        job_doc = job_ref.get()
        job_data = job_doc.to_dict()
        if job_data.get("webhook_url"):
            await trigger_webhook(job_id, "job.completed", job_data)

    except Exception as e:
        # Job failed
        error_data = {
            "code": "pipeline_error",
            "message": str(e),
            "retryable": True,
        }

        job_ref.update({
            "status": JobStatus.FAILED.value,
            "error": error_data,
            "completed_at": datetime.utcnow(),
        })

        # Refund tokens on failure
        job_doc = job_ref.get()
        job_data = job_doc.to_dict()
        cost = job_data["cost"]["charged"]
        if cost > 0:
            refund_tokens(user_id, cost, "job_failed", job_id)
            job_ref.update({"cost.refunded": cost})

        # Trigger failure webhook
        if job_data.get("webhook_url"):
            await trigger_webhook(job_id, "job.failed", job_data)


async def trigger_webhook(job_id: str, event: str, job_data: dict) -> None:
    """
    Trigger a webhook notification.

    In production, this should use Cloud Tasks for reliability and retries.
    """
    webhook_url = job_data.get("webhook_url")
    if not webhook_url:
        return

    # For MVP, fire and forget
    # Production should use Cloud Tasks with retries
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                webhook_url,
                json={
                    "event": event,
                    "job_id": job_id,
                    "status": job_data["status"],
                    "results": job_data.get("results"),
                    "error": job_data.get("error"),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
    except Exception:
        # Log but don't fail - webhook delivery is best-effort for MVP
        pass


def _transform_job(job_data: dict) -> Job:
    """Transform Firestore job data to Job model."""
    progress = None
    if job_data.get("progress"):
        progress = JobProgress(
            nova=JobStatus(job_data["progress"]["nova"]) if job_data["progress"].get("nova") else None,
            flux=JobStatus(job_data["progress"]["flux"]) if job_data["progress"].get("flux") else None,
            atlas=JobStatus(job_data["progress"]["atlas"]) if job_data["progress"].get("atlas") else None,
        )

    results = None
    if job_data.get("results"):
        r = job_data["results"]
        results = JobResults(
            golden_codex=r.get("golden_codex"),
            urls=JobUrls(**r["urls"]) if r.get("urls") else None,
            artwork_id=r.get("artwork_id"),
        )

    cost_data = job_data.get("cost", {})

    return Job(
        job_id=job_data["job_id"],
        status=JobStatus(job_data["status"]),
        operations=[Operation(op) for op in job_data["operations"]],
        progress=progress,
        results=results,
        error=job_data.get("error"),
        cost=JobCost(
            estimated_aet=cost_data.get("estimated", 0),
            charged_aet=cost_data.get("charged"),
            refunded_aet=cost_data.get("refunded"),
        ),
        client_metadata=job_data.get("client_metadata"),
        created_at=job_data["created_at"],
        started_at=job_data.get("started_at"),
        completed_at=job_data.get("completed_at"),
    )
