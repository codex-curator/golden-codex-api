/**
 * Golden Codex SDK for Node.js
 *
 * AI-powered image enrichment and provenance tracking
 *
 * @example
 * ```typescript
 * import { GoldenCodex } from '@golden-codex/sdk';
 *
 * const gcx = new GoldenCodex({ apiKey: 'gcx_live_...' });
 *
 * const job = await gcx.jobs.create({
 *   imageUrl: 'https://example.com/image.jpg',
 *   operations: ['nova', 'flux', 'atlas']
 * });
 *
 * const result = await gcx.jobs.wait(job.jobId);
 * console.log(result.results.goldenCodex);
 * ```
 *
 * @packageDocumentation
 */

export { GoldenCodex } from './client';
export type { GoldenCodexConfig } from './client';

export { JobsAPI } from './resources/jobs';
export type {
  Job,
  JobStatus,
  CreateJobOptions,
  CreateJobResponse,
  ListJobsOptions,
  ListJobsResponse,
  WaitOptions,
} from './resources/jobs';

export { AccountAPI } from './resources/account';
export type { Account, AccountBalance, RateLimit } from './resources/account';

export { WebhooksAPI } from './resources/webhooks';
export type {
  Webhook,
  CreateWebhookOptions,
  WebhookEvent,
} from './resources/webhooks';

export { GoldenCodexError, APIError, AuthenticationError, RateLimitError, InsufficientCreditsError } from './errors';

export type {
  GoldenCodexMetadata,
  NovaOptions,
  FluxOptions,
  AtlasOptions,
  Operation,
  JobResults,
  JobCost,
  CostEstimate,
} from './types';
