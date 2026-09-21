/**
 * @file FloorPlanCanvas.tsx
 * @purpose Main SVG floor plan canvas with collision-aware dimension labels and improved viewport UX.
 * @stage Frontend Stage 3 — Floor Plan UX Improvements.
 * @inputs PropertyViewModel, selectedRoomId, onSelectRoom, activeTab.
 * @outputs Interactive SVG canvas with deterministic pan/zoom, dimension collision avoidance,
 *          scroll support, fit-to-view, focus-room, and accessible keyboard controls.
 * @dependencies ../../domain/types, ../../geometry/viewbox, ../../geometry/polygon,
 *               ../../geometry/collision, ./CanvasControls, ../ui/EmptyState.
 * @assumptions Floor coordinates in meters. Pure native SVG (zero WebGL/Three.js). Preserves aspect ratio.
 * @failureModes Empty or invalid geometry renders informative EmptyState.
 * @firstDebuggingPoints Verify property.bounds has positive width/height; check room polygon points array.
 */

'use client';

import React, { useState, useRef, useCallback, useMemo } from 'react';
import { PropertyViewModel, RoomViewModel, Point2D } from '../../domain/types';
import { formatDamageLabel } from '../../domain/adapters';
import { computeViewBox } from '../../geometry/viewbox';
import { pointsToSvgPath } from '../../geometry/polygon';
import {
  estimateLabelBounds,
  resolveCollisions,
  getMaxLabelsForZoom,
  computeLabelRotation,
  LabelPriority,
  type LabelCandidate,
} from '../../geometry/collision';
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

  /** Focus viewport on the selected room. */
  const handleFocusRoom = useCallback(() => {
    if (!selectedRoomId) return;
    const room = rooms.find((r) => r.id === selectedRoomId);
    if (!room) return;

    // Calculate zoom to fit room with margin
    const roomWidth = room.bounds.width;
    const roomHeight = room.bounds.height;
    const propWidth = bounds.width || 1;
    const propHeight = bounds.height || 1;

    const fitZoom = Math.min(
      (propWidth / Math.max(roomWidth, 0.5)) * 0.7,
      (propHeight / Math.max(roomHeight, 0.5)) * 0.7,
      4.0,
    );

    // Pan to center room relative to property center
    const propCenterX = bounds.minX + bounds.width / 2;
    const propCenterY = bounds.minY + bounds.height / 2;
    const roomCenterX = room.bounds.minX + room.bounds.width / 2;
    const roomCenterY = room.bounds.minY + room.bounds.height / 2;

    setPanOffset({
      x: propCenterX - roomCenterX,
      y: propCenterY - roomCenterY,
    });
    setZoom(Math.max(fitZoom, 1.0));
  }, [selectedRoomId, rooms, bounds]);

  // Mouse pan handlers
  const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
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

  // Ctrl/Cmd + wheel zoom
  const handleWheel = useCallback(
    (e: React.WheelEvent<HTMLDivElement>) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = -e.deltaY * 0.002;
        setZoom((z) => Math.min(Math.max(z * (1 + delta), 0.25), 6.0));
      }
    },
    [],
  );

  // Keyboard navigation handler
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === '+' || e.key === '=') {
      handleZoomIn();
    } else if (e.key === '-' || e.key === '_') {
      handleZoomOut();
    } else if (e.key === '0') {
      handleReset();
    } else if (e.key === 'f' || e.key === 'F') {
      handleFocusRoom();
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

  // Compute collision-resolved dimension labels
  const dimensionPlacements = useMemo(() => {
    if (!rooms || rooms.length === 0) return [];

    const candidates: LabelCandidate[] = [];
    const WALL_FONT = 0.13;

    for (const room of rooms) {
      const isSelectedRoom = selectedRoomId === room.id;

      // Room name label
      candidates.push({
        id: `name_${room.id}`,
        position: room.center,
        bounds: estimateLabelBounds(room.center, room.name.length, 0.28),
        priority: LabelPriority.ROOM_NAME,
        text: room.name,
      });

      // Floor area label
      if (room.floorArea) {
        const areaPos = { x: room.center.x, y: room.center.y + 0.32 };
        const areaText = `${room.floorArea.value.toFixed(2)} m²`;
        candidates.push({
          id: `area_${room.id}`,
          position: areaPos,
          bounds: estimateLabelBounds(areaPos, areaText.length, 0.20),
          priority: LabelPriority.MAJOR_DIMENSION,
          text: areaText,
        });
      }

      // Wall dimension labels
      for (const wall of room.walls) {
        if (!wall.length) continue;
        const dimText = `${wall.length.value.toFixed(2)}m`;

        // Determine priority based on selection state
        const priority = isSelectedRoom
          ? LabelPriority.SELECTED_ROOM
          : LabelPriority.OTHER_DIMENSION;

        candidates.push({
          id: `dim_${wall.id}`,
          position: wall.labelPoint,
          bounds: estimateLabelBounds(wall.labelPoint, dimText.length, WALL_FONT),
          priority,
          text: dimText,
          wallStart: wall.start,
          wallEnd: wall.end,
        });
      }
    }

    const maxLabels = getMaxLabelsForZoom(zoom, candidates.length);
    return resolveCollisions(candidates, maxLabels);
  }, [rooms, selectedRoomId, zoom]);

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
              : property.status === 'FAILED'
              ? 'Reconstruction failed. See status details for more information.'
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

  // Build lookup for visible labels by ID
  const visibleLabels = new Map(
    dimensionPlacements
      .filter((p) => p.visible)
      .map((p) => [p.candidate.id, p])
  );

  return (
    <main
      tabIndex={0}
      role="region"
      aria-label="Interactive Floor Plan Canvas"
      onKeyDown={handleKeyDown}
      onWheel={handleWheel}
      style={{
        flex: 1,
        backgroundColor: 'var(--canvas-background)',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'auto',
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
          minHeight: '400px',
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <defs>
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

              {/* Room name — only if visible after collision resolution */}
              {visibleLabels.has(`name_${room.id}`) && (
                <text
                  x={visibleLabels.get(`name_${room.id}`)!.position.x}
                  y={visibleLabels.get(`name_${room.id}`)!.position.y}
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
              )}

              {/* Floor area — only if visible */}
              {room.floorArea && visibleLabels.has(`area_${room.id}`) && (
                <text
                  x={visibleLabels.get(`area_${room.id}`)!.position.x}
                  y={visibleLabels.get(`area_${room.id}`)!.position.y}
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
            const labelKey = `dim_${wall.id}`;
            const placement = visibleLabels.get(labelKey);
            const rotation = computeLabelRotation(wall.start, wall.end);

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

                {/* Wall length dimension — only if visible after collision resolution */}
                {wall.length && placement && (
                  <g>
                    {/* Subtle background for readability */}
                    <rect
                      x={placement.position.x - (wall.length.value.toFixed(2).length + 1) * 0.13 * 0.275 - 0.04}
                      y={placement.position.y - 0.09}
                      width={(wall.length.value.toFixed(2).length + 1) * 0.13 * 0.55 + 0.08}
                      height={0.18}
                      rx={0.03}
                      fill="var(--surface, #ffffff)"
                      fillOpacity="0.85"
                      transform={Math.abs(rotation) > 5 ? `rotate(${rotation}, ${placement.position.x}, ${placement.position.y})` : undefined}
                    />
                    <text
                      x={placement.position.x}
                      y={placement.position.y}
                      textAnchor="middle"
                      dominantBaseline="central"
                      className="mono"
                      transform={Math.abs(rotation) > 5 ? `rotate(${rotation}, ${placement.position.x}, ${placement.position.y})` : undefined}
                      style={{
                        fontSize: '0.13px',
                        fontWeight: 500,
                        fill: 'var(--wall-dimension)',
                        pointerEvents: 'none',
                      }}
                    >
                      {wall.length.value.toFixed(2)}m
                    </text>
                  </g>
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
              const hostWall = room.walls.find((w) => w.id === dmg.hostSurfaceId);
              const pos = hostWall ? hostWall.labelPoint : room.center;
              const markerRadius = dmg.metricArea
                ? Math.max(0.16, Math.min(0.35, Math.sqrt(dmg.metricArea.value / Math.PI) * 0.35))
                : 0.20;
              const labelText = formatDamageLabel(dmg.damageClass);
              const pillHeight = 0.16;
              const pillWidth = Math.max(0.70, labelText.length * 0.052 + 0.16);
              const labelY = pos.y - markerRadius - 0.12;

              return (
                <g key={dmg.id} className="damage-marker-group">
                  {/* Outer dashed perimeter circle */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={markerRadius}
                    fill="var(--damage-fill)"
                    stroke="var(--damage-stroke)"
                    strokeWidth="0.02"
                    strokeDasharray="0.04 0.02"
                  />
                  {/* Center origin dot */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={0.035}
                    fill="var(--damage-stroke)"
                  />
                  {/* Offset connector line to label pill */}
                  <line
                    x1={pos.x}
                    y1={pos.y - markerRadius}
                    x2={pos.x}
                    y2={labelY + pillHeight / 2}
                    stroke="var(--damage-stroke)"
                    strokeWidth="0.012"
                    strokeDasharray="0.02 0.01"
                    opacity={0.8}
                  />
                  {/* Damage label pill background */}
                  <rect
                    x={pos.x - pillWidth / 2}
                    y={labelY - pillHeight / 2}
                    width={pillWidth}
                    height={pillHeight}
                    rx={0.04}
                    fill="var(--surface)"
                    stroke="var(--damage-stroke)"
                    strokeWidth="0.015"
                  />
                  {/* Human-readable label text */}
                  <text
                    x={pos.x}
                    y={labelY}
                    textAnchor="middle"
                    dominantBaseline="central"
                    style={{
                      fontSize: '0.082px',
                      fontWeight: 600,
                      fill: 'var(--danger-text)',
                      pointerEvents: 'none',
                    }}
                  >
                    {labelText}
                  </text>
                </g>
              );
            })
          )}
      </svg>

      {/* Unobtrusive Canvas Legend */}
      <div
        aria-label="Floor Plan Legend"
        style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '6px 12px',
          backgroundColor: 'var(--surface-subtle)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '11px',
          color: 'var(--text-secondary)',
          pointerEvents: 'none',
          userSelect: 'none',
          backdropFilter: 'blur(4px)',
          zIndex: 5,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{ width: '10px', height: '10px', backgroundColor: 'var(--room-fill-selected)', border: '1px solid var(--room-stroke-selected)', borderRadius: '2px' }} />
          <span>Room</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{ width: '14px', height: '3px', backgroundColor: 'var(--wall-stroke)' }} />
          <span>Wall</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{ width: '14px', height: '2px', borderTop: '2px dashed var(--opening-stroke)' }} />
          <span>Opening</span>
        </div>
        {(showDamageOverlay || property.rooms.some((r) => r.damages.length > 0)) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--damage-fill)', border: '1px solid var(--damage-stroke)' }} />
            <span style={{ color: 'var(--danger-text)' }}>Damage</span>
          </div>
        )}
      </div>

      {/* Floating View Controls */}
      <CanvasControls
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onReset={handleReset}
        onFocusRoom={selectedRoomId ? handleFocusRoom : undefined}
        zoomLevel={zoom}
      />
    </main>
  );
}
