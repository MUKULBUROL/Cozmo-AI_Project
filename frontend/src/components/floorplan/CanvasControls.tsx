/**
 * @file CanvasControls.tsx
 * @purpose Floating zoom, fit, and focus controls for the floor plan viewport.
 * @stage Frontend Stage 3 — Floor Plan UX Improvements.
 * @inputs Zoom callbacks, current zoom level, optional focus room handler.
 * @outputs Accessible floating control bar with Zoom In, Zoom Out, Fit, and Focus Room buttons.
 * @dependencies None.
 * @assumptions Controls remain visible/sticky inside the canvas viewport.
 * @failureModes None.
 * @firstDebuggingPoints Check that onFocusRoom is provided when a room is selected.
 */

'use client';

import React from 'react';

interface CanvasControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFocusRoom?: () => void;
  zoomLevel: number;
}

export function CanvasControls({
  onZoomIn,
  onZoomOut,
  onReset,
  onFocusRoom,
  zoomLevel,
}: CanvasControlsProps) {
  const buttonStyle: React.CSSProperties = {
    width: '32px',
    height: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    transition: 'background-color 0.1s ease',
  };

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '16px',
        right: '16px',
        display: 'flex',
        gap: '4px',
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '4px',
        boxShadow: 'var(--shadow-md)',
        zIndex: 10,
      }}
    >
      <button
        onClick={onZoomOut}
        aria-label="Zoom out"
        title="Zoom out (−)"
        style={buttonStyle}
      >
        −
      </button>

      <div
        className="mono"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '11px',
          color: 'var(--text-muted)',
          minWidth: '40px',
          userSelect: 'none',
        }}
      >
        {Math.round(zoomLevel * 100)}%
      </div>

      <button
        onClick={onZoomIn}
        aria-label="Zoom in"
        title="Zoom in (+)"
        style={buttonStyle}
      >
        +
      </button>

      <div
        style={{
          width: '1px',
          backgroundColor: 'var(--border)',
          margin: '4px 2px',
        }}
      />

      <button
        onClick={onReset}
        aria-label="Fit to view"
        title="Fit to view (0)"
        style={{
          ...buttonStyle,
          fontSize: '11px',
          fontWeight: 500,
          width: 'auto',
          padding: '0 8px',
        }}
      >
        Fit
      </button>

      {onFocusRoom && (
        <button
          onClick={onFocusRoom}
          aria-label="Focus selected room"
          title="Focus selected room (F)"
          style={{
            ...buttonStyle,
            fontSize: '11px',
            fontWeight: 500,
            width: 'auto',
            padding: '0 8px',
            color: 'var(--primary)',
          }}
        >
          Focus
        </button>
      )}
    </div>
  );
}
