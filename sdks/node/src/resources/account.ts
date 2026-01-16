/**
 * Account API resource
 */

import type { GoldenCodex } from '../client';

/**
 * Account balance information
 */
export interface AccountBalance {
  /** Current AET balance */
  aet: number;

  /** Storage used in bytes */
  storageUsedBytes: number;

  /** Storage limit in bytes */
  storageLimitBytes: number;
}

/**
 * Rate limit information
 */
export interface RateLimit {
  /** Maximum requests per minute */
  requestsPerMinute: number;

  /** Maximum concurrent jobs */
  concurrentJobs: number;
}

/**
 * Account information
 */
export interface Account {
  /** User ID */
  userId: string;

  /** Email address */
  email: string;

  /** Subscription tier */
  tier: 'FREE_TRIAL' | 'CURATOR' | 'STUDIO' | 'GALLERY';

  /** Balance information */
  balance: AccountBalance;

  /** Rate limit information */
  rateLimit: RateLimit;
}

/**
 * Usage statistics for a time period
 */
export interface UsageStats {
  /** Start of the period */
  periodStart: string;

  /** End of the period */
  periodEnd: string;

  /** Total jobs created */
  jobsCreated: number;

  /** Jobs by status */
  jobsByStatus: {
    completed: number;
    failed: number;
    cancelled: number;
  };

  /** Total AET spent */
  aetSpent: number;

  /** AET spent by operation */
  aetByOperation: {
    nova: number;
    flux: number;
    atlas: number;
  };
}

/**
 * Account API for retrieving account information and usage
 */
export class AccountAPI {
  constructor(private readonly client: GoldenCodex) {}

  /**
   * Get current account information
   *
   * @example
   * ```typescript
   * const account = await gcx.account.get();
   *
   * console.log(`Balance: ${account.balance.aet} AET`);
   * console.log(`Tier: ${account.tier}`);
   * console.log(`Rate limit: ${account.rateLimit.requestsPerMinute} req/min`);
   * ```
   */
  async get(): Promise<Account> {
    const response = await this.client.request<RawAccount>('GET', '/account');
    return this.transformAccount(response.data);
  }

  /**
   * Get usage statistics for the last 30 days
   *
   * @example
   * ```typescript
   * const usage = await gcx.account.usage();
   *
   * console.log(`Jobs created: ${usage.jobsCreated}`);
   * console.log(`AET spent: ${usage.aetSpent}`);
   * ```
   */
  async usage(): Promise<UsageStats> {
    const response = await this.client.request<RawUsageStats>('GET', '/account/usage');
    return this.transformUsage(response.data);
  }

  private transformAccount(raw: RawAccount): Account {
    return {
      userId: raw.user_id,
      email: raw.email,
      tier: raw.tier,
      balance: {
        aet: raw.balance.aet,
        storageUsedBytes: raw.balance.storage_used_bytes,
        storageLimitBytes: raw.balance.storage_limit_bytes,
      },
      rateLimit: {
        requestsPerMinute: raw.rate_limit.requests_per_minute,
        concurrentJobs: raw.rate_limit.concurrent_jobs ?? 10,
      },
    };
  }

  private transformUsage(raw: RawUsageStats): UsageStats {
    return {
      periodStart: raw.period_start,
      periodEnd: raw.period_end,
      jobsCreated: raw.jobs_created,
      jobsByStatus: raw.jobs_by_status,
      aetSpent: raw.aet_spent,
      aetByOperation: raw.aet_by_operation,
    };
  }
}

// ============ Raw API Types ============

interface RawAccount {
  user_id: string;
  email: string;
  tier: 'FREE_TRIAL' | 'CURATOR' | 'STUDIO' | 'GALLERY';
  balance: {
    aet: number;
    storage_used_bytes: number;
    storage_limit_bytes: number;
  };
  rate_limit: {
    requests_per_minute: number;
    concurrent_jobs?: number;
  };
}

interface RawUsageStats {
  period_start: string;
  period_end: string;
  jobs_created: number;
  jobs_by_status: {
    completed: number;
    failed: number;
    cancelled: number;
  };
  aet_spent: number;
  aet_by_operation: {
    nova: number;
    flux: number;
    atlas: number;
  };
}
