/**
 * @file MeasurementStatus.tsx
 * @purpose Subdued, transparent disclosure informing users that physical accuracy is not ground-truth validated.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs customMessage (optional).
 * @outputs Accessible informational banner rendered in inspector and measurement tabs.
 * @dependencies None
 * @assumptions Ground-truth benchmarks have not established cm-level real-world calibration. Transparency is mandatory.
 * @failureModes None (static informational UI).
 * @firstDebuggingPoints Verify component is visible on property inspector and measurement views.
 */

import React from 'react';

interface MeasurementStatusProps {
  customMessage?: string;
}

export function MeasurementStatus({ customMessage }: MeasurementStatusProps) {
  const message =
    customMessage ||
    'Physical accuracy has not yet been validated against independent laser/tape ground truth.';

  return (
    <div
      role="note"
      aria-label="Accuracy disclaimer"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '8px',
        padding: '10px 12px',
        backgroundColor: 'var(--surface-subtle)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        fontSize: '12px',
        lineHeight: 1.45,
        color: 'var(--text-secondary)',
      }}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ flexShrink: 0, marginTop: '2px', color: 'var(--text-muted)' }}
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
      <div>
        <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
          Accuracy Notice
        </div>
        <div>{message}</div>
      </div>
    </div>
  );
}
