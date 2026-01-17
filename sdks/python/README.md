# golden-codex

Official Python SDK for the [Golden Codex API](https://golden-codex.com/docs/api) - AI-powered image enrichment and provenance tracking.

## Installation

```bash
pip install golden-codex
```

## Quick Start

```python
from golden_codex import GoldenCodex

gcx = GoldenCodex(api_key="gcx_live_...")

# Create an enhancement job
job = gcx.jobs.create(
    image_url="https://example.com/artwork.jpg",
    operations=["nova", "flux", "atlas"]
)

print(f"Job created: {job['job_id']}")

# Wait for completion
result = gcx.jobs.wait(job["job_id"])

print("Metadata:", result["results"]["golden_codex"])
print("Final image:", result["results"]["urls"]["final"])
```

## Features

- **Sync and async clients** - `GoldenCodex` and `GoldenCodexAsync`
- **Automatic retries** for rate limits and transient errors
- **Webhook signature verification** utilities included
- **Type hints** throughout for excellent IDE support
- **Minimal dependencies** - just `httpx`

## API Reference

### Client Configuration

```python
gcx = GoldenCodex(
    api_key="gcx_live_...",                            # Required
    base_url="https://api.golden-codex.com/v1",        # Optional
    timeout=30.0,                                       # Optional, default 30s
    max_retries=2,                                      # Optional, default 2
)

# Use as context manager to auto-close
with GoldenCodex(api_key="...") as gcx:
    ...
```

### Async Client

```python
from golden_codex import GoldenCodexAsync

async with GoldenCodexAsync(api_key="gcx_live_...") as gcx:
    job = await gcx.jobs.create(
        image_url="https://example.com/artwork.jpg"
    )
    result = await gcx.jobs.wait(job["job_id"])
```

### Jobs

```python
# Create a job
job = gcx.jobs.create(
    image_url="https://example.com/image.jpg",
    operations=["nova", "flux", "atlas"],  # Optional, defaults to all
    options={
        "nova": {"tier": "full_gcx"},      # "standard" or "full_gcx"
        "flux": {"model": "4x"},           # "2x", "4x", "anime", "photo"
        "atlas": {"format": "png"}         # "png", "jpg", "webp"
    },
    webhook_url="https://your-app.com/webhook",  # Optional
    metadata={"order_id": "12345"},              # Optional, returned in results
)

# Get job status
job = gcx.jobs.get("job_abc123")

# List jobs
result = gcx.jobs.list(
    limit=20,
    offset=0,
    status="completed"  # Optional filter
)

# Wait for completion with progress callback
def on_progress(job):
    print(f"Status: {job['status']}")

result = gcx.jobs.wait(
    "job_abc123",
    poll_interval=5.0,   # Poll every 5 seconds
    timeout=300.0,       # Timeout after 5 minutes
    on_progress=on_progress
)

# Create and wait in one call
result = gcx.jobs.create_and_wait(
    image_url="https://example.com/image.jpg"
)

# Cancel a pending job
gcx.jobs.cancel("job_abc123")
```

### Account

```python
# Get account info
account = gcx.account.get()
print(f"Balance: {account['balance']['gcx']} GCX")
print(f"Tier: {account['tier']}")

# Get usage statistics
usage = gcx.account.usage()
print(f"Jobs this month: {usage['jobs_created']}")
```

### Cost Estimation

```python
estimate = gcx.estimate(
    operations=["nova", "flux", "atlas"],
    options={"nova": {"tier": "full_gcx"}}
)

print(f"Cost: {estimate['estimated_gcx']} GCX")
print(f"Sufficient balance: {estimate['sufficient_balance']}")
```

### Webhooks

```python
# Create a webhook
webhook = gcx.webhooks.create(
    url="https://your-app.com/gcx-webhook",
    events=["job.completed", "job.failed"]
)

# IMPORTANT: Save this secret! Only shown once.
print(f"Secret: {webhook['secret']}")

# List webhooks
result = gcx.webhooks.list()

# Update a webhook
gcx.webhooks.update(
    "wh_abc123",
    events=["job.completed"],
    active=True
)

# Rotate secret
new_secret = gcx.webhooks.rotate_secret("wh_abc123")

# Delete a webhook
gcx.webhooks.delete("wh_abc123")
```

### Webhook Verification

```python
from golden_codex import verify_webhook_signature

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    payload = request.get_data(as_text=True)
    signature = request.headers.get("X-GCX-Signature", "")

    if not verify_webhook_signature(
        payload=payload,
        signature=signature,
        secret=WEBHOOK_SECRET,
        max_age=300  # Optional, default 5 minutes
    ):
        return "Invalid signature", 401

    event = request.json

    if event["event"] == "job.completed":
        print(f"Job completed: {event['job_id']}")
        print(f"Results: {event['results']}")
    elif event["event"] == "job.failed":
        print(f"Job failed: {event['error']}")

    return "OK", 200
```

## Error Handling

```python
from golden_codex import (
    GoldenCodexError,
    AuthenticationError,
    InsufficientCreditsError,
    RateLimitError,
    TimeoutError,
    JobFailedError
)

try:
    result = gcx.jobs.create_and_wait(image_url="...")
except AuthenticationError:
    print("Invalid API key")
except InsufficientCreditsError as e:
    print(f"Need {e.required} GCX, have {e.balance}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except TimeoutError as e:
    print(f"Job {e.job_id} timed out")
except JobFailedError as e:
    print(f"Job {e.job_id} failed: {e.error_message}")
except GoldenCodexError as e:
    print(f"API error: {e}")
```

## Batch Processing Example

```python
import asyncio
from golden_codex import GoldenCodexAsync

async def process_batch(image_urls: list[str]):
    async with GoldenCodexAsync(api_key="gcx_live_...") as gcx:
        # Create all jobs
        tasks = [
            gcx.jobs.create(image_url=url)
            for url in image_urls
        ]
        jobs = await asyncio.gather(*tasks)

        # Wait for all jobs
        wait_tasks = [
            gcx.jobs.wait(job["job_id"])
            for job in jobs
        ]
        results = await asyncio.gather(*wait_tasks, return_exceptions=True)

        return results

urls = [
    "https://example.com/art1.jpg",
    "https://example.com/art2.jpg",
    "https://example.com/art3.jpg",
]

results = asyncio.run(process_batch(urls))
for result in results:
    if isinstance(result, Exception):
        print(f"Error: {result}")
    else:
        print(f"Success: {result['job_id']}")
```

## Requirements

- Python 3.9+
- API key from [golden-codex.com](https://golden-codex.com)

## License

MIT
