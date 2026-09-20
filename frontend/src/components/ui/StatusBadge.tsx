/**
 * @file StatusBadge.tsx
 * @purpose Architectural status indicator badge for COMPLETE, PROVISIONAL, NOT_EVALUABLE, and FAILED states.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs status (ReconstructionStatus), optional size.
 * @outputs Accessible badge with semantic colors and restrained design.
 * @dependencies ../../domain/types
 * @assumptions Avoids loud neon colors or giant pill shapes; adheres to Spatial Pro aesthetic.
 * @failureModes Unrecognized status falls back to neutral styling.
 * @firstDebuggingPoints Check status casing (must be COMPLETE, PROVISIONAL, NOT_EVALUABLE, FAILED).
 */

import React from 'react';
import { ReconstructionStatus } from '../../domain/types';

interface StatusBadgeProps {
  status: ReconstructionStatus;
  size?: 'sm' | 'md';
}

const STATUS_CONFIG: Record<
  ReconstructionStatus,
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  COMPLETE: {
    label: 'Complete',
    bg: 'var(--success-subtle)',
    text: 'var(--success-text)',
    border: 'var(--success-border)',
    dot: 'var(--success)',
  },
  PROVISIONAL: {
    label: 'Provisional',
    bg: 'var(--warning-subtle)',
    text: 'var(--warning-text)',
    border: 'var(--warning-border)',
    dot: 'var(--warning)',
  },
  NOT_EVALUABLE: {
    label: 'Not Evaluable',
    bg: 'var(--neutral-subtle)',
    text: 'var(--neutral-text)',
    border: 'var(--neutral-border)',
    dot: 'var(--text-muted)',
  },
  FAILED: {
    label: 'Failed',
    bg: 'var(--danger-subtle)',
    text: 'var(--danger-text)',
    border: 'var(--danger-border)',
    dot: 'var(--danger)',
  },
};

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.PROVISIONAL;
  const isSmall = size === 'sm';

  return (
    <span
      role="status"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: isSmall ? '2px 8px' : '4px 10px',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: config.bg,
        color: config.text,
        border: `1px solid ${config.border}`,
        fontSize: isSmall ? '12px' : '13px',
        fontWeight: 500,
        letterSpacing: '-0.01em',
        lineHeight: 1.4,
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: config.dot,
        }}
        aria-hidden="true"
      />
      {config.label}
    </span>
  );
}
