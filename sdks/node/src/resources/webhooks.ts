/**
 * Webhooks API resource
 */

import type { GoldenCodex } from '../client';
import type { Pagination } from '../types';

/**
 * Webhook event types
 */
export type WebhookEvent = 'job.completed' | 'job.failed' | 'job.cancelled';

/**
 * A registered webhook
 */
export interface Webhook {
  /** Unique webhook identifier */
  webhookId: string;

  /** Webhook URL */
  url: string;

  /** Events this webhook receives */
  events: WebhookEvent[];

  /** Whether the webhook is active */
  active: boolean;

  /** When the webhook was created */
  createdAt: string;

  /** When the webhook last succeeded */
  lastSuccessAt?: string;

  /** Number of consecutive failures */
  consecutiveFailures: number;
}

/**
 * Options for creating a webhook
 */
export interface CreateWebhookOptions {
  /**
   * URL to receive webhook notifications
   * Must be HTTPS
   */
  url: string;

  /**
   * Events to subscribe to
   * @default ['job.completed', 'job.failed']
   */
  events?: WebhookEvent[];
}

/**
 * Response from creating a webhook
 */
export interface CreateWebhookResponse {
  /** Unique webhook identifier */
  webhookId: string;

  /** Webhook URL */
  url: string;

  /** Events subscribed to */
  events: WebhookEvent[];

  /**
   * Signing secret for verifying webhook payloads
   * This is only returned once at creation time!
   */
  secret: string;

  /** When the webhook was created */
  createdAt: string;
}

/**
 * Options for listing webhooks
 */
export interface ListWebhooksOptions {
  /** Maximum number to return */
  limit?: number;

  /** Offset for pagination */
  offset?: number;
}

/**
 * Response from listing webhooks
 */
export interface ListWebhooksResponse {
  /** List of webhooks */
  webhooks: Webhook[];

  /** Pagination info */
  pagination: Pagination;
}

/**
 * Webhooks API for managing webhook subscriptions
 */
export class WebhooksAPI {
  constructor(private readonly client: GoldenCodex) {}

  /**
   * Create a new webhook subscription
   *
   * @example
   * ```typescript
   * const webhook = await gcx.webhooks.create({
   *   url: 'https://your-app.com/gcx-webhook',
   *   events: ['job.completed', 'job.failed']
   * });
   *
   * // IMPORTANT: Save this secret! It's only shown once.
   * console.log('Webhook secret:', webhook.secret);
   * ```
   */
  async create(options: CreateWebhookOptions): Promise<CreateWebhookResponse> {
    const response = await this.client.request<RawCreateWebhookResponse>('POST', '/webhooks', {
      url: options.url,
      events: options.events ?? ['job.completed', 'job.failed'],
    });

    return {
      webhookId: response.data.webhook_id,
      url: response.data.url,
      events: response.data.events,
      secret: response.data.secret,
      createdAt: response.data.created_at,
    };
  }

  /**
   * Get a webhook by ID
   *
   * @example
   * ```typescript
   * const webhook = await gcx.webhooks.get('wh_abc123');
   * console.log(`Status: ${webhook.active ? 'active' : 'disabled'}`);
   * ```
   */
  async get(webhookId: string): Promise<Webhook> {
    const response = await this.client.request<RawWebhook>('GET', `/webhooks/${webhookId}`);
    return this.transformWebhook(response.data);
  }

  /**
   * List all webhooks
   *
   * @example
   * ```typescript
   * const { webhooks } = await gcx.webhooks.list();
   * webhooks.forEach(wh => console.log(`${wh.url}: ${wh.active}`));
   * ```
   */
  async list(options: ListWebhooksOptions = {}): Promise<ListWebhooksResponse> {
    const params = new URLSearchParams();
    if (options.limit) params.set('limit', String(options.limit));
    if (options.offset) params.set('offset', String(options.offset));

    const queryString = params.toString();
    const path = queryString ? `/webhooks?${queryString}` : '/webhooks';

    const response = await this.client.request<RawListResponse>('GET', path);

    return {
      webhooks: response.data.webhooks.map(w => this.transformWebhook(w)),
      pagination: {
        total: response.data.pagination.total,
        limit: response.data.pagination.limit,
        offset: response.data.pagination.offset,
        hasMore: response.data.pagination.offset + response.data.pagination.limit < response.data.pagination.total,
      },
    };
  }

  /**
   * Update a webhook
   *
   * @example
   * ```typescript
   * await gcx.webhooks.update('wh_abc123', {
   *   events: ['job.completed', 'job.failed', 'job.cancelled'],
   *   active: true
   * });
   * ```
   */
  async update(webhookId: string, options: {
    events?: WebhookEvent[];
    active?: boolean;
  }): Promise<Webhook> {
    const response = await this.client.request<RawWebhook>('PATCH', `/webhooks/${webhookId}`, options);
    return this.transformWebhook(response.data);
  }

  /**
   * Delete a webhook
   *
   * @example
   * ```typescript
   * await gcx.webhooks.delete('wh_abc123');
   * ```
   */
  async delete(webhookId: string): Promise<void> {
    await this.client.request('DELETE', `/webhooks/${webhookId}`);
  }

  /**
   * Rotate the signing secret for a webhook
   *
   * @example
   * ```typescript
   * const { secret } = await gcx.webhooks.rotateSecret('wh_abc123');
   * // Update your application with the new secret
   * console.log('New secret:', secret);
   * ```
   */
  async rotateSecret(webhookId: string): Promise<{ secret: string }> {
    const response = await this.client.request<{ secret: string }>('POST', `/webhooks/${webhookId}/rotate-secret`);
    return response.data;
  }

  private transformWebhook(raw: RawWebhook): Webhook {
    return {
      webhookId: raw.webhook_id,
      url: raw.url,
      events: raw.events,
      active: raw.active,
      createdAt: raw.created_at,
      lastSuccessAt: raw.last_success_at,
      consecutiveFailures: raw.consecutive_failures ?? 0,
    };
  }
}

// ============ Webhook Verification Utilities ============

export interface WebhookVerificationOptions {
  /** The raw request body as a string */
  payload: string;

  /** The X-GCX-Signature header value */
  signature: string;

  /** Your webhook signing secret */
  secret: string;

  /**
   * Maximum age of the webhook in seconds (for replay protection)
   * @default 300 (5 minutes)
   */
  maxAge?: number;
}

/**
 * Verify a webhook signature
 *
 * @example
 * ```typescript
 * import { verifyWebhookSignature } from '@golden-codex/sdk';
 *
 * app.post('/webhook', (req, res) => {
 *   const isValid = verifyWebhookSignature({
 *     payload: req.rawBody,
 *     signature: req.headers['x-gcx-signature'],
 *     secret: process.env.WEBHOOK_SECRET
 *   });
 *
 *   if (!isValid) {
 *     return res.status(401).send('Invalid signature');
 *   }
 *
 *   // Process the webhook...
 * });
 * ```
 */
export function verifyWebhookSignature(options: WebhookVerificationOptions): boolean {
  const { payload, signature, secret, maxAge = 300 } = options;

  // Parse signature header: t=timestamp,v1=hash
  const parts = signature.split(',').reduce((acc, part) => {
    const [key, value] = part.split('=');
    acc[key] = value;
    return acc;
  }, {} as Record<string, string>);

  const timestamp = parseInt(parts.t, 10);
  const hash = parts.v1;

  if (!timestamp || !hash) {
    return false;
  }

  // Check timestamp is within allowed window
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - timestamp) > maxAge) {
    return false;
  }

  // Compute expected signature
  const crypto = require('crypto');
  const expectedHash = crypto
    .createHmac('sha256', secret)
    .update(`${timestamp}.${payload}`)
    .digest('hex');

  // Constant-time comparison
  return crypto.timingSafeEqual(
    Buffer.from(hash),
    Buffer.from(expectedHash)
  );
}

// ============ Raw API Types ============

interface RawWebhook {
  webhook_id: string;
  url: string;
  events: WebhookEvent[];
  active: boolean;
  created_at: string;
  last_success_at?: string;
  consecutive_failures?: number;
}

interface RawCreateWebhookResponse {
  webhook_id: string;
  url: string;
  events: WebhookEvent[];
  secret: string;
  created_at: string;
}

interface RawListResponse {
  webhooks: RawWebhook[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
  };
}
