/**
 * @file page.tsx
 * @purpose Home product workspace route displaying available properties and captures.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs None (reads static fixture summaries via getAllFixtureSummaries).
 * @outputs Accessible property directory linking to interactive workspace routes (/property/[id]).
 * @dependencies ../data/fixture-loader, ../components/ui/StatusBadge, ../components/ui/TierBadge, next/link
 * @assumptions Not an analytics dashboard; focuses strictly on spatial property records.
 * @failureModes None.
 * @firstDebuggingPoints Verify fixture manifest is generated and loaded in fixture-loader.ts.
 */

import React from 'react';
import Link from 'next/link';
import { getAllFixtureSummaries } from '../data/fixture-loader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TierBadge } from '../components/ui/TierBadge';

export default function HomePage() {
  const fixtures = getAllFixtureSummaries();

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
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
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
            }}
          >
            C
          </div>
          <span style={{ fontWeight: 700, fontSize: '15px', letterSpacing: '0.04em', color: 'var(--text-primary)' }}>
            COZMO
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>— Spatial Intelligence Workspace</span>
        </div>

        <Link
          href="/new"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 14px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--primary)',
            color: 'var(--text-on-primary)',
            fontSize: '13px',
            fontWeight: 500,
            transition: 'background-color 0.15s ease',
          }}
        >
          <span>+</span>
          <span>New Capture</span>
        </Link>
      </header>

      {/* Main Container */}
      <main
        style={{
          maxWidth: '960px',
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
            Property Workspaces
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Select a verified reconstruction capture to explore floor plans, room metrics, doorway openings, and defect scope.
          </p>
        </div>

        {/* Property Grid / List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {fixtures.map((item) => (
            <Link
              key={item.id}
              href={`/property/${item.id}`}
              className="property-card"
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  marginBottom: '10px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                    <h2
                      style={{
                        fontSize: '16px',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                      }}
                    >
                      {item.name}
                    </h2>
                    <span className="mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      ({item.id})
                    </span>
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                    {item.description}
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0, marginLeft: '16px' }}>
                  <TierBadge tier={item.tier} />
                  <StatusBadge status={item.status} />
                </div>
              </div>

              {/* Dimensional Summary Chips */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  paddingTop: '12px',
                  borderTop: '1px solid var(--border)',
                  fontSize: '12px',
                  color: 'var(--text-secondary)',
                }}
              >
                <span>
                  Rooms: <strong style={{ color: 'var(--text-primary)' }}>{item.roomCount}</strong>
                </span>
                <span style={{ color: 'var(--border)' }}>•</span>
                <span className="mono">
                  Floor Area:{' '}
                  <strong style={{ color: 'var(--text-primary)' }}>
                    {item.totalAreaM2 !== null ? `${item.totalAreaM2.toFixed(2)} m²` : 'Not available'}
                  </strong>
                </span>
                <span style={{ color: 'var(--border)' }}>•</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                  Source: <span className="mono">{item.fileName}</span>
                </span>
              </div>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
