/**
 * Core type definitions for the Golden Codex SDK
 */

/**
 * Available pipeline operations
 */
export type Operation = 'nova' | 'flux' | 'atlas';

/**
 * Nova AI analysis tier
 * - standard: Basic metadata generation (1 AET)
 * - full_gcx: Museum-grade 50+ field analysis (2 AET)
 */
export type NovaTier = 'standard' | 'full_gcx';

/**
 * Flux upscaling model
 * - 2x: 2x upscale, faster
 * - 4x: 4x upscale, highest quality
 * - anime: Optimized for anime/illustration
 * - photo: Optimized for photography
 */
export type FluxModel = '2x' | '4x' | 'anime' | 'photo';

/**
 * Output format for Atlas metadata infusion
 */
export type AtlasFormat = 'png' | 'jpg' | 'webp';

/**
 * Options for Nova AI metadata generation
 */
export interface NovaOptions {
  /**
   * Analysis tier - standard or full museum-grade
   * @default 'standard'
   */
  tier?: NovaTier;

  /**
   * Language for generated text (ISO 639-1)
   * @default 'en'
   */
  language?: string;
}

/**
 * Options for Flux upscaling
 */
export interface FluxOptions {
  /**
   * Upscaling model to use
   * @default '4x'
   */
  model?: FluxModel;
}

/**
 * Options for Atlas metadata infusion
 */
export interface AtlasOptions {
  /**
   * Output image format
   * @default 'png'
   */
  format?: AtlasFormat;
}

/**
 * Golden Codex metadata structure
 * Contains 50+ fields of AI-generated metadata
 */
export interface GoldenCodexMetadata {
  /** Generated title for the artwork */
  title?: string;

  /** AI interpretation of the artwork's meaning */
  artistInterpretation?: string;

  /** Style classifications (e.g., impressionism, abstract) */
  styleClassification?: string[];

  /** Color analysis data */
  colorAnalysis?: {
    dominant?: string[];
    mood?: string;
    palette?: string[];
  };

  /** Composition analysis */
  composition?: {
    focalPoint?: string;
    balance?: string;
    depth?: string;
    movement?: string;
  };

  /** First-person narrative from the artwork's perspective */
  soulWhisper?: string;

  /** Technical analysis */
  technicalAnalysis?: {
    medium?: string;
    technique?: string[];
    lighting?: string;
  };

  /** Emotional resonance analysis */
  emotionalResonance?: {
    primary?: string;
    secondary?: string[];
    intensity?: number;
  };

  /** Historical and cultural context */
  context?: {
    period?: string;
    movement?: string;
    influences?: string[];
  };

  /** Symbolic elements identified */
  symbolism?: {
    elements?: Array<{
      symbol: string;
      meaning: string;
    }>;
  };

  /** Raw JSON for additional fields */
  [key: string]: unknown;
}

/**
 * URLs to processed images
 */
export interface JobResultUrls {
  /** Original image URL */
  original: string;

  /** Upscaled image URL (if flux operation was run) */
  upscaled?: string;

  /** Final image with embedded metadata */
  final: string;
}

/**
 * Results from a completed job
 */
export interface JobResults {
  /** Generated Golden Codex metadata */
  goldenCodex: GoldenCodexMetadata;

  /** URLs to processed images */
  urls: JobResultUrls;

  /** Assigned artwork ID */
  artworkId?: string;
}

/**
 * Cost breakdown for a job
 */
export interface JobCost {
  /** Estimated cost in AET */
  estimatedAet: number;

  /** Actual charged cost in AET (after completion) */
  chargedAet?: number;

  /** Refunded amount (if job failed) */
  refundedAet?: number;
}

/**
 * Cost estimate response
 */
export interface CostEstimate {
  /** Total estimated cost in AET */
  estimatedAet: number;

  /** Breakdown by operation */
  breakdown: {
    [operation: string]: {
      cost: number;
      tier?: string;
      model?: string;
    };
  };

  /** Current account balance */
  currentBalance: number;

  /** Whether the account has sufficient balance */
  sufficientBalance: boolean;
}

/**
 * Error details from the API
 */
export interface ErrorDetails {
  /** Error code */
  code: string;

  /** Human-readable error message */
  message: string;

  /** Which stage failed (for job errors) */
  stage?: Operation;

  /** Whether the operation can be retried */
  retryable?: boolean;

  /** Current balance (for insufficient credits errors) */
  balance?: number;

  /** Required balance (for insufficient credits errors) */
  required?: number;
}

/**
 * Pagination info
 */
export interface Pagination {
  /** Total number of items */
  total: number;

  /** Items per page */
  limit: number;

  /** Current offset */
  offset: number;

  /** Whether there are more pages */
  hasMore: boolean;
}

/**
 * Rate limit information
 */
export interface RateLimitInfo {
  /** Maximum requests per minute */
  limit: number;

  /** Remaining requests in current window */
  remaining: number;

  /** Unix timestamp when the limit resets */
  reset: number;
}
