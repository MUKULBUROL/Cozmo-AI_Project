/**
 * @file TopBar.tsx
 * @purpose Workspace top navigation bar showing branding, property title, tier, status, evaluator guide link, and capture ID.
 * @stage Frontend Final Polish — Simplified Evaluator UX.
 * @inputs title (string), tier (ReconstructionTier), status (ReconstructionStatus), captureId (string).
 * @outputs Accessible header bar matching Spatial Pro aesthetic.
 * @dependencies ../../domain/types, ../ui/StatusBadge, ../ui/TierBadge, next/link
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
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
          <h1
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--text-primary)',
              margin: 0,
            }}
          >
            {title}
          </h1>
          <span
            className="mono"
            style={{
              fontSize: '11.5px',
              color: 'var(--text-muted)',
            }}
          >
            ({captureId})
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Link
          href="/demo"
          style={{
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-secondary)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
            backgroundColor: 'var(--surface-subtle)',
            transition: 'color 0.15s ease, border-color 0.15s ease',
          }}
        >
          Evaluator Guide
        </Link>
        <TierBadge tier={tier} />
        <StatusBadge status={status} />
      </div>
    </header>
  );
}
