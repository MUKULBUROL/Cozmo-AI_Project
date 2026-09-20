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
 * Export formats supported by the Cozmo platform.
 */
export type ExportFormat = 'json' | 'svg' | 'pdf' | 'dxf';

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

/**
 * Get the direct download URL for a capture export deliverable.
 *
 * @param captureId - The capture identifier.
 * @param format - Target format ('json', 'svg', 'pdf', 'dxf').
 * @returns Fully-qualified API URL for downloading the file.
 */
export function getCaptureExportUrl(captureId: string, format: ExportFormat): string {
  const baseUrl =
    (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_BASE_URL) ||
    'http://localhost:8000';
  return `${baseUrl}/api/captures/${encodeURIComponent(captureId)}/exports/${format}`;
}

/**
 * Triggers a browser file download for a capture deliverable.
 *
 * @param captureId - The capture identifier.
 * @param format - Target format ('json', 'svg', 'pdf', 'dxf').
 * @param fallbackProperty - Optional client-side property model if in static preview mode.
 *
 * Debugging clues: Check network tab for GET request to /api/captures/{id}/exports/{format}.
 */
export async function downloadCaptureExport(
  captureId: string,
  format: ExportFormat,
  fallbackProperty?: PropertyViewModel | null,
): Promise<void> {
  const exportUrl = getCaptureExportUrl(captureId, format);
  const defaultFilename = `cozmo_${captureId}_${format === 'pdf' ? 'report' : format === 'json' ? 'property' : 'floorplan'}.${format}`;

  try {
    const response = await fetch(exportUrl);
    if (!response.ok) {
      throw new Error(`Export download failed with status ${response.status}: ${response.statusText}`);
    }

    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;

    // Extract filename from Content-Disposition header if present
    const disposition = response.headers.get('Content-Disposition');
    let filename = defaultFilename;
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) {
        filename = match[1];
      }
    }

    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(blobUrl);
  } catch (err) {
    // If running in dev/static preview and API is offline, generate client-side deliverable
    if (fallbackProperty) {
      _downloadFallbackClientExport(fallbackProperty, format, defaultFilename);
      return;
    }
    throw err;
  }
}

/**
 * Generates client-side export fallback when in static fixture mode without backend.
 */
function _downloadFallbackClientExport(
  property: PropertyViewModel,
  format: ExportFormat,
  filename: string,
): void {
  let blob: Blob;

  if (format === 'json') {
    const jsonStr = JSON.stringify(property, null, 2);
    blob = new Blob([jsonStr], { type: 'application/json' });
  } else if (format === 'svg') {
    const svgStr = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 800" width="1000" height="800" style="background:#0b0f19;font-family:sans-serif;">
  <text x="50" y="50" fill="#ffffff" font-size="18" font-weight="bold">COZMO SPATIAL RECONSTRUCTION</text>
  <text x="50" y="80" fill="#94a3b8" font-size="12">Capture: ${property.captureId} • Property: ${property.name}</text>
  <text x="50" y="110" fill="#f59e0b" font-size="12">Status: ${property.status} • Total Area: ${property.totalFloorArea?.value || 'N/A'} m²</text>
  <text x="50" y="750" fill="#94a3b8" font-size="10">Notice: Physical accuracy has not yet been validated against independent laser/tape ground truth.</text>
</svg>`;
    blob = new Blob([svgStr], { type: 'image/svg+xml' });
  } else if (format === 'dxf') {
    const dxfStr = `  0\nSECTION\n  2\nHEADER\n  9\n$INSUNITS\n 70\n     6\n  0\nENDSEC\n  0\nSECTION\n  2\nENTITIES\n  0\nTEXT\n  8\nTEXT\n 10\n0.0\n 20\n0.0\n 30\n0.0\n 40\n0.25\n  1\nCOZMO ${property.captureId}\n  0\nENDSEC\n  0\nEOF\n`;
    blob = new Blob([dxfStr], { type: 'application/dxf' });
  } else {
    throw new Error('PDF export requires live API connection.');
  }

  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
}
