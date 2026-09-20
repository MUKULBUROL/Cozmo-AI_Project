/**
 * @file polygon.ts
 * @purpose Polygon path generation, centroid computation, and geometric annotation positioning.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Array of Point2D vertices or WallViewModel segments.
 * @outputs SVG path strings, centroid coordinates, dimension label positions.
 * @dependencies ../domain/types
 * @assumptions Polygons are planar 2D loops in meters. Closed loops have first == last or implicit closure.
 * @failureModes Degenerate polygons (< 3 points) returning fallback center.
 * @firstDebuggingPoints Verify vertex ordering and presence of coordinate numbers.
 */

import { Point2D } from '../domain/types';

/**
 * Converts an ordered array of 2D points into an SVG path `d` attribute string.
 * 
 * @param points - Array of vertices in meters.
 * @param close - Whether to close the path with 'Z'.
 * @returns SVG path data string (e.g., "M 1.2 3.4 L 5.6 7.8 Z").
 */
export function pointsToSvgPath(points: Point2D[], close = true): string {
  if (!points || points.length === 0) return '';
  const d = points
    .map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${pt.x.toFixed(4)} ${pt.y.toFixed(4)}`)
    .join(' ');
  return close ? `${d} Z` : d;
}

/**
 * Computes the geometric centroid of a 2D polygon using the standard polygon area centroid formula.
 * Falls back to average of vertices if area is near-zero.
 * 
 * @param vertices - Ordered list of vertices in meters.
 * @returns Centroid Point2D.
 */
export function computePolygonCentroid(vertices: Point2D[]): Point2D {
  if (!vertices || vertices.length === 0) {
    return { x: 0, y: 0 };
  }
  if (vertices.length === 1) {
    return { x: vertices[0].x, y: vertices[0].y };
  }
  if (vertices.length === 2) {
    return {
      x: (vertices[0].x + vertices[1].x) / 2,
      y: (vertices[0].y + vertices[1].y) / 2,
    };
  }

  let signedArea = 0;
  let cx = 0;
  let cy = 0;

  const n = vertices.length;
  for (let i = 0; i < n; i++) {
    const p0 = vertices[i];
    const p1 = vertices[(i + 1) % n];
    const cross = p0.x * p1.y - p1.x * p0.y;
    signedArea += cross;
    cx += (p0.x + p1.x) * cross;
    cy += (p0.y + p1.y) * cross;
  }

  signedArea *= 0.5;
  if (Math.abs(signedArea) < 1e-6) {
    // Degenerate/collinear polygon: compute arithmetic mean
    let sumX = 0;
    let sumY = 0;
    for (const v of vertices) {
      sumX += v.x;
      sumY += v.y;
    }
    return { x: sumX / n, y: sumY / n };
  }

  cx = cx / (6 * signedArea);
  cy = cy / (6 * signedArea);

  return { x: cx, y: cy };
}

/**
 * Computes midpoint and perpendicular offset for a wall dimension label.
 * 
 * @param start - Starting point of wall segment.
 * @param end - Ending point of wall segment.
 * @param offsetMeters - Perpendicular offset distance.
 * @returns Point2D position for label placement.
 */
export function computeDimensionLabelPosition(
  start: Point2D,
  end: Point2D,
  offsetMeters = 0.15
): Point2D {
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;

  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const len = Math.hypot(dx, dy);

  if (len < 1e-4) {
    return { x: midX, y: midY };
  }

  // Normal vector: (-dy, dx) / len
  const nx = -dy / len;
  const ny = dx / len;

  return {
    x: midX + nx * offsetMeters,
    y: midY + ny * offsetMeters,
  };
}
