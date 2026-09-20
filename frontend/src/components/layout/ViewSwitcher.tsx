/**
 * @file ViewSwitcher.tsx
 * @purpose Bottom workspace control bar switching between Plan, Measurements, Damage, and Scope modes, plus live Export controls.
 * @stage Frontend Stage 4 — Exports + Final Product Polish.
 * @inputs activeTab, onTabChange, captureId, property.
 * @outputs Accessible bottom bar with clear active indicator and functional Export menu.
 * @dependencies ./SideNavigation, ../ui/ExportMenu, ../../domain/types.
 * @assumptions Live export triggered directly via ExportMenu for JSON, SVG, PDF, and DXF deliverables.
 * @failureModes None.
 * @firstDebuggingPoints Verify tab switching and export trigger callbacks.
 */

'use client';

import React from 'react';
import { WorkspaceTab } from './SideNavigation';
import { ExportMenu } from '../ui/ExportMenu';
import { PropertyViewModel } from '../../domain/types';

interface ViewSwitcherProps {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  captureId?: string;
  property?: PropertyViewModel | null;
}

export function ViewSwitcher({
  activeTab,
  onTabChange,
  captureId,
  property,
}: ViewSwitcherProps) {
  const tabs: Array<{ id: WorkspaceTab; label: string }> = [
    { id: 'plan', label: 'Floor Plan' },
    { id: 'rooms', label: 'Measurements' },
    { id: 'damage', label: 'Damage Overlay' },
    { id: 'scope', label: 'Repair Scope' },
  ];

  const targetCaptureId = captureId || property?.captureId || 'default';

  return (
    <footer
      style={{
        height: '48px',
        backgroundColor: 'var(--surface)',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              aria-pressed={isActive}
              style={{
                padding: '6px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? 'var(--primary)' : 'var(--text-secondary)',
                backgroundColor: isActive ? 'var(--primary-subtle)' : 'transparent',
                border: isActive ? '1px solid var(--primary-border)' : '1px solid transparent',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <ExportMenu captureId={targetCaptureId} property={property} />
      </div>
    </footer>
  );
}
