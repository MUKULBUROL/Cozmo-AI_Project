/**
 * @file captures.ts
 * @purpose High-level capture API functions consumed by React components.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 * @inputs Tier selection, file reference, capture ID.
 * @outputs Typed capture lifecycle data (creation, status, result).
 * @dependencies ./client, ./schemas, ./errors, ../../domain/adapters.
 * @assumptions API is running at NEXT_PUBLIC_API_BASE_URL. Adapters handle raw → ViewModel conversion.
 * @failureModes API errors bubble as typed exceptions. Malformed responses caught by Zod validation.
 * @firstDebuggingPoints Check browser Network tab for request/response; verify API URL in .env.local.
 */

import { apiGet, apiPost } from './client';
import {
  CaptureCreatedSchema,
  CaptureStatusSchema,
  type CaptureCreated,
  type CaptureStatusResponse,
} from './schemas';
import { ApiValidationError } from './errors';
import { adaptBackendProperty } from '../../domain/adapters';
import type { PropertyViewModel, ReconstructionTier } from '../../domain/types';

/**
 * Accepted file extensions per tier for client-side pre-validation.
 * This mirrors backend validation to fail fast before upload.
 */
const TIER_ACCEPTED_EXTENSIONS: Record<ReconstructionTier, string[]> = {
  lidar: ['.zip'],
  video: ['.mp4', '.mov', '.zip'],
  photo: ['.zip'],
};

/**
 * Upload a new capture file and create a processing job.
 *
 * @param tier - Sensor tier.
 * @param file - The File object to upload.
 * @returns CaptureCreated with job ID and initial status.
 *
 * @throws ApiValidationError if file extension doesn't match tier.
 * @throws ApiConnectionError if API is unreachable.
 * @throws ApiServerError on server-side failures.
 */
export async function createCapture(
  tier: ReconstructionTier,
  file: File,
): Promise<CaptureCreated> {
  // Client-side extension check (fail fast)
  const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '');
  const accepted = TIER_ACCEPTED_EXTENSIONS[tier];
  if (!accepted.includes(ext)) {
    throw new ApiValidationError(
      `${tier.toUpperCase()} tier does not accept ${ext} files. ` +
      `Accepted: ${accepted.join(', ')}.`
    );
  }

  const formData = new FormData();
  formData.append('file', file);
  formData.append('tier', tier);

  const raw = await apiPost<unknown>('/api/captures', formData);
  return CaptureCreatedSchema.parse(raw);
}

/**
 * Poll the current status of a capture processing job.
 *
 * @param captureId - The capture job identifier.
 * @returns Validated CaptureStatusResponse.
 *
 * @throws CaptureNotFoundError if ID doesn't exist.
 * @throws ApiConnectionError on network failure.
 */
export async function getCaptureStatus(
  captureId: string,
): Promise<CaptureStatusResponse> {
  const raw = await apiGet<unknown>(`/api/captures/${encodeURIComponent(captureId)}`);
  return CaptureStatusSchema.parse(raw);
}

/**
 * Fetch the reconstruction result for a completed capture and convert
 * to PropertyViewModel using the existing adapter pipeline.
 *
 * @param captureId - The capture job identifier.
 * @returns PropertyViewModel ready for UI rendering.
 *
 * @throws CaptureNotFoundError if capture doesn't exist.
 * @throws ApiValidationError if processing not yet complete.
 * @throws ApiServerError on result retrieval failures.
 *
 * Debugging clues: Check that adaptBackendProperty handles the raw shape.
 */
export async function getCaptureResult(
  captureId: string,
): Promise<PropertyViewModel> {
  const raw = await apiGet<unknown>(`/api/captures/${encodeURIComponent(captureId)}/result`);
  return adaptBackendProperty(raw);
}

/**
 * Determine the accepted file type filter string for a tier.
 * Used by the file input element's `accept` attribute.
 *
 * @param tier - Sensor tier.
 * @returns Accept string for <input type="file">.
 */
export function getAcceptedFileTypes(tier: ReconstructionTier): string {
  switch (tier) {
    case 'lidar':
      return '.zip';
    case 'video':
      return '.mp4,.mov,.zip';
    case 'photo':
      return '.zip';
  }
}
