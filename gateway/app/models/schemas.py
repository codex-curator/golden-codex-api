"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


# ============ Enums ============


class Operation(str, Enum):
    """Enhancement operations."""

    NOVA = "nova"
    FLUX = "flux"
    ATLAS = "atlas"


class JobStatus(str, Enum):
    """Job status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubscriptionTier(str, Enum):
    """User subscription tiers."""

    FREE_TRIAL = "FREE_TRIAL"
    CURATOR = "CURATOR"
    STUDIO = "STUDIO"
    GALLERY = "GALLERY"


class WebhookEvent(str, Enum):
    """Webhook event types."""

    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"


# ============ Options ============


class NovaOptions(BaseModel):
    """Options for Nova AI analysis."""

    tier: Literal["standard", "full_gcx"] = "standard"
    language: str = "en"


class FluxOptions(BaseModel):
    """Options for Flux upscaling."""

    model: Literal["2x", "4x", "anime", "photo"] = "4x"


class AtlasOptions(BaseModel):
    """Options for Atlas metadata infusion."""

    format: Literal["png", "jpg", "webp"] = "png"


class OperationOptions(BaseModel):
    """Combined options for all operations."""

    nova: NovaOptions | None = None
    flux: FluxOptions | None = None
    atlas: AtlasOptions | None = None


# ============ Jobs ============


class CreateJobRequest(BaseModel):
    """Request to create a new job."""

    image_url: HttpUrl = Field(..., description="URL of image to process")
    operations: list[Operation] = Field(
        default=[Operation.NOVA, Operation.FLUX, Operation.ATLAS],
        description="Operations to perform",
    )
    options: OperationOptions | None = Field(default=None, description="Operation options")
    webhook_url: HttpUrl | None = Field(default=None, description="Webhook URL for notifications")
    metadata: dict[str, Any] | None = Field(default=None, description="Custom metadata")


class JobCost(BaseModel):
    """Job cost information."""

    estimated_aet: int
    charged_aet: int | None = None
    refunded_aet: int | None = None


class JobLinks(BaseModel):
    """Links for a job."""

    self: str
    cancel: str


class CreateJobResponse(BaseModel):
    """Response from creating a job."""

    job_id: str
    status: JobStatus
    operations: list[Operation]
    cost: JobCost
    created_at: datetime
    links: JobLinks


class JobProgress(BaseModel):
    """Progress of individual operations."""

    nova: JobStatus | None = None
    flux: JobStatus | None = None
    atlas: JobStatus | None = None


class JobUrls(BaseModel):
    """URLs to job outputs."""

    original: str
    upscaled: str | None = None
    final: str | None = None


class GoldenCodexMetadata(BaseModel):
    """Simplified Golden Codex metadata structure."""

    title: str | None = None
    artist_interpretation: str | None = None
    style_classification: list[str] | None = None
    soul_whisper: str | None = None

    class Config:
        extra = "allow"


class JobResults(BaseModel):
    """Results from a completed job."""

    golden_codex: GoldenCodexMetadata | None = None
    urls: JobUrls | None = None
    artwork_id: str | None = None


class JobError(BaseModel):
    """Error details for a failed job."""

    code: str
    message: str
    stage: Operation | None = None
    retryable: bool = False


class Job(BaseModel):
    """Full job details."""

    job_id: str
    status: JobStatus
    operations: list[Operation]
    progress: JobProgress | None = None
    results: JobResults | None = None
    error: JobError | None = None
    cost: JobCost
    client_metadata: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Pagination(BaseModel):
    """Pagination information."""

    total: int
    limit: int
    offset: int


class ListJobsResponse(BaseModel):
    """Response from listing jobs."""

    jobs: list[Job]
    pagination: Pagination


# ============ Account ============


class AccountBalance(BaseModel):
    """Account balance information."""

    aet: int
    storage_used_bytes: int
    storage_limit_bytes: int


class RateLimit(BaseModel):
    """Rate limit information."""

    requests_per_minute: int
    concurrent_jobs: int = 10


class Account(BaseModel):
    """Account information."""

    user_id: str
    email: str
    tier: SubscriptionTier
    balance: AccountBalance
    rate_limit: RateLimit


class UsageByStatus(BaseModel):
    """Usage broken down by status."""

    completed: int = 0
    failed: int = 0
    cancelled: int = 0


class UsageByOperation(BaseModel):
    """Usage broken down by operation."""

    nova: int = 0
    flux: int = 0
    atlas: int = 0


class UsageStats(BaseModel):
    """Usage statistics."""

    period_start: datetime
    period_end: datetime
    jobs_created: int
    jobs_by_status: UsageByStatus
    aet_spent: int
    aet_by_operation: UsageByOperation


# ============ Cost Estimation ============


class CostBreakdownItem(BaseModel):
    """Cost breakdown for a single operation."""

    cost: int
    tier: str | None = None
    model: str | None = None


class CostEstimate(BaseModel):
    """Cost estimate response."""

    estimated_aet: int
    breakdown: dict[str, CostBreakdownItem]
    current_balance: int
    sufficient_balance: bool


class EstimateCostRequest(BaseModel):
    """Request to estimate costs."""

    operations: list[Operation] = [Operation.NOVA, Operation.FLUX, Operation.ATLAS]
    options: OperationOptions | None = None


# ============ Webhooks ============


class CreateWebhookRequest(BaseModel):
    """Request to create a webhook."""

    url: HttpUrl = Field(..., description="HTTPS URL to receive webhooks")
    events: list[WebhookEvent] = Field(
        default=[WebhookEvent.JOB_COMPLETED, WebhookEvent.JOB_FAILED],
        description="Events to subscribe to",
    )


class CreateWebhookResponse(BaseModel):
    """Response from creating a webhook."""

    webhook_id: str
    url: str
    events: list[WebhookEvent]
    secret: str  # Only shown once!
    created_at: datetime


class Webhook(BaseModel):
    """Webhook details (without secret)."""

    webhook_id: str
    url: str
    events: list[WebhookEvent]
    active: bool
    created_at: datetime
    last_success_at: datetime | None = None
    consecutive_failures: int = 0


class UpdateWebhookRequest(BaseModel):
    """Request to update a webhook."""

    events: list[WebhookEvent] | None = None
    active: bool | None = None


class ListWebhooksResponse(BaseModel):
    """Response from listing webhooks."""

    webhooks: list[Webhook]
    pagination: Pagination


# ============ Errors ============


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str
    message: str
    balance: int | None = None
    required: int | None = None
    retry_after: int | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
