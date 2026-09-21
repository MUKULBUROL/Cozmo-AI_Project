/**
 * @file InspectorPanel.tsx
 * @purpose Right inspector pane detailing property summary, room measurements, openings, damage findings, scope, and advanced details.
 * @stage Frontend Final Polish — Simplified Evaluator UX.
 * @inputs PropertyViewModel, selectedRoom (RoomViewModel | null), onSelectRoom.
 * @outputs Accessible inspector panel with clear human terminology and collapsed advanced technical details.
 * @dependencies ../../domain/types, ../ui/StatusBadge, ../ui/MeasurementStatus
 */

'use client';

import React, { useState } from 'react';
import { PropertyViewModel, RoomViewModel } from '../../domain/types';
import { formatDamageLabel } from '../../domain/adapters';
import { StatusBadge } from '../ui/StatusBadge';
import { MeasurementStatus } from '../ui/MeasurementStatus';

interface InspectorPanelProps {
  property: PropertyViewModel;
  selectedRoom: RoomViewModel | null;
  onSelectRoom: (roomId: string) => void;
}

/**
 * Returns evaluator-friendly status explanation message based on reconstruction quality.
 */
function getStatusExplanation(status: string, failureReasons?: string[]): { title: string; desc: string; type: 'success' | 'warning' | 'danger' } {
  switch (status) {
    case 'COMPLETE':
      return {
        title: 'Complete',
        desc: 'Reconstruction completed successfully.',
        type: 'success',
      };
    case 'PROVISIONAL':
      return {
        title: 'Completed with limitations',
        desc: 'Reconstruction completed with provisional scale or boundary estimates.',
        type: 'warning',
      };
    case 'NOT_EVALUABLE':
      return {
        title: 'Could not produce a reliable plan',
        desc: 'Insufficient reconstruction quality to produce an accurate property plan.',
        type: 'danger',
      };
    case 'FAILED':
      return {
        title: 'Processing failed',
        desc: failureReasons && failureReasons.length > 0 ? failureReasons[0] : 'Processing failed.',
        type: 'danger',
      };
    default:
      return {
        title: status,
        desc: 'Reconstruction status recorded.',
        type: 'warning',
      };
  }
}

export function InspectorPanel({
  property,
  selectedRoom,
  onSelectRoom,
}: InspectorPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  const totalOpenings = property.rooms.reduce((acc, r) => acc + (r.openings?.length || 0), 0);
  const totalDamages = property.rooms.reduce((acc, r) => acc + (r.damages?.length || 0), 0);
  const statusInfo = getStatusExplanation(property.status, property.statusReasons);

  // If no room is selected or property has no rooms, show property overview
  if (!selectedRoom) {
    return (
      <aside
        aria-label="Property Overview Inspector"
        style={{
          backgroundColor: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          padding: '20px',
          overflowY: 'auto',
          userSelect: 'text',
        }}
      >
        {/* Header */}
        <div style={{ marginBottom: '14px' }}>
          <div
            style={{
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-muted)',
              marginBottom: '2px',
            }}
          >
            Property Overview
          </div>
          <h2
            style={{
              fontSize: '16px',
              fontWeight: 600,
              color: 'var(--text-primary)',
            }}
          >
            {property.name}
          </h2>
        </div>

        {/* Status Explanation Card */}
        <div
          style={{
            padding: '12px',
            borderRadius: 'var(--radius-md)',
            backgroundColor:
              statusInfo.type === 'success'
                ? 'var(--success-subtle)'
                : statusInfo.type === 'warning'
                ? 'var(--warning-subtle)'
                : 'var(--danger-subtle)',
            border: `1px solid ${
              statusInfo.type === 'success'
                ? 'var(--success-border)'
                : statusInfo.type === 'warning'
                ? 'var(--warning-border)'
                : 'var(--danger-border)'
            }`,
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <span
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color:
                  statusInfo.type === 'success'
                    ? 'var(--success-text)'
                    : statusInfo.type === 'warning'
                    ? 'var(--warning-text)'
                    : 'var(--danger-text)',
              }}
            >
              {statusInfo.title}
            </span>
            <StatusBadge status={property.status} size="sm" />
          </div>
          <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.45, margin: 0 }}>
            {statusInfo.desc}
          </p>
        </div>

        {/* Summary Metric Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '18px' }}>
          <div
            style={{
              padding: '12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
              Total Reconstructed Area
            </div>
            <div className="mono" style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {property.totalFloorArea ? `${property.totalFloorArea.value.toFixed(2)} m²` : 'Not available'}
            </div>
            {property.totalFloorArea?.interval && (
              <div className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Estimated Range: {property.totalFloorArea.interval[0].toFixed(2)} – {property.totalFloorArea.interval[1].toFixed(2)} m²
              </div>
            )}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '8px',
            }}
          >
            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--surface-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
              }}
            >
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
                Rooms
              </div>
              <div className="mono" style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {property.rooms.length}
              </div>
            </div>

            <div
              style={{
                padding: '10px 12px',
                backgroundColor: 'var(--surface-subtle)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
              }}
            >
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
                Openings
              </div>
              <div className="mono" style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {totalOpenings}
              </div>
            </div>
          </div>

          <div
            style={{
              padding: '10px 12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>Damage Findings</span>
            <span
              className="mono"
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: totalDamages > 0 ? 'var(--danger-text)' : 'var(--success-text)',
              }}
            >
              {totalDamages} {totalDamages === 1 ? 'finding' : 'findings'}
            </span>
          </div>
        </div>

        {/* Room List Selector with Direct Guidance */}
        {property.rooms.length > 0 && (
          <div
            style={{
              padding: '12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)',
              marginBottom: '16px',
            }}
          >
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
              Rooms
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Click a room to view its measurements.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {property.rooms.map((room) => (
                <button
                  key={room.id}
                  onClick={() => onSelectRoom(room.id)}
                  className="room-select-btn"
                >
                  <span style={{ fontWeight: 500 }}>{room.name}</span>
                  <span className="mono" style={{ color: 'var(--text-secondary)' }}>
                    {room.floorArea ? `${room.floorArea.value.toFixed(2)} m²` : '—'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Collapsible Advanced Details Accordion */}
        <div style={{ marginBottom: '16px' }}>
          <button
            onClick={() => setShowAdvanced((prev) => !prev)}
            id="toggle-advanced-details-btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              padding: '8px 10px',
              backgroundColor: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11.5px',
              fontWeight: 600,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            <span>Advanced Details</span>
            <span style={{ transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}>
              ▾
            </span>
          </button>

          {showAdvanced && (
            <div
              style={{
                marginTop: '6px',
                padding: '10px 12px',
                backgroundColor: 'var(--surface-subtle)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '11px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Capture ID</span>
                <span className="mono" style={{ color: 'var(--text-primary)' }}>{property.captureId}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Sensor Tier</span>
                <span style={{ color: 'var(--text-primary)', textTransform: 'uppercase' }}>{property.tier}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Internal Status</span>
                <span style={{ color: 'var(--text-primary)' }}>{property.status}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Reconstruction Method</span>
                <span style={{ color: 'var(--text-primary)' }}>{property.reconstructionMethod || 'Spatial Pro Fusion'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Uncertainty Calibration</span>
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Physical GT Pending</span>
              </div>
            </div>
          )}
        </div>

        <div style={{ marginTop: 'auto' }}>
          <MeasurementStatus />
        </div>
      </aside>
    );
  }

  // Selected Room Inspection View
  return (
    <aside
      aria-label={`Room Inspector: ${selectedRoom.name}`}
      style={{
        backgroundColor: 'var(--surface)',
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px',
        overflowY: 'auto',
        userSelect: 'text',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: '14px', paddingBottom: '12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
          <button
            onClick={() => onSelectRoom('')}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--primary)',
              cursor: 'pointer',
            }}
          >
            ← Property Overview
          </button>
          <StatusBadge status={property.status} size="sm" />
        </div>

        <h2
          style={{
            fontSize: '17px',
            fontWeight: 700,
            color: 'var(--text-primary)',
            letterSpacing: '-0.01em',
          }}
        >
          {selectedRoom.name}
        </h2>
      </div>

      {/* Primary Room Measurements */}
      <section aria-labelledby="room-measurements-heading" style={{ marginBottom: '18px' }}>
        <h3 id="room-measurements-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '8px' }}>
          Room Measurements
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          {/* Floor Area */}
          <div
            style={{
              padding: '10px 12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
              Floor Area
            </div>
            <div className="mono" style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {selectedRoom.floorArea ? `${selectedRoom.floorArea.value.toFixed(2)} m²` : 'Not available'}
            </div>
            {selectedRoom.floorArea?.interval && (
              <div className="mono" style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Range: {selectedRoom.floorArea.interval[0].toFixed(2)} – {selectedRoom.floorArea.interval[1].toFixed(2)} m²
              </div>
            )}
          </div>

          {/* Ceiling Height */}
          <div
            style={{
              padding: '10px 12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
              Ceiling Height
            </div>
            <div
              className="mono"
              style={{
                fontSize: selectedRoom.ceilingHeight ? '15px' : '13px',
                fontWeight: selectedRoom.ceilingHeight ? 600 : 500,
                color: selectedRoom.ceilingHeight ? 'var(--text-primary)' : 'var(--text-muted)',
              }}
            >
              {selectedRoom.ceilingHeight ? `${selectedRoom.ceilingHeight.value.toFixed(3)} m` : 'Not available'}
            </div>
            {selectedRoom.ceilingHeight?.interval && (
              <div className="mono" style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Range: {selectedRoom.ceilingHeight.interval[0].toFixed(3)} – {selectedRoom.ceilingHeight.interval[1].toFixed(3)} m
              </div>
            )}
          </div>
        </div>

        {/* Perimeter */}
        {selectedRoom.perimeter && (
          <div
            style={{
              marginTop: '8px',
              padding: '8px 12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Perimeter</span>
            <span className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {selectedRoom.perimeter.value.toFixed(2)} m
            </span>
          </div>
        )}
      </section>

      {/* Wall Segment Measurements */}
      {selectedRoom.walls && selectedRoom.walls.length > 0 && (
        <section aria-labelledby="wall-measurements-heading" style={{ marginBottom: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <h3 id="wall-measurements-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Wall Dimensions
            </h3>
            <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {selectedRoom.walls.length} walls
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {selectedRoom.walls.map((wall) => (
              <div
                key={wall.id}
                style={{
                  padding: '8px 10px',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)' }}>
                    Wall Length
                  </span>
                  <span className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {wall.length.value.toFixed(3)} m
                  </span>
                </div>

                {wall.length.interval && (
                  <div className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Estimated Range: {wall.length.interval[0].toFixed(3)} – {wall.length.interval[1].toFixed(3)} m
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Openings & Doorways */}
      {selectedRoom.openings && selectedRoom.openings.length > 0 && (
        <section aria-labelledby="openings-heading" style={{ marginBottom: '18px' }}>
          <h3 id="openings-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '8px' }}>
            Openings
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {selectedRoom.openings.map((op) => (
              <div
                key={op.id}
                style={{
                  padding: '8px 10px',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                    {op.type}
                  </span>
                  <span className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {op.width.value.toFixed(3)} m
                  </span>
                </div>
                {!op.calibrated && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', fontStyle: 'italic' }}>
                    Estimate not physically calibrated
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Damage Findings */}
      {selectedRoom.damages && selectedRoom.damages.length > 0 && (
        <section aria-labelledby="damage-heading" style={{ marginBottom: '18px' }}>
          <h3 id="damage-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--danger-text)', marginBottom: '8px' }}>
            Damage Findings ({selectedRoom.damages.length})
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {selectedRoom.damages.map((dmg) => (
              <div
                key={dmg.id}
                style={{
                  padding: '10px 12px',
                  backgroundColor: 'var(--danger-subtle)',
                  border: '1px solid var(--danger-border)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--danger-text)' }}>
                    {formatDamageLabel(dmg.damageClass)}
                  </span>
                  <span className="mono" style={{ fontSize: '11px', color: 'var(--danger-text)' }}>
                    {(dmg.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Size: </span>
                  <strong className="mono">
                    {dmg.metricArea
                      ? `${dmg.metricArea.value.toFixed(2)} m²`
                      : dmg.metricLength
                      ? `${dmg.metricLength.value.toFixed(2)} m`
                      : 'Unquantified'}
                  </strong>
                </div>

                {dmg.scopeItems && dmg.scopeItems.length > 0 && (
                  <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    <span style={{ fontWeight: 600 }}>Recommended action: </span>
                    {dmg.scopeItems[0].action}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Collapsible Advanced Details Accordion */}
      <div style={{ marginBottom: '16px' }}>
        <button
          onClick={() => setShowAdvanced((prev) => !prev)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            padding: '8px 10px',
            backgroundColor: 'transparent',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '11.5px',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            cursor: 'pointer',
          }}
        >
          <span>Advanced Details</span>
          <span style={{ transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}>
            ▾
          </span>
        </button>

        {showAdvanced && (
          <div
            style={{
              marginTop: '6px',
              padding: '10px 12px',
              backgroundColor: 'var(--surface-subtle)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Room ID</span>
              <span className="mono" style={{ color: 'var(--text-primary)' }}>{selectedRoom.id}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Polygon Vertices</span>
              <span className="mono" style={{ color: 'var(--text-primary)' }}>{selectedRoom.polygon.length} points</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Capture ID</span>
              <span className="mono" style={{ color: 'var(--text-primary)' }}>{property.captureId}</span>
            </div>
          </div>
        )}
      </div>

      {/* Mandatory Accuracy Notice */}
      <div style={{ marginTop: 'auto', paddingTop: '16px' }}>
        <MeasurementStatus />
      </div>
    </aside>
  );
}
