/**
 * @file ViewSwitcher.tsx
 * @purpose Bottom workspace control bar switching between Plan, Measurements, Damage, and Scope modes, plus disabled Export notice.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs activeTab, onTabChange.
 * @outputs Accessible bottom bar with clear active indicator and truthful stage-3 notices.
 * @dependencies ./SideNavigation
 * @assumptions Export is scheduled for Stage 3; button is visibly disabled with clear tooltip/notice.
 * @failureModes None.
 * @firstDebuggingPoints Verify tab switching callback triggers correctly.
 */

import React from 'react';
import { WorkspaceTab } from './SideNavigation';

interface ViewSwitcherProps {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}

export function ViewSwitcher({ activeTab, onTabChange }: ViewSwitcherProps) {
  const tabs: Array<{ id: WorkspaceTab; label: string }> = [
    { id: 'plan', label: 'Floor Plan' },
    { id: 'rooms', label: 'Measurements' },
    { id: 'damage', label: 'Damage Overlay' },
    { id: 'scope', label: 'Repair Scope' },
  ];

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

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            fontStyle: 'italic',
          }}
        >
          Export integration coming in Stage 3
        </span>
        <button
          disabled
          aria-disabled="true"
          title="Export integration coming in Stage 3"
          style={{
            padding: '5px 12px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-muted)',
            backgroundColor: 'var(--surface-subtle)',
            border: '1px solid var(--border)',
            cursor: 'not-allowed',
            opacity: 0.7,
          }}
        >
          Export DXF / PDF
        </button>
      </div>
    </footer>
  );
}
