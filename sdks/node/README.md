# @golden-codex/sdk

Official Node.js SDK for the [Golden Codex API](https://golden-codex.com/docs/api) - AI-powered image enrichment and provenance tracking.

## Installation

```bash
npm install @golden-codex/sdk
# or
yarn add @golden-codex/sdk
# or
pnpm add @golden-codex/sdk
```

## Quick Start

```typescript
import { GoldenCodex } from '@golden-codex/sdk';

const gcx = new GoldenCodex({
  apiKey: process.env.GOLDEN_CODEX_API_KEY!
});

// Create an enhancement job
const job = await gcx.jobs.create({
  imageUrl: 'https://example.com/artwork.jpg',
  operations: ['nova', 'flux', 'atlas']
});

console.log(`Job created: ${job.jobId}`);

// Wait for completion
const result = await gcx.jobs.wait(job.jobId);

console.log('Metadata:', result.results?.goldenCodex);
console.log('Final image:', result.results?.urls.final);
```

## Features

- **Full TypeScript support** with comprehensive type definitions
- **Automatic retries** for rate limits and transient errors
- **Webhook signature verification** utilities included
- **Promise-based** async API
- **Zero dependencies** (uses native fetch)

## API Reference

### Client Configuration

```typescript
const gcx = new GoldenCodex({
  apiKey: 'gcx_live_...',           // Required
  baseUrl: 'https://api.golden-codex.com/v1',  // Optional
  timeout: 30000,                    // Optional, default 30s
  maxRetries: 2,                     // Optional, default 2
});
```

### Jobs

```typescript
// Create a job
const job = await gcx.jobs.create({
  imageUrl: 'https://example.com/image.jpg',
  operations: ['nova', 'flux', 'atlas'],  // Optional, defaults to all
  options: {
    nova: { tier: 'full_gcx' },  // 'standard' or 'full_gcx'
    flux: { model: '4x' },       // '2x', '4x', 'anime', 'photo'
    atlas: { format: 'png' }     // 'png', 'jpg', 'webp'
  },
  webhookUrl: 'https://your-app.com/webhook',  // Optional
  metadata: { orderId: '12345' },  // Optional, returned in results
  requestId: 'unique-id',          // Optional, for idempotency
});

// Get job status
const job = await gcx.jobs.get('job_abc123');

// List jobs
const { jobs, pagination } = await gcx.jobs.list({
  limit: 20,
  offset: 0,
  status: 'completed'  // Optional filter
});

// Wait for completion
const result = await gcx.jobs.wait('job_abc123', {
  pollInterval: 5000,  // Poll every 5 seconds
  timeout: 300000,     // Timeout after 5 minutes
  onProgress: (job) => console.log(job.status)
});

// Create and wait in one call
const result = await gcx.jobs.createAndWait({
  imageUrl: 'https://example.com/image.jpg'
});

// Cancel a pending job
await gcx.jobs.cancel('job_abc123');
```

### Account

```typescript
// Get account info
const account = await gcx.account.get();
console.log(`Balance: ${account.balance.gcx} GCX`);
console.log(`Tier: ${account.tier}`);

// Get usage statistics
const usage = await gcx.account.usage();
console.log(`Jobs this month: ${usage.jobsCreated}`);
```

### Cost Estimation

```typescript
const estimate = await gcx.estimate({
  operations: ['nova', 'flux', 'atlas'],
  options: {
    nova: { tier: 'full_gcx' }
  }
});

console.log(`Cost: ${estimate.estimatedAet} GCX`);
console.log(`Sufficient balance: ${estimate.sufficientBalance}`);
```

### Webhooks

```typescript
// Create a webhook
const webhook = await gcx.webhooks.create({
  url: 'https://your-app.com/gcx-webhook',
  events: ['job.completed', 'job.failed']
});

// IMPORTANT: Save this secret! Only shown once.
console.log('Secret:', webhook.secret);

// List webhooks
const { webhooks } = await gcx.webhooks.list();

// Update a webhook
await gcx.webhooks.update('wh_abc123', {
  events: ['job.completed'],
  active: true
});

// Rotate secret
const { secret } = await gcx.webhooks.rotateSecret('wh_abc123');

// Delete a webhook
await gcx.webhooks.delete('wh_abc123');
```

### Webhook Verification

```typescript
import { verifyWebhookSignature } from '@golden-codex/sdk';

app.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  const isValid = verifyWebhookSignature({
    payload: req.body.toString(),
    signature: req.headers['x-gcx-signature'] as string,
    secret: process.env.WEBHOOK_SECRET!,
    maxAge: 300  // Optional, default 5 minutes
  });

  if (!isValid) {
    return res.status(401).send('Invalid signature');
  }

  const event = JSON.parse(req.body);

  switch (event.event) {
    case 'job.completed':
      console.log('Job completed:', event.job_id);
      break;
    case 'job.failed':
      console.log('Job failed:', event.error);
      break;
  }

  res.send('OK');
});
```

## Error Handling

```typescript
import {
  GoldenCodexError,
  AuthenticationError,
  InsufficientCreditsError,
  RateLimitError,
  TimeoutError,
  JobFailedError
} from '@golden-codex/sdk';

try {
  const result = await gcx.jobs.createAndWait({ imageUrl: '...' });
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Invalid API key');
  } else if (error instanceof InsufficientCreditsError) {
    console.error(`Need ${error.required} GCX, have ${error.balance}`);
  } else if (error instanceof RateLimitError) {
    console.error(`Rate limited. Retry after ${error.retryAfter}s`);
  } else if (error instanceof TimeoutError) {
    console.error(`Job ${error.jobId} timed out`);
  } else if (error instanceof JobFailedError) {
    console.error(`Job failed: ${error.details.message}`);
  }
}
```

## Requirements

- Node.js 18+
- API key from [golden-codex.com](https://golden-codex.com)

## License

MIT
