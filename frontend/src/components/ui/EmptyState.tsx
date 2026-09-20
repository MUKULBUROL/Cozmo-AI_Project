/**
 * @file EmptyState.tsx
 * @purpose Architectural empty and failure state presentation component.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs title, description, optional reasons array, optional action button.
 * @outputs Accessible empty state card with restrained technical design.
 * @dependencies None
 * @assumptions Displayed when geometry is empty, capture failed, or data is missing.
 * @failureModes None.
 * @firstDebuggingPoints Verify that failure_reasons array is mapped correctly.
 */

import React from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  reasons?: string[];
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  title,
  description,
  reasons,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        textAlign: 'center',
        backgroundColor: 'var(--surface)',
        border: '1px dashed var(--border-strong)',
        borderRadius: 'var(--radius-lg)',
        maxWidth: '520px',
        margin: '40px auto',
      }}
    >
      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          backgroundColor: 'var(--surface-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '16px',
          color: 'var(--text-muted)',
        }}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polygon points="12 2 2 22 22 22 12 2" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </div>

      <h3
        style={{
          fontSize: '15px',
          fontWeight: 600,
          color: 'var(--text-primary)',
          marginBottom: '6px',
        }}
      >
        {title}
      </h3>

      <p
        style={{
          fontSize: '13px',
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
          marginBottom: reasons && reasons.length > 0 ? '16px' : '0',
        }}
      >
        {description}
      </p>

      {reasons && reasons.length > 0 && (
        <div
          style={{
            width: '100%',
            textAlign: 'left',
            backgroundColor: 'var(--surface-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 16px',
            marginBottom: '16px',
            border: '1px solid var(--border)',
          }}
        >
          <div
            style={{
              fontSize: '11px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--text-muted)',
              marginBottom: '6px',
            }}
          >
            Backend Diagnostic Reasons
          </div>
          <ul
            style={{
              paddingLeft: '16px',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
            }}
          >
            {reasons.map((reason, idx) => (
              <li key={idx} className="mono">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            padding: '8px 16px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--primary)',
            color: 'var(--text-on-primary)',
            fontSize: '13px',
            fontWeight: 500,
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
