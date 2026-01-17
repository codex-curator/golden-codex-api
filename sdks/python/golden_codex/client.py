"""Golden Codex API client implementations."""

from __future__ import annotations

import time
from typing import Any, Callable, Literal, Optional, TypedDict

import httpx

from .errors import (
    APIError,
    AuthenticationError,
    InsufficientCreditsError,
    JobFailedError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)


# ============ Type Definitions ============


class NovaOptions(TypedDict, total=False):
    """Options for Nova AI metadata generation."""

    tier: Literal["standard", "full_gcx"]
    language: str


class FluxOptions(TypedDict, total=False):
    """Options for Flux upscaling."""

    model: Literal["2x", "4x", "anime", "photo"]


class AtlasOptions(TypedDict, total=False):
    """Options for Atlas metadata infusion."""

    format: Literal["png", "jpg", "webp"]


class EnhancementOptions(TypedDict, total=False):
    """Options for each enhancement operation."""

    nova: NovaOptions
    flux: FluxOptions
    atlas: AtlasOptions


Operation = Literal["nova", "flux", "atlas"]
JobStatus = Literal["pending", "processing", "completed", "failed", "cancelled"]


# ============ Base Client ============


class BaseClient:
    """Base client with shared logic for sync and async clients."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.golden-codex.com/v1",
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        if not api_key:
            raise ValueError("API key is required. Get one at https://golden-codex.com/dashboard")

        if not api_key.startswith(("gcx_live_", "gcx_test_")):
            raise ValueError("Invalid API key format. Keys should start with gcx_live_ or gcx_test_")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "golden-codex-python/1.0.0",
        }

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle error responses from the API."""
        try:
            body = response.json()
            error = body.get("error", {})
        except Exception:
            error = {}

        code = error.get("code", "unknown_error")
        message = error.get("message", f"Request failed with status {response.status_code}")

        if response.status_code == 401:
            raise AuthenticationError(code, message, error)

        if response.status_code == 402:
            raise InsufficientCreditsError(
                code,
                message,
                balance=error.get("balance", 0),
                required=error.get("required", 0),
                details=error,
            )

        if response.status_code == 404:
            raise NotFoundError(code, message, error)

        if response.status_code == 429:
            raise RateLimitError(
                code,
                message,
                retry_after=error.get("retry_after", 60),
                details=error,
            )

        if response.status_code == 400:
            raise ValidationError(code, message, error)

        raise APIError(response.status_code, code, message, error)


# ============ Synchronous Client ============


class GoldenCodex(BaseClient):
    """
    Synchronous Golden Codex API client.

    Example:
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

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.golden-codex.com/v1",
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, base_url, timeout, max_retries)
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        self.jobs = JobsAPI(self)
        self.account = AccountAPI(self)
        self.webhooks = WebhooksAPI(self)

    def __enter__(self) -> "GoldenCodex":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        retry: int = 0,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API."""
        try:
            response = self._client.request(method, path, json=json, params=params)
        except httpx.TimeoutException:
            raise TimeoutError("request", self.timeout)

        if response.is_success:
            return response.json()

        # Handle retryable errors
        if response.status_code in (429, 500, 502, 503) and retry < self.max_retries:
            if response.status_code == 429:
                try:
                    retry_after = response.json().get("error", {}).get("retry_after", 60)
                except Exception:
                    retry_after = 60
                time.sleep(retry_after)
            else:
                time.sleep(1 * (retry + 1))

            return self._request(method, path, json, params, retry + 1)

        self._handle_error(response)
        return {}  # Never reached, but makes type checker happy

    def estimate(
        self,
        operations: Optional[list[Operation]] = None,
        options: Optional[EnhancementOptions] = None,
    ) -> dict[str, Any]:
        """
        Estimate the cost of operations without creating a job.

        Args:
            operations: List of operations to estimate.
            options: Options for each operation.

        Returns:
            Cost estimate with breakdown and balance check.

        Example:
            >>> estimate = gcx.estimate(
            ...     operations=["nova", "flux"],
            ...     options={"nova": {"tier": "full_gcx"}}
            ... )
            >>> print(f"Cost: {estimate['estimated_gcx']} GCX")
        """
        return self._request(
            "POST",
            "/estimate",
            json={
                "operations": operations or ["nova", "flux", "atlas"],
                "options": options or {},
            },
        )


# ============ Async Client ============


class GoldenCodexAsync(BaseClient):
    """
    Asynchronous Golden Codex API client.

    Example:
        >>> async with GoldenCodexAsync(api_key="gcx_live_...") as gcx:
        ...     job = await gcx.jobs.create(
        ...         image_url="https://example.com/artwork.jpg"
        ...     )
        ...     result = await gcx.jobs.wait(job["job_id"])
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.golden-codex.com/v1",
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, base_url, timeout, max_retries)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        self.jobs = AsyncJobsAPI(self)
        self.account = AsyncAccountAPI(self)
        self.webhooks = AsyncWebhooksAPI(self)

    async def __aenter__(self) -> "GoldenCodexAsync":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        retry: int = 0,
    ) -> dict[str, Any]:
        """Make an async HTTP request to the API."""
        import asyncio

        try:
            response = await self._client.request(method, path, json=json, params=params)
        except httpx.TimeoutException:
            raise TimeoutError("request", self.timeout)

        if response.is_success:
            return response.json()

        # Handle retryable errors
        if response.status_code in (429, 500, 502, 503) and retry < self.max_retries:
            if response.status_code == 429:
                try:
                    retry_after = response.json().get("error", {}).get("retry_after", 60)
                except Exception:
                    retry_after = 60
                await asyncio.sleep(retry_after)
            else:
                await asyncio.sleep(1 * (retry + 1))

            return await self._request(method, path, json, params, retry + 1)

        self._handle_error(response)
        return {}

    async def estimate(
        self,
        operations: Optional[list[Operation]] = None,
        options: Optional[EnhancementOptions] = None,
    ) -> dict[str, Any]:
        """Estimate the cost of operations without creating a job."""
        return await self._request(
            "POST",
            "/estimate",
            json={
                "operations": operations or ["nova", "flux", "atlas"],
                "options": options or {},
            },
        )


# ============ Jobs API ============


class JobsAPI:
    """Jobs API for creating and managing enhancement jobs."""

    def __init__(self, client: GoldenCodex):
        self._client = client

    def create(
        self,
        image_url: str,
        operations: Optional[list[Operation]] = None,
        options: Optional[EnhancementOptions] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new enhancement job.

        Args:
            image_url: URL of the image to process. Must be publicly accessible.
            operations: List of operations to perform. Defaults to all.
            options: Options for each operation.
            webhook_url: URL to receive completion notifications.
            metadata: Custom metadata to attach to the job.
            request_id: Unique ID for idempotency.

        Returns:
            Job creation response with job_id and status.

        Example:
            >>> job = gcx.jobs.create(
            ...     image_url="https://example.com/artwork.jpg",
            ...     operations=["nova", "flux", "atlas"],
            ...     options={"nova": {"tier": "full_gcx"}}
            ... )
            >>> print(f"Job ID: {job['job_id']}")
        """
        # Add request ID header if provided
        if request_id:
            # For simplicity, we include it in the body
            # In production, this would be a header
            pass

        return self._client._request(
            "POST",
            "/jobs",
            json={
                "image_url": image_url,
                "operations": operations or ["nova", "flux", "atlas"],
                "options": options or {},
                "webhook_url": webhook_url,
                "metadata": metadata or {},
            },
        )

    def get(self, job_id: str) -> dict[str, Any]:
        """
        Get the status and results of a job.

        Args:
            job_id: The job ID to retrieve.

        Returns:
            Job details including status and results if completed.

        Example:
            >>> job = gcx.jobs.get("job_abc123")
            >>> if job["status"] == "completed":
            ...     print(job["results"]["golden_codex"])
        """
        return self._client._request("GET", f"/jobs/{job_id}")

    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[JobStatus] = None,
    ) -> dict[str, Any]:
        """
        List your jobs with pagination.

        Args:
            limit: Maximum number of jobs to return (1-100).
            offset: Number of jobs to skip for pagination.
            status: Filter by job status.

        Returns:
            List of jobs and pagination info.

        Example:
            >>> result = gcx.jobs.list(limit=10, status="completed")
            >>> for job in result["jobs"]:
            ...     print(job["job_id"], job["status"])
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        return self._client._request("GET", "/jobs", params=params)

    def cancel(self, job_id: str) -> None:
        """
        Cancel a pending job.

        Args:
            job_id: The job ID to cancel.

        Example:
            >>> gcx.jobs.cancel("job_abc123")
        """
        self._client._request("DELETE", f"/jobs/{job_id}")

    def wait(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """
        Wait for a job to complete.

        Args:
            job_id: The job ID to wait for.
            poll_interval: How often to poll in seconds.
            timeout: Maximum time to wait in seconds.
            on_progress: Optional callback for progress updates.

        Returns:
            Completed job with results.

        Raises:
            TimeoutError: If the job doesn't complete in time.
            JobFailedError: If the job fails.

        Example:
            >>> result = gcx.jobs.wait(
            ...     "job_abc123",
            ...     poll_interval=3.0,
            ...     on_progress=lambda j: print(j["status"])
            ... )
            >>> print(result["results"]["urls"]["final"])
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            job = self.get(job_id)

            if on_progress:
                on_progress(job)

            status = job.get("status")

            if status == "completed":
                return job

            if status == "failed":
                error = job.get("error", {})
                raise JobFailedError(
                    job_id,
                    error.get("code", "unknown"),
                    error.get("message", "Job failed"),
                    error.get("stage"),
                )

            if status == "cancelled":
                raise JobFailedError(job_id, "cancelled", "Job was cancelled")

            time.sleep(poll_interval)

        raise TimeoutError(job_id, timeout)

    def create_and_wait(
        self,
        image_url: str,
        operations: Optional[list[Operation]] = None,
        options: Optional[EnhancementOptions] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """
        Create a job and wait for completion in one call.

        Example:
            >>> result = gcx.jobs.create_and_wait(
            ...     image_url="https://example.com/artwork.jpg"
            ... )
            >>> print(result["results"]["golden_codex"])
        """
        job = self.create(image_url, operations, options, webhook_url, metadata)
        return self.wait(job["job_id"], poll_interval, timeout, on_progress)


class AsyncJobsAPI:
    """Async Jobs API for creating and managing enhancement jobs."""

    def __init__(self, client: GoldenCodexAsync):
        self._client = client

    async def create(
        self,
        image_url: str,
        operations: Optional[list[Operation]] = None,
        options: Optional[EnhancementOptions] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new enhancement job."""
        return await self._client._request(
            "POST",
            "/jobs",
            json={
                "image_url": image_url,
                "operations": operations or ["nova", "flux", "atlas"],
                "options": options or {},
                "webhook_url": webhook_url,
                "metadata": metadata or {},
            },
        )

    async def get(self, job_id: str) -> dict[str, Any]:
        """Get the status and results of a job."""
        return await self._client._request("GET", f"/jobs/{job_id}")

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[JobStatus] = None,
    ) -> dict[str, Any]:
        """List your jobs with pagination."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        return await self._client._request("GET", "/jobs", params=params)

    async def cancel(self, job_id: str) -> None:
        """Cancel a pending job."""
        await self._client._request("DELETE", f"/jobs/{job_id}")

    async def wait(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """Wait for a job to complete."""
        import asyncio

        start_time = time.time()

        while time.time() - start_time < timeout:
            job = await self.get(job_id)

            if on_progress:
                on_progress(job)

            status = job.get("status")

            if status == "completed":
                return job

            if status == "failed":
                error = job.get("error", {})
                raise JobFailedError(
                    job_id,
                    error.get("code", "unknown"),
                    error.get("message", "Job failed"),
                    error.get("stage"),
                )

            if status == "cancelled":
                raise JobFailedError(job_id, "cancelled", "Job was cancelled")

            await asyncio.sleep(poll_interval)

        raise TimeoutError(job_id, timeout)

    async def create_and_wait(
        self,
        image_url: str,
        operations: Optional[list[Operation]] = None,
        options: Optional[EnhancementOptions] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """Create a job and wait for completion in one call."""
        job = await self.create(image_url, operations, options, webhook_url, metadata)
        return await self.wait(job["job_id"], poll_interval, timeout, on_progress)


# ============ Account API ============


class AccountAPI:
    """Account API for retrieving account information."""

    def __init__(self, client: GoldenCodex):
        self._client = client

    def get(self) -> dict[str, Any]:
        """
        Get current account information.

        Returns:
            Account details including balance and rate limits.

        Example:
            >>> account = gcx.account.get()
            >>> print(f"Balance: {account['balance']['gcx']} GCX")
        """
        return self._client._request("GET", "/account")

    def usage(self) -> dict[str, Any]:
        """
        Get usage statistics for the last 30 days.

        Returns:
            Usage stats including jobs created and GCX spent.
        """
        return self._client._request("GET", "/account/usage")


class AsyncAccountAPI:
    """Async Account API."""

    def __init__(self, client: GoldenCodexAsync):
        self._client = client

    async def get(self) -> dict[str, Any]:
        """Get current account information."""
        return await self._client._request("GET", "/account")

    async def usage(self) -> dict[str, Any]:
        """Get usage statistics for the last 30 days."""
        return await self._client._request("GET", "/account/usage")


# ============ Webhooks API ============


class WebhooksAPI:
    """Webhooks API for managing webhook subscriptions."""

    def __init__(self, client: GoldenCodex):
        self._client = client

    def create(
        self,
        url: str,
        events: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Create a new webhook subscription.

        Args:
            url: HTTPS URL to receive webhook notifications.
            events: Events to subscribe to. Defaults to completed and failed.

        Returns:
            Webhook details including the signing secret (only shown once!).

        Example:
            >>> webhook = gcx.webhooks.create(
            ...     url="https://your-app.com/gcx-webhook",
            ...     events=["job.completed", "job.failed"]
            ... )
            >>> print(f"Secret: {webhook['secret']}")  # Save this!
        """
        return self._client._request(
            "POST",
            "/webhooks",
            json={
                "url": url,
                "events": events or ["job.completed", "job.failed"],
            },
        )

    def get(self, webhook_id: str) -> dict[str, Any]:
        """Get a webhook by ID."""
        return self._client._request("GET", f"/webhooks/{webhook_id}")

    def list(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List all webhooks."""
        return self._client._request(
            "GET",
            "/webhooks",
            params={"limit": limit, "offset": offset},
        )

    def update(
        self,
        webhook_id: str,
        events: Optional[list[str]] = None,
        active: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update a webhook."""
        data: dict[str, Any] = {}
        if events is not None:
            data["events"] = events
        if active is not None:
            data["active"] = active

        return self._client._request("PATCH", f"/webhooks/{webhook_id}", json=data)

    def delete(self, webhook_id: str) -> None:
        """Delete a webhook."""
        self._client._request("DELETE", f"/webhooks/{webhook_id}")

    def rotate_secret(self, webhook_id: str) -> dict[str, Any]:
        """Rotate the signing secret for a webhook."""
        return self._client._request("POST", f"/webhooks/{webhook_id}/rotate-secret")


class AsyncWebhooksAPI:
    """Async Webhooks API."""

    def __init__(self, client: GoldenCodexAsync):
        self._client = client

    async def create(
        self,
        url: str,
        events: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new webhook subscription."""
        return await self._client._request(
            "POST",
            "/webhooks",
            json={
                "url": url,
                "events": events or ["job.completed", "job.failed"],
            },
        )

    async def get(self, webhook_id: str) -> dict[str, Any]:
        """Get a webhook by ID."""
        return await self._client._request("GET", f"/webhooks/{webhook_id}")

    async def list(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List all webhooks."""
        return await self._client._request(
            "GET",
            "/webhooks",
            params={"limit": limit, "offset": offset},
        )

    async def update(
        self,
        webhook_id: str,
        events: Optional[list[str]] = None,
        active: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update a webhook."""
        data: dict[str, Any] = {}
        if events is not None:
            data["events"] = events
        if active is not None:
            data["active"] = active

        return await self._client._request("PATCH", f"/webhooks/{webhook_id}", json=data)

    async def delete(self, webhook_id: str) -> None:
        """Delete a webhook."""
        await self._client._request("DELETE", f"/webhooks/{webhook_id}")

    async def rotate_secret(self, webhook_id: str) -> dict[str, Any]:
        """Rotate the signing secret for a webhook."""
        return await self._client._request("POST", f"/webhooks/{webhook_id}/rotate-secret")
