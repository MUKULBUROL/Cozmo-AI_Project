/**
 * @file InspectorPanel.tsx
 * @purpose Right inspector pane detailing selected room measurements, openings, damage detections, and scope.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs PropertyViewModel, selectedRoom (RoomViewModel | null), onSelectRoom.
 * @outputs Accessible inspector panel matching Spatial Pro typography and technical fidelity.
 * @dependencies ../../domain/types, ../ui/StatusBadge, ../ui/MeasurementStatus
 * @assumptions Renders "Not available" when measurements/ceilings are missing; never invents placeholder values.
 * @failureModes None (handles null room gracefully by displaying property overview).
 * @firstDebuggingPoints Verify selectedRoom object propagation; check ceilingHeight null handling.
 */

import React from 'react';
import { PropertyViewModel, RoomViewModel } from '../../domain/types';
import { StatusBadge } from '../ui/StatusBadge';
import { MeasurementStatus } from '../ui/MeasurementStatus';

interface InspectorPanelProps {
  property: PropertyViewModel;
  selectedRoom: RoomViewModel | null;
  onSelectRoom: (roomId: string) => void;
}

export function InspectorPanel({
  property,
  selectedRoom,
  onSelectRoom,
}: InspectorPanelProps) {
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
        <div style={{ marginBottom: '16px' }}>
          <div
            style={{
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-muted)',
              marginBottom: '4px',
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
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
                Confidence interval: {property.totalFloorArea.interval[0].toFixed(2)} –{' '}
                {property.totalFloorArea.interval[1].toFixed(2)} m²
              </div>
            )}
          </div>

          <div
            style={{
              padding: '12px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Reconstructed Rooms
            </div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              {property.rooms.length} {property.rooms.length === 1 ? 'room' : 'rooms'} detected
            </div>

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
        </div>

        <div style={{ marginTop: 'auto' }}>
          <MeasurementStatus />
        </div>
      </aside>
    );
  }

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
      <div style={{ marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span
            className="mono"
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
            }}
          >
            {selectedRoom.id}
          </span>
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

      {/* Primary Dimensional Metrics */}
      <section aria-labelledby="primary-metrics-heading" style={{ marginBottom: '20px' }}>
        <h3 id="primary-metrics-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '8px' }}>
          Room Metrics
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
                [{selectedRoom.floorArea.interval[0].toFixed(2)} – {selectedRoom.floorArea.interval[1].toFixed(2)}]
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
                [{selectedRoom.ceilingHeight.interval[0].toFixed(3)} – {selectedRoom.ceilingHeight.interval[1].toFixed(3)}]
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
        <section aria-labelledby="wall-measurements-heading" style={{ marginBottom: '20px' }}>
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
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {wall.id}
                  </span>
                  <span className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {wall.length.value.toFixed(3)} m
                  </span>
                </div>

                {wall.length.interval && (
                  <div className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Confidence interval: {wall.length.interval[0].toFixed(3)} – {wall.length.interval[1].toFixed(3)} m
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Doorways / Openings */}
      {selectedRoom.openings && selectedRoom.openings.length > 0 && (
        <section aria-labelledby="openings-heading" style={{ marginBottom: '20px' }}>
          <h3 id="openings-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '8px' }}>
            Openings & Doorways
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
                    {op.type} ({op.id})
                  </span>
                  <span className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {op.width.value.toFixed(3)} m
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  Status: <span style={{ textTransform: 'capitalize' }}>{op.status}</span>
                  {!op.calibrated && (
                    <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>
                      (Awaiting GT benchmark)
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Detected Damages & Concealed Risk */}
      {selectedRoom.damages && selectedRoom.damages.length > 0 && (
        <section aria-labelledby="damage-heading" style={{ marginBottom: '20px' }}>
          <h3 id="damage-heading" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--danger-text)', marginBottom: '8px' }}>
            Damage & Risk Detections ({selectedRoom.damages.length})
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
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--danger-text)', textTransform: 'uppercase' }}>
                    {dmg.damageClass.replace('_', ' ')}
                  </span>
                  <span className="mono" style={{ fontSize: '11px', color: 'var(--danger-text)' }}>
                    {(dmg.confidence * 100).toFixed(0)}% conf
                  </span>
                </div>

                <div className="mono" style={{ fontSize: '12px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  {dmg.metricArea
                    ? `Extent: ${dmg.metricArea.value.toFixed(2)} m²`
                    : dmg.metricLength
                    ? `Length: ${dmg.metricLength.value.toFixed(2)} m`
                    : 'Extent: Unquantified'}
                </div>

                {dmg.concealedFlags && dmg.concealedFlags.length > 0 && (
                  <div
                    style={{
                      marginTop: '6px',
                      padding: '6px 8px',
                      backgroundColor: 'var(--surface)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '11px',
                      lineHeight: 1.4,
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ fontWeight: 600, color: 'var(--warning-text)', marginBottom: '2px' }}>
                      Concealed Risk Flag
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>
                      {dmg.concealedFlags[0].suspectedIssue}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Mandatory Accuracy Notice */}
      <div style={{ marginTop: 'auto', paddingTop: '16px' }}>
        <MeasurementStatus />
      </div>
    </aside>
  );
}
