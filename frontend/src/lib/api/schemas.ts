/**
 * @file schemas.ts
 * @purpose Zod runtime validation schemas for API response payloads.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 * @inputs Raw JSON responses from FastAPI capture endpoints.
 * @outputs Validated, typed response data or clear parse error diagnostics.
 * @dependencies zod.
 * @assumptions API response shapes match the schemas defined in backend/app/api/captures.py.
 * @failureModes ZodError thrown on schema mismatch with path breakdown.
 * @firstDebuggingPoints Compare raw API JSON against schema fields below.
 */

import { z } from 'zod';

/**
 * Schema for POST /api/captures response.
 */
export const CaptureCreatedSchema = z.object({
  id: z.string(),
  tier: z.enum(['lidar', 'video', 'photo']),
  status: z.string(),
});

export type CaptureCreated = z.infer<typeof CaptureCreatedSchema>;

/**
 * Schema for GET /api/captures/{id} response (status polling).
 */
export const CaptureStatusSchema = z.object({
  id: z.string(),
  tier: z.enum(['lidar', 'video', 'photo']),
  status: z.enum([
    'UPLOADING', 'QUEUED', 'PROCESSING',
    'COMPLETE', 'PROVISIONAL', 'NOT_EVALUABLE', 'FAILED',
  ]),
  created_at: z.string(),
  progress_stage: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});

export type CaptureStatusResponse = z.infer<typeof CaptureStatusSchema>;

/**
 * Terminal statuses that indicate processing has finished.
 * Frontend polling should stop when status reaches one of these.
 */
export const TERMINAL_STATUSES = new Set([
  'COMPLETE', 'PROVISIONAL', 'NOT_EVALUABLE', 'FAILED',
] as const);

/**
 * Check whether a status string is terminal (polling should stop).
 *
 * @param status - Status string from API.
 * @returns True if terminal.
 */
export function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.has(status as typeof TERMINAL_STATUSES extends Set<infer T> ? T : never);
}
