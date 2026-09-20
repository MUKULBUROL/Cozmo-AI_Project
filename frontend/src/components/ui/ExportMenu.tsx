/**
 * @file ExportMenu.tsx
 * @purpose Dropdown control for downloading real JSON, SVG, PDF, and DXF deliverables.
 * @stage Frontend Stage 4 — Exports + Final Product Polish.
 * @inputs captureId (string), property (PropertyViewModel | null).
 * @outputs Accessible Spatial Pro dropdown trigger with loading indicators and error feedback.
 * @dependencies ../../lib/api/captures, ../../domain/types.
 * @assumptions Live mode downloads directly from FastAPI export endpoints; static fallback supported.
 * @failureModes Download error displayed inline without full page reload or silent failure.
 * @firstDebuggingPoints Check network tab for GET /api/captures/{id}/exports/{format}.
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { PropertyViewModel } from '../../domain/types';
import { downloadCaptureExport, ExportFormat } from '../../lib/api/captures';

interface ExportMenuProps {
  captureId: string;
  property?: PropertyViewModel | null;
}

interface ExportOption {
  format: ExportFormat;
  label: string;
  extension: string;
  description: string;
  icon: string;
}

const EXPORT_OPTIONS: ExportOption[] = [
  {
    format: 'pdf',
    label: 'PDF Report',
    extension: '.pdf',
    description: 'Multi-page report with vector plan & schedules',
    icon: '📄',
  },
  {
    format: 'svg',
    label: 'Vector Floor Plan',
    extension: '.svg',
    description: 'Standalone 2D vector architectural drawing',
    icon: '📐',
  },
  {
    format: 'json',
    label: 'Property JSON',
    extension: '.json',
    description: 'Machine-readable schema with 95% intervals',
    icon: '{ }',
  },
  {
    format: 'dxf',
    label: 'AutoCAD DXF',
    extension: '.dxf',
    description: 'Metric CAD drawing with layered geometry',
    icon: '🏛️',
  },
];

export function ExportMenu({ captureId, property }: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [loadingFormat, setLoadingFormat] = useState<ExportFormat | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Close dropdown on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  async function handleExport(format: ExportFormat) {
    setLoadingFormat(format);
    setErrorMessage(null);

    try {
      await downloadCaptureExport(captureId, format, property);
      setIsOpen(false);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : `Failed to download ${format.toUpperCase()} export.`
      );
    } finally {
      setLoadingFormat(null);
    }
  }

  return (
    <div ref={menuRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* Dropdown Trigger Button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="true"
        aria-expanded={isOpen}
        disabled={loadingFormat !== null}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 14px',
          backgroundColor: isOpen ? 'var(--surface-active)' : 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '12px',
          fontWeight: 600,
          color: 'var(--text-primary)',
          cursor: loadingFormat !== null ? 'wait' : 'pointer',
          boxShadow: 'var(--shadow-xs)',
          transition: 'all 0.15s ease',
        }}
      >
        <span>Export</span>
        <svg
          width="10"
          height="6"
          viewBox="0 0 10 6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.15s ease',
          }}
        >
          <path d="M1 1L5 5L9 1" />
        </svg>
      </button>

      {/* Dropdown Menu Modal / Popover */}
      {isOpen && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            bottom: '100%',
            right: 0,
            marginBottom: '8px',
            width: '280px',
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            padding: '6px',
            zIndex: 100,
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
            animation: 'fadeInScale 0.15s ease-out',
          }}
        >
          <div
            style={{
              padding: '6px 10px 4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              borderBottom: '1px solid var(--border-subtle)',
              marginBottom: '4px',
            }}
          >
            Deliverable Formats
          </div>

          {EXPORT_OPTIONS.map((opt) => {
            const isLoading = loadingFormat === opt.format;
            return (
              <button
                key={opt.format}
                role="menuitem"
                disabled={isLoading}
                onClick={() => void handleExport(opt.format)}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'transparent',
                  border: 'none',
                  textAlign: 'left',
                  cursor: isLoading ? 'wait' : 'pointer',
                  transition: 'background-color 0.1s ease',
                  width: '100%',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--surface-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <span
                  style={{
                    fontSize: '14px',
                    width: '20px',
                    textAlign: 'center',
                    flexShrink: 0,
                    marginTop: '1px',
                  }}
                >
                  {isLoading ? '⏳' : opt.icon}
                </span>

                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {opt.label}
                    </span>
                    <span className="mono" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      {opt.extension}
                    </span>
                  </div>
                  <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {isLoading ? 'Preparing download…' : opt.description}
                  </span>
                </div>
              </button>
            );
          })}

          {errorMessage && (
            <div
              style={{
                marginTop: '6px',
                padding: '8px 10px',
                backgroundColor: 'var(--danger-subtle)',
                border: '1px solid var(--danger-border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '11px',
                color: 'var(--danger-text)',
              }}
            >
              ⚠️ {errorMessage}
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes fadeInScale {
          from { opacity: 0; transform: scale(0.96) translateY(4px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
}
