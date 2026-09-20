/**
 * @file AppShell.tsx
 * @purpose Main 3-pane application shell coordinating navigation, canvas, inspector, and responsive layouts.
 * @stage Frontend Final Polish — Simplified Evaluator UX.
 * @inputs PropertyViewModel.
 * @outputs Unified interactive workspace supporting desktop, tablet, and mobile layouts.
 * @dependencies ./TopBar, ./SideNavigation, ./ViewSwitcher, ../floorplan/FloorPlanCanvas, ../inspector/InspectorPanel, ../ui/EmptyState
 */

'use client';

import React, { useState } from 'react';
import { PropertyViewModel, RoomViewModel } from '../../domain/types';
import { TopBar } from './TopBar';
import { SideNavigation, WorkspaceTab } from './SideNavigation';
import { ViewSwitcher } from './ViewSwitcher';
import { FloorPlanCanvas } from '../floorplan/FloorPlanCanvas';
import { InspectorPanel } from '../inspector/InspectorPanel';

interface AppShellProps {
  property: PropertyViewModel;
}

export function AppShell({ property }: AppShellProps) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('plan');
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(
    property.rooms && property.rooms.length > 0 ? property.rooms[0].id : null
  );

  const selectedRoom: RoomViewModel | null =
    property.rooms.find((r) => r.id === selectedRoomId) || null;

  // Aggregate counts for side navigation badges
  const totalDamages = property.rooms.reduce((acc, r) => acc + r.damages.length, 0);
  const totalScopeItems = property.rooms.reduce(
    (acc, r) => acc + r.damages.reduce((dAcc, d) => dAcc + d.scopeItems.length, 0),
    0
  );

  return (
    <div className="app-shell">
      {/* Top Bar */}
      <TopBar
        title={property.name}
        tier={property.tier}
        status={property.status}
        captureId={property.captureId}
      />

      {/* Main 3-Pane Spatial Workspace */}
      <div className="workspace-grid">
        {/* Left Side Navigation */}
        <SideNavigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
          roomCount={property.rooms.length}
          damageCount={totalDamages}
          scopeCount={totalScopeItems}
        />

        {/* Center Main Stage (Floor Plan Canvas or Scope View) */}
        {activeTab === 'scope' ? (
          <main
            style={{
              flex: 1,
              backgroundColor: 'var(--canvas-background)',
              padding: '32px',
              overflowY: 'auto',
            }}
          >
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
              <div style={{ marginBottom: '20px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Remediation & Repair Scope
                </h2>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Itemized repair scope derived from detected surface defects and dimensional extents.
                </p>
              </div>

              {totalScopeItems > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {property.rooms.flatMap((r) =>
                    r.damages.flatMap((d) =>
                      d.scopeItems.map((item) => (
                        <div
                          key={item.id}
                          style={{
                            padding: '16px',
                            backgroundColor: 'var(--surface)',
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius-md)',
                            boxShadow: 'var(--shadow-sm)',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              marginBottom: '8px',
                            }}
                          >
                            <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              {item.id}
                            </span>
                            <span
                              style={{
                                fontSize: '11px',
                                padding: '2px 8px',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: item.inspectionRequired
                                  ? 'var(--warning-subtle)'
                                  : 'var(--success-subtle)',
                                color: item.inspectionRequired
                                  ? 'var(--warning-text)'
                                  : 'var(--success-text)',
                                border: `1px solid ${
                                  item.inspectionRequired ? 'var(--warning-border)' : 'var(--success-border)'
                                }`,
                                fontWeight: 500,
                              }}
                            >
                              {item.inspectionRequired ? 'Inspection Required' : 'Standard Remediation'}
                            </span>
                          </div>

                          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
                            {item.action}
                          </div>

                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '16px',
                              fontSize: '12px',
                              color: 'var(--text-secondary)',
                            }}
                          >
                            <span>
                              Target:{' '}
                              <strong style={{ color: 'var(--text-primary)' }}>{item.targetSurface}</strong>
                            </span>
                            <span className="mono">
                              Quantity:{' '}
                              <strong style={{ color: 'var(--text-primary)' }}>
                                {item.quantity} {item.unit}
                              </strong>
                            </span>
                          </div>
                        </div>
                      ))
                    )
                  )}
                </div>
              ) : (
                <div
                  style={{
                    padding: '40px',
                    textAlign: 'center',
                    backgroundColor: 'var(--surface)',
                    border: '1px dashed var(--border-strong)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-secondary)',
                    fontSize: '13px',
                  }}
                >
                  No repair scope line items generated for this capture.
                </div>
              )}
            </div>
          </main>
        ) : (
          <FloorPlanCanvas
            property={property}
            selectedRoomId={selectedRoomId}
            onSelectRoom={setSelectedRoomId}
            showDamageOverlay={activeTab === 'damage'}
          />
        )}

        {/* Right Inspector */}
        <InspectorPanel
          property={property}
          selectedRoom={selectedRoom}
          onSelectRoom={setSelectedRoomId}
        />
      </div>

      {/* Bottom Switcher with Real Multi-Format Exports */}
      <ViewSwitcher
        activeTab={activeTab}
        onTabChange={setActiveTab}
        captureId={property.captureId}
        property={property}
      />
    </div>
  );
}
