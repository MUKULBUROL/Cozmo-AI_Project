/**
 * @file page.tsx
 * @purpose Evaluator homepage for COZMO spatial reconstruction platform.
 * @stage Frontend Final Polish — Simplified Evaluator UX.
 * @inputs None (reads static fixture summaries via getAllFixtureSummaries).
 * @outputs Accessible property directory linking to interactive workspace routes (/property/[id]).
 * @dependencies ../data/fixture-loader, ../components/ui/StatusBadge, ../components/ui/TierBadge, next/link
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
              width: '26px',
              height: '26px',
              backgroundColor: 'var(--text-primary)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--surface)',
              fontWeight: 700,
              fontSize: '14px',
            }}
          >
            C
          </div>
          <span style={{ fontWeight: 700, fontSize: '15px', letterSpacing: '0.04em', color: 'var(--text-primary)' }}>
            COZMO
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            href="/demo"
            style={{
              fontSize: '13px',
              fontWeight: 500,
              color: 'var(--text-secondary)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              backgroundColor: 'var(--surface)',
              transition: 'color 0.15s ease, border-color 0.15s ease',
            }}
          >
            Evaluator Guide
          </Link>

          <Link
            href="/new"
            id="new-capture-btn-header"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--primary)',
              color: 'var(--text-on-primary)',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none',
              transition: 'background-color 0.15s ease',
            }}
          >
            <span>+</span>
            <span>New Capture</span>
          </Link>
        </div>
      </header>

      {/* Main Hero Container */}
      <main
        style={{
          maxWidth: '880px',
          width: '100%',
          margin: '40px auto',
          padding: '0 24px',
        }}
      >
        {/* Simple Evaluator Hero Section */}
        <div
          style={{
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '36px 32px',
            marginBottom: '32px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ maxWidth: '640px' }}>
            <h1
              style={{
                fontSize: '26px',
                fontWeight: 700,
                color: 'var(--text-primary)',
                letterSpacing: '-0.02em',
                marginBottom: '10px',
                lineHeight: 1.25,
              }}
            >
              Turn room captures into measurable floor plans.
            </h1>
            <p
              style={{
                fontSize: '15px',
                color: 'var(--text-secondary)',
                lineHeight: 1.55,
                marginBottom: '16px',
              }}
            >
              Upload LiDAR, video, or room photos to generate interactive 2D floor plans, room dimensions, doorway openings, defect scopes, and CAD/PDF exports.
            </p>

            <div
              style={{
                fontSize: '13px',
                color: 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span style={{ color: 'var(--primary)', fontWeight: 600 }}>•</span>
              <span>Supports LiDAR ZIP, handheld MP4 video, or photo archives.</span>
            </div>
          </div>
        </div>

        {/* Workspaces Section */}
        <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2
              style={{
                fontSize: '16px',
                fontWeight: 700,
                color: 'var(--text-primary)',
                letterSpacing: '-0.01em',
                marginBottom: '2px',
              }}
            >
              Sample Evaluator Workspaces
            </h2>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Select a reconstructed property below to inspect its floor plan, dimensions, and exports.
            </p>
          </div>
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
                    <h3
                      style={{
                        fontSize: '15px',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                      }}
                    >
                      {item.name}
                    </h3>
                    <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
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
                  paddingTop: '10px',
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
