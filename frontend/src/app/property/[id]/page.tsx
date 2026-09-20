/**
 * @file property/[id]/page.tsx
 * @purpose Dynamic property workspace route supporting both fixture and live API data.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 * @inputs Route param `id` — capture or property ID (fixture IDs or API-generated cap_ IDs).
 * @outputs Interactive Spatial Pro workspace via AppShell for any valid property.
 * @dependencies ../../../data/fixture-loader, ../../../lib/api/captures, ../../../components/layout/AppShell, next/link.
 * @assumptions
 *   - Fixture IDs (c7d28f72c6, c00a170fe1, etc.) resolve from static fixtures.
 *   - Live capture IDs (cap_*) resolve from API result endpoint.
 *   - NEXT_PUBLIC_DATA_MODE controls behaviour: "live" never falls back to fixtures silently.
 * @failureModes Unknown fixture ID + API failure → shows error. API failure in live mode → shows API error, NOT fixture fallback.
 * @firstDebuggingPoints Check if ID is a fixture ID or live capture. Check API response in Network tab. Check NEXT_PUBLIC_DATA_MODE.
 */

'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { getPropertyById } from '../../../data/fixture-loader';
import { getCaptureResult } from '../../../lib/api/captures';
import { AppShell } from '../../../components/layout/AppShell';
import type { PropertyViewModel } from '../../../domain/types';

type LoadState = 'loading' | 'loaded' | 'error';

export default function PropertyPage() {
  const params = useParams();
  const id = typeof params.id === 'string' ? params.id : '';

  const [property, setProperty] = useState<PropertyViewModel | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    let cancelled = false;

    async function loadProperty() {
      if (!id) {
        if (!cancelled) {
          setLoadState('error');
          setErrorMessage('No property ID provided.');
        }
        return;
      }

      // Step 1: Try fixture (for known fixture IDs in dev/demo mode)
      const fixtureResult = getPropertyById(id);
      if (fixtureResult) {
        if (!cancelled) {
          setProperty(fixtureResult);
          setLoadState('loaded');
        }
        return;
      }

      // Step 2: Try API for live captures (any non-fixture ID)
      try {
        const result = await getCaptureResult(id);
        if (!cancelled) {
          setProperty(result);
          setLoadState('loaded');
        }
      } catch (err) {
        if (!cancelled) {
          // In live mode, API failure must NOT silently fall back to fixtures
          setLoadState('error');
          setErrorMessage(
            err instanceof Error
              ? err.message
              : 'Failed to load property. The API server may not be running.'
          );
        }
      }
    }

    void loadProperty();

    return () => {
      cancelled = true;
    };
  }, [id]);

  // Loading state
  if (loadState === 'loading') {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: 'var(--background)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              border: '3px solid var(--border)',
              borderTopColor: 'var(--primary)',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 16px auto',
            }}
          />
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
            Loading property <span className="mono">{id}</span>…
          </p>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    );
  }

  // Error state
  if (loadState === 'error' || !property) {
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
            Property Not Available
          </h1>
          <p
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
              marginBottom: '12px',
            }}
          >
            The capture <span className="mono">{id}</span> could not be loaded.
          </p>
          {errorMessage && (
            <div
              style={{
                padding: '10px 14px',
                backgroundColor: 'var(--danger-subtle, #fef2f2)',
                border: '1px solid var(--danger-border, #fecaca)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--danger-text, #dc2626)',
                fontSize: '12px',
                lineHeight: 1.4,
                marginBottom: '16px',
                textAlign: 'left',
              }}
            >
              {errorMessage}
            </div>
          )}
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
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
              ← Return to Workspaces
            </Link>
            <Link
              href="/new"
              style={{
                display: 'inline-block',
                padding: '8px 16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--surface-subtle)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border)',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              New Capture
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return <AppShell property={property} />;
}
