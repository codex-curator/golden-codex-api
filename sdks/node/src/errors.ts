/**
 * Custom error classes for the Golden Codex SDK
 */

import type { ErrorDetails } from './types';

/**
 * Base error class for all Golden Codex errors
 */
export class GoldenCodexError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'GoldenCodexError';
    Object.setPrototypeOf(this, GoldenCodexError.prototype);
  }
}

/**
 * Error thrown when an API request fails
 */
export class APIError extends GoldenCodexError {
  /** HTTP status code */
  public readonly status: number;

  /** Error code from the API */
  public readonly code: string;

  /** Full error details */
  public readonly details: ErrorDetails;

  constructor(status: number, details: ErrorDetails) {
    super(details.message);
    this.name = 'APIError';
    this.status = status;
    this.code = details.code;
    this.details = details;
    Object.setPrototypeOf(this, APIError.prototype);
  }
}

/**
 * Error thrown when authentication fails (401)
 */
export class AuthenticationError extends APIError {
  constructor(details: ErrorDetails) {
    super(401, details);
    this.name = 'AuthenticationError';
    Object.setPrototypeOf(this, AuthenticationError.prototype);
  }
}

/**
 * Error thrown when the account has insufficient credits (402)
 */
export class InsufficientCreditsError extends APIError {
  /** Current account balance in GCX */
  public readonly balance: number;

  /** Required balance for the operation */
  public readonly required: number;

  constructor(details: ErrorDetails) {
    super(402, details);
    this.name = 'InsufficientCreditsError';
    this.balance = details.balance ?? 0;
    this.required = details.required ?? 0;
    Object.setPrototypeOf(this, InsufficientCreditsError.prototype);
  }
}

/**
 * Error thrown when rate limited (429)
 */
export class RateLimitError extends APIError {
  /** Seconds until the rate limit resets */
  public readonly retryAfter: number;

  constructor(details: ErrorDetails & { retryAfter?: number }) {
    super(429, details);
    this.name = 'RateLimitError';
    this.retryAfter = details.retryAfter ?? 60;
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }
}

/**
 * Error thrown when a resource is not found (404)
 */
export class NotFoundError extends APIError {
  constructor(details: ErrorDetails) {
    super(404, details);
    this.name = 'NotFoundError';
    Object.setPrototypeOf(this, NotFoundError.prototype);
  }
}

/**
 * Error thrown when validation fails (400)
 */
export class ValidationError extends APIError {
  constructor(details: ErrorDetails) {
    super(400, details);
    this.name = 'ValidationError';
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

/**
 * Error thrown when waiting for a job times out
 */
export class TimeoutError extends GoldenCodexError {
  /** The job ID that timed out */
  public readonly jobId: string;

  constructor(jobId: string, timeout: number) {
    super(`Job ${jobId} did not complete within ${timeout}ms`);
    this.name = 'TimeoutError';
    this.jobId = jobId;
    Object.setPrototypeOf(this, TimeoutError.prototype);
  }
}

/**
 * Error thrown when a job fails
 */
export class JobFailedError extends GoldenCodexError {
  /** The job ID that failed */
  public readonly jobId: string;

  /** Error details from the job */
  public readonly details: ErrorDetails;

  constructor(jobId: string, details: ErrorDetails) {
    super(`Job ${jobId} failed: ${details.message}`);
    this.name = 'JobFailedError';
    this.jobId = jobId;
    this.details = details;
    Object.setPrototypeOf(this, JobFailedError.prototype);
  }
}
