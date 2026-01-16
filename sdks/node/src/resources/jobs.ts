/**
 * Jobs API resource
 */

import type { GoldenCodex } from '../client';
import { TimeoutError, JobFailedError } from '../errors';
import type {
  Operation,
  NovaOptions,
  FluxOptions,
  AtlasOptions,
  JobResults,
  JobCost,
  ErrorDetails,
  Pagination,
} from '../types';

/**
 * Job status values
 */
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

/**
 * Progress of individual operations within a job
 */
export interface JobProgress {
  nova?: JobStatus;
  flux?: JobStatus;
  atlas?: JobStatus;
}

/**
 * A Golden Codex enhancement job
 */
export interface Job {
  /** Unique job identifier */
  jobId: string;

  /** Current job status */
  status: JobStatus;

  /** Operations requested for this job */
  operations: Operation[];

  /** Progress of individual operations */
  progress?: JobProgress;

  /** Results (available when status is 'completed') */
  results?: JobResults;

  /** Error details (available when status is 'failed') */
  error?: ErrorDetails;

  /** Cost information */
  cost: JobCost;

  /** Custom metadata passed when creating the job */
  clientMetadata?: Record<string, unknown>;

  /** When the job was created */
  createdAt: string;

  /** When the job started processing */
  startedAt?: string;

  /** When the job completed */
  completedAt?: string;
}

/**
 * Options for creating a new job
 */
export interface CreateJobOptions {
  /**
   * URL of the image to process
   * Must be publicly accessible or a signed URL
   */
  imageUrl: string;

  /**
   * Operations to perform on the image
   * @default ['nova', 'flux', 'atlas']
   */
  operations?: Operation[];

  /**
   * Options for each operation
   */
  options?: {
    nova?: NovaOptions;
    flux?: FluxOptions;
    atlas?: AtlasOptions;
  };

  /**
   * Webhook URL to receive notifications when the job completes
   */
  webhookUrl?: string;

  /**
   * Custom metadata to attach to the job
   * This data is returned in job responses and webhook payloads
   */
  metadata?: Record<string, unknown>;

  /**
   * Unique request ID for idempotency
   * If a job with this ID already exists, the existing job is returned
   */
  requestId?: string;
}

/**
 * Response from creating a job
 */
export interface CreateJobResponse {
  /** Unique job identifier */
  jobId: string;

  /** Current job status */
  status: JobStatus;

  /** Operations being performed */
  operations: Operation[];

  /** Estimated cost */
  cost: {
    estimatedAet: number;
  };

  /** When the job was created */
  createdAt: string;

  /** Links for following up on the job */
  links: {
    self: string;
    cancel: string;
  };
}

/**
 * Options for listing jobs
 */
export interface ListJobsOptions {
  /** Maximum number of jobs to return (1-100) */
  limit?: number;

  /** Number of jobs to skip (for pagination) */
  offset?: number;

  /** Filter by status */
  status?: JobStatus;
}

/**
 * Response from listing jobs
 */
export interface ListJobsResponse {
  /** List of jobs */
  jobs: Job[];

  /** Pagination information */
  pagination: Pagination;
}

/**
 * Options for waiting on a job
 */
export interface WaitOptions {
  /**
   * How often to poll for status updates (in milliseconds)
   * @default 5000
   */
  pollInterval?: number;

  /**
   * Maximum time to wait (in milliseconds)
   * @default 300000 (5 minutes)
   */
  timeout?: number;

  /**
   * Callback for progress updates
   */
  onProgress?: (job: Job) => void;
}

/**
 * Jobs API for creating and managing enhancement jobs
 */
export class JobsAPI {
  constructor(private readonly client: GoldenCodex) {}

  /**
   * Create a new enhancement job
   *
   * @example
   * ```typescript
   * const job = await gcx.jobs.create({
   *   imageUrl: 'https://example.com/artwork.jpg',
   *   operations: ['nova', 'flux', 'atlas'],
   *   options: {
   *     nova: { tier: 'full_gcx' },
   *     flux: { model: '4x' }
   *   }
   * });
   *
   * console.log(`Job created: ${job.jobId}`);
   * ```
   */
  async create(options: CreateJobOptions): Promise<CreateJobResponse> {
    const headers: Record<string, string> = {};
    if (options.requestId) {
      headers['X-Request-ID'] = options.requestId;
    }

    const response = await this.client.request<RawCreateJobResponse>('POST', '/jobs', {
      image_url: options.imageUrl,
      operations: options.operations ?? ['nova', 'flux', 'atlas'],
      options: options.options ?? {},
      webhook_url: options.webhookUrl,
      metadata: options.metadata ?? {},
    }, { headers });

    return this.transformCreateResponse(response.data);
  }

  /**
   * Get the status and results of a job
   *
   * @example
   * ```typescript
   * const job = await gcx.jobs.get('job_abc123');
   *
   * if (job.status === 'completed') {
   *   console.log('Metadata:', job.results.goldenCodex);
   *   console.log('Final image:', job.results.urls.final);
   * }
   * ```
   */
  async get(jobId: string): Promise<Job> {
    const response = await this.client.request<RawJob>('GET', `/jobs/${jobId}`);
    return this.transformJob(response.data);
  }

  /**
   * List your jobs with pagination
   *
   * @example
   * ```typescript
   * const { jobs, pagination } = await gcx.jobs.list({
   *   limit: 20,
   *   status: 'completed'
   * });
   *
   * console.log(`Found ${pagination.total} total jobs`);
   * ```
   */
  async list(options: ListJobsOptions = {}): Promise<ListJobsResponse> {
    const params = new URLSearchParams();
    if (options.limit) params.set('limit', String(options.limit));
    if (options.offset) params.set('offset', String(options.offset));
    if (options.status) params.set('status', options.status);

    const queryString = params.toString();
    const path = queryString ? `/jobs?${queryString}` : '/jobs';

    const response = await this.client.request<RawListResponse>('GET', path);

    return {
      jobs: response.data.jobs.map(j => this.transformJob(j)),
      pagination: {
        total: response.data.pagination.total,
        limit: response.data.pagination.limit,
        offset: response.data.pagination.offset,
        hasMore: response.data.pagination.offset + response.data.pagination.limit < response.data.pagination.total,
      },
    };
  }

  /**
   * Cancel a pending job
   *
   * @example
   * ```typescript
   * await gcx.jobs.cancel('job_abc123');
   * ```
   */
  async cancel(jobId: string): Promise<void> {
    await this.client.request('DELETE', `/jobs/${jobId}`);
  }

  /**
   * Wait for a job to complete
   *
   * Polls the job status until it reaches a terminal state (completed, failed, or cancelled).
   *
   * @example
   * ```typescript
   * const result = await gcx.jobs.wait('job_abc123', {
   *   pollInterval: 3000,
   *   timeout: 120000,
   *   onProgress: (job) => console.log(`Status: ${job.status}`)
   * });
   *
   * console.log('Final image:', result.results.urls.final);
   * ```
   *
   * @throws {TimeoutError} If the job doesn't complete within the timeout
   * @throws {JobFailedError} If the job fails
   */
  async wait(jobId: string, options: WaitOptions = {}): Promise<Job> {
    const pollInterval = options.pollInterval ?? 5000;
    const timeout = options.timeout ?? 300000;
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const job = await this.get(jobId);

      if (options.onProgress) {
        options.onProgress(job);
      }

      switch (job.status) {
        case 'completed':
          return job;

        case 'failed':
          throw new JobFailedError(jobId, job.error ?? { code: 'unknown', message: 'Job failed' });

        case 'cancelled':
          throw new JobFailedError(jobId, { code: 'cancelled', message: 'Job was cancelled' });

        default:
          // Still processing, wait and poll again
          await this.sleep(pollInterval);
      }
    }

    throw new TimeoutError(jobId, timeout);
  }

  /**
   * Create a job and wait for completion in one call
   *
   * @example
   * ```typescript
   * const result = await gcx.jobs.createAndWait({
   *   imageUrl: 'https://example.com/artwork.jpg'
   * });
   *
   * console.log('Done!', result.results.urls.final);
   * ```
   */
  async createAndWait(
    createOptions: CreateJobOptions,
    waitOptions?: WaitOptions
  ): Promise<Job> {
    const createResponse = await this.create(createOptions);
    return this.wait(createResponse.jobId, waitOptions);
  }

  // ============ Private Helpers ============

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private transformJob(raw: RawJob): Job {
    return {
      jobId: raw.job_id,
      status: raw.status,
      operations: raw.operations,
      progress: raw.progress,
      results: raw.results ? {
        goldenCodex: this.camelCaseKeys(raw.results.golden_codex),
        urls: raw.results.urls,
        artworkId: raw.results.artwork_id,
      } : undefined,
      error: raw.error,
      cost: {
        estimatedAet: raw.cost?.estimated_aet ?? raw.cost?.estimated ?? 0,
        chargedAet: raw.cost?.charged_aet ?? raw.cost?.charged,
        refundedAet: raw.cost?.refunded_aet ?? raw.cost?.refunded,
      },
      clientMetadata: raw.client_metadata,
      createdAt: raw.created_at,
      startedAt: raw.started_at,
      completedAt: raw.completed_at,
    };
  }

  private transformCreateResponse(raw: RawCreateJobResponse): CreateJobResponse {
    return {
      jobId: raw.job_id,
      status: raw.status,
      operations: raw.operations,
      cost: {
        estimatedAet: raw.cost?.estimated_aet ?? raw.cost?.estimated ?? 0,
      },
      createdAt: raw.created_at,
      links: raw.links,
    };
  }

  private camelCaseKeys(obj: Record<string, unknown>): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      result[camelKey] = value && typeof value === 'object' && !Array.isArray(value)
        ? this.camelCaseKeys(value as Record<string, unknown>)
        : value;
    }
    return result;
  }
}

// ============ Raw API Types (snake_case) ============

interface RawJob {
  job_id: string;
  status: JobStatus;
  operations: Operation[];
  progress?: JobProgress;
  results?: {
    golden_codex: Record<string, unknown>;
    urls: {
      original: string;
      upscaled?: string;
      final: string;
    };
    artwork_id?: string;
  };
  error?: ErrorDetails;
  cost?: {
    estimated?: number;
    estimated_aet?: number;
    charged?: number;
    charged_aet?: number;
    refunded?: number;
    refunded_aet?: number;
  };
  client_metadata?: Record<string, unknown>;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface RawCreateJobResponse {
  job_id: string;
  status: JobStatus;
  operations: Operation[];
  cost?: {
    estimated?: number;
    estimated_aet?: number;
  };
  created_at: string;
  links: {
    self: string;
    cancel: string;
  };
}

interface RawListResponse {
  jobs: RawJob[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
  };
}
