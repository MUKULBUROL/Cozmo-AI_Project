/**
 * @file new/page.tsx
 * @purpose Visual New Capture wizard route for Stage 2.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs None (UI preview).
 * @outputs Accessible capture initiation screen with honest placeholders for Stage 3 FastAPI integration.
 * @dependencies next/link
 * @assumptions Live upload pipeline is scheduled for Stage 3. Buttons clearly indicate future integration.
 * @failureModes None.
 * @firstDebuggingPoints Verify tier selection toggles visual state without attempting network requests.
 */

'use client';

import React, { useState } from 'react';
import Link from 'next/link';

type CaptureTier = 'lidar' | 'video' | 'photo';

export default function NewCapturePage() {
  const [selectedTier, setSelectedTier] = useState<CaptureTier>('lidar');

  const tiers: Array<{
    id: CaptureTier;
    title: string;
    description: string;
    features: string[];
    badge: string;
  }> = [
    {
      id: 'lidar',
      title: 'LiDAR Reconstruction',
      badge: 'High Precision',
      description: 'Metric unprojection from ARKit depth frames with deterministic RANSAC extraction.',
      features: ['Sub-cm point cloud resolution', 'Direct metric scale', 'Ceiling & floor height separation'],
    },
    {
      id: 'video',
      title: 'RGB Video SfM',
      badge: 'Stage 11 Metric Scale',
      description: 'Continuous video keyframe tracking with Depth Anything v2 metric unprojection.',
      features: ['Multi-view feature matching', 'Temporal continuity audit', 'Provisional plan topology'],
    },
    {
      id: 'photo',
      title: 'Multi-View Photo Set',
      badge: 'Sparse Alignment',
      description: 'Uncalibrated photo set reconstruction with COLMAP structure-from-motion.',
      features: ['Ordered perspective matching', 'Requires visual overlap > 60%', 'Uncalibrated baseline'],
    },
  ];

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
          justifyContent: 'space-between',
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
            }}
          >
            ← Back to Workspaces
          </Link>
          <span style={{ color: 'var(--border-strong)' }}>/</span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            New Capture Setup
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main
        style={{
          maxWidth: '780px',
          width: '100%',
          margin: '40px auto',
          padding: '0 24px',
        }}
      >
        <div style={{ marginBottom: '28px' }}>
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em',
              marginBottom: '6px',
            }}
          >
            Select Reconstruction Sensor Tier
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Choose the capture methodology matching your input data. Live upload and FastAPI processing pipeline will be integrated in Stage 3.
          </p>
        </div>

        {/* Tier Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '32px' }}>
          {tiers.map((t) => {
            const isSelected = selectedTier === t.id;
            return (
              <div
                key={t.id}
                onClick={() => setSelectedTier(t.id)}
                style={{
                  backgroundColor: 'var(--surface)',
                  border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '20px 24px',
                  cursor: 'pointer',
                  boxShadow: isSelected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {t.title}
                    </h2>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--surface-subtle)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border)',
                        fontWeight: 500,
                      }}
                    >
                      {t.badge}
                    </span>
                  </div>

                  <div
                    style={{
                      width: '18px',
                      height: '18px',
                      borderRadius: '50%',
                      border: isSelected ? '5px solid var(--primary)' : '2px solid var(--border-strong)',
                      backgroundColor: 'var(--surface)',
                    }}
                  />
                </div>

                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px', lineHeight: 1.4 }}>
                  {t.description}
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {t.features.map((feat, idx) => (
                    <span
                      key={idx}
                      style={{
                        fontSize: '12px',
                        color: 'var(--text-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <span style={{ color: 'var(--success)' }}>✓</span> {feat}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Upload Action Area */}
        <div
          style={{
            backgroundColor: 'var(--surface)',
            border: '1px dashed var(--border-strong)',
            borderRadius: 'var(--radius-md)',
            padding: '32px',
            textAlign: 'center',
            marginBottom: '24px',
          }}
        >
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '50%',
              backgroundColor: 'var(--surface-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto',
              color: 'var(--text-muted)',
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>

          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Upload Capture Payload
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
            Drag and drop ZIP, MP4, or ARKit trajectory folder.
          </p>

          <button
            disabled
            aria-disabled="true"
            title="Upload integration coming in Stage 3"
            style={{
              padding: '9px 20px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--surface-subtle)',
              color: 'var(--text-muted)',
              border: '1px solid var(--border)',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'not-allowed',
            }}
          >
            Upload Pipeline Coming in Stage 3
          </button>
        </div>

        <div style={{ textAlign: 'center' }}>
          <Link
            href="/"
            style={{
              fontSize: '13px',
              color: 'var(--primary)',
              fontWeight: 500,
            }}
          >
            ← Or explore existing benchmark captures
          </Link>
        </div>
      </main>
    </div>
  );
}
