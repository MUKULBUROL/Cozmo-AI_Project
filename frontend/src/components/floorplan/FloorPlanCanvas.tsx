/**
 * @file FloorPlanCanvas.tsx
 * @purpose Main SVG floor plan canvas rendering architectural room polygons, walls, doors, and defect overlays.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs PropertyViewModel, selectedRoomId, onSelectRoom, activeTab.
 * @outputs Interactive SVG canvas with auto-fit viewBox, deterministic pan/zoom, and accessible keyboard controls.
 * @dependencies ../../domain/types, ../../geometry/viewbox, ../../geometry/polygon, ./CanvasControls, ../ui/EmptyState
 * @assumptions Floor coordinates in meters. Pure native SVG (zero WebGL/Three.js). Preserves aspect ratio automatically.
 * @failureModes Empty or invalid geometry renders informative EmptyState.
 * @firstDebuggingPoints Verify property.bounds has positive width/height; check room polygon points array.
 */

'use client';

import React, { useState, useRef, useCallback } from 'react';
import { PropertyViewModel, RoomViewModel, Point2D } from '../../domain/types';
import { computeViewBox } from '../../geometry/viewbox';
import { pointsToSvgPath } from '../../geometry/polygon';
import { CanvasControls } from './CanvasControls';
import { EmptyState } from '../ui/EmptyState';

interface FloorPlanCanvasProps {
  property: PropertyViewModel;
  selectedRoomId: string | null;
  onSelectRoom: (roomId: string) => void;
  showDamageOverlay?: boolean;
}

export function FloorPlanCanvas({
  property,
  selectedRoomId,
  onSelectRoom,
  showDamageOverlay = false,
}: FloorPlanCanvasProps) {
  const [zoom, setZoom] = useState<number>(1.0);
  const [panOffset, setPanOffset] = useState<Point2D>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<Point2D>({ x: 0, y: 0 });

  const { rooms, bounds } = property;

  const handleZoomIn = useCallback(() => {
    setZoom((z) => Math.min(z * 1.25, 6.0));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoom((z) => Math.max(z / 1.25, 0.25));
  }, []);

  const handleReset = useCallback(() => {
    setZoom(1.0);
    setPanOffset({ x: 0, y: 0 });
  }, []);

  // Mouse pan handlers
  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - panOffset.x * 20, y: e.clientY - panOffset.y * 20 };
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDragging) return;
    const dx = (e.clientX - dragStartRef.current.x) / 20;
    const dy = (e.clientY - dragStartRef.current.y) / 20;
    setPanOffset({ x: dx, y: dy });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Keyboard navigation handler
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === '+' || e.key === '=') {
      handleZoomIn();
    } else if (e.key === '-' || e.key === '_') {
      handleZoomOut();
    } else if (e.key === '0') {
      handleReset();
    } else if (e.key === 'ArrowLeft') {
      setPanOffset((p) => ({ ...p, x: p.x - 0.5 / zoom }));
    } else if (e.key === 'ArrowRight') {
      setPanOffset((p) => ({ ...p, x: p.x + 0.5 / zoom }));
    } else if (e.key === 'ArrowUp') {
      setPanOffset((p) => ({ ...p, y: p.y - 0.5 / zoom }));
    } else if (e.key === 'ArrowDown') {
      setPanOffset((p) => ({ ...p, y: p.y + 0.5 / zoom }));
    }
  };

  if (!rooms || rooms.length === 0 || bounds.width === 0) {
    return (
      <main
        style={{
          flex: 1,
          backgroundColor: 'var(--canvas-background)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          overflow: 'auto',
        }}
      >
        <EmptyState
          title="Floor plan geometry unavailable"
          description={
            property.status === 'NOT_EVALUABLE'
              ? 'This capture did not meet the spatial continuity criteria required to reconstruct room topology.'
              : 'No geometric wall segments or room polygons were extracted from this capture.'
          }
          reasons={property.statusReasons}
        />
      </main>
    );
  }

  const viewBoxStr = computeViewBox(bounds, {
    zoom,
    panOffset,
    paddingRatio: 0.1,
  });

  return (
    <main
      tabIndex={0}
      role="region"
      aria-label="Interactive Floor Plan Canvas"
      onKeyDown={handleKeyDown}
      style={{
        flex: 1,
        backgroundColor: 'var(--canvas-background)',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        cursor: isDragging ? 'grabbing' : 'default',
        outline: 'none',
      }}
    >
      <svg
        viewBox={viewBoxStr}
        preserveAspectRatio="xMidYMid meet"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          width: '100%',
          height: '100%',
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <defs>
          {/* Subtle architectural floor pattern */}
          <pattern
            id="grid-pattern"
            width="1"
            height="1"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 1 0 L 0 0 0 1"
              fill="none"
              stroke="var(--border)"
              strokeWidth="0.015"
            />
          </pattern>
        </defs>

        {/* Room Polygon Surfaces */}
        {rooms.map((room: RoomViewModel) => {
          const isSelected = selectedRoomId === room.id;
          const pathD = pointsToSvgPath(room.polygon, true);

          return (
            <g
              key={room.id}
              onClick={(e) => {
                e.stopPropagation();
                onSelectRoom(room.id);
              }}
              style={{ cursor: 'pointer' }}
            >
              <path
                d={pathD}
                fill={isSelected ? 'var(--room-selected-fill)' : 'var(--room-fill)'}
                stroke={isSelected ? 'var(--room-selected-stroke)' : 'var(--border)'}
                strokeWidth={isSelected ? '0.05' : '0.02'}
                style={{
                  transition: 'fill 0.15s ease, stroke 0.15s ease',
                }}
              />

              {/* Room Identifier and Area Label */}
              <text
                x={room.center.x}
                y={room.center.y - 0.1}
                textAnchor="middle"
                dominantBaseline="central"
                style={{
                  fontSize: '0.28px',
                  fontWeight: 600,
                  fill: isSelected ? 'var(--primary)' : 'var(--text-primary)',
                  pointerEvents: 'none',
                }}
              >
                {room.name}
              </text>

              {room.floorArea && (
                <text
                  x={room.center.x}
                  y={room.center.y + 0.22}
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="mono"
                  style={{
                    fontSize: '0.20px',
                    fontWeight: 500,
                    fill: 'var(--text-secondary)',
                    pointerEvents: 'none',
                  }}
                >
                  {room.floorArea.value.toFixed(2)} m²
                </text>
              )}
            </g>
          );
        })}

        {/* Structural Walls */}
        {rooms.map((room) =>
          room.walls.map((wall) => {
            const isSelected = selectedRoomId === room.id;
            return (
              <g key={wall.id}>
                <line
                  x1={wall.start.x}
                  y1={wall.start.y}
                  x2={wall.end.x}
                  y2={wall.end.y}
                  stroke={isSelected ? 'var(--wall-stroke-strong)' : 'var(--wall-stroke)'}
                  strokeWidth="0.06"
                  strokeLinecap="round"
                />

                {/* Wall Length Dimension Tag */}
                {wall.length && (
                  <text
                    x={wall.labelPoint.x}
                    y={wall.labelPoint.y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="mono"
                    style={{
                      fontSize: '0.13px',
                      fontWeight: 500,
                      fill: 'var(--wall-dimension)',
                      pointerEvents: 'none',
                    }}
                  >
                    {wall.length.value.toFixed(2)}m
                  </text>
                )}
              </g>
            );
          })
        )}

        {/* Doorways & Openings */}
        {rooms.map((room) =>
          room.openings.map((opening) => {
            if (!opening.leftJamb || !opening.rightJamb) return null;
            return (
              <g key={opening.id}>
                {/* Door Opening Gap Marker */}
                <line
                  x1={opening.leftJamb.x}
                  y1={opening.leftJamb.y}
                  x2={opening.rightJamb.x}
                  y2={opening.rightJamb.y}
                  stroke="var(--opening-stroke)"
                  strokeWidth="0.04"
                  strokeDasharray="0.08 0.04"
                />
              </g>
            );
          })
        )}

        {/* Defect / Damage Overlays */}
        {(showDamageOverlay || property.rooms.some((r) => r.id === selectedRoomId)) &&
          rooms.map((room) =>
            room.damages.map((dmg) => {
              // Position damage indicator near host surface or room center
              const hostWall = room.walls.find((w) => w.id === dmg.hostSurfaceId);
              const pos = hostWall ? hostWall.labelPoint : room.center;

              return (
                <g key={dmg.id}>
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={dmg.metricArea ? Math.sqrt(dmg.metricArea.value / Math.PI) * 0.4 : 0.25}
                    fill="var(--damage-fill)"
                    stroke="var(--damage-stroke)"
                    strokeWidth="0.02"
                    strokeDasharray="0.04 0.02"
                  />
                  <text
                    x={pos.x}
                    y={pos.y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    style={{
                      fontSize: '0.11px',
                      fontWeight: 700,
                      fill: 'var(--danger-text)',
                      pointerEvents: 'none',
                    }}
                  >
                    {dmg.damageClass.replace('_', ' ').toUpperCase()}
                  </text>
                </g>
              );
            })
          )}
      </svg>

      {/* Floating View Controls */}
      <CanvasControls
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onReset={handleReset}
        zoomLevel={zoom}
      />
    </main>
  );
}
