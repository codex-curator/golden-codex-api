/**
 * Main Golden Codex client
 */

import { JobsAPI } from './resources/jobs';
import { AccountAPI } from './resources/account';
import { WebhooksAPI } from './resources/webhooks';
import {
  APIError,
  AuthenticationError,
  InsufficientCreditsError,
  RateLimitError,
  NotFoundError,
  ValidationError,
} from './errors';
import type { CostEstimate, Operation, NovaOptions, FluxOptions, RateLimitInfo } from './types';

/**
 * Configuration options for the Golden Codex client
 */
export interface GoldenCodexConfig {
  /**
   * Your Golden Codex API key
   * Get one at https://golden-codex.com/dashboard
   */
  apiKey: string;

  /**
   * Base URL for the API
   * @default 'https://api.golden-codex.com/v1'
   */
  baseUrl?: string;

  /**
   * Request timeout in milliseconds
   * @default 30000
   */
  timeout?: number;

  /**
   * Maximum number of retries for failed requests
   * @default 2
   */
  maxRetries?: number;
}

/**
 * HTTP response from the API
 */
interface APIResponse<T = unknown> {
  data: T;
  status: number;
  headers: Headers;
  rateLimit: RateLimitInfo;
}

/**
 * Golden Codex API client
 *
 * @example
 * ```typescript
 * const gcx = new GoldenCodex({
 *   apiKey: process.env.GOLDEN_CODEX_API_KEY
 * });
 *
 * // Create an enhancement job
 * const job = await gcx.jobs.create({
 *   imageUrl: 'https://example.com/artwork.jpg',
 *   operations: ['nova', 'flux', 'atlas']
 * });
 *
 * // Wait for completion
 * const result = await gcx.jobs.wait(job.jobId);
 * console.log(result.results);
 * ```
 */
export class GoldenCodex {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;

  /** Job management API */
  public readonly jobs: JobsAPI;

  /** Account information API */
  public readonly account: AccountAPI;

  /** Webhook management API */
  public readonly webhooks: WebhooksAPI;

  constructor(config: GoldenCodexConfig) {
    if (!config.apiKey) {
      throw new Error('API key is required. Get one at https://golden-codex.com/dashboard');
    }

    if (!config.apiKey.startsWith('gcx_live_') && !config.apiKey.startsWith('gcx_test_')) {
      throw new Error('Invalid API key format. Keys should start with gcx_live_ or gcx_test_');
    }

    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl ?? 'https://api.golden-codex.com/v1';
    this.timeout = config.timeout ?? 30000;
    this.maxRetries = config.maxRetries ?? 2;

    // Initialize resource APIs
    this.jobs = new JobsAPI(this);
    this.account = new AccountAPI(this);
    this.webhooks = new WebhooksAPI(this);
  }

  /**
   * Estimate the cost of operations without creating a job
   *
   * @example
   * ```typescript
   * const estimate = await gcx.estimate({
   *   operations: ['nova', 'flux', 'atlas'],
   *   options: {
   *     nova: { tier: 'full_gcx' },
   *     flux: { model: '4x' }
   *   }
   * });
   *
   * console.log(`Cost: ${estimate.estimatedGcx} GCX`);
   * console.log(`Sufficient balance: ${estimate.sufficientBalance}`);
   * ```
   */
  async estimate(options: {
    operations?: Operation[];
    options?: {
      nova?: NovaOptions;
      flux?: FluxOptions;
    };
  }): Promise<CostEstimate> {
    const response = await this.request<CostEstimate>('POST', '/estimate', {
      operations: options.operations ?? ['nova', 'flux', 'atlas'],
      options: options.options ?? {},
    });

    return response.data;
  }

  /**
   * Make an authenticated request to the API
   * @internal
   */
  async request<T>(
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    path: string,
    body?: unknown,
    options: { headers?: Record<string, string>; retry?: number } = {}
  ): Promise<APIResponse<T>> {
    const url = `${this.baseUrl}${path}`;
    const retry = options.retry ?? 0;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'User-Agent': '@golden-codex/sdk/1.0.0',
          ...options.headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Parse rate limit headers
      const rateLimit: RateLimitInfo = {
        limit: parseInt(response.headers.get('X-RateLimit-Limit') ?? '100', 10),
        remaining: parseInt(response.headers.get('X-RateLimit-Remaining') ?? '100', 10),
        reset: parseInt(response.headers.get('X-RateLimit-Reset') ?? '0', 10),
      };

      // Handle success
      if (response.ok) {
        const data = await response.json() as T;
        return { data, status: response.status, headers: response.headers, rateLimit };
      }

      // Handle errors
      const errorBody = await response.json().catch(() => ({})) as { error?: { code?: string; message?: string; balance?: number; required?: number; retry_after?: number } };
      const errorDetails = {
        code: errorBody.error?.code ?? 'unknown_error',
        message: errorBody.error?.message ?? `Request failed with status ${response.status}`,
        balance: errorBody.error?.balance,
        required: errorBody.error?.required,
        retryAfter: errorBody.error?.retry_after,
      };

      // Handle specific error types
      switch (response.status) {
        case 401:
          throw new AuthenticationError(errorDetails);

        case 402:
          throw new InsufficientCreditsError(errorDetails);

        case 404:
          throw new NotFoundError(errorDetails);

        case 429:
          // Retry rate limited requests
          if (retry < this.maxRetries) {
            const retryAfter = errorDetails.retryAfter ?? 60;
            await this.sleep(retryAfter * 1000);
            return this.request<T>(method, path, body, { ...options, retry: retry + 1 });
          }
          throw new RateLimitError(errorDetails);

        case 400:
          throw new ValidationError(errorDetails);

        case 500:
        case 502:
        case 503:
          // Retry server errors
          if (retry < this.maxRetries) {
            await this.sleep(1000 * (retry + 1));
            return this.request<T>(method, path, body, { ...options, retry: retry + 1 });
          }
          throw new APIError(response.status, errorDetails);

        default:
          throw new APIError(response.status, errorDetails);
      }
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof GoldenCodex) {
        throw error;
      }

      if ((error as Error).name === 'AbortError') {
        throw new Error(`Request timed out after ${this.timeout}ms`);
      }

      throw error;
    }
  }

  /**
   * Sleep for a given number of milliseconds
   * @internal
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
