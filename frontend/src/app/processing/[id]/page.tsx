/**
 * @file processing/[id]/page.tsx
 * @purpose Evaluator capture processing status page with simple UI and collapsible details.
 * @stage Frontend Final Polish — Simplified Evaluator UX.
 * @inputs Route param `id` — the capture job identifier (e.g. cap_a1b2c3d4).
 * @outputs Real-time processing status display with automatic redirect on completion.
 * @dependencies next/navigation, ../../../lib/api/captures, ../../../lib/api/schemas.
 */

'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import { getCaptureStatus } from '../../../lib/api/captures';
import { isTerminalStatus, type CaptureStatusResponse } from '../../../lib/api/schemas';

/** Polling interval in milliseconds. */
const POLL_INTERVAL_MS = 3000;

/** Maximum polling retries on network error before showing persistent error. */
const MAX_RETRIES = 5;

/** Evaluator-friendly status labels. */
const STATUS_LABELS: Record<string, string> = {
  UPLOADING: 'Uploading capture…',
  QUEUED: 'Queued for processing…',
  PROCESSING: 'Processing',
  COMPLETE: 'Complete',
  PROVISIONAL: 'Completed with limitations',
  NOT_EVALUABLE: 'Could not produce a reliable plan',
  FAILED: 'Processing failed',
};

export default function ProcessingPage() {
  const router = useRouter();
  const params = useParams();
  const captureId = typeof params.id === 'string' ? params.id : '';

  const [status, setStatus] = useState<CaptureStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [showDetails, setShowDetails] = useState(false);
  const retriesRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollStatus = useCallback(async () => {
    try {
      const result = await getCaptureStatus(captureId);
      setStatus(result);
      setError(null);
      retriesRef.current = 0;

      // Redirect on success statuses
      if (result.status === 'COMPLETE' || result.status === 'PROVISIONAL') {
        setTimeout(() => {
          router.push(`/property/${captureId}`);
        }, 1500);
      }

      // Stop polling on terminal status
      if (isTerminalStatus(result.status)) {
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      }
    } catch (err) {
      retriesRef.current++;
      if (retriesRef.current >= MAX_RETRIES) {
        setError(
          err instanceof Error ? err.message : 'Lost connection to the backend service.'
        );
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      }
    }
  }, [captureId, router]);

  // Start polling and elapsed timer
  useEffect(() => {
    if (!captureId) return;

    let mounted = true;
    const initialPoll = async () => {
      if (mounted) {
        await pollStatus();
      }
    };
    void initialPoll();

    // Polling interval
    timerRef.current = setInterval(pollStatus, POLL_INTERVAL_MS);

    // Elapsed time counter
    const startTime = Date.now();
    elapsedRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => {
      mounted = false;
      if (timerRef.current) clearInterval(timerRef.current);
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [captureId, pollStatus]);

  const formatElapsed = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const isTerminal = status ? isTerminalStatus(status.status) : false;
  const isSuccess = status?.status === 'COMPLETE' || status?.status === 'PROVISIONAL';
  const isFailed = status?.status === 'FAILED' || status?.status === 'NOT_EVALUABLE';

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--background)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top Header */}
      <header
        style={{
          height: 'var(--topbar-height)',
          backgroundColor: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 32px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            href="/"
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              textDecoration: 'none',
            }}
          >
            ← Back to Workspaces
          </Link>
          <span style={{ color: 'var(--border-strong)' }}>/</span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Processing
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main
        style={{
          maxWidth: '560px',
          width: '100%',
          margin: '60px auto',
          padding: '0 24px',
          textAlign: 'center',
        }}
      >
        {/* Status Icon */}
        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: isSuccess
              ? 'var(--success-subtle, #f0fdf4)'
              : isFailed
              ? 'var(--danger-subtle, #fef2f2)'
              : 'var(--surface-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px auto',
          }}
        >
          {isSuccess ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : isFailed ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--danger-text, #dc2626)" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          ) : (
            <div
              style={{
                width: '28px',
                height: '28px',
                border: '3px solid var(--border)',
                borderTopColor: 'var(--primary)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
          )}
        </div>

        {/* Heading & Subtitle */}
        <h1
          style={{
            fontSize: '22px',
            fontWeight: 700,
            color: 'var(--text-primary)',
            marginBottom: '6px',
            letterSpacing: '-0.01em',
          }}
        >
          {isSuccess
            ? 'Reconstruction Complete'
            : isFailed
            ? STATUS_LABELS[status?.status || 'FAILED'] || 'Processing Failed'
            : 'Processing your capture'}
        </h1>

        <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.5 }}>
          {!isTerminal
            ? 'This may take a few minutes. You can leave this page open while COZMO reconstructs the property.'
            : isSuccess
            ? 'Redirecting to your property plan…'
            : 'COZMO could not complete the reconstruction.'}
        </p>

        {/* Error Detail */}
        {status?.error && isFailed && (
          <div
            role="alert"
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--danger-subtle, #fef2f2)',
              border: '1px solid var(--danger-border, #fecaca)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--danger-text, #dc2626)',
              fontSize: '13px',
              lineHeight: 1.5,
              textAlign: 'left',
              marginBottom: '16px',
              maxHeight: '120px',
              overflow: 'auto',
            }}
          >
            {status.error}
          </div>
        )}

        {/* Connection Error */}
        {error && (
          <div
            role="alert"
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--warning-subtle, #fffbeb)',
              border: '1px solid var(--warning-border, #fed7aa)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--warning-text, #d97706)',
              fontSize: '13px',
              lineHeight: 1.5,
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        {/* Collapsible Capture Details Accordion */}
        <div
          style={{
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            marginTop: '20px',
            textAlign: 'left',
            overflow: 'hidden',
          }}
        >
          <button
            onClick={() => setShowDetails((prev) => !prev)}
            id="toggle-capture-details-btn"
            style={{
              width: '100%',
              padding: '12px 16px',
              backgroundColor: 'transparent',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--text-secondary)',
            }}
          >
            <span>Capture details</span>
            <span style={{ transform: showDetails ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}>
              ▾
            </span>
          </button>

          {showDetails && (
            <div
              style={{
                padding: '12px 16px',
                borderTop: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--surface-subtle)',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                fontSize: '12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Capture ID</span>
                <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                  {captureId}
                </span>
              </div>
              {status?.tier && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Sensor Tier</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500, textTransform: 'uppercase' }}>
                    {status.tier}
                  </span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Elapsed Time</span>
                <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                  {formatElapsed(elapsed)}
                </span>
              </div>
              {status?.progress_stage && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Stage</span>
                  <span style={{ color: 'var(--text-primary)' }}>{status.progress_stage}</span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Status</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                  {status ? (STATUS_LABELS[status.status] || status.status) : 'Connecting…'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
          {isFailed && (
            <Link
              href="/new"
              style={{
                padding: '8px 18px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--primary)',
                color: 'var(--text-on-primary)',
                fontSize: '13px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Try Another Capture
            </Link>
          )}
          {isSuccess && (
            <Link
              href={`/property/${captureId}`}
              style={{
                padding: '8px 18px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--primary)',
                color: 'var(--text-on-primary)',
                fontSize: '13px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              View Property Plan →
            </Link>
          )}
        </div>
      </main>

      {/* Spinner animation */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
