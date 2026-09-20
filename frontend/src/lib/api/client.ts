/**
 * @file client.ts
 * @purpose Base HTTP client for communicating with the Cozmo FastAPI backend.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 * @inputs NEXT_PUBLIC_API_BASE_URL environment variable.
 * @outputs Configured fetch wrappers with timeout, error handling, and JSON parsing.
 * @dependencies None (uses native fetch).
 * @assumptions API base URL is set via NEXT_PUBLIC_API_BASE_URL. Defaults to http://localhost:8000.
 * @failureModes Network errors → ApiConnectionError. 4xx/5xx → typed API errors. JSON parse failures → ApiServerError.
 * @firstDebuggingPoints Check NEXT_PUBLIC_API_BASE_URL in .env.local; verify FastAPI is running; check browser Network tab.
 */

import { ApiConnectionError, ApiServerError, ApiValidationError, CaptureNotFoundError } from './errors';

/**
 * Resolved API base URL from environment variable.
 * Falls back to http://localhost:8000 for development.
 */
const API_BASE_URL: string =
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_BASE_URL) || 'http://localhost:8000';

/**
 * Default request timeout in milliseconds.
 * Status checks: 30s.  Uploads: 120s (set per-call).
 */
const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Perform a JSON GET request against the API.
 *
 * @param path - API path (e.g. "/api/captures/cap_abc123").
 * @param timeoutMs - Request timeout in milliseconds.
 * @returns Parsed JSON response.
 *
 * @throws ApiConnectionError on network failure or timeout.
 * @throws CaptureNotFoundError on 404.
 * @throws ApiServerError on 5xx or parse failure.
 * @throws ApiValidationError on 4xx.
 */
export async function apiGet<T = unknown>(path: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: controller.signal,
    });

    clearTimeout(timer);
    return await _handleResponse<T>(response, url);
  } catch (err) {
    if (err instanceof ApiConnectionError || err instanceof ApiServerError ||
        err instanceof ApiValidationError || err instanceof CaptureNotFoundError) {
      throw err;
    }
    throw new ApiConnectionError(
      `Failed to connect to API at ${url}: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
}

/**
 * Perform a multipart POST request to upload a file.
 *
 * @param path - API path (e.g. "/api/captures").
 * @param formData - FormData containing the file and metadata.
 * @param timeoutMs - Request timeout in milliseconds.
 * @returns Parsed JSON response.
 *
 * @throws ApiConnectionError on network failure.
 * @throws ApiValidationError on 422 (validation error).
 * @throws ApiServerError on 5xx.
 */
export async function apiPost<T = unknown>(
  path: string,
  formData: FormData,
  timeoutMs = 120_000,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
      // Do NOT set Content-Type — browser sets multipart boundary automatically.
    });

    clearTimeout(timer);
    return await _handleResponse<T>(response, url);
  } catch (err) {
    if (err instanceof ApiConnectionError || err instanceof ApiServerError ||
        err instanceof ApiValidationError || err instanceof CaptureNotFoundError) {
      throw err;
    }
    throw new ApiConnectionError(
      `Failed to connect to API at ${url}: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
}

/**
 * Check API health / connectivity.
 *
 * @returns True if the API is reachable.
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    await apiGet('/api/health', 5000);
    return true;
  } catch {
    return false;
  }
}

/**
 * Parse response body and convert HTTP errors to typed exceptions.
 *
 * @param response - Fetch Response object.
 * @param url - Request URL for error messages.
 * @returns Parsed JSON body.
 */
async function _handleResponse<T>(response: Response, url: string): Promise<T> {
  if (response.status === 404) {
    const body = await _safeParseJson(response);
    throw new CaptureNotFoundError(
      body?.detail || `Resource not found: ${url}`,
    );
  }

  if (response.status === 422) {
    const body = await _safeParseJson(response);
    throw new ApiValidationError(
      body?.detail || `Validation error at ${url}`,
    );
  }

  if (response.status === 409) {
    const body = await _safeParseJson(response);
    throw new ApiValidationError(
      body?.detail || `Conflict at ${url}`,
    );
  }

  if (response.status >= 500) {
    const body = await _safeParseJson(response);
    throw new ApiServerError(
      body?.detail || `Server error (${response.status}) at ${url}`,
    );
  }

  if (!response.ok) {
    const body = await _safeParseJson(response);
    throw new ApiServerError(
      body?.detail || `Unexpected status ${response.status} at ${url}`,
    );
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiServerError(`Failed to parse JSON response from ${url}`);
  }
}

/**
 * Attempt to parse response body as JSON without throwing.
 */
async function _safeParseJson(response: Response): Promise<{ detail?: string } | null> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object' && 'detail' in data && typeof (data as { detail: unknown }).detail === 'string') {
      return { detail: (data as { detail: string }).detail };
    }
    return (data as { detail?: string }) || null;
  } catch {
    return null;
  }
}
