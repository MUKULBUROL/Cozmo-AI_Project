/**
 * @file TopBar.tsx
 * @purpose Workspace top navigation bar showing branding, property breadcrumb, tier, and status.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs title (string), tier (ReconstructionTier), status (ReconstructionStatus), captureId (string).
 * @outputs Accessible header bar matching Spatial Pro aesthetic.
 * @dependencies ../../domain/types, ../ui/StatusBadge, ../ui/TierBadge, next/link
 * @assumptions Fixed height (52px), crisp border-bottom.
 * @failureModes None.
 * @firstDebuggingPoints Check property title and badge prop propagation.
 */

import React from 'react';
import Link from 'next/link';
import { ReconstructionTier, ReconstructionStatus } from '../../domain/types';
import { StatusBadge } from '../ui/StatusBadge';
import { TierBadge } from '../ui/TierBadge';

interface TopBarProps {
  title: string;
  tier: ReconstructionTier;
  status: ReconstructionStatus;
  captureId: string;
}

export function TopBar({ title, tier, status, captureId }: TopBarProps) {
  return (
    <header
      style={{
        height: 'var(--topbar-height)',
        backgroundColor: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        flexShrink: 0,
        zIndex: 20,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <Link
          href="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            textDecoration: 'none',
          }}
          aria-label="COZMO Home"
        >
          <div
            style={{
              width: '24px',
              height: '24px',
              backgroundColor: 'var(--text-primary)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--surface)',
              fontWeight: 700,
              fontSize: '13px',
              letterSpacing: '-0.02em',
            }}
          >
            C
          </div>
          <span
            style={{
              fontWeight: 700,
              fontSize: '14px',
              letterSpacing: '0.04em',
              color: 'var(--text-primary)',
            }}
          >
            COZMO
          </span>
        </Link>

        <span style={{ color: 'var(--border-strong)', fontSize: '14px' }}>/</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--text-primary)',
            }}
          >
            {title}
          </span>
          <span
            className="mono"
            style={{
              fontSize: '12px',
              color: 'var(--text-muted)',
            }}
          >
            ({captureId})
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <TierBadge tier={tier} />
        <StatusBadge status={status} />
      </div>
    </header>
  );
}
