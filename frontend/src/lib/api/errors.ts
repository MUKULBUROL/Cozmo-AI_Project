/**
 * @file errors.ts
 * @purpose Typed API error classes for structured error handling across the frontend.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 * @inputs Raw network/HTTP errors from fetch calls.
 * @outputs Typed error instances with useful messages for UI display.
 * @dependencies None.
 * @assumptions Errors are caught at the component level and displayed to users.
 * @failureModes N/A — these are error definitions.
 * @firstDebuggingPoints Check the error.message and error.name in catch blocks.
 */

/**
 * Network connectivity failure or timeout.
 *
 * Thrown when the API server is unreachable, the request times out,
 * or DNS resolution fails.
 */
export class ApiConnectionError extends Error {
  readonly name = 'ApiConnectionError' as const;

  constructor(message: string) {
    super(message);
    Object.setPrototypeOf(this, ApiConnectionError.prototype);
  }
}

/**
 * Client-side validation or 422 response from the API.
 *
 * Thrown when the upload format is invalid, a required field is missing,
 * or the API returns HTTP 422.
 */
export class ApiValidationError extends Error {
  readonly name = 'ApiValidationError' as const;

  constructor(message: string) {
    super(message);
    Object.setPrototypeOf(this, ApiValidationError.prototype);
  }
}

/**
 * Server-side error (5xx) or unexpected response format.
 *
 * Thrown when the API returns a 500-level error or the response
 * body cannot be parsed as expected JSON.
 */
export class ApiServerError extends Error {
  readonly name = 'ApiServerError' as const;

  constructor(message: string) {
    super(message);
    Object.setPrototypeOf(this, ApiServerError.prototype);
  }
}

/**
 * Capture not found (404).
 *
 * Thrown when a capture ID does not exist in the job store.
 */
export class CaptureNotFoundError extends Error {
  readonly name = 'CaptureNotFoundError' as const;

  constructor(message: string) {
    super(message);
    Object.setPrototypeOf(this, CaptureNotFoundError.prototype);
  }
}

/**
 * Capture processing failure.
 *
 * Thrown when a capture's reconstruction pipeline fails.
 * Contains the error reason from the backend.
 */
export class CaptureProcessingError extends Error {
  readonly name = 'CaptureProcessingError' as const;

  constructor(message: string) {
    super(message);
    Object.setPrototypeOf(this, CaptureProcessingError.prototype);
  }
}
