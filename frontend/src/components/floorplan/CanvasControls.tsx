/**
 * @file CanvasControls.tsx
 * @purpose Minimal deterministic viewport controls for Zoom In, Zoom Out, and Fit/Reset.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs onZoomIn, onZoomOut, onReset, zoomLevel.
 * @outputs Accessible floating button group positioned over the floor plan canvas.
 * @dependencies None
 * @assumptions Avoids heavy zoom libraries; strictly relies on stateful viewBox math.
 * @failureModes None.
 * @firstDebuggingPoints Check zoom callback wiring in FloorPlanCanvas.
 */

import React from 'react';

interface CanvasControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  zoomLevel: number;
}

export function CanvasControls({
  onZoomIn,
  onZoomOut,
  onReset,
  zoomLevel,
}: CanvasControlsProps) {
  return (
    <div
      role="toolbar"
      aria-label="Floor plan view controls"
      style={{
        position: 'absolute',
        bottom: '16px',
        right: '16px',
        display: 'flex',
        alignItems: 'center',
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--border-strong)',
        borderRadius: 'var(--radius-sm)',
        boxShadow: 'var(--shadow-sm)',
        padding: '2px',
        gap: '2px',
        zIndex: 10,
      }}
    >
      <button
        onClick={onZoomIn}
        aria-label="Zoom In"
        title="Zoom In (+)"
        style={{
          width: '28px',
          height: '28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--text-primary)',
          fontSize: '16px',
          fontWeight: 600,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--surface-subtle)')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        +
      </button>

      <span
        className="mono"
        style={{
          fontSize: '11px',
          color: 'var(--text-secondary)',
          padding: '0 4px',
          minWidth: '40px',
          textAlign: 'center',
        }}
      >
        {Math.round(zoomLevel * 100)}%
      </span>

      <button
        onClick={onZoomOut}
        aria-label="Zoom Out"
        title="Zoom Out (-)"
        style={{
          width: '28px',
          height: '28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--text-primary)',
          fontSize: '16px',
          fontWeight: 600,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--surface-subtle)')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        −
      </button>

      <div style={{ width: '1px', height: '16px', backgroundColor: 'var(--border)' }} />

      <button
        onClick={onReset}
        aria-label="Fit to View"
        title="Fit to View (Reset)"
        style={{
          padding: '0 8px',
          height: '28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--text-secondary)',
          fontSize: '11px',
          fontWeight: 500,
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--surface-subtle)')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        Fit
      </button>
    </div>
  );
}
