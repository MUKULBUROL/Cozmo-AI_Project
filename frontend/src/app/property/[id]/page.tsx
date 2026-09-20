/**
 * @file property/[id]/page.tsx
 * @purpose Primary Spatial Pro property workspace route rendering the full interactive floor plan and inspector.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Route param `id` (e.g. c7d28f72c6, c00a170fe1, stage11-video, video-multi-room-failure).
 * @outputs Fully interactive spatial intelligence workspace rendered via AppShell.
 * @dependencies ../../../data/fixture-loader, ../../../components/layout/AppShell, ../../../components/ui/EmptyState, next/link
 * @assumptions Real backend fixtures are loaded synchronously from generated JSON artifacts.
 * @failureModes Unrecognized property ID displays a clean, accessible error state with return link.
 * @firstDebuggingPoints Verify fixture ID exists in manifest.json; check getPropertyById lookup.
 */

import React from 'react';
import Link from 'next/link';
import { getPropertyById, getAllFixtureSummaries } from '../../../data/fixture-loader';
import { AppShell } from '../../../components/layout/AppShell';

interface PropertyPageProps {
  params: Promise<{ id: string }>;
}

export async function generateStaticParams() {
  const fixtures = getAllFixtureSummaries();
  return fixtures.map((f) => ({ id: f.id }));
}

export default async function PropertyPage({ params }: PropertyPageProps) {
  const { id } = await params;
  const property = getPropertyById(id);

  if (!property) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: 'var(--background)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
        }}
      >
        <div
          style={{
            maxWidth: '480px',
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '32px',
            textAlign: 'center',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <h1
            style={{
              fontSize: '18px',
              fontWeight: 600,
              color: 'var(--text-primary)',
              marginBottom: '8px',
            }}
          >
            Property Record Not Found
          </h1>
          <p
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
              marginBottom: '20px',
            }}
          >
            The capture ID <span className="mono">{id}</span> does not match any known benchmark or reconstruction fixture.
          </p>
          <Link
            href="/"
            style={{
              display: 'inline-block',
              padding: '8px 16px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--primary)',
              color: 'var(--text-on-primary)',
              fontSize: '13px',
              fontWeight: 500,
            }}
          >
            ← Return to Property Workspaces
          </Link>
        </div>
      </div>
    );
  }

  return <AppShell property={property} />;
}
