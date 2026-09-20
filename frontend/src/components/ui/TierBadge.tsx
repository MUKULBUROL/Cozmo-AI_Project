/**
 * @file TierBadge.tsx
 * @purpose Technical sensor tier badge (LiDAR / Video / Photos) paired with reconstruction status.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs tier (ReconstructionTier), optional status (ReconstructionStatus).
 * @outputs Neutral, technical tier label.
 * @dependencies ../../domain/types
 * @assumptions Keeps styling understated and technical. Never writes promotional slogans like "AI POWERED".
 * @failureModes Fallback to generic tier name.
 * @firstDebuggingPoints Check tier string value.
 */

import React from 'react';
import { ReconstructionTier, ReconstructionStatus } from '../../domain/types';

interface TierBadgeProps {
  tier: ReconstructionTier;
  status?: ReconstructionStatus;
}

const TIER_LABELS: Record<ReconstructionTier, string> = {
  lidar: 'LiDAR',
  video: 'Video',
  photo: 'Photos',
};

export function TierBadge({ tier, status }: TierBadgeProps) {
  const tierName = TIER_LABELS[tier] || tier;

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 8px',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: 'var(--surface-subtle)',
        border: '1px solid var(--border)',
        fontSize: '12px',
        fontWeight: 500,
        color: 'var(--text-secondary)',
      }}
    >
      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{tierName}</span>
      {status && (
        <>
          <span style={{ color: 'var(--border-strong)' }}>•</span>
          <span style={{ textTransform: 'capitalize' }}>{status.toLowerCase().replace('_', ' ')}</span>
        </>
      )}
    </div>
  );
}
